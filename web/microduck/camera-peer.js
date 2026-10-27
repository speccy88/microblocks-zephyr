/* SPDX-License-Identifier: MIT */
/* Owned receive-only WebRTC peer. No local capture or general control API. */
((root)=>{
 'use strict';
 const P=typeof module==='object'&&module.exports?require('./camera-protocol.js'):root.MicroDuckCameraProtocol;
 const states=new WeakMap(),METADATA_REQUEST=JSON.stringify({jsonrpc:'2.0',id:1,method:'media.video',params:{}})+'\n';
 const fail=code=>{throw new P.CameraError(code);};
 const invoke=(fn,...args)=>{try{fn(...args);}catch{}};
 const state=owner=>{const s=states.get(owner);if(!s)fail('PARAMS');return s;};
 function answerDirection(raw){
  const media=raw.split(/\r?\nm=/).slice(1);let video=0;
  for(const section of media){const fields=section.split(/\r?\n/,1)[0].split(' '),kind=fields[0];if(kind==='application')continue;if(!['video','audio'].includes(kind))fail('ANSWER_DIRECTION');const directions=[...section.matchAll(/(?:^|\r?\n)a=(sendrecv|sendonly|recvonly|inactive)(?=\r?\n|$)/g)].map(match=>match[1]);
   if(directions.length!==1||kind==='audio'&&directions[0]!=='inactive'||kind==='video'&&directions[0]!=='recvonly')fail('ANSWER_DIRECTION');if(kind==='video'&&fields[1]!=='0')video++;
  }
  if(video!==1)fail('NO_VIDEO');
 }
 function metadata(s,value){
  let next;try{next=P.geometry(value);}catch{badMetadata(s,'METADATA_INVALID');return;}
  if(s.metadata&&JSON.stringify(s.metadata)!==JSON.stringify(next)){badMetadata(s,'METADATA_CHANGED');return;}
  s.metadata=next;s.metadataError=null;clearTimeout(s.metadataTimer);if(s.active)invoke(s.onMetadata,next,null);
 }
 function badMetadata(s,code){
  if(s.closed)return;s.metadata=null;s.metadataError=code;clearTimeout(s.metadataTimer);
  const channel=s.control;s.control=null;if(channel){channel.onopen=channel.onmessage=channel.onclose=channel.onerror=null;try{channel.close();}catch{}}
  if(s.active)invoke(s.onMetadata,null,code);
 }
 function requestMetadata(s){
  const channel=s.control;if(s.closed||!s.active||s.metadataRequested||!channel||channel.readyState!=='open')return;
  s.metadataRequested=true;
  try{if(typeof channel.bufferedAmount!=='number'||channel.bufferedAmount>16384)fail('METADATA_WRITE_FAILED');channel.send(METADATA_REQUEST);}
  catch{badMetadata(s,'METADATA_WRITE_FAILED');}
 }
 class BrowserPeer{
  constructor({RTCPeerConnection=root.RTCPeerConnection,MediaStream=root.MediaStream,onVideo=()=>{},onIce=()=>{},onMetadata=()=>{},onFailure=()=>{},metadataTimeoutMs=5000}={}){
   if(typeof RTCPeerConnection!=='function'||typeof MediaStream!=='function'||[onVideo,onIce,onMetadata,onFailure].some(fn=>typeof fn!=='function')||!Number.isInteger(metadataTimeoutMs)||metadataTimeoutMs<1||metadataTimeoutMs>30000)fail('PARAMS');
   const pc=new RTCPeerConnection({iceServers:[]});
   if(['setRemoteDescription','createAnswer','setLocalDescription','addIceCandidate','getTransceivers','getSenders','getReceivers','close'].some(key=>typeof pc[key]!=='function')){try{pc.close();}catch{}fail('PEER_POLICY');}
   const s={pc,MediaStream,onVideo,onIce,onMetadata,onFailure,metadataTimeoutMs,closed:false,answering:false,answered:false,active:false,track:null,stream:null,endTrack:null,control:null,controlSeen:false,channels:0,controlMessages:0,metadataRequested:false,metadata:null,metadataError:null,metadataTimer:null};states.set(this,s);
   const stopWith=code=>{if(s.closed)return;this.close();invoke(onFailure,code);};
   pc.onicecandidate=event=>{if(!s.closed&&event?.candidate){try{invoke(onIce,P.ice({candidate:event.candidate.candidate,sdpMLineIndex:event.candidate.sdpMLineIndex}));}catch{stopWith('ICE_INVALID');}}};
   pc.onconnectionstatechange=()=>{if(!s.closed&&['failed','closed','disconnected'].includes(pc.connectionState))stopWith('PEER_FAILED');};
   pc.ontrack=event=>{
    const track=event?.track;if(!track)return;
    if(s.closed||track.kind!=='video'){try{track.stop();}catch{}return;}
    if(s.track&&s.track!==track){try{track.stop();}catch{}stopWith('TRACK_LIMIT');return;}
    if(s.track===track)return;
    try{
     if(track.readyState!=='live'||typeof track.stop!=='function')fail('NO_VIDEO');
     const stream=new MediaStream([track]);if(typeof stream.getTracks!=='function'||stream.getTracks().length!==1||stream.getTracks()[0]!==track)fail('PEER_POLICY');
     s.track=track;s.stream=stream;s.endTrack=()=>stopWith('TRACK_ENDED');track.addEventListener?.('ended',s.endTrack,{once:true});if(s.active)invoke(onVideo,stream);
    }catch{try{track.stop();}catch{}stopWith('PEER_POLICY');}
   };
   pc.ondatachannel=event=>{
    const channel=event?.channel;if(!channel)return;
    if(s.closed){try{channel.close();}catch{}return;}
    if(++s.channels>P.LIMITS.channels){try{channel.close();}catch{}stopWith('CHANNEL_LIMIT');return;}
    if(channel.label!=='control'||s.controlSeen||channel.ordered!==true||channel.maxRetransmits!==null||channel.maxPacketLifeTime!==null||typeof channel.send!=='function'||typeof channel.close!=='function'){try{channel.close();}catch{}return;}
    s.control=channel;s.controlSeen=true;
    channel.onopen=()=>requestMetadata(s);
    channel.onclose=()=>{if(s.control===channel&&!s.closed)badMetadata(s,'METADATA_UNOBSERVED');};
    channel.onerror=()=>{if(s.control===channel&&!s.closed)badMetadata(s,'METADATA_PROTOCOL');};
    channel.onmessage=event=>{
     if(s.closed||s.control!==channel)return;
     try{
      if(++s.controlMessages>P.LIMITS.controlMessages)fail('MESSAGE_LIMIT');const message=P.parse(event.data,16384);if(message.jsonrpc!=='2.0')fail('PROTOCOL');
      if(!Object.hasOwn(message,'id')&&message.method==='media.video'&&!Object.hasOwn(message,'result')&&!Object.hasOwn(message,'error'))metadata(s,message.params);
      else if(message.id===1&&!Object.hasOwn(message,'method')){
       if(Object.hasOwn(message,'result')===Object.hasOwn(message,'error'))fail('PROTOCOL');
       if(Object.hasOwn(message,'error'))badMetadata(s,'METADATA_UNAVAILABLE');else metadata(s,message.result);
      }
     }catch{badMetadata(s,'METADATA_PROTOCOL');}
    };
    requestMetadata(s);
   };
  }
  async answer(offer){
   const s=state(this);if(s.closed)fail('DISCONNECTED');if(s.answering||s.answered)fail('BUSY');P.sdp(offer);s.answering=true;
   const current=()=>{if(s.closed)fail('DISCONNECTED');};
   try{
    if(s.pc.getSenders().some(sender=>sender.track))fail('LOCAL_TRACK_DENIED');
    await s.pc.setRemoteDescription({type:'offer',sdp:offer});current();
    const transceivers=s.pc.getTransceivers();if(!Array.isArray(transceivers)||transceivers.length>8)fail('PEER_POLICY');let videos=0;
    for(const item of transceivers){if(item.receiver?.track?.kind==='video'){item.direction='recvonly';videos++;}else{item.direction='inactive';try{item.receiver?.track?.stop();}catch{}}}
    if(videos!==1)fail('NO_VIDEO');if(s.pc.getSenders().some(sender=>sender.track))fail('LOCAL_TRACK_DENIED');
    const answer=await s.pc.createAnswer();current();if(answer?.type!=='answer')fail('SDP_DIRECTION');P.sdp(answer.sdp);answerDirection(answer.sdp);
    await s.pc.setLocalDescription({type:'answer',sdp:answer.sdp});current();s.answered=true;return Object.freeze({type:'answer',sdp:answer.sdp});
   }catch(error){const code=P.safeCode(error);this.close();throw new P.CameraError(code==='INTERNAL'?'PEER_FAILED':code);}
  }
  async addIce(candidate){const s=state(this);if(s.closed)fail('DISCONNECTED');P.ice(candidate);try{await s.pc.addIceCandidate(candidate);if(s.closed)fail('DISCONNECTED');}catch{this.close();fail('ICE_INVALID');}}
  activate(){
   const s=state(this);if(s.closed)fail('DISCONNECTED');if(!s.answered)fail('PEER_POLICY');if(s.active)return;s.active=true;
   if(s.metadata||s.metadataError)invoke(s.onMetadata,s.metadata,s.metadataError);
   else{s.metadataTimer=setTimeout(()=>{if(!s.closed&&!s.metadata){s.metadataError='METADATA_UNOBSERVED';invoke(s.onMetadata,null,s.metadataError);}},s.metadataTimeoutMs);}
   if(s.stream)invoke(s.onVideo,s.stream);requestMetadata(s);
  }
  snapshot(){const s=state(this);return Object.freeze({phase:s.closed?'closed':s.active?'active':s.answered?'answered':s.answering?'answering':'created',videoTrackReceived:!!s.track,geometry:s.metadata,metadataError:s.metadataError,metadataRequestAttempts:s.metadataRequested?1:0,channelsObserved:s.channels,controlMessages:s.controlMessages,decodedFramesVerified:false});}
  close(){
   const s=state(this);if(s.closed)return;s.closed=true;clearTimeout(s.metadataTimer);s.pc.onicecandidate=s.pc.ontrack=s.pc.ondatachannel=s.pc.onconnectionstatechange=null;
   if(s.control){s.control.onopen=s.control.onclose=s.control.onmessage=s.control.onerror=null;try{s.control.close();}catch{}s.control=null;}
   if(s.track&&s.endTrack)s.track.removeEventListener?.('ended',s.endTrack);
   const tracks=new Set([s.track]);try{for(const receiver of s.pc.getReceivers())tracks.add(receiver.track);}catch{}
   for(const track of tracks)try{track?.stop();}catch{}s.track=s.stream=null;s.metadata=null;
   try{s.pc.close();}catch{}
  }
 }
 const api=Object.freeze({BrowserPeer,METADATA_REQUEST});if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckCameraPeer=api;
})(typeof globalThis==='object'?globalThis:this);
