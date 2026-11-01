/* SPDX-License-Identifier: MIT */
// Actual RpcClient and NDJSON with private in-memory transports, never a robot.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {RpcClient,MAX_REPLY,UPDATE_PHASES}=require('../web/microduck/rpc.js');
const commands=require('../web/microduck/commands.js');
const source=require('../linux/microduck/tests/update-watch-source.json');
const encode=value=>new TextEncoder().encode(typeof value==='string'?value:JSON.stringify(value)+'\n');
const error=code=>value=>value.code===code;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function transport({confidential=true,timeoutMs=1000,onWatch=()=>{},onNotification=()=>{}}={}){
 let receive,dropped,buffer='',closed=0,writing=0,maxWriting=0;
 const requests=[],chunks=[],references=[];
 const link={subscribe(r,d){receive=r;dropped=d;return ()=>{receive=null;dropped=null;};},
  async write(bytes){
   ++writing;maxWriting=Math.max(maxWriting,writing);chunks.push(bytes.slice());references.push(bytes);
   try{buffer+=new TextDecoder().decode(bytes);await Promise.resolve();if(!buffer.endsWith('\n'))return;
    const request=JSON.parse(buffer);buffer='';requests.push(request);
    if(request.method==='system.authenticate')receive(encode({jsonrpc:'2.0',id:request.id,result:{authenticated:true}}));
    else if(request.method==='update.subscribe')await onWatch({request,send:raw=>receive?.(raw instanceof Uint8Array?raw:encode(raw))});
   }finally{--writing;}
  },close(){closed++;}
 };
 Object.defineProperty(link,'confidential',{value:confidential,enumerable:true});
 const client=new RpcClient(link,{timeoutMs,onNotification});
 return {client,requests,chunks,references,send:raw=>receive?.(raw instanceof Uint8Array?raw:encode(raw)),drop:()=>dropped?.(),closed:()=>closed,maxWriting:()=>maxWriting};
}
const note=(params={})=>({jsonrpc:'2.0',method:'update.progress',params:{component:'robotd',phase:'downloading',percent:50,detail:null,...params}});
async function authenticate(value){await value.client.authenticate('000000');return value;}

test('accepted progress phases and no-reply semantics match the independent pinned upstream audit',()=>{
 assert.equal(source.source_commit,'96b89d8613f06722c1d64ce75ab0d7124fed9d8f');assert.equal(source.api_version,44);assert.deepEqual(UPDATE_PHASES,source.phase_names);assert.equal(source.subscribe_has_ordinary_reply,false);assert.equal(source.ble_route_allows_subscribe,true);assert.equal(source.authentication_still_required,true);assert.equal(source.confidentiality_attested,false);
});

test('streaming method refuses ordinary requests and unauthenticated watches before writes',async()=>{
 const f=transport();assert.equal(commands.validate('update.subscribe',{}).policy.stream,true);
 await assert.rejects(f.client.request('update.subscribe'),error('STREAM_REQUIRED'));
 await assert.rejects(f.client.watchUpdates(),error('AUTH_REQUIRED'));assert.equal(f.requests.length,0);assert.equal(f.chunks.length,0);assert.equal(f.client.nextId,1);f.client.close();
 const insecure=transport({confidential:false});await assert.rejects(insecure.client.authenticate('000000'),error('CONFIDENTIALITY_REQUIRED'));
 await assert.rejects(insecure.client.watchUpdates(),error('AUTH_REQUIRED'));assert.equal(insecure.chunks.length,0);insecure.client.close();
});

test('explicit watch sends one official request without waiting for an invented response',async()=>{
 const f=await authenticate(transport()),events=[],ends=[];
 const handle=await f.client.watchUpdates({onProgress:event=>events.push(event),onEnd:end=>ends.push(end)});
 assert.deepEqual(f.requests.map(q=>q.method),['system.authenticate','update.subscribe']);assert.deepEqual(f.requests[1],{jsonrpc:'2.0',id:2,method:'update.subscribe',params:{}});
 assert.equal(handle.snapshot().phase,'observing');assert.equal(handle.snapshot().acknowledged,true);assert.equal(events.length,0);
 await assert.rejects(f.client.request('robot.health'),error('BUSY'));await assert.rejects(f.client.watchUpdates(),error('BUSY'));
 f.send(note());assert.deepEqual(events[0],{component:'robotd',phase:'downloading',percent:50,detailOmitted:false,origin:'unmarked'});assert.ok(Object.isFrozen(events[0]));
 assert.equal(f.maxWriting(),1);assert.ok(f.chunks.every(chunk=>chunk.length<=20));assert.ok(f.references.every(chunk=>chunk.every(byte=>byte===0)));
 handle.stop();handle.stop();assert.equal(ends.length,1);assert.equal(ends[0].code,'WATCH_STOPPED');assert.equal(f.closed(),1);assert.equal(f.client.authenticated,false);assert.equal(handle.snapshot().phase,'closed');assert.ok(Object.isFrozen(handle.snapshot()));
});

test('early progress is delivered only after every ATT ACK, with no detail text retained',async()=>{
 let release;const events=[];
 const f=await authenticate(transport({onWatch:async({send})=>{send(note({detail:'private daemon text',simulation:true}));await new Promise(resolve=>{release=resolve;});}}));
 const pending=f.client.watchUpdates({onProgress:event=>events.push(event)});await tick();assert.deepEqual(events,[]);assert.equal(f.client.pending.early.length,1);assert.equal(f.client.pending.acknowledged,false);
 release();const handle=await pending;assert.equal(events.length,1);assert.equal(events[0].detailOmitted,true);assert.equal(events[0].origin,'simulation');assert.ok(!JSON.stringify(events).includes('private'));assert.ok(!JSON.stringify(handle.snapshot()).includes('private'));handle.stop();
});

test('a failed final ACK never exposes early progress or claims an observing session',async()=>{
 const events=[],ends=[];const f=await authenticate(transport({onWatch:async({send})=>{send(note());throw Error('private failure');}}));
 await assert.rejects(f.client.watchUpdates({onProgress:event=>events.push(event),onEnd:end=>ends.push(end)}),error('WRITE_FAILED'));
 assert.deepEqual(events,[]);assert.equal(ends.length,1);assert.equal(ends[0].acknowledged,false);assert.equal(ends[0].accepted,0);assert.equal(f.client.pending,null);assert.equal(f.closed(),1);assert.ok(f.references.every(chunk=>chunk.every(byte=>byte===0)));
});

test('write-ACK timeout and abort discard queued progress; late ACK cannot restart a watch',async()=>{
 for(const cancelled of [false,true]){
  let release;const events=[],ends=[],signal=new AbortController();
  const f=await authenticate(transport({timeoutMs:cancelled?1000:15,onWatch:async({send})=>{send(note());await new Promise(resolve=>{release=resolve;});}}));
  const promise=f.client.watchUpdates({signal:signal.signal,onProgress:event=>events.push(event),onEnd:end=>ends.push(end)});
  const rejected=assert.rejects(promise,error(cancelled?'CANCELLED':'TIMEOUT'));await tick();if(cancelled)signal.abort();await rejected;
  release();await tick();assert.equal(events.length,0);assert.equal(ends.length,1);assert.equal(f.closed(),1);assert.equal(f.client.pending,null);
 }
});

test('duration lease ends an idle watcher without inventing an update outcome or retry',async()=>{
 const f=await authenticate(transport()),ends=[];
 const ended=new Promise(resolve=>{ends.push=event=>{Array.prototype.push.call(ends,event);resolve();};});
 const handle=await f.client.watchUpdates({durationMs:15,onEnd:end=>ends.push(end)});await ended;
 assert.equal(handle.snapshot().endCode,'WATCH_TIME_LIMIT');assert.equal(handle.snapshot().accepted,0);assert.equal(f.requests.length,2);assert.equal(f.closed(),1);assert.equal(ends.length,1);
 await assert.rejects(f.client.request('update.status'),error('DISCONNECTED'));
});

test('event budget counts unrelated notifications and stops at the configured bound',async()=>{
 const f=await authenticate(transport()),events=[],ends=[];const handle=await f.client.watchUpdates({maxEvents:2,onProgress:event=>events.push(event),onEnd:end=>ends.push(end)});
 f.send({jsonrpc:'2.0',method:'unrelated',params:{secret:'not retained'}});f.send(note());f.send(note({percent:100}));
 assert.equal(events.length,1);assert.equal(handle.snapshot().notifications,2);assert.equal(handle.snapshot().accepted,1);assert.equal(ends[0].code,'WATCH_EVENT_LIMIT');assert.equal(f.closed(),1);assert.equal(f.requests.length,2);
});

test('early event budget is bounded while the final acknowledgement is pending',async()=>{
 let release;const events=[],ends=[];
 const f=await authenticate(transport({onWatch:async({send})=>{send(note());send(note());await new Promise(resolve=>{release=resolve;});}}));
 const promise=f.client.watchUpdates({maxEvents:1,onProgress:event=>events.push(event),onEnd:end=>ends.push(end)});
 await assert.rejects(promise,error('WATCH_EVENT_LIMIT'));assert.equal(events.length,0);assert.equal(ends.length,1);release();await tick();assert.equal(f.client.closed,true);
});

test('only upstream phases and bounded typed progress are exposed; idle and 100 are not terminal',async()=>{
 const f=await authenticate(transport()),events=[];const handle=await f.client.watchUpdates({onProgress:event=>events.push(event)});
 for(const phase of UPDATE_PHASES)f.send(note({phase,percent:null}));f.send(note({phase:'idle',percent:100}));
 assert.equal(events.length,14);assert.equal(handle.snapshot().phase,'observing');assert.equal(f.client.closed,false);assert.ok(events.every(event=>!Object.hasOwn(event,'success')));handle.stop();
});

test('invalid progress schemas close rather than fabricating values or accepting unknown success phases',async()=>{
 for(const params of [{phase:'success'},{percent:101},{percent:-1},{percent:1.5},{percent:'50'},{component:'../robotd'},{component:''},{detail:{}},{simulation:'true'},{other:true}]){
  const f=await authenticate(transport()),events=[],ends=[];await f.client.watchUpdates({onProgress:event=>events.push(event),onEnd:end=>ends.push(end)});f.send(note(params));
  assert.equal(events.length,0,JSON.stringify(params));assert.equal(ends[0].code,'PROTOCOL');assert.equal(f.client.closed,true);
 }
});

test('fragmented UTF-8 and coalesced progress preserve samples while omitting raw detail',async()=>{
 const f=await authenticate(transport()),events=[];const handle=await f.client.watchUpdates({onProgress:event=>events.push(event)});
 const bytes=encode(note({detail:'caf\u00e9 \ud83e\udd86'}));for(const byte of bytes)f.send(Uint8Array.of(byte));
 f.send(JSON.stringify(note({percent:75}))+'\r\n'+JSON.stringify(note({percent:100}))+'\n');
 assert.deepEqual(events.map(event=>event.percent),[50,75,100]);assert.equal(events[0].detailOmitted,true);handle.stop();
});

test('malformed envelopes, UTF-8 and oversized progress stop exactly once',async()=>{
 for(const frame of ['broken\n','[]\n','{"jsonrpc":"1.0","method":"update.progress"}\n',Uint8Array.of(255,10),new Uint8Array(MAX_REPLY+1)]){
  const f=await authenticate(transport()),ends=[];await f.client.watchUpdates({onEnd:end=>ends.push(end)});f.send(frame);f.drop();f.client.close();
  assert.equal(ends.length,1);assert.equal(f.closed(),1);assert.equal(f.client.pending,null);
 }
});

test('matching remote errors are redacted, and an ordinary stream success response is refused',async()=>{
 for(const success of [false,true]){
  const f=await authenticate(transport()),ends=[];await f.client.watchUpdates({onEnd:end=>ends.push(end)});
  f.send({jsonrpc:'2.0',id:2,...(success?{result:{ok:true}}:{error:{code:-32003,message:'private failure',data:'private'}})});
  assert.equal(ends[0].code,success?'PROTOCOL':'REMOTE_-32003');assert.ok(!JSON.stringify(ends).includes('private'));assert.equal(f.client.closed,true);
 }
});

test('mismatched response IDs do not end an observation and cannot become progress',async()=>{
 const f=await authenticate(transport()),events=[];const handle=await f.client.watchUpdates({onProgress:event=>events.push(event)});
 f.send({jsonrpc:'2.0',id:1,result:{percent:100}});assert.equal(events.length,0);assert.equal(f.client.closed,false);f.send(note());assert.equal(events.length,1);handle.stop();
});

test('abort, dropped transport and explicit close remove ownership and never replay',async()=>{
 for(const operation of ['abort','drop','close']){
  const f=await authenticate(transport()),ends=[],abort=new AbortController();const handle=await f.client.watchUpdates({signal:abort.signal,onEnd:end=>ends.push(end)});
  if(operation==='abort')abort.abort();else if(operation==='drop')f.drop();else f.client.close();
  handle.stop();assert.equal(ends.length,1);assert.equal(f.closed(),1);assert.equal(f.client.pending,null);assert.equal(f.requests.length,2);assert.equal(f.client.authenticated,false);
 }
});

test('callbacks cannot prevent cleanup, and coalesced notifications after stop are not delivered',async()=>{
 let handle;const notes=[];const f=await authenticate(transport({onNotification:value=>notes.push(value)}));
 handle=await f.client.watchUpdates({onProgress:()=>{handle.stop();throw Error('consumer');},onEnd:()=>{throw Error('consumer');}});
 f.send(JSON.stringify(note())+'\n'+JSON.stringify(note())+'\n');assert.equal(handle.snapshot().accepted,1);assert.equal(f.closed(),1);assert.deepEqual(notes,[]);
});

test('invalid watch options, pre-aborted signals and exhausted IDs send no subscription',async()=>{
 const f=await authenticate(transport());
 for(const options of [null,[],{durationMs:0},{durationMs:300001},{durationMs:NaN},{maxEvents:0},{maxEvents:257},{maxEvents:1.5},{onProgress:null},{onEnd:true},{signal:{}},{url:'wss://invalid'}])await assert.rejects(f.client.watchUpdates(options),error('PARAMS'));
 const abort=new AbortController();abort.abort();await assert.rejects(f.client.watchUpdates({signal:abort.signal}),error('CANCELLED'));
 f.client.nextId=Number.MAX_SAFE_INTEGER+1;await assert.rejects(f.client.watchUpdates(),error('ID_EXHAUSTED'));assert.equal(f.requests.length,1);f.client.close();
});

test('a pending ordinary request prevents starting an overlapping watcher',async()=>{
 const f=await authenticate(transport()),abort=new AbortController();const pending=f.client.request('robot.health',{}, {signal:abort.signal});
 const rejected=assert.rejects(pending,error('CANCELLED'));await assert.rejects(f.client.watchUpdates(),error('BUSY'));abort.abort();await rejected;assert.ok(!f.requests.some(request=>request.method==='update.subscribe'));
});
