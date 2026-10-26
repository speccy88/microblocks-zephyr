/* SPDX-License-Identifier: MIT */
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),{spawn}=require('node:child_process');
const core=require('../web/device-files-core.js'),wire=require('../web/device-files-wire.js');
const code=value=>error=>error.code===value,bytes=core.encodeText;
const req=(op='capabilities',args={},id=1)=>({version:1,id,op,args});
function response(request,payload=[],status=0,session=1){
 const b=new Uint8Array(16+payload.length),v=new DataView(b.buffer);
 b.set([77,66,70,82,1,wire.encode(request,session)[10]]);v.setUint32(6,request.id,true);v.setUint32(10,session,true);b[14]=status;b.set(payload,16);
 const frame=new Uint8Array(b.length+5);frame.set([251,217,0,b.length&255,b.length>>8]);frame.set(b,5);return frame;
}
const caps=[8,0,32,0,2,3,1];
function fake(){
 let receive,removed=0;const sent=[];
 const transport=new wire.Transport({session:1,send:frame=>{sent.push(frame);},subscribe:fn=>{receive=fn;return ()=>removed++;}});
 return {transport,sent,receive:frame=>receive(frame),removed:()=>removed};
}
test('request codec uses bounded existing VM framing and canonical revisions',()=>{
 const r=req('read',{path:'/RAM/a',revision:'r17',offset:12,count:512},99),frame=wire.encode(r,5),v=new DataView(frame.buffer);
 assert.deepEqual([...frame.slice(0,5)],[251,217,0,33,0]);assert.equal(frame.at(-1),254);
 assert.equal(v.getUint32(11,true),99);assert.equal(v.getUint32(15,true),5);assert.equal(v.getUint32(19,true),17);
 for(const revision of ['r0','r01','r1073741824','r-1','other',undefined])assert.throws(()=>wire.encode(req('begin',{path:'/RAM/a',bytes:0,expectedRevision:revision}),1),code('PROTOCOL'));
 assert.equal(wire.encode(req('begin',{path:'/RAM/a',bytes:0,expectedRevision:null}),1).length,38);
 assert.throws(()=>wire.encode(req('append',{job:1,offset:0,bytes:new Uint8Array(513)}),1),code('PROTOCOL'));
 assert.throws(()=>wire.encode(req('stat',{path:'/RAM/../secret'}),1),code('PATH'));
 assert.throws(()=>wire.encode(req('stat',{path:'/Flash/credentials'}),1),code('UNAVAILABLE'));
});
test('response decoder checks bounds, identity, capability and exact length',()=>{
 const r=req(),good=response(r,caps);assert.equal(core.capabilities(wire.decode(good,r,1).data).chunkBytes,512);
 for(const index of [0,1,2,3,5,9,10,11,15,19,20,good.length-1]){
  const bad=good.slice();bad[index]^=128;assert.throws(()=>wire.decode(bad,r,1));
 }
 assert.throws(()=>wire.decode(response(r,[...caps,0]),r,1),code('PROTOCOL'));
 assert.throws(()=>wire.decode(response(r,[9,...caps.slice(1)]),r,1),code('PROTOCOL'));
 assert.throws(()=>wire.decode(response(r,[8,0,32,0,4,3,1]),r,1),code('PROTOCOL'));
 assert.throws(()=>wire.decode(response(r,[0],7),r,1),code('PROTOCOL'));
 assert.equal(wire.decode(response(r,[],7),r,1).code,'CONFLICT');
 assert.throws(()=>wire.decode(new Uint8Array(647),r,1),code('PROTOCOL'));
});
test('read replies copy payload bytes and reject oversized or truncated chunks',()=>{
 const r=req('read',{path:'/RAM/a',revision:'r2',offset:0,count:3}),f=response(r,[2,0,0,0,3,0,5,6,7]);
 const result=wire.decode(f,r,1).data;f.fill(0);assert.deepEqual([...result.bytes],[5,6,7]);assert.equal(result.revision,'r2');
 assert.throws(()=>wire.decode(response(r,[2,0,0,0,3,0,5,6]),r,1),code('PROTOCOL'));
 assert.throws(()=>wire.decode(response(r,[2,0,0,0,1,2]),r,1),code('PROTOCOL'));
});
test('transport waits for actual reply, isolates late IDs and detaches on close',async()=>{
 const f=fake(),r=req(),p=f.transport.request(r);assert.equal(f.sent.length,1);
 await assert.rejects(f.transport.request(req('capabilities',{},2)),code('BUSY'));
 f.receive(response(req('capabilities',{},99),caps));assert.notEqual(f.transport.pending,null);
 f.receive(response(r,caps));assert.equal((await p).ok,true);
 await assert.rejects(f.transport.request(r),code('PROTOCOL'));
 const next=f.transport.request(req('list',{backend:'RAM'},2));f.transport.close();
 await assert.rejects(next,code('DISCONNECTED'));assert.equal(f.removed(),1);f.transport.close();assert.equal(f.removed(),1);
 await assert.rejects(f.transport.request(req('list',{backend:'RAM'},3)),code('DISCONNECTED'));
});
test('abort cancels local wait and malformed same-ID replies never become success',async()=>{
 const f=fake(),abort=new AbortController(),r=req(),p=f.transport.request(r,{signal:abort.signal});abort.abort();
 await assert.rejects(p,code('CANCELLED'));const second=f.transport.request(req('capabilities',{},2));
 f.receive(response(r,caps));assert.notEqual(f.transport.pending,null);
 const broken=response(req('capabilities',{},2),caps);broken[20]=2;f.receive(broken);
 await assert.rejects(second,code('PROTOCOL'));f.transport.close();
});
test('synchronous replies and asynchronous send failure have no listener race',async()=>{
 let receive;
 const t=new wire.Transport({session:1,subscribe:f=>{receive=f;return ()=>{};},send:()=>receive(response(req(),caps))});
 const a=new AbortController();assert.equal((await t.request(req(),{signal:a.signal})).ok,true);a.abort();assert.equal(t.pending,null);t.close();
 const bad=new wire.Transport({session:1,subscribe:()=>()=>{},send:async()=>{throw Error('fixture send failed');}});
 await assert.rejects(bad.request(req()),code('DISCONNECTED'));bad.close();
});
test('10000 malformed responses terminate within fixed bounds',()=>{
 let seed=19;
 for(let i=0;i<10000;i++){
  const b=new Uint8Array(i%648);for(let j=0;j<b.length;j++){seed=(Math.imul(seed,1664525)+1013904223)>>>0;b[j]=seed>>>24;}
  if(i%4===0&&b.length>22)b.set([251,217,0,(b.length-5)&255,(b.length-5)>>8]);
  try{wire.decode(b,req(),1);assert.fail('random frame accepted');}catch(e){assert.ok(e instanceof core.StorageError);}
 }
});
test('real JS Client and sanitized native C dispatcher roundtrip synthetic files', {timeout:30000},async()=>{
 const binary=process.env.MB_FILES_HOST;
 assert.ok(binary,'Set MB_FILES_HOST to the compiled synthetic wire-host; no board fallback is permitted.');
 const child=process.env.MB_FILES_WSL?spawn('wsl.exe',['-d',process.env.MB_FILES_WSL,'--',binary]):spawn(binary,[]);
 let pending=Buffer.alloc(0),receive=()=>{},diagnostics='',exitCode;
 const ended=new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',code=>{exitCode=code;resolve(code);});});
 let markReady;
 const ready=new Promise(resolve=>{markReady=resolve;});
 child.stderr.on('data',chunk=>{diagnostics+=chunk.toString();if(diagnostics.includes('MBFS_HOST_READY v1\n'))markReady();if(diagnostics.length>4096)diagnostics=diagnostics.slice(-4096);});
 child.stdout.on('data',chunk=>{
  pending=Buffer.concat([pending,chunk]);
  while(pending.length>=5){const n=5+pending.readUInt16LE(3);if(n>645||n<21){child.kill();return;}if(pending.length<n)return;
   const frame=new Uint8Array(pending.subarray(0,n));pending=pending.subarray(n);receive(frame);
  }
 });
 const sent=[];
 const transport=new wire.Transport({session:1,send:frame=>{sent.push(frame);return new Promise((resolve,reject)=>child.stdin.write(frame,e=>e?reject(e):resolve()));},subscribe:fn=>{receive=fn;return ()=>{receive=()=>{};};}});
 const client=new core.Client(transport,{timeout:5000});
 try{
  let startupTimer;
  try{await Promise.race([ready,ended.then(()=>{throw Error('Synthetic host exited before ready');}),new Promise((resolve,reject)=>{startupTimer=setTimeout(()=>reject(Error('Synthetic host startup exceeded 10 seconds')),10000);})]);}
  finally{clearTimeout(startupTimer);}
  assert.equal((await client.refresh()).caps.chunkBytes,512);
  for(const [path,data] of [['/RAM/empty',new Uint8Array()],['/RAM/text',bytes('Caf\u00e9 \u03bb \ud83e\udd16\n')],['/RAM/full',Uint8Array.from({length:8192},(_,i)=>i)],['/RAM/'+ 'x'.repeat(58),bytes('long name')]]){
   await client.save(path,data);assert.deepEqual((await client.read(path)).bytes,data);
  }
  assert.ok(sent.every(f=>f.length<=544));
  const before=(await client.read('/RAM/text')).meta;
  await assert.rejects(client.save('/RAM/text',bytes('accidental')),code('EXISTS'));
  const after=await client.save('/RAM/text',bytes('new'),before.revision);assert.notEqual(after.revision,before.revision);
  await assert.rejects(client.save('/RAM/text',bytes('stale'),before.revision),code('CONFLICT'));
  const stale=await client.rpc('read',{path:'/RAM/text',revision:before.revision,offset:0,count:1},new AbortController().signal).catch(e=>e);
  assert.equal(stale.code,'CONFLICT');assert.equal(core.decodeText((await client.read('/RAM/text')).bytes),'new');
  // Cancel after the native append acknowledgement, while a valid job is known.
  const original=transport.request.bind(transport);let cancel=true;
  transport.request=async(r,o)=>{const result=await original(r,o);if(cancel&&r.op==='append'){cancel=false;client.cancel();}return result;};
  await assert.rejects(client.save('/RAM/text',bytes('unfinished'),after.revision),code('CANCELLED'));
  assert.equal(client.uncertain,false);assert.equal(core.decodeText((await client.read('/RAM/text')).bytes),'new');
  // A lost native commit acknowledgement is never retried. The mutation really
  // completed in C, while the client blocks subsequent writes as uncertain.
  let commits=0;transport.request=async(r,o)=>{const result=await original(r,o);if(r.op==='finish'){commits++;return new Promise(()=>{});}return result;};
  client.timeout=500;await assert.rejects(client.save('/RAM/text',bytes('committed'),after.revision),code('TIMEOUT'));
  assert.equal(client.uncertain,true);assert.equal(commits,1);
  await assert.rejects(client.save('/RAM/no',bytes('blocked')),code('UNCERTAIN'));
  assert.equal(core.decodeText((await client.read('/RAM/text')).bytes),'committed');
  assert.equal((await client.refresh()).list.files.length,4);
 }catch(error){
  const last=sent.at(-1);error.message+=` (synthetic host: sent=${sent.length}, lastOp=${last?.[10]}, lastId=${last?new DataView(last.buffer).getUint32(11,true):0}, pendingBytes=${pending.length}, exit=${exitCode}, diagnostics=${diagnostics})`;throw error;
 }finally{
  transport.close();child.stdin.end();const timer=setTimeout(()=>child.kill(),5000);
  try{await ended;}finally{clearTimeout(timer);}
 }
 assert.equal(exitCode,0,diagnostics);assert.equal(diagnostics,'MBFS_HOST_READY v1\n');assert.equal(pending.length,0);
});
