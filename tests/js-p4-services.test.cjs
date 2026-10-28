// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert=require('node:assert/strict');const {load}=require('./support/js_editor_headless.cjs');
const {spawn}=require('node:child_process');
const assets=process.argv[2],tick=()=>new Promise(resolve=>setTimeout(resolve,0));
const long=(type,body,chunk=0)=>new Uint8Array([251,type,chunk,body.length&255,body.length>>8,...body]);
async function until(check){const end=Date.now()+2500;while(!check()){if(Date.now()>end)throw Error('Service fixture timed out');await tick();}}
function device(){
 const chunks=[],reads=[],messages=[];let incoming=[],closed=0;
 const reader={read(){if(chunks.length)return Promise.resolve({value:chunks.shift(),done:false});return new Promise(resolve=>reads.push(resolve));},async cancel(){for(const resolve of reads.splice(0))resolve({done:true});},releaseLock(){}};
 const writer={async write(bytes){incoming.push(...bytes);while(incoming.length>=3){const n=incoming[0]===250?3:incoming.length>=5?5+incoming[3]+256*incoming[4]:Infinity;if(incoming.length<n)break;const frame=new Uint8Array(incoming.splice(0,n));messages.push(frame);if(d.onMessage)d.onMessage(frame);}},async abort(){},releaseLock(){}};
 const d={messages,onMessage:null,port:{async open(){},async setSignals(){},async close(){closed++;},readable:{getReader:()=>reader},writable:{getWriter:()=>writer}},get closed(){return closed;},
  feed(bytes){const value=new Uint8Array(bytes);if(reads.length)reads.shift()({value,done:false});else chunks.push(value);}};
 return d;
}
async function fixture(identify=true){
 const devices=[],h=load(assets,{serial:{async requestPort(){const d=device();devices.push(d);return d.port;}}});
 const c=h.evaluate('MB_connection'),broker=h.evaluate('MB_p4Services');
 h.evaluate('globalThis.output=[];MB_editor.showResult=(id,value)=>output.push({id,value});MB_editor.updateRunning=()=>{};');
 async function connect(){await h.evaluate('MB_connection.connect("serial")');await until(()=>c.isConnected());if(identify)await inject(long(22,[2,...Buffer.from('v417 Waveshare ESP32-P4 WIFI6 Zephyr')]));}
 async function inject(bytes){devices.at(-1).feed(bytes);await tick();c.processMessages();}
 await connect();return {h,c,broker,devices,connect,inject,async close(){c.disconnect();await until(()=>devices.at(-1).closed===1);}};
}
async function nativeFiles(binary,distribution){
 const wsl=require('node:path').join(process.env.SystemRoot||'C:\\Windows','System32','wsl.exe');
 const f=await fixture();const child=distribution?spawn(wsl,['-d',distribution,'--','env','ASAN_OPTIONS=detect_leaks=1',binary]):spawn(binary,[],{env:{...process.env,ASAN_OPTIONS:'detect_leaks=1'}});
 let stderr='',ready=false,exit=null,childError=null;child.stderr.on('data',b=>{stderr+=b.toString();if(stderr.includes('MBFS_APPLICATION_READY v1'))ready=true;});child.on('error',e=>{childError=e;});child.on('close',code=>{exit=code;});
 try{
  await until(()=>ready||childError||exit!==null);if(childError)throw childError;assert(ready,stderr);
  f.devices[0].onMessage=frame=>{if(frame[1]===217)child.stdin.write(frame);};
  child.stdout.on('data',bytes=>{f.devices[0].feed(bytes.subarray(0,3));if(bytes.length>3)f.devices[0].feed(bytes.subarray(3));setImmediate(()=>f.c.processMessages());});
  const files=f.h.evaluate('MicroBlocksFilesConnection'),transport=await files.open();
  f.h.set('nativeTransport',transport);f.h.evaluate('globalThis.nativeClient=new MicroBlocksFiles.Client(nativeTransport);');
  const client=f.h.evaluate('nativeClient'),state=await client.refresh();assert.equal(state.caps.maxFileBytes,8192);assert.equal(state.list.files.length,0);
  const bytes=new Uint8Array(Buffer.from('JavaScript native file bridge\n')),path='/RAM/js-native.txt';const meta=await client.save(path,bytes,null);const opened=await client.read(path);assert.deepEqual([...opened.bytes],[...bytes]);
  await assert.rejects(client.save(path,bytes,null),e=>e.code==='EXISTS');
  const replacement=new Uint8Array(Buffer.from('conditional replacement'));await client.save(path,replacement,meta.revision);assert.deepEqual([...(await client.read(path)).bytes],[...replacement]);
  await files.close();await f.c.sendQueue;child.stdin.end();await until(()=>exit!==null);assert.equal(exit,0,stderr);assert(!/AddressSanitizer|runtime error:/.test(stderr),stderr);
  return {actual_pinned_connection:true,native_storage_service:true,native_pinned_vm_sender:true,synthetic_usb:true,physical_hardware:false,conditional_writes:true,exact_bytes:true,asan_ubsan:true};
 }finally{await f.close();if(exit===null){child.stdin.end();child.kill();}}
}
async function main(){if(process.argv[3]==='--native'){const config=JSON.parse(process.argv[4]);assert.equal(typeof config.binary,'string');console.log(JSON.stringify(await nativeFiles(config.binary,config.distribution)));return;}let passed=0;async function test(run){await run();passed++;}
 await test(async()=>{const f=await fixture(),seen=[],second=[];try{
  f.broker.subscribe(frame=>{seen.push([...frame]);frame.fill(0);});f.broker.subscribe(frame=>second.push([...frame]));
  const type=f.c.msgNameToID('taskReturnedValueMsg'),result=long(type,[1,42,0,0,0],7),media=long(208,new Uint8Array(14));
  await f.inject(new Uint8Array([...media.slice(0,3)]));assert.equal(seen.length,0);
  await f.inject(new Uint8Array([...media.slice(3),...result]));assert.equal(seen.length,1);assert.deepEqual(second[0],seen[0]);assert.deepEqual(JSON.parse(f.h.evaluate('JSON.stringify(output)')),[{id:7,value:42}]);
  for(const [id,max] of [[206,514],[207,4],[208,526],[209,12],[216,1010],[217,640]])await f.inject(long(id,new Uint8Array(max)));
  assert.equal(seen.length,7);assert(f.c.isConnected());
 }finally{await f.close();}});
 await test(async()=>{for(const [id,min,max] of [[206,2,514],[207,4,4],[208,14,526],[209,12,12],[216,10,1010],[217,16,640]])for(const length of [min-1,max+1]){
  const f=await fixture();try{await f.inject(new Uint8Array([251,id,0,length&255,length>>8]));assert.equal(f.c.port,null);}finally{await f.close();}}
 });
 await test(async()=>{const f=await fixture(false),seen=[];try{f.broker.subscribe(x=>seen.push(x));await f.inject(long(208,new Uint8Array(14)));assert.equal(seen.length,0);assert(!f.broker.available());
  await f.inject(long(22,[2,...Buffer.from('v417 Waveshare ESP32-P4 WIFI6 Zephyr')]));await f.inject(long(208,new Uint8Array(14)));assert.equal(seen.length,1);
 }finally{await f.close();}});
 await test(async()=>{const f=await fixture();let delivered=0;try{f.broker.subscribe(()=>{throw Error('Consumer fixture failure');});f.broker.subscribe(()=>delivered++);await f.inject(long(208,new Uint8Array(14)));assert.equal(delivered,1);assert(f.c.isConnected());}finally{await f.close();}});
 await test(async()=>{const f=await fixture();try{
  const core=require('../web/p4-neural-core.js'),frame=core.packet(0,71);assert.equal(f.broker.send(frame),frame.length);await f.c.sendQueue;await f.c.port.boardUSB.chain;
  assert.deepEqual([...f.devices[0].messages.find(x=>x[1]===216)],[...frame]);
  assert.throws(()=>f.broker.send(new Uint8Array([251,209,0,1,0,254])),/Unsupported/);
  assert.throws(()=>f.broker.send(new Uint8Array([251,216,0,1,0,0])),/Invalid framed/);
  const stale=f.h.evaluate('MicroBlocksFilesConnection.send');f.c.disconnect();await until(()=>f.devices[0].closed===1);await f.connect();assert.equal(stale(frame),0);assert.notEqual(f.h.evaluate('MicroBlocksFilesConnection.send'),stale);assert.equal(f.devices.length,2);
 }finally{await f.close();}});
 await test(async()=>{const f=await fixture();try{
  f.h.evaluate('globalThis.neuralClient=new MicroBlocksP4Neural.Client(MB_p4Services,P4NeuralCore,{timeout:500});');const client=f.h.evaluate('neuralClient'),session=client.bind();
  const pending=session.request(0);await f.c.sendQueue;const sent=f.devices[0].messages.at(-1),id=new DataView(sent.buffer,sent.byteOffset).getUint32(11,true);
  const body=new Uint8Array(10+2),v=new DataView(body.buffer);v.setUint32(0,id,true);body.set(Buffer.from('{}'),10);await f.inject(long(216,body));assert.equal((await pending).token,0);
  const interrupted=session.request(10);const rejected=assert.rejects(interrupted,/session changed/);f.c.disconnect();await rejected;await until(()=>f.devices[0].closed===1);await f.connect();
  await assert.rejects(session.request(0),/previous connection/);const current=client.bind(),next=current.request(0);await f.c.sendQueue;
  await f.inject(long(216,body));assert(client.pending);const latest=f.devices.at(-1).messages.at(-1),newId=new DataView(latest.buffer,latest.byteOffset).getUint32(11,true);v.setUint32(0,newId,true);body[4]=3;await f.inject(long(216,body));await assert.rejects(next,/unavailable/);client.close();
 }finally{await f.close();}});
 await test(async()=>{const f=await fixture();try{f.h.evaluate('globalThis.neuralClient=new MicroBlocksP4Neural.Client(MB_p4Services,P4NeuralCore,{timeout:10});');const client=f.h.evaluate('neuralClient');await assert.rejects(client.bind().request(0),/outcome may be uncertain/);assert.equal(client.pending,null);client.close();}finally{await f.close();}});
 await test(async()=>{const f=await fixture();try{
  const files=f.h.evaluate('MicroBlocksFilesConnection'),opening=files.open();await f.c.sendQueue;const sent=f.devices[0].messages.find(x=>x[1]===217),sv=new DataView(sent.buffer,sent.byteOffset),id=sv.getUint32(11,true),nonce=sv.getUint32(19,true);
  function fileReply(op,id,session,payload){const body=new Uint8Array(16+payload.length),v=new DataView(body.buffer);body.set([77,66,70,82,1,op]);v.setUint32(6,id,true);v.setUint32(10,session,true);body.set(payload,16);return long(217,body);}
  const grant=new Uint8Array(8),gv=new DataView(grant.buffer);gv.setUint32(0,91,true);gv.setUint32(4,nonce,true);await f.inject(fileReply(9,id,0,grant));const transport=await opening;
  const request={version:1,id:1,op:'capabilities',args:{}},pending=transport.request(request);await f.c.sendQueue;await f.inject(fileReply(1,1,91,[8,0,32,0,2,3,1]));const reply=await pending;
  assert.equal(reply.data.backends[0].maxFileBytes,8192);assert.equal(reply.data.backends[1].available,false);assert.equal(reply.data.backends[2].available,false);
  const waiting=transport.request({version:1,id:2,op:'list',args:{backend:'RAM'}});const rejected=assert.rejects(waiting,e=>e.code==='DISCONNECTED');f.c.disconnect();await rejected;
 }finally{await f.close();}});
 console.log(JSON.stringify({passed,actual_pinned_connection:true,typed_file_controller:true,neural_generation_guards:true,native_robot_or_board:false,service_data:'protocol fixtures'}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
