/* SPDX-License-Identifier: MIT */
// Actual camera protocol/session/browser adapter with in-memory/fake RTC only.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const P=require('../web/microduck/camera-protocol.js');
const {BrowserPeer,METADATA_REQUEST}=require('../web/microduck/camera-peer.js');
const {CameraSession}=require('../web/microduck/camera-session.js');
const {createFixture}=require('../web/microduck/camera-fixture.js');
const source=require('../linux/microduck/tests/camera-source.json');
const tick=()=>new Promise(resolve=>setImmediate(resolve)),code=value=>error=>error.code===value;
const SDP='v=0\r\no=- 0 0 IN IP4 0.0.0.0\r\ns=SIMULATION\r\nt=0 0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=sendonly\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=sendonly\r\nm=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n';
const ANSWER=SDP.replaceAll('a=sendonly','a=recvonly').replace('m=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=recvonly','m=audio 0 UDP/TLS/RTP/SAVPF 111\r\na=inactive');
const candidate={candidate:'candidate:SIMULATION',sdpMLineIndex:0};
const geometry={width:1280,height:720,rotate:90,mono_ns:1000000,real_ns:1760000000000000000};
function deferred(){let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};}
class Track{
 constructor(kind){this.kind=kind;this.readyState='live';this.stops=0;this.listeners=new Set();}
 addEventListener(name,fn){if(name==='ended')this.listeners.add(fn);}
 removeEventListener(name,fn){if(name==='ended')this.listeners.delete(fn);}
 stop(){if(this.readyState==='ended')return;this.readyState='ended';this.stops++;for(const fn of [...this.listeners])fn();}
}
function channel(options={}){return {label:'control',ordered:true,maxRetransmits:null,maxPacketLifeTime:null,readyState:'open',bufferedAmount:0,sends:[],closes:0,
 send(raw){this.sends.push(raw);},close(){if(this.readyState==='closed')return;this.closes++;this.readyState='closed';this.onclose?.();},...options};}
function rig(options={}){
 const context={video:new Track('video'),audio:new Track('audio'),control:channel(),videos:[],ice:[],metadata:[],failures:[],stages:[],pc:null};
 const sinks=options.sinks||{onVideo:value=>context.videos.push(value),onIce:value=>context.ice.push(value),onMetadata:(value,error)=>context.metadata.push({value,error}),onFailure:error=>context.failures.push(error)};
 class Stream{constructor(tracks){this.tracks=options.mixedStream?[...tracks,context.audio]:[...tracks];}getTracks(){return [...this.tracks];}}
 class Peer{
  constructor(config){context.pc=this;context.config=config;this.connectionState='new';this.closes=0;this.transceivers=[{receiver:{track:context.video},direction:'sendrecv'},{receiver:{track:context.audio},direction:'sendrecv'}];}
  getSenders(){return options.localTrack?[{track:options.localTrack}]:[];}
  getReceivers(){return this.transceivers.map(item=>item.receiver);}
  getTransceivers(){return options.noVideo?[this.transceivers[1]]:this.transceivers;}
  async setRemoteDescription(description){context.stages.push('remote');this.remoteDescription=description;
   if(!options.noTrack){this.ontrack?.({track:context.audio,streams:[new Stream([context.audio,context.video])]});this.ontrack?.({track:context.video,streams:[new Stream([context.audio,context.video])]});}
   this.ondatachannel?.({channel:context.control});if(options.holdRemote)await options.holdRemote.promise;
  }
  async createAnswer(){context.stages.push('answer');if(options.holdAnswer)await options.holdAnswer.promise;return {type:'answer',sdp:options.answer??ANSWER};}
  async setLocalDescription(description){context.stages.push('local');this.localDescription=description;this.onicecandidate?.({candidate});if(options.holdLocal)await options.holdLocal.promise;}
  async addIceCandidate(value){if(!this.remoteDescription)throw Error('remote SDP required');context.stages.push('ice');if(options.iceFailure)throw Error('PRIVATE ICE');context.addedIce=value;}
  close(){this.closes++;this.connectionState='closed';}
 }
 if(options.controlWriteFailure)context.control.send=function(){this.sends.push(METADATA_REQUEST);throw Error('PRIVATE write');};
 if(options.autoMetadata)context.control.send=function(raw){this.sends.push(raw);queueMicrotask(()=>this.onmessage?.({data:JSON.stringify({jsonrpc:'2.0',id:1,result:geometry})}));};
 const peer=new BrowserPeer({RTCPeerConnection:Peer,MediaStream:Stream,...sinks,metadataTimeoutMs:options.metadataTimeoutMs??1000});
 return {peer,...context};
}
function link(onSend=()=>{}){
 let receive=null,drop=null,closed=false,closes=0;const sent=[];
 const value={emit(message){receive?.(typeof message==='string'?message:JSON.stringify(message));},drop(){drop?.();},sent,closed:()=>closed,closes:()=>closes,receiver:()=>receive};
 value.transport={subscribe(r,d){receive=r;drop=d;return ()=>{receive=null;drop=null;};},async send(raw){if(closed)throw Error('closed');sent.push(JSON.parse(raw));return onSend(JSON.parse(raw),value);},close(){closed=true;closes++;}};return value;
}
function driver(options={}){
 const peers=[],videos=[],states=[];let session;
 const transport=link(options.onSend||((message,source)=>{
  if(message.type==='list')queueMicrotask(()=>source.emit({type:'list',producers:[{id:'producer-1',meta:{name:'SIMULATION',api_version:44}}]}));
  if(message.type==='startSession')queueMicrotask(()=>{source.emit({type:'sessionStarted',peerId:message.peerId,sessionId:'session-1'});source.emit({type:'peer',sessionId:'session-1',ice:candidate});source.emit({type:'peer',sessionId:'session-1',sdp:{type:'offer',sdp:SDP}});});
 }));
 session=new CameraSession({link:transport.transport,makePeer:options.makePeer||((sinks)=>{const value=rig({autoMetadata:true,...options.peerOptions,sinks});peers.push(value);return value.peer;}),simulation:true,timeoutMs:options.timeoutMs??1000,durationMs:options.durationMs??1000,onVideo:value=>{videos.push(value);options.onVideo?.(value,session);},onState:value=>{states.push(value);options.onState?.(value,session);}});
 return {session,link:transport,peers,videos,states};
}
async function listed(value){value.link.emit({type:'welcome',peerId:'observer-1'});return value.session.discover();}
async function started(value){const producers=await listed(value);const snapshot=await value.session.start(producers[0].id,{confirmed:true});await tick();return snapshot;}

test('wire expectations match the pinned independent camera/GStreamer source audit',()=>{
 assert.equal(source.source_commit,'96b89d8613f06722c1d64ce75ab0d7124fed9d8f');assert.equal(source.signaling_protocol.version,'0.15.3');assert.equal(source.producer_offers_consumer_answers,true);assert.equal(source.server_creates_reliable_ordered_control,true);assert.equal(source.lan_signaling_authentication_gate,false);assert.equal(source.sole_observer_application_method,'media.video');assert.deepEqual(source.consumer_requests,['list','startSession','peer','endSession']);
 assert.equal(METADATA_REQUEST,'{"jsonrpc":"2.0","id":1,"method":"media.video","params":{}}\n');
});

test('bounded signaling parser rejects duplicates, prototypes, batches, invalid Unicode and nonfinite values',()=>{
 for(const text of ['{"type":"list","type":"peer"}','{"__proto__":{}}','[]','{}{}','{"x":1e999}','{"x":"\\ud800"}','{"x":01}','{"x":true,}'])assert.throws(()=>P.parse(text));
 assert.throws(()=>P.parse('{"x":'+'['.repeat(18)+'0'+']'.repeat(18)+'}'),code('MESSAGE_LIMIT'));
 assert.throws(()=>P.parse(' '.repeat(65537)),code('MESSAGE_LIMIT'));assert.throws(()=>P.parse('{}',Infinity),code('PARAMS'));
 assert.deepEqual(P.parse(' {"hello":[0,false,null,"caf\u00e9"]} '),{hello:[0,false,null,'caf\u00e9']});
});

test('exact signaling envelopes refuse arbitrary RPC methods and mixed SDP/ICE',()=>{
 for(const raw of [{type:'robot.move'},{type:'welcome',peerId:'a',password:'PRIVATE'},{type:'peer',sessionId:'s',sdp:{type:'offer',sdp:SDP},ice:candidate},{type:'endSession',sessionId:'s',reason:'PRIVATE'},{type:'peer',sessionId:'s',sdp:{type:'rollback',sdp:SDP}}])assert.throws(()=>P.signal(JSON.stringify(raw)));
 assert.deepEqual(P.signal('{"type":"error","details":"PRIVATE ERROR"}'),{type:'error'});
});

test('producer list is bounded, unique, sanitized, ephemeral and does not attest API or identity',()=>{
 const rows=P.signal(JSON.stringify({type:'list',producers:[{id:'a',meta:{name:'<camera>\u202ePRIVATE',api_version:'44'}},{id:'b',meta:null}]})).producers;
 assert.equal(rows[0].advertisedApiVersion,null);assert.ok(!rows[0].name.includes('\u202e'));assert.ok(Object.isFrozen(rows));assert.ok(Object.isFrozen(rows[0]));
 assert.throws(()=>P.signal(JSON.stringify({type:'list',producers:Array.from({length:33},(_,id)=>({id:String(id)}))})),code('PRODUCER_LIMIT'));
 assert.throws(()=>P.signal('{"type":"list","producers":[{"id":"a"},{"id":"a"}]}'),code('PROTOCOL'));
});

test('SDP and ICE validation bounds payloads without exposing candidates in state',()=>{
 assert.equal(P.sdp(SDP),SDP);assert.throws(()=>P.sdp('PRIVATE'),code('SDP_INVALID'));assert.throws(()=>P.sdp('v=0'+'x'.repeat(49152)),code('SDP_INVALID'));
 for(const value of [{...candidate,sdpMLineIndex:-1},{...candidate,sdpMLineIndex:null},{...candidate,sdpMLineIndex:32},{...candidate,candidate:'candidate:x\r\ny'},{...candidate,candidate:'candidate:'+'x'.repeat(4096)}])assert.throws(()=>P.ice(value),code('ICE_INVALID'));
 assert.ok(Object.isFrozen(P.ice(candidate)));
});

test('geometry has no invented upright default, calibration or imprecise clock conversion',()=>{
 const value=P.geometry({...geometry,intrinsics:{unvalidated:'ignored'}});assert.deepEqual(value,{reportedWidth:1280,reportedHeight:720,reportedRotateClockwise:90,origin:'unattested-remote'});
 for(const item of [{width:1280,height:720},{...geometry,rotate:45},{...geometry,width:0},{...geometry,height:8193},{...geometry,width:8192,height:8192},{...geometry,real_ns:'not a clock'}])assert.throws(()=>P.geometry(item));
 assert.ok(!Object.hasOwn(value,'real_ns'));assert.ok(!Object.hasOwn(value,'intrinsics'));assert.ok(Object.isFrozen(value));
});

test('browser peer is passive until answered/activated and uses no implicit ICE servers',async t=>{
 const r=rig();t.after(()=>r.peer.close());assert.deepEqual(r.config,{iceServers:[]});assert.equal(r.control.sends.length,0);assert.deepEqual(r.stages,[]);assert.throws(()=>r.peer.activate(),code('PEER_POLICY'));
 await r.peer.answer(SDP);assert.deepEqual(r.stages,['remote','answer','local']);assert.equal(r.control.sends.length,0);assert.equal(r.videos.length,0);
 assert.deepEqual(r.pc.transceivers.map(item=>item.direction),['recvonly','inactive']);assert.equal(r.audio.readyState,'ended');
 r.peer.activate();r.peer.activate();r.control.onopen?.();assert.equal(r.control.sends.length,1);assert.equal(r.control.sends[0],METADATA_REQUEST);assert.deepEqual(r.videos[0].getTracks().map(track=>track.kind),['video']);assert.equal(r.peer.snapshot().decodedFramesVerified,false);
});

test('a local sender is refused before remote negotiation and no local capture is stopped',async()=>{
 const local=new Track('video'),r=rig({localTrack:local});await assert.rejects(r.peer.answer(SDP),code('LOCAL_TRACK_DENIED'));assert.deepEqual(r.stages,[]);assert.equal(local.readyState,'live');assert.equal(r.pc.closes,1);
});

test('answer policy rejects outgoing media, audio receive, missing direction and rejected video',async()=>{
 for(const answer of [ANSWER.replace('a=recvonly','a=sendrecv'),ANSWER.replace('a=recvonly','a=sendonly'),ANSWER.replace('a=inactive','a=recvonly'),ANSWER.replace('a=recvonly\r\n',''),ANSWER.replace('a=recvonly','a=recvonly\r\na=sendonly'),ANSWER.replace('m=video 9','m=video 0')]){
  const r=rig({answer});await assert.rejects(r.peer.answer(SDP));assert.equal(r.peer.snapshot().phase,'closed');assert.equal(r.control.sends.length,0);
 }
});

test('missing video transceiver or a mixed output stream is refused',async()=>{
 const none=rig({noVideo:true});await assert.rejects(none.peer.answer(SDP),code('NO_VIDEO'));assert.equal(none.pc.closes,1);
 const mixed=rig({mixedStream:true});await assert.rejects(mixed.peer.answer(SDP),code('DISCONNECTED'));assert.equal(mixed.videos.length,0);assert.equal(mixed.pc.closes,1);
});

test('audio is excluded, duplicate video is not redelivered, and a second track closes the peer',async t=>{
 const r=rig();t.after(()=>r.peer.close());await r.peer.answer(SDP);r.peer.activate();r.pc.ontrack({track:r.video});assert.equal(r.videos.length,1);
 const extra=new Track('video');r.pc.ontrack({track:extra});assert.equal(extra.readyState,'ended');assert.equal(r.video.readyState,'ended');assert.deepEqual(r.failures,['TRACK_LIMIT']);assert.equal(r.peer.snapshot().phase,'closed');
});

test('other, unreliable and duplicate data channels are closed without a write',async t=>{
 const r=rig();t.after(()=>r.peer.close());await r.peer.answer(SDP);r.peer.activate();
 for(const options of [{label:'teleop'},{ordered:false},{maxRetransmits:0},{maxPacketLifeTime:10},{}]){const extra=channel(options);r.pc.ondatachannel({channel:extra});assert.equal(extra.closes,1);assert.deepEqual(extra.sends,[]);}
 assert.equal(r.control.sends.length,1);assert.equal(r.control.sends[0],METADATA_REQUEST);
});

test('data-channel flooding closes the owned peer within its bound',async()=>{
 const r=rig();await r.peer.answer(SDP);for(let i=0;i<8;i++)r.pc.ondatachannel?.({channel:channel({label:'other'})});assert.equal(r.peer.snapshot().phase,'closed');assert.deepEqual(r.failures,['CHANNEL_LIMIT']);assert.equal(r.control.sends.length,0);
});

test('typed metadata accepts the query/push race but omits timestamps and raw errors',async t=>{
 const r=rig();t.after(()=>r.peer.close());await r.peer.answer(SDP);r.control.onmessage({data:JSON.stringify({jsonrpc:'2.0',method:'media.video',params:geometry})});assert.deepEqual(r.metadata,[]);
 r.peer.activate();r.control.onmessage({data:JSON.stringify({jsonrpc:'2.0',id:1,result:geometry})});assert.equal(r.peer.snapshot().geometry.reportedRotateClockwise,90);assert.ok(r.metadata.length>=1);assert.ok(!JSON.stringify(r.peer.snapshot()).includes('1760000000000000000'));
});

test('missing, invalid or changing metadata becomes unknown and never guesses orientation',async t=>{
 for(const result of [{width:1280,height:720},{...geometry,rotate:45}]){const r=rig();t.after(()=>r.peer.close());await r.peer.answer(SDP);r.peer.activate();r.control.onmessage({data:JSON.stringify({jsonrpc:'2.0',id:1,result})});assert.equal(r.peer.snapshot().geometry,null);assert.equal(r.peer.snapshot().metadataError,'METADATA_INVALID');assert.equal(r.peer.snapshot().phase,'active');}
 const r=rig();t.after(()=>r.peer.close());await r.peer.answer(SDP);r.peer.activate();r.control.onmessage({data:JSON.stringify({jsonrpc:'2.0',id:1,result:geometry})});r.control.onmessage({data:JSON.stringify({jsonrpc:'2.0',method:'media.video',params:{...geometry,rotate:180}})});assert.equal(r.peer.snapshot().metadataError,'METADATA_CHANGED');assert.equal(r.peer.snapshot().geometry,null);
});

test('incoming robot commands cannot be invoked or forwarded; malformed control is bounded',async t=>{
 const r=rig();t.after(()=>r.peer.close());await r.peer.answer(SDP);r.peer.activate();
 for(let index=0;index<32;index++)r.control.onmessage?.({data:JSON.stringify({jsonrpc:'2.0',id:3,method:'robot.move',params:{PRIVATE:'never copied'}})});
 r.control.onmessage?.({data:'{}'});assert.equal(r.peer.snapshot().metadataError,'METADATA_PROTOCOL');assert.deepEqual(r.control.sends,[METADATA_REQUEST]);assert.ok(!JSON.stringify(r.peer.snapshot()).includes('PRIVATE'));
});

test('metadata errors, send failure and timeout have fixed codes without replay',async t=>{
 const r=rig();t.after(()=>r.peer.close());await r.peer.answer(SDP);r.peer.activate();r.control.onmessage({data:'{"jsonrpc":"2.0","id":1,"error":{"code":-1,"message":"PRIVATE"}}'});assert.equal(r.peer.snapshot().metadataError,'METADATA_UNAVAILABLE');assert.ok(!JSON.stringify(r.peer.snapshot()).includes('PRIVATE'));
 const failed=rig({controlWriteFailure:true});t.after(()=>failed.peer.close());await failed.peer.answer(SDP);failed.peer.activate();assert.equal(failed.peer.snapshot().metadataError,'METADATA_WRITE_FAILED');assert.equal(failed.control.sends.length,1);
 const quiet=rig({metadataTimeoutMs:5});t.after(()=>quiet.peer.close());await quiet.peer.answer(SDP);quiet.peer.activate();await new Promise(resolve=>setTimeout(resolve,15));assert.equal(quiet.peer.snapshot().metadataError,'METADATA_UNOBSERVED');assert.equal(quiet.control.sends.length,1);
});

test('a control channel rejected before activation cannot be replaced or lose its error',async t=>{
 const r=rig({metadataTimeoutMs:5});t.after(()=>r.peer.close());await r.peer.answer(SDP);
 r.control.onmessage({data:JSON.stringify({jsonrpc:'2.0',method:'media.video',params:{width:1280,height:720,rotate:45}})});
 assert.equal(r.control.closes,1);r.peer.activate();assert.equal(r.metadata.at(-1).error,'METADATA_INVALID');
 const replacement=channel();r.pc.ondatachannel({channel:replacement});assert.equal(replacement.closes,1);assert.deepEqual(replacement.sends,[]);
 await new Promise(resolve=>setTimeout(resolve,15));assert.equal(r.peer.snapshot().metadataError,'METADATA_INVALID');assert.equal(r.peer.snapshot().metadataRequestAttempts,0);
});

test('a connecting control channel sends its sole query only after open and activation',async t=>{
 const r=rig();t.after(()=>r.peer.close());r.control.readyState='connecting';await r.peer.answer(SDP);r.peer.activate();assert.deepEqual(r.control.sends,[]);
 r.control.readyState='open';r.control.onopen();r.control.onopen();assert.deepEqual(r.control.sends,[METADATA_REQUEST]);
});

test('close during a pending browser API prevents late activation, metadata and video',async()=>{
 for(const key of ['holdRemote','holdAnswer','holdLocal']){const wait=deferred(),r=rig({[key]:wait});const pending=r.peer.answer(SDP),rejected=assert.rejects(pending,code('DISCONNECTED'));await tick();r.peer.close();wait.resolve();await rejected;assert.equal(r.videos.length,0);assert.equal(r.control.sends.length,0);assert.throws(()=>r.peer.activate(),code('DISCONNECTED'));}
});

test('peer failure, ended track and callback exceptions cannot prevent cleanup',async()=>{
 const r=rig();await r.peer.answer(SDP);r.peer.activate();r.video.stop();assert.equal(r.peer.snapshot().phase,'closed');assert.deepEqual(r.failures,['TRACK_ENDED']);
 const next=rig({sinks:{onVideo(){throw Error('consumer');},onIce(){throw Error('consumer');},onMetadata(){throw Error('consumer');},onFailure(){throw Error('consumer');}}});await next.peer.answer(SDP);next.peer.activate();next.pc.connectionState='failed';next.pc.onconnectionstatechange();assert.equal(next.peer.snapshot().phase,'closed');assert.equal(next.video.readyState,'ended');
});

test('discovery is explicit, never selects the first producer, and requires a confirmed known ID',async t=>{
 const f=driver();t.after(()=>f.session.stop());assert.deepEqual(f.link.sent,[]);const pending=f.session.discover();assert.deepEqual(f.link.sent,[]);f.link.emit({type:'welcome',peerId:'observer-1'});const rows=await pending;
 assert.deepEqual(f.link.sent.map(item=>item.type),['list']);assert.equal(f.peers.length,0);await assert.rejects(f.session.start(rows[0].id),code('CONFIRMATION_REQUIRED'));await assert.rejects(f.session.start('unknown',{confirmed:true}),code('UNDISCOVERED_PRODUCER'));assert.equal(f.peers.length,0);
});

test('session uses producer offer, flushes early ICE and queues answer before local ICE',async t=>{
 const f=driver();t.after(()=>f.session.stop());const snapshot=await started(f);assert.equal(snapshot.phase,'track-received');assert.equal(snapshot.decodedFramesVerified,false);assert.equal(snapshot.identityVerified,false);assert.equal(snapshot.physicalMicroDuckTested,false);
 assert.deepEqual(f.link.sent.map(item=>item.type+(item.sdp?':'+item.sdp.type:item.ice?':ice':'')),['list','startSession','peer:answer','peer:ice']);assert.equal(f.peers[0].stages.at(-1),'ice');assert.deepEqual(f.videos[0].getTracks().map(track=>track.kind),['video']);assert.equal(f.session.snapshot().geometry.reportedWidth,1280);assert.deepEqual(f.peers[0].control.sends,[METADATA_REQUEST]);
});

test('wrong selected peer is refused without sending endSession for an unowned session',async()=>{
 const f=driver({onSend(message,source){if(message.type==='list')source.emit({type:'list',producers:[{id:'producer-1'}]});if(message.type==='startSession')source.emit({type:'sessionStarted',peerId:'other',sessionId:'FOREIGN'});}});
 const rows=await listed(f);await assert.rejects(f.session.start(rows[0].id,{confirmed:true}),code('SESSION_MISMATCH'));assert.equal(f.peers.length,0);assert.ok(!f.link.sent.some(item=>item.type==='endSession'));assert.equal(f.link.closes(),1);
});

test('foreign SDP, ICE and endSession do not enter or stop the owned peer',async t=>{
 const f=driver();t.after(()=>f.session.stop());await started(f);const before=f.session.snapshot().counters.ignored;
 for(const value of [{type:'peer',sessionId:'foreign',sdp:{type:'offer',sdp:SDP}},{type:'peer',sessionId:'foreign',ice:candidate},{type:'endSession',sessionId:'foreign'}])f.link.emit(value);
 await tick();assert.equal(f.session.snapshot().phase,'track-received');assert.equal(f.session.snapshot().counters.ignored,before+3);assert.equal(f.peers[0].stages.filter(value=>value==='remote').length,1);
});

test('an early track cannot resolve start before the final answer is queued successfully',async()=>{
 const gate=deferred(),f=driver({onSend(message,source){
  if(message.type==='list')source.emit({type:'list',producers:[{id:'producer-1'}]});
  if(message.type==='startSession'){source.emit({type:'sessionStarted',peerId:'producer-1',sessionId:'session-1'});source.emit({type:'peer',sessionId:'session-1',sdp:{type:'offer',sdp:SDP}});}
  if(message.sdp?.type==='answer')return gate.promise;
 }});
 const rows=await listed(f);const pending=f.session.start(rows[0].id,{confirmed:true});const rejected=assert.rejects(pending,code('SIGNAL_WRITE_FAILED'));await tick();assert.equal(f.videos.length,0);assert.equal(f.peers[0].control.sends.length,0);gate.reject(Error('PRIVATE write'));await rejected;assert.equal(f.videos.length,0);assert.equal(f.peers[0].video.readyState,'ended');
});

test('serialized signaling backlog and early ICE are bounded while negotiation waits',async()=>{
 const wait=deferred(),f=driver({peerOptions:{holdRemote:wait}});const rows=await listed(f);const pending=f.session.start(rows[0].id,{confirmed:true}),rejected=assert.rejects(pending,code('QUEUE_LIMIT'));await tick();
 for(let index=0;index<33;index++)f.link.emit({type:'peer',sessionId:'session-1',ice:candidate});await rejected;wait.resolve();await tick();assert.equal(f.link.closes(),1);assert.equal(f.videos.length,0);assert.ok(!JSON.stringify(f.session.snapshot()).includes('candidate:'));
});

test('local and remote ICE budgets close instead of accepting an unbounded stream',async()=>{
 for(const local of [false,true]){const f=driver();await started(f);for(let index=0;index<64&&!f.link.closed();index++){
  if(local)f.peers[0].pc.onicecandidate?.({candidate});else{f.link.emit({type:'peer',sessionId:'session-1',ice:candidate});await tick();}
 }await tick();assert.equal(f.session.snapshot().code,'ICE_LIMIT');assert.equal(f.link.closes(),1);}
});

test('discovery, negotiation and observation leases all terminate without auto-retry',async()=>{
 const empty=driver({timeoutMs:5,onSend(){}});await assert.rejects(empty.session.discover(),code('DISCOVERY_TIMEOUT'));assert.equal(empty.link.sent.length,0);
 const noTrack=driver({timeoutMs:5,peerOptions:{noTrack:true}});const rows=await listed(noTrack);await assert.rejects(noTrack.session.start(rows[0].id,{confirmed:true}),code('NEGOTIATION_TIMEOUT'));assert.equal(noTrack.link.sent.filter(item=>item.type==='startSession').length,1);
 const lease=driver({durationMs:5});await started(lease);await new Promise(resolve=>setTimeout(resolve,15));assert.equal(lease.session.snapshot().code,'SESSION_TIME_LIMIT');assert.equal(lease.link.closes(),1);assert.equal(lease.link.sent.filter(item=>item.type==='endSession').length,1);
});

test('stop rejects pending work, clears private selection, and late callbacks cannot reopen it',async()=>{
 const f=driver({onSend(){}}),pending=f.session.discover(),rejected=assert.rejects(pending,code('STOPPED'));const receive=f.link.receiver();f.session.stop();await rejected;receive?.('{"type":"welcome","peerId":"late"}');await tick();assert.equal(f.session.snapshot().phase,'closed');assert.deepEqual(f.session.snapshot().producers,[]);await assert.rejects(f.session.discover(),code('DISCONNECTED'));assert.equal(f.link.sent.length,0);assert.equal(f.link.closes(),1);
});

test('remote end and signaling loss close local resources without replay or a robot-stop claim',async()=>{
 for(const remoteEnd of [true,false]){const f=driver();await started(f);if(remoteEnd)f.link.emit({type:'endSession',sessionId:'session-1'});else f.link.drop();await tick();assert.equal(f.session.snapshot().code,remoteEnd?'REMOTE_END':'DISCONNECTED');assert.equal(f.peers[0].video.readyState,'ended');assert.equal(f.session.snapshot().geometry,null);if(remoteEnd)assert.ok(!f.link.sent.some(item=>item.type==='endSession'));}
});

test('producer removal, remote errors and malformed messages have fixed redacted outcomes',async()=>{
 const f=driver();await started(f);f.link.emit({type:'peerStatusChanged',peerId:'producer-1',roles:[]});await tick();assert.equal(f.session.snapshot().code,'PRODUCER_REMOVED');
 const other=driver();other.link.emit({type:'error',details:'PRIVATE ERROR'});await tick();assert.equal(other.session.snapshot().code,'SIGNAL_REMOTE_ERROR');assert.ok(!JSON.stringify(other.session.snapshot()).includes('PRIVATE'));
 const broken=driver();broken.link.emit('{"type":"welcome","peerId":"x","peerId":"y"}');await tick();assert.equal(broken.session.snapshot().code,'JSON_DUPLICATE');
});

test('unrestricted peer factories are refused and callback exceptions cannot suppress cleanup',async()=>{
 let closed=0;const wrong=driver({makePeer:()=>({close(){closed++;}})});const rows=await listed(wrong);await assert.rejects(wrong.session.start(rows[0].id,{confirmed:true}),code('PEER_POLICY'));assert.equal(closed,1);assert.equal(wrong.link.closes(),1);
 const f=driver({onState(){throw Error('consumer');},onVideo(){throw Error('consumer');}});await started(f);f.session.stop();assert.equal(f.link.closes(),1);assert.equal(f.peers[0].video.readyState,'ended');
});

test('a synchronous consumer stop does not resolve a successful start afterwards',async()=>{
 const f=driver({onVideo(stream,session){session.stop();}});const rows=await listed(f);await assert.rejects(f.session.start(rows[0].id,{confirmed:true}),code('STOPPED'));assert.equal(f.session.snapshot().phase,'closed');assert.equal(f.peers[0].control.sends.length,0);
});

test('the complete camera fixture uses actual modules, video-only tracks and one metadata RPC',async()=>{
 const videos=[],f=createFixture({onVideo:value=>videos.push(value)});assert.equal(f.snapshot().signalMessages,0);const rows=await f.session.discover();assert.match(rows[0].name,/SIMULATION/);await f.session.start(rows[0].id,{confirmed:true});await tick();
 assert.equal(f.session.snapshot().simulation,true);assert.equal(f.session.snapshot().decodedFramesVerified,false);assert.deepEqual(f.snapshot().controlMethods,['media.video']);assert.deepEqual(f.snapshot().transceiverDirections,['recvonly','inactive']);assert.deepEqual(videos[0].getTracks().map(track=>track.kind),['video']);assert.equal(f.snapshot().iceAdded,1);f.close();f.close();assert.equal(f.snapshot().peerCloses,1);assert.equal(f.snapshot().videoStops,1);assert.equal(f.snapshot().audioStops,1);
});

test('fixture faults never contact a real peer or fabricate physical video success',async()=>{
 for(const fault of ['discovery-timeout','wrong-session','malformed-offer','negotiation-timeout','signal-write-failure']){const f=createFixture({fault,timeoutMs:10});try{if(fault==='discovery-timeout')await assert.rejects(f.session.discover());else{const rows=await f.session.discover();await assert.rejects(f.session.start(rows[0].id,{confirmed:true}));}assert.equal(f.snapshot().physicalMicroDuckTested,false);assert.equal(f.session.snapshot().phase,'closed');assert.ok(f.snapshot().controlMethods.every(method=>method==='media.video'));}finally{f.close();}}
 const f=createFixture({fault:'metadata-invalid'});const rows=await f.session.discover();await f.session.start(rows[0].id,{confirmed:true});await tick();assert.equal(f.session.snapshot().geometry,null);assert.equal(f.session.snapshot().metadataError,'METADATA_INVALID');f.close();
});

test('fixture rejects real endpoints/providers/credentials and snapshots retain no SDP or ICE',()=>{
 for(const options of [{url:'wss://private'},{transport:{}},{peer:{}},{token:'PRIVATE'},{pin:'000000'},{RTCPeerConnection:()=>{}},{fault:'unknown'}])assert.throws(()=>createFixture(options),code('PARAMS'));
 const f=createFixture();assert.ok(!JSON.stringify(f.snapshot()).includes('candidate:'));assert.ok(!JSON.stringify(f.session.snapshot()).includes('v=0'));f.close();
});

test('browser-global fixture runs with every external network/RTC/capture API unavailable',async()=>{
 const forbidden=()=>{throw Error('External operation prohibited');};
 const context=vm.createContext({TextEncoder,setTimeout,clearTimeout,queueMicrotask,WebSocket:forbidden,RTCPeerConnection:forbidden,MediaStream:forbidden,navigator:new Proxy({},{get:forbidden})});
 for(const name of ['camera-protocol.js','camera-peer.js','camera-session.js','camera-fixture.js'])vm.runInContext(fs.readFileSync(require.resolve('../web/microduck/'+name),'utf8'),context);
 await vm.runInContext('globalThis.fixture=MicroDuckCameraFixture.createFixture(); fixture.session.discover().then(rows=>fixture.session.start(rows[0].id,{confirmed:true}))',context);await tick();
 assert.equal(vm.runInContext('fixture.snapshot().controlMethods.join(",")',context),'media.video');assert.equal(vm.runInContext('fixture.session.snapshot().decodedFramesVerified',context),false);vm.runInContext('fixture.close()',context);
});
