/* SPDX-License-Identifier: MIT */
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const core=require('../web/device-files-core.js'),{create}=require('../web/device-files-fixture.js');
const code=value=>error=>error.code===value;
const setup=()=>{const transport=create({latency:0,empty:true});return {transport,client:new core.Client(transport)};};
const bytes=s=>new TextEncoder().encode(s);
test('paths bound aliases, depth and ASCII without URL decoding',()=>{
 for(const p of ['/RAM/a','/RAM/a/b/c/d.txt','/RAM/'+ 'x'.repeat(58)])assert.equal(core.path(p),p);
 for(const p of ['','RAM/a','/RAM/','/RAM/.x','/RAM/../x','/RAM/a//b','/RAM/a/','/RAM/a/b/c/d/e','/RAM/a%2fb','/RAM/a\\b','/RAM/a:b','/RAM/a?b','/RAM/a#b','/RAM/a\0b','/NVS/key','/RAM/'+'x'.repeat(59)])assert.throws(()=>core.path(p),code('PATH'));
 for(const p of ['/Flash/a','/SD/a'])assert.throws(()=>core.path(p),code('UNAVAILABLE'));
});
test('text preserves UTF-8 and rejects NUL, malformed UTF-8 and surrogate replacement',()=>{
 const s='Café € 😀\n';assert.equal(core.decodeText(core.encodeText(s)),s);
 for(const s of ['a\0b','\ud800','\udc00','\ud800x'])assert.throws(()=>core.encodeText(s),code('TEXT'));
 for(const b of [[0],[0xc0,0x80],[0xed,0xa0,0x80],[0xf4,0x90,0x80,0x80]])assert.throws(()=>core.decodeText(Uint8Array.from(b)),code('TEXT'));
 assert.throws(()=>core.encodeText('é'.repeat(4097)),code('SIZE'));
 assert.equal(core.encodeText('é'.repeat(4096)).length,8192);
});
test('disconnected client never substitutes storage or a network request',async()=>{
 const c=new core.Client();await assert.rejects(c.refresh(),code('DISCONNECTED'));await assert.rejects(c.read('/RAM/a'),code('DISCONNECTED'));assert.equal(c.busy,false);
});
test('capability and list replies cannot inflate limits or inject paths',async()=>{
 const {transport}=setup(),reply=await transport.request({version:1,id:1,op:'capabilities',args:{}});
 const caps=core.capabilities(reply.data);assert.equal(caps.volatile,true);
 const changed=structuredClone(reply.data);changed.backends[0].maxFileBytes=8193;assert.throws(()=>core.capabilities(changed),code('PROTOCOL'));
 changed.backends[0].maxFileBytes=8192;changed.backends[1].available=true;assert.throws(()=>core.capabilities(changed),code('UNAVAILABLE'));
 const f={path:'/RAM/a',bytes:1,revision:'r1'};
 assert.throws(()=>core.fileList({files:[f,f],used:2,freeSlots:6},caps),code('PROTOCOL'));
 assert.throws(()=>core.fileList({files:[f],used:999,freeSlots:7},caps),code('PROTOCOL'));
 assert.throws(()=>core.metadata({...f,path:'/RAM/<img>'}));assert.throws(()=>core.metadata({...f,revision:'<script>'}));
});
test('empty, Unicode and full-size binary files roundtrip in bounded chunks',async()=>{
 const {transport,client}=setup(),ops=[];
 const raw=transport.request;transport.request=(m,o)=>{ops.push(m);return raw(m,o);};
 for(const [name,data] of [['empty',new Uint8Array()],['text',bytes('é 😀')],['full',Uint8Array.from({length:8192},(_,i)=>i)]]){
  await client.save('/RAM/'+name,data);assert.deepEqual((await client.read('/RAM/'+name)).bytes,data);
 }
 assert.ok(ops.filter(x=>x.op==='append').every(x=>x.args.bytes.length<=1024));
 assert.ok(ops.filter(x=>x.op==='read').every(x=>x.args.count<=1024));
 const snap=await client.refresh();assert.equal(snap.list.files.length,3);assert.equal(snap.list.freeSlots,5);
});
test('create refuses overwrites and conditional replace rejects stale revisions',async()=>{
 const {transport,client}=setup(),other=new core.Client(transport);
 const old=await client.save('/RAM/a',bytes('old'));
 await assert.rejects(client.save('/RAM/a',bytes('accidental')),code('EXISTS'));
 const changed=await other.save('/RAM/a',bytes('changed'),old.revision);assert.notEqual(changed.revision,old.revision);
 await assert.rejects(client.save('/RAM/a',bytes('stale draft'),old.revision),code('CONFLICT'));
 assert.equal(core.decodeText((await client.read('/RAM/a')).bytes),'changed');
});
test('cancel during upload preserves the previous complete file and frees staging',async()=>{
 const {transport,client}=setup(),old=await client.save('/RAM/a',bytes('old')),raw=transport.request;let cancel=true;
 transport.request=(m,o)=>{if(cancel&&m.op==='append'){cancel=false;client.cancel();}return raw(m,o);};
 await assert.rejects(client.save('/RAM/a',bytes('replacement'),old.revision),code('CANCELLED'));
 assert.equal(client.uncertain,false);assert.equal(core.decodeText((await client.read('/RAM/a')).bytes),'old');
 await client.save('/RAM/a',bytes('later'),old.revision);
});
test('failed append acknowledgements cancel staging without changing file data',async()=>{
 const {transport,client}=setup(),old=await client.save('/RAM/a',bytes('old')),raw=transport.request;
 transport.request=async(m,o)=>{const r=await raw(m,o);if(m.op==='append')r.data.received++;return r;};
 await assert.rejects(client.save('/RAM/a',bytes('new'),old.revision),code('PROTOCOL'));
 assert.equal(client.uncertain,false);assert.equal(core.decodeText((await client.read('/RAM/a')).bytes),'old');
});
test('lost commit reply is uncertain, blocks further writes, and never retries',async()=>{
 const transport=create({latency:0,empty:true}),raw=transport.request;let commits=0;
 transport.request=async(m,o)=>{const r=await raw(m,o);if(m.op==='finish'){commits++;return new Promise(()=>{});}return r;};
 const client=new core.Client(transport,{timeout:20});await assert.rejects(client.save('/RAM/a',bytes('committed')),code('TIMEOUT'));
 assert.equal(client.uncertain,true);assert.equal(commits,1);
 await assert.rejects(client.save('/RAM/b',bytes('no')),code('UNCERTAIN'));
 assert.equal(core.decodeText((await client.read('/RAM/a')).bytes),'committed');
 await client.refresh();assert.equal(client.uncertain,true);
});
test('mismatched begin reply cannot become success or be blindly cancelled',async()=>{
 const {transport,client}=setup(),raw=transport.request;let cancellations=0;
 transport.request=async(m,o)=>{const r=await raw(m,o);if(m.op==='begin')r.id++;if(m.op==='cancel')cancellations++;return r;};
 await assert.rejects(client.save('/RAM/a',bytes('x')),code('PROTOCOL'));assert.equal(client.uncertain,true);assert.equal(cancellations,0);
});
test('mixed or oversized read chunks are rejected',async()=>{
 for(const mode of ['revision','bytes']){
  const {transport,client}=setup();await client.save('/RAM/a',bytes('original'));const raw=transport.request;
  transport.request=async(m,o)=>{const r=await raw(m,o);if(m.op==='read'){if(mode==='revision')r.data.revision='other';else r.data.bytes=new Uint8Array(8193);}return r;};
  await assert.rejects(client.read('/RAM/a'),code('PROTOCOL'));
 }
});
test('one foreground operation prevents parallel request queues',async()=>{
 const {transport,client}=setup(),raw=transport.request;let release;
 transport.request=(m,o)=>m.op==='capabilities'?new Promise(resolve=>{release=()=>raw(m,o).then(resolve);}):raw(m,o);
 const first=client.refresh();await Promise.resolve();await Promise.resolve();
 await assert.rejects(client.refresh(),code('BUSY'));release();await first;assert.equal(client.busy,false);
});
test('timeouts abort adapters and late replies cannot be accepted',async()=>{
 let signal,respond;
 const c=new core.Client({request:(m,o)=>{signal=o.signal;return new Promise(r=>{respond=()=>r({version:1,id:m.id,ok:true,data:{}});});}},{timeout:20});
 await assert.rejects(c.refresh(),code('TIMEOUT'));assert.equal(signal.aborted,true);respond();await Promise.resolve();assert.equal(c.caps,null);assert.equal(c.busy,false);
});
test('capacity is bounded and failed writes consume no file slots',async()=>{
 const {client}=setup();for(let i=0;i<8;i++)await client.save('/RAM/f'+i,new Uint8Array());
 await assert.rejects(client.save('/RAM/full',bytes('x')),code('FULL'));
 await assert.rejects(client.save('/RAM/large',new Uint8Array(8193)),code('SIZE'));
 assert.equal((await client.refresh()).list.files.length,8);
});
test('downloads use copied opaque bytes and safe basenames, including active types',()=>{
 const data=bytes('<svg onload="bad">');const d=core.download('/RAM/logs/page.svg',data);
 assert.equal(d.name,'page.svg');assert.equal(d.type,'application/octet-stream');data.fill(0);assert.notEqual(d.bytes[0],0);
 assert.throws(()=>core.download('/RAM/../secret',new Uint8Array()),code('PATH'));
});
test('10,000 deterministic malformed paths do not become requests',()=>{
 let seed=17;for(let i=0;i<10000;i++){let p='';for(let j=0;j<i%70;j++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;p+=String.fromCharCode(seed>>>24);}assert.throws(()=>core.path(p));}
});
