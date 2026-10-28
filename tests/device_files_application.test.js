/* SPDX-License-Identifier: MPL-2.0 */
// Production generated adapter + real SerialTransport + native VM file bridge.
// Device selection/streams are synthetic; there is no browser/network/board I/O.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),path=require('node:path');
const {spawn,execFileSync}=require('node:child_process');
const portal=require('../web/portal/portal-core.js'),core=require('../web/device-files-core.js'),{Controller}=require('../web/device-files-controller.js');
const repo=path.resolve(__dirname,'..');
const adapter=execFileSync(process.env.PYTHON||'python',['-c',"import sys;from pathlib import Path;sys.path.insert(0,'tools');from package_p4_ide import adapter;sys.stdout.buffer.write(adapter(Path('.')))"],{cwd:repo,encoding:'utf8'});
const code=c=>e=>e.code===c;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function until(fn){const end=Date.now()+3000;while(!fn()){if(Date.now()>end)throw Error('Synthetic lifecycle wait exceeded bound');await tick();}}

test('actual P4 adapter and SerialTransport route native file sessions and preserve GP frames',{timeout:30000},async()=>{
 const binary=process.env.MB_FILES_APPLICATION_HOST;assert.ok(binary,'Build tools/test_storage_controller.py; no device fallback is allowed.');
 const child=process.env.MB_FILES_WSL?spawn('wsl.exe',['-d',process.env.MB_FILES_WSL,'--',binary]):spawn(binary,[]);
 let diagnostics='',readyResolve,output=Buffer.alloc(0),current=null,requests=0,nonce=40,hold=false,held=[],allReplies=[];
 const ready=new Promise(resolve=>{readyResolve=resolve;});
 const ended=new Promise((resolve,reject)=>{child.once('error',reject);child.once('close',resolve);});
 child.stderr.on('data',data=>{diagnostics+=data.toString();if(diagnostics.includes('MBFS_APPLICATION_READY v1\n'))readyResolve();});
 const send=data=>new Promise((resolve,reject)=>child.stdin.write(data,e=>e?reject(e):resolve()));
 const inject=data=>{if(current&&!current.closed)current.stream.enqueue(data);};
 child.stdout.on('data',data=>{
  output=Buffer.concat([output,data]);
  while(output.length>=5){const n=5+output.readUInt16LE(3);assert.ok(n>=21&&n<=645);if(output.length<n)return;
   const frame=new Uint8Array(output.subarray(0,n));output=output.subarray(n);allReplies.push(frame);
   if(hold)held.push(frame);else {inject(frame.slice(0,7));inject(frame.slice(7));}
  }
 });
 const provider={async requestPort(){
  requests++;const port={closed:false,async open(){},async setSignals(){},async close(){this.closed=true;await send(new Uint8Array([250,1,0]));},
   writable:{getWriter(){return {write:send,releaseLock(){}};}}};
  port.readable=new ReadableStream({start(stream){port.stream=stream;},cancel(){port.closed=true;}});current=port;return port;
 }};
 const controller=new Controller({nonce:()=>++nonce,timeout:1000}),listeners={};
 const window={MicroBlocksFilesConnection:controller,addEventListener(name,fn){listeners[name]=fn;},dispatchEvent(){}};
 const context={window,MicroBlocksPortal:portal,PORTAL_BOARD:{board:'esp32p4',name:'P4'},navigator:{serial:provider},
  document:{addEventListener(){}},GP_writeFile(){},GP:{apiCall(){}},WebSocket:class{static OPEN=1;constructor(){throw Error('No network allowed');}},
  CustomEvent:class{constructor(type,detail){this.type=type;this.detail=detail;}},TextEncoder,TextDecoder,setTimeout,clearTimeout,Uint8Array,Uint32Array,Map,URL};
 vm.runInNewContext(adapter,context);
 let timer;
 try{
  try{await Promise.race([ready,ended.then(()=>{throw Error('Native fixture exited before ready');}),new Promise((resolve,reject)=>{timer=setTimeout(()=>reject(Error('Native fixture startup timeout')),10000);})]);}finally{clearTimeout(timer);}
  assert.equal(controller.state,'disconnected');await window.webSerialConnect();assert.equal(requests,1);assert.equal(controller.state,'available');
  assert.equal(allReplies.length,0,'Board connect must not automatically open file access');
  const transport=await controller.open(),client=new core.Client(transport);
  const oldSession=transport.session;assert.equal(controller.state,'ready');
  inject(new Uint8Array([250,26,42]));await tick();assert.deepEqual([...window.GP_readSerialPort(30)],[250,26,42]);
  const meta=await client.save('/RAM/message',core.encodeText('Caf\u00e9 native frame'));
  assert.equal(core.decodeText((await client.read('/RAM/message')).bytes),'Caf\u00e9 native frame');
  assert.equal(window.GP_readSerialPort(4096).length,0,'Storage replies must not reach GP parser');
  // Repeated reads and a real conditional replacement on the same connection.
  for(let i=0;i<4;i++)assert.equal((await client.read('/RAM/message')).meta.revision,meta.revision);
  const changed=await client.save('/RAM/message',new Uint8Array([0,254,255]),meta.revision);
  assert.deepEqual([...(await client.read('/RAM/message')).bytes],[0,254,255]);
  const oldReply=allReplies.find(f=>f[10]===1); // old capability response, id1/session1
  await controller.close();assert.equal(controller.state,'available');
  await assert.rejects(client.refresh(),code('DISCONNECTED'));
  const second=await controller.open(),client2=new core.Client(second);assert.notEqual(second.session,oldSession);
  hold=true;const refresh=client2.refresh();await until(()=>held.length>0);
  inject(oldReply);await tick();assert.notEqual(second.pending,null,'Old-session same-id reply is ignored');
  hold=false;for(const frame of held)inject(frame);held=[];await refresh;
  assert.equal((await client2.read('/RAM/message')).meta.revision,changed.revision);
  // Real transport cancellation after the native append acknowledgement.
  const original=second.request.bind(second);let cancel=true;
  second.request=async(r,o)=>{const answer=await original(r,o);if(cancel&&r.op==='append'){cancel=false;client2.cancel();}return answer;};
  await assert.rejects(client2.save('/RAM/message',core.encodeText('unfinished'),changed.revision),code('CANCELLED'));
  assert.deepEqual([...(await client2.read('/RAM/message')).bytes],[0,254,255]);
  // Disconnect during an in-flight read; no old frame or partial head leaks.
  hold=true;const waiting=client2.read('/RAM/message');const rejection=assert.rejects(waiting,code('DISCONNECTED'));
  await until(()=>held.length>0);inject(new Uint8Array([251,217,0,80]));window.webSerialDisconnect();await rejection;
  await until(()=>current.closed);await tick();assert.equal(controller.state,'disconnected');
  hold=false;held=[];await window.webSerialConnect();await until(()=>controller.state==='available');assert.equal(requests,2);
  const third=await controller.open(),client3=new core.Client(third);assert.notEqual(third.session,second.session);
  assert.deepEqual([...(await client3.read('/RAM/message')).bytes],[0,254,255]);
  assert.equal(window.GP_readSerialPort(4096).length,0);
  await controller.close();window.webSerialDisconnect();await until(()=>current.closed);
 }finally{
  window.webSerialDisconnect();await tick();child.stdin.end();timer=setTimeout(()=>child.kill(),5000);
  try{assert.equal(await ended,0,diagnostics);}finally{clearTimeout(timer);}
 }
 assert.equal(diagnostics,'MBFS_APPLICATION_READY v1\n');assert.equal(output.length,0);
});

test('open cancellation and replacement links cannot publish an obsolete grant',async()=>{
 let nonce=1;const controller=new Controller({timeout:50,nonce:()=>nonce++}),sent=[];
 const wire=require('../web/device-files-wire.js');
 function grant(frame,session){
  const b=new Uint8Array(29),v=new DataView(b.buffer);b.set([251,217,0,24,0,77,66,70,82,1,9]);
  v.setUint32(11,new DataView(frame.buffer).getUint32(11,true),true);v.setUint32(21,session,true);v.setUint32(25,new DataView(frame.buffer).getUint32(19,true),true);return b;
 }
 const send=f=>{sent.push(f);return f.length;};controller.link(send);
 const first=controller.open();const rejected=assert.rejects(first,code('DISCONNECTED'));controller.link(null);await rejected;
 controller.link(send);const second=controller.open();controller.receive(grant(sent[0],1));assert.equal(controller.state,'connecting');
 controller.receive(grant(sent[1],2));const current=await second;assert.equal(current.session,2);controller.link(null);assert.equal(current.closed,true);
 controller.link(send);const interrupted=controller.open();const interruptedRejection=assert.rejects(interrupted,code('DISCONNECTED'));
 await controller.close();await interruptedRejection;assert.equal(controller.state,'available');
 const timed=controller.open();await assert.rejects(timed,code('TIMEOUT'));assert.equal(controller.state,'error');assert.equal(controller.transport,null);
 assert.throws(()=>wire.encode({version:1,id:1,op:'open',args:{nonce:0}},0),code('PROTOCOL'));
 controller.link(null);
});

for(const [nativeStatus,nativeCode] of [[2,'DISCONNECTED'],[12,'TIMEOUT']])test('expired native '+nativeCode+' grants leave ready state without reconnecting or replaying',async()=>{
 const controller=new Controller({timeout:50,nonce:()=>42}),sent=[],states=[];
 controller.subscribe(s=>states.push(s.state));
 controller.link(f=>{sent.push(f);return f.length;});
 const opened=controller.open(),grant=new Uint8Array(29),gv=new DataView(grant.buffer);
 grant.set([251,217,0,24,0,77,66,70,82,1,9]);gv.setUint32(11,42,true);gv.setUint32(21,7,true);gv.setUint32(25,42,true);
 controller.receive(grant);const transport=await opened,client=new core.Client(transport);
 const pending=client.keepAlive(),rejected=assert.rejects(pending,code(nativeCode));await tick();
 const response=new Uint8Array(21),v=new DataView(response.buffer);
 response.set([251,217,0,16,0,77,66,70,82,1,1]);v.setUint32(11,1,true);v.setUint32(15,7,true);response[19]=nativeStatus;
 controller.receive(response);await rejected;
 assert.equal(controller.state,'available');assert.equal(controller.error,nativeCode);
 assert.equal(controller.transport,null);assert.equal(transport.closed,true);
 assert.equal(sent.length,2,'One grant and one read-only check; no implicit new grant or replay');
 assert.deepEqual(states,['disconnected','available','connecting','ready','available']);
 controller.link(null);
});
