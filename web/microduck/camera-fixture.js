/* SPDX-License-Identifier: MIT */
/* In-memory GStreamer-shaped camera fixture. No networking, capture or real RTC. */
((root)=>{
 'use strict';
 const common=typeof module==='object'&&module.exports;
 const P=common?require('./camera-protocol.js'):root.MicroDuckCameraProtocol;
 const {BrowserPeer}=common?require('./camera-peer.js'):root.MicroDuckCameraPeer;
 const {CameraSession}=common?require('./camera-session.js'):root.MicroDuckCameraSession;
 const OFFER='v=0\r\no=- 0 0 IN IP4 0.0.0.0\r\ns=SIMULATION-NOT-REAL-RTC\r\nt=0 0\r\nm=video 9 UDP/TLS/RTP/SAVPF 96\r\na=sendonly\r\nm=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=sendonly\r\nm=application 9 UDP/DTLS/SCTP webrtc-datachannel\r\n';
 const ANSWER=OFFER.replaceAll('a=sendonly','a=recvonly').replace('m=audio 9 UDP/TLS/RTP/SAVPF 111\r\na=recvonly','m=audio 0 UDP/TLS/RTP/SAVPF 111\r\na=inactive');
 const FAULTS=new Set(['discovery-timeout','wrong-session','malformed-offer','negotiation-timeout','metadata-invalid','signal-write-failure']);
 const PRODUCER='simulation-camera-1',SESSION='simulation-session-1';
 const fail=code=>{throw new P.CameraError(code);};
 function createFixture(options={}){
  if(!options||Object.getPrototypeOf(options)!==Object.prototype||Object.keys(options).some(key=>!['timeoutMs','durationMs','fault','onVideo','onState'].includes(key)))fail('PARAMS');
  const {timeoutMs=1000,durationMs=60000,fault=null,onVideo=()=>{},onState=()=>{}}=options;
  if(fault!==null&&!FAULTS.has(fault))fail('PARAMS');
  let receive=null,dropped=null,closed=false,pc=null;
  const stats={simulation:true,signalMessages:0,signalKinds:[],controlRequests:0,controlMethods:[],peerConstructions:0,remoteOffers:0,localAnswers:0,iceAdded:0,videoStops:0,audioStops:0,channelCloses:0,peerCloses:0};
  const remember=(list,value)=>{list.push(value);if(list.length>32)list.shift();};
  const deliver=value=>{queueMicrotask(()=>{if(!closed)receive?.(typeof value==='string'?value:JSON.stringify(value));});};
  class Track{
   constructor(kind){this.kind=kind;this.readyState='live';this.listeners=new Set();}
   addEventListener(name,fn){if(name==='ended')this.listeners.add(fn);}
   removeEventListener(name,fn){if(name==='ended')this.listeners.delete(fn);}
   stop(){if(this.readyState==='ended')return;this.readyState='ended';stats[this.kind==='video'?'videoStops':'audioStops']++;for(const fn of [...this.listeners])fn();}
  }
  class Stream{constructor(tracks){this.tracks=[...tracks];}getTracks(){return [...this.tracks];}}
  function channel(){return {label:'control',ordered:true,maxRetransmits:null,maxPacketLifeTime:null,readyState:'open',bufferedAmount:0,onopen:null,onmessage:null,onclose:null,onerror:null,
   send(raw){
    stats.controlRequests++;const message=P.parse(raw,16384);remember(stats.controlMethods,message.method);
    if(raw!==JSON.stringify({jsonrpc:'2.0',id:1,method:'media.video',params:{}})+'\n')fail('SIGNAL_METHOD_DENIED');
    const target=this;queueMicrotask(()=>{if(!closed&&target.readyState==='open')target.onmessage?.({data:JSON.stringify({jsonrpc:'2.0',id:1,result:{width:1280,height:720,rotate:fault==='metadata-invalid'?45:90,mono_ns:1000000,real_ns:1760000000000000000}})});});
   },close(){if(this.readyState==='closed')return;this.readyState='closed';stats.channelCloses++;this.onclose?.();}
  };}
  class Peer{
   constructor(config){if(JSON.stringify(config)!=='{"iceServers":[]}')fail('PEER_POLICY');stats.peerConstructions++;pc=this;this.video=new Track('video');this.audio=new Track('audio');this.transceivers=[{receiver:{track:this.video},direction:'sendrecv'},{receiver:{track:this.audio},direction:'sendrecv'}];this.connectionState='new';this.closed=false;this.pendingReject=null;}
   getSenders(){return [];}
   getReceivers(){return this.transceivers.map(item=>item.receiver);}
   getTransceivers(){return this.transceivers;}
   async setRemoteDescription(offer){
    if(offer.type!=='offer')fail('SDP_DIRECTION');stats.remoteOffers++;this.remoteDescription=offer;
    this.ontrack?.({track:this.audio,streams:[new Stream([this.audio,this.video])]});
    this.ontrack?.({track:this.video,streams:[new Stream([this.audio,this.video])]});
    this.ondatachannel?.({channel:channel()});await Promise.resolve();
   }
   async createAnswer(){return {type:'answer',sdp:ANSWER};}
   async setLocalDescription(answer){
    stats.localAnswers++;this.localDescription=answer;this.onicecandidate?.({candidate:{candidate:'candidate:SIMULATION-LOCAL',sdpMLineIndex:0}});
    if(fault==='negotiation-timeout')await new Promise((resolve,reject)=>{this.pendingReject=reject;});
   }
   async addIceCandidate(){if(!this.remoteDescription)fail('ICE_INVALID');stats.iceAdded++;}
   close(){if(this.closed)return;this.closed=true;this.connectionState='closed';stats.peerCloses++;this.pendingReject?.(new Error('SIMULATION close'));this.pendingReject=null;}
  }
  const link=Object.freeze({
   subscribe(onMessage,onDrop){receive=onMessage;dropped=onDrop;deliver({type:'welcome',peerId:'simulation-observer-1'});return ()=>{receive=null;dropped=null;};},
   async send(raw){
    if(closed)fail('DISCONNECTED');if(++stats.signalMessages>128)fail('MESSAGE_LIMIT');const message=P.parse(raw);remember(stats.signalKinds,message.type+(message.sdp?':'+message.sdp.type:message.ice?':ice':''));
    if(message.type==='list'){
     if(fault!=='discovery-timeout')deliver({type:'list',producers:[{id:PRODUCER,meta:{name:'SIMULATION CAMERA / NO REAL VIDEO',api_version:44}}]});return;
    }
    if(message.type==='startSession'){
     if(fault==='signal-write-failure')throw new Error('SIMULATION write failure');
     if(message.peerId!==PRODUCER||Object.hasOwn(message,'offer'))fail('PROTOCOL');
     deliver({type:'sessionStarted',peerId:fault==='wrong-session'?'simulation-other':PRODUCER,sessionId:SESSION});
     deliver({type:'peer',sessionId:SESSION,ice:{candidate:'candidate:SIMULATION-REMOTE',sdpMLineIndex:0}});
     deliver({type:'peer',sessionId:SESSION,sdp:{type:'offer',sdp:fault==='malformed-offer'?'NOT SDP':OFFER}});return;
    }
    if(message.type==='peer'){if(message.sessionId!==SESSION||(!message.ice&&message.sdp?.type!=='answer'))fail('PROTOCOL');return;}
    if(message.type==='endSession'){if(message.sessionId!==SESSION)fail('SESSION_MISMATCH');return;}
    fail('SIGNAL_METHOD_DENIED');
   },
   close(){closed=true;receive=dropped=null;}
  });
  const session=new CameraSession({link,makePeer:sinks=>new BrowserPeer({...sinks,RTCPeerConnection:Peer,MediaStream:Stream,metadataTimeoutMs:timeoutMs}),simulation:true,timeoutMs,durationMs,onVideo,onState});
  return Object.freeze({session,simulation:true,snapshot(){return JSON.parse(JSON.stringify({...stats,closed,transceiverDirections:pc?.transceivers.map(item=>item.direction)||[],decodedFramesVerified:false,physicalMicroDuckTested:false}));},close(){session.stop();}});
 }
 const api=Object.freeze({createFixture});if(common)module.exports=api;else root.MicroDuckCameraFixture=api;
})(typeof globalThis==='object'?globalThis:this);
