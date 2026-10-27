/* SPDX-License-Identifier: MIT */
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const commands=require('../web/microduck/commands.js'),rpc=require('../web/microduck/rpc.js'),ble=require('../web/microduck/bluetooth.js');
const bytes=s=>new TextEncoder().encode(s),code=c=>e=>e.code===c;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function fixture({confidential=true,answer=()=>({ok:true}),timeoutMs=1000,onNotification}={}){
 let receive,dropped,buf='',closed=0;const writes=[],requests=[];
 const transport={confidential,subscribe:(r,d)=>{receive=r;dropped=d;return ()=>{receive=null;dropped=null;};},
  write:async chunk=>{writes.push(chunk.slice());buf+=new TextDecoder().decode(chunk);if(buf.endsWith('\n')){const request=JSON.parse(buf);buf='';requests.push(request);const result=answer(request);if(result!==undefined)queueMicrotask(()=>receive?.(bytes(JSON.stringify({jsonrpc:'2.0',id:request.id,result})+'\n')));}},
  close:()=>closed++};
 const client=new rpc.RpcClient(transport,{timeoutMs,onNotification});
 return {client,transport,writes,requests,closed:()=>closed,receive:s=>receive?.(typeof s==='string'?bytes(s):s),drop:()=>dropped?.()};
}
const authAnswer=r=>r.method==='system.authenticate'?{authenticated:true,attempts_remaining:3}:{ok:true};

test('framing reassembles UTF-8 split at every byte and accepts CRLF/coalescing',()=>{
 const text='{"jsonrpc":"2.0","id":1,"result":"café 🦆"}',encoded=bytes(text+'\r\n');
 for(let at=0;at<=encoded.length;at++){const l=new rpc.Lines();assert.deepEqual([...l.push(encoded.slice(0,at)),...l.push(encoded.slice(at))],[text]);assert.equal(l.used,0);}
 const l=new rpc.Lines();assert.deepEqual(l.push(bytes('\n\r\n{}\n[]\n{"x":')),['{}','[]']);assert.equal(l.used,5);assert.deepEqual(l.push(bytes('1}\n')),['{"x":1}']);
});
test('framing bounds each line, rejects invalid UTF-8, and clears state',()=>{
 const l=new rpc.Lines(8);assert.throws(()=>l.push(bytes('123456789')),code('LINE_TOO_LONG'));assert.equal(l.used,0);
 assert.throws(()=>l.push(Uint8Array.of(255,10)),code('UTF8'));assert.equal(l.used,0);
 assert.deepEqual(l.push(bytes('{}\n{}\n{}\n{}\n')),['{}','{}','{}','{}']);
 assert.throws(()=>l.push(new Uint8Array(rpc.MAX_REPLY+1)),code('LINE_TOO_LONG'));
 assert.throws(()=>new rpc.Lines(65537),code('LIMIT'));
});
test('request encoding preserves official envelope and bounds request bytes',()=>{
 const q={jsonrpc:'2.0',id:1,method:'hello',params:{api_version:44}};
 assert.equal(new TextDecoder().decode(rpc.encode(q)),JSON.stringify(q)+'\n');
 assert.throws(()=>rpc.encode({pad:'x'.repeat(8192)}),code('REQUEST_TOO_LONG'));
});
test('writes are 20-byte acknowledged chunks in order and one request owns stream',async()=>{
 const f=fixture({answer:()=>undefined}),p=f.client.request('hello');
 await assert.rejects(f.client.request('hello'),code('BUSY'));await tick();
 assert.ok(f.writes.length>1);assert.ok(f.writes.every(x=>x.length<=20));
 assert.equal(f.requests[0].method,'hello');assert.equal(f.requests[0].params.api_version,44);
 f.receive(JSON.stringify({jsonrpc:'2.0',id:999,result:'late'})+'\n');assert.ok(f.client.pending);
 f.receive(JSON.stringify({jsonrpc:'2.0',id:1,result:{api_version:44}})+'\n');assert.deepEqual(await p,{api_version:44});f.client.close();
});
test('sequential writer never overlaps asynchronous acknowledgements',async()=>{
 let receive,inflight=0,max=0,buf='';
 const t={confidential:true,subscribe:f=>{receive=f;return ()=>{};},write:async b=>{inflight++;max=Math.max(max,inflight);await tick();buf+=new TextDecoder().decode(b);inflight--;if(buf.endsWith('\n'))receive(bytes('{"jsonrpc":"2.0","id":1,"result":{}}\n'));}};
 const c=new rpc.RpcClient(t);await c.request('hello');assert.equal(max,1);c.close();
});
test('early final response retains ownership until its ATT acknowledgement before chained request',async()=>{
 let receive,inflight=0,max=0,buf='',releaseFinal,completed=false;const chunks=[],requests=[];
 const transport={confidential:true,subscribe:f=>{receive=f;return ()=>{};},write:async chunk=>{
  chunks.push(chunk);inflight++;max=Math.max(max,inflight);buf+=new TextDecoder().decode(chunk);
  if(buf.endsWith('\n')){
   const request=JSON.parse(buf);buf='';requests.push(request);
   receive(bytes(JSON.stringify({jsonrpc:'2.0',id:request.id,result:{id:request.id}})+'\n'));
   if(request.id===1)await new Promise(resolve=>{releaseFinal=resolve;});
  }
  inflight--;
 }};
 const c=new rpc.RpcClient(transport),first=c.request('hello');
 const next=first.then(result=>{completed=true;assert.equal(result.id,1);return c.request('hello');});
 await tick();assert.equal(completed,false);assert.equal(c.pending.id,1);assert.equal(inflight,1);assert.equal(requests.length,1);
 await assert.rejects(c.request('hello'),code('BUSY'));releaseFinal();assert.deepEqual(await next,{id:2});
 assert.equal(requests.length,2);assert.equal(max,1);assert.ok(chunks.every(chunk=>chunk.every(b=>b===0)));c.close();
});
test('early authentication response cannot succeed if final acknowledgement fails',async()=>{
 let receive,buf='';const chunks=[];
 const c=new rpc.RpcClient({confidential:true,subscribe:f=>{receive=f;return ()=>{};},write:async chunk=>{
  chunks.push(chunk);buf+=new TextDecoder().decode(chunk);if(buf.endsWith('\n')){
   const request=JSON.parse(buf);receive(bytes(JSON.stringify({jsonrpc:'2.0',id:request.id,result:{authenticated:true}})+'\n'));
   assert.equal(c.authenticated,false);await tick();throw Error('late ATT failure');
  }
 }});
 await assert.rejects(c.authenticate('000042'),code('WRITE_FAILED'));assert.equal(c.authenticated,false);assert.equal(c.closed,true);assert.ok(chunks.every(chunk=>chunk.every(b=>b===0)));
});
test('timeout and abort still close after response while final acknowledgement remains pending',async()=>{
 for(const abort of [false,true]){
  let receive,buf='',releaseFinal,closed=0;const ac=new AbortController(),chunks=[];
  const c=new rpc.RpcClient({confidential:true,subscribe:f=>{receive=f;return ()=>{};},close:()=>closed++,write:async chunk=>{
   chunks.push(chunk);buf+=new TextDecoder().decode(chunk);if(buf.endsWith('\n')){const r=JSON.parse(buf);receive(bytes(JSON.stringify({jsonrpc:'2.0',id:r.id,result:{}})+'\n'));await new Promise(resolve=>{releaseFinal=resolve;});}
  }},{timeoutMs:abort?1000:20});
  const p=c.request('hello',{}, {signal:ac.signal});await tick();if(abort)ac.abort();
  await assert.rejects(p,code(abort?'CANCELLED':'TIMEOUT'));assert.equal(closed,1);assert.equal(c.pending,null);
  releaseFinal();await tick();assert.ok(chunks.every(chunk=>chunk.every(b=>b===0)));await assert.rejects(c.request('hello'),code('DISCONNECTED'));
 }
});
test('authentication gate, leading-zero PIN, failed PIN, and no automatic retries',async()=>{
 const f=fixture({answer:authAnswer});await assert.rejects(f.client.request('system.info'),code('AUTH_REQUIRED'));assert.equal(f.writes.length,0);
 await f.client.authenticate('000042');assert.equal(f.requests[0].params.pin,'000042');assert.equal(f.client.authenticated,true);
 assert.deepEqual(await f.client.request('system.info'),{ok:true});f.client.close();assert.equal(f.client.authenticated,false);
 const wrong=fixture({answer:()=>({authenticated:false,attempts_remaining:2})});await assert.rejects(wrong.client.authenticate('123456'),code('AUTH_FAILED'));assert.equal(wrong.requests.length,1);assert.equal(wrong.client.authenticated,false);wrong.client.close();
});
test('PIN and Wi-Fi secrets cannot leave confidentiality-unproven transport',async()=>{
 const f=fixture({confidential:false});
 await assert.rejects(f.client.authenticate('123456'),code('CONFIDENTIALITY_REQUIRED'));
 await assert.rejects(f.client.request('net.connect',{ssid:'fixture',psk:'test-only-secret'},{confirmed:true}),code('CONFIDENTIALITY_REQUIRED'));
 assert.equal(f.writes.length,0);await f.client.request('hello');f.client.close();
});
test('mutations require confirmation and preserve exact official parameter shapes',async()=>{
 const f=fixture({answer:authAnswer});await f.client.authenticate('123456');
 await assert.rejects(f.client.request('robot.init'),code('CONFIRMATION_REQUIRED'));
 await f.client.request('robot.enable',{on:false,toggle:true},{confirmed:true});
 await f.client.request('robot.sound',{tag:'chirp'},{confirmed:true});
 await f.client.request('update.apply',{component:'daemon',target:{exact:'1.2.3'}},{confirmed:true});
 assert.deepEqual(f.requests[1].params,{on:false,toggle:true});assert.deepEqual(f.requests[3].params,{component:'daemon',target:{exact:'1.2.3'},options:{}});f.client.close();
});
test('advanced console cannot forward unknown or upstream BLE-refused methods',()=>{
 for(const method of ['robot.move','robot.head','robot.stop','robot.relax','robot.shutdown','robot.subscribe','media.frame','system.pairingPin','system.setPairingPin','update.resetToGolden','update.pin','__proto__','constructor','exec'])assert.throws(()=>commands.validate(method,{}),code('METHOD_DENIED'));
 for(const [method,p] of [['hello',{api_version:44,extra:1}],['system.authenticate',{pin:'12345'}],['net.connect',{ssid:'x',psk:'short'}],['robot.enable',{on:1}],['robot.sound',{tag:'wheee'}],['robot.do',{skill:'x\n'}],['system.logs',{unit:'--directory=/etc'}],['update.apply',{component:'daemon',target:{ref:'main'}}],['update.apply',{component:'daemon',options:{force:true}}]])assert.throws(()=>commands.validate(method,p),code('PARAMS'));
});
test('actual robot-discovered skills gate the convenience control helper',async()=>{
 const f=fixture({answer:r=>r.method==='system.authenticate'?{authenticated:true}:r.method==='robot.policies'?{skills:['bow','nod']}:{accepted:true}}),c=new commands.Controls(f.client);
 await f.client.authenticate('123456');await assert.rejects(c.performSkill('bow',{confirmed:true}),code('UNDISCOVERED_SKILL'));
 await c.discover();await c.performSkill('bow',{confirmed:true});assert.deepEqual(f.requests.at(-1).params,{skill:'bow'});
 await assert.rejects(c.performSkill('unknown',{confirmed:true}),code('UNDISCOVERED_SKILL'));f.client.close();
});
test('timeout closes ambiguous session and does not retry a command',async()=>{
 const f=fixture({answer:()=>undefined,timeoutMs:15});await assert.rejects(f.client.request('hello'),code('TIMEOUT'));assert.equal(f.closed(),1);assert.equal(f.requests.length,1);assert.equal(f.client.pending,null);
 await assert.rejects(f.client.request('hello'),code('DISCONNECTED'));f.client.close();assert.equal(f.closed(),1);
});
test('abort and dropped GATT close pending requests and remove subscriptions',async()=>{
 const f=fixture({answer:()=>undefined}),ac=new AbortController(),p=f.client.request('hello',{}, {signal:ac.signal});ac.abort();await assert.rejects(p,code('CANCELLED'));assert.equal(f.closed(),1);
 const g=fixture({answer:()=>undefined}),q=g.client.request('hello');g.drop();await assert.rejects(q,code('DISCONNECTED'));assert.equal(g.closed(),1);
 const h=fixture();await assert.rejects(h.client.request('hello',{}, {signal:{aborted:false}}),code('PARAMS'));assert.equal(h.writes.length,0);h.client.close();
});
test('malformed same-ID responses never become success; server error text is redacted',async()=>{
 for(const line of ['broken\n','[]\n','{"jsonrpc":"1.0","id":1,"result":1}\n','{"jsonrpc":"2.0","id":1,"result":1,"error":{"code":1}}\n','{"jsonrpc":"2.0","id":1,"error":{"code":"bad"}}\n']){
  const f=fixture({answer:()=>undefined}),p=f.client.request('hello');f.receive(line);await assert.rejects(p,code('PROTOCOL'));assert.equal(f.closed(),1);
 }
 const f=fixture({answer:()=>undefined}),p=f.client.request('hello');f.receive('{"jsonrpc":"2.0","id":1,"error":{"code":-32602,"message":"secret should never enter public errors","data":"private"}}\n');
 await assert.rejects(p,e=>e.code==='REMOTE_-32602'&&!String(e).includes('secret')&&!Object.hasOwn(e,'data'));f.client.close();
});
test('notifications are separate from replies and reply buffer accepts bounded log tails',async()=>{
 const notes=[],f=fixture({answer:()=>undefined,onNotification:n=>notes.push(n)}),p=f.client.request('hello');
 f.receive('{"jsonrpc":"2.0","method":"update.progress","params":{"phase":"download"}}\n');assert.equal(notes[0].method,'update.progress');assert.ok(f.client.pending);
 const line=JSON.stringify({jsonrpc:'2.0',id:1,result:{tail:'x'.repeat(32*1024)}})+'\n',b=bytes(line);for(let i=0;i<b.length;i+=20)f.receive(b.slice(i,i+20));assert.equal((await p).tail.length,32*1024);f.client.close();
});
test('send failure is sanitized, rejects once, and closes without replay',async()=>{
 const f=fixture();f.transport.write=async()=>{throw new Error('secret');};await assert.rejects(f.client.request('hello'),code('WRITE_FAILED'));assert.equal(f.closed(),1);
});
function gattFixture(){
 const order=[],characteristic=new EventTarget(),device=new EventTarget();let receive='';
 Object.assign(characteristic,{properties:{read:true,write:true,notify:true},readValue:async()=>{order.push('read');return new DataView(Uint8Array.of(44).buffer);},startNotifications:async()=>{order.push('subscribe');},writeValueWithResponse:async b=>{order.push('write');receive+=new TextDecoder().decode(b);if(receive.endsWith('\n')){const r=JSON.parse(receive);receive='';characteristic.value=new DataView(bytes(JSON.stringify({jsonrpc:'2.0',id:r.id,result:{api_version:44}})+'\n').buffer);characteristic.dispatchEvent(new Event('characteristicvaluechanged'));}}});
 const server={getPrimaryService:async uuid=>{assert.equal(uuid,ble.SERVICE_UUID);return {getCharacteristic:async id=>{assert.equal(id,ble.RPC_UUID);return characteristic;}};}};
 device.gatt={connected:false,connect:async()=>{order.push('connect');device.gatt.connected=true;return server;},disconnect:()=>{device.gatt.connected=false;order.push('disconnect');}};
 const bluetooth={requestDevice:async options=>{order.push('chooser');assert.deepEqual(options,{filters:[{services:[ble.SERVICE_UUID]}]});return device;}};
 return {order,bluetooth,characteristic,device};
}
test('mock Web Bluetooth discovers by service, reads before subscribe/write, and cannot attest encryption',async()=>{
 const f=gattFixture(),connection=await ble.connect({bluetooth:f.bluetooth});assert.equal(connection.apiVersion,44);assert.equal(connection.confidential,false);
 assert.deepEqual(f.order,['chooser','connect','read','subscribe']);await connection.client.request('hello');assert.equal(f.order[4],'write');
 assert.throws(()=>{connection.client.transport.confidential=true;},TypeError);
 await assert.rejects(connection.client.authenticate('123456'),code('CONFIDENTIALITY_REQUIRED'));connection.client.close();assert.equal(f.device.gatt.connected,false);
});
test('mock GATT rejects missing acknowledged write and cleans failed discovery connection',async()=>{
 const f=gattFixture();f.characteristic.properties.write=false;await assert.rejects(ble.connect({bluetooth:f.bluetooth}),code('GATT_PROPERTIES'));assert.equal(f.device.gatt.connected,false);
 await assert.rejects(ble.connect({bluetooth:{}}),code('WEB_BLUETOOTH_UNAVAILABLE'));
});
test('mock GATT connect timeout also disconnects a connection that completes late',async()=>{
 const f=gattFixture(),original=f.device.gatt.connect;let release;
 f.device.gatt.connect=()=>new Promise(resolve=>{release=async()=>resolve(await original());});
 await assert.rejects(ble.connect({bluetooth:f.bluetooth,timeoutMs:10}),code('GATT_TIMEOUT'));
 await release();await tick();assert.equal(f.device.gatt.connected,false);
});
test('mock GATT read timeout disconnects without subscribing or sending a secret',async()=>{
 const f=gattFixture();f.characteristic.readValue=()=>new Promise(()=>{});
 await assert.rejects(ble.connect({bluetooth:f.bluetooth,timeoutMs:10}),code('GATT_TIMEOUT'));
 assert.equal(f.device.gatt.connected,false);assert.equal(f.order.includes('subscribe'),false);assert.equal(f.order.includes('write'),false);
});
test('reconnect requires a new authentication and never replays old requests',async()=>{
 const first=fixture({answer:authAnswer});await first.client.authenticate('000042');first.drop();assert.equal(first.client.authenticated,false);
 const second=fixture({answer:authAnswer});await assert.rejects(second.client.request('system.info'),code('AUTH_REQUIRED'));assert.equal(second.requests.length,0);second.client.close();
});
