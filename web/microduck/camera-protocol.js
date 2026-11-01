/* SPDX-License-Identifier: MIT */
/* Pinned GStreamer0.15.3 signaling and MicroDuck API44 camera-only metadata. */
((root)=>{
 'use strict';
 const LIMITS=Object.freeze({message:65536,sdp:49152,candidate:4096,producers:32,queue:32,candidates:64,channels:8,controlMessages:32});
 class CameraError extends Error{constructor(code){super(code);this.name='CameraError';this.code=code;}}
 const fail=code=>{throw new CameraError(code);};
 const CODES=new Set('PARAMS PROTOCOL MESSAGE_LIMIT JSON_DUPLICATE SDP_INVALID ICE_INVALID PRODUCER_LIMIT SIGNAL_METHOD_DENIED DISCONNECTED BUSY CONFIRMATION_REQUIRED UNDISCOVERED_PRODUCER PEER_POLICY LOCAL_TRACK_DENIED NO_VIDEO TRACK_LIMIT TRACK_ENDED PEER_FAILED ANSWER_DIRECTION CHANNEL_LIMIT METADATA_INVALID METADATA_UNOBSERVED METADATA_PROTOCOL METADATA_WRITE_FAILED METADATA_CHANGED METADATA_UNAVAILABLE SIGNAL_REMOTE_ERROR SIGNAL_WRITE_FAILED SESSION_MISMATCH QUEUE_LIMIT ICE_LIMIT DISCOVERY_TIMEOUT NEGOTIATION_TIMEOUT SESSION_TIME_LIMIT STOPPED PRODUCER_REMOVED REMOTE_END SDP_DIRECTION INTERNAL'.split(' '));
 const safeCode=error=>CODES.has(error?.code)?error.code:'INTERNAL';
 const plain=value=>value&&Object.getPrototypeOf(value)===Object.prototype;
 const keys=(value,allowed,required=[])=>{if(!plain(value)||Object.keys(value).some(key=>!allowed.includes(key))||required.some(key=>!Object.hasOwn(value,key)))fail('PROTOCOL');};
 const unicode=text=>{for(let at=0;at<text.length;at++){const n=text.charCodeAt(at);if(n>=0xd800&&n<=0xdbff){const next=text.charCodeAt(++at);if(!(next>=0xdc00&&next<=0xdfff))fail('PROTOCOL');}else if(n>=0xdc00&&n<=0xdfff)fail('PROTOCOL');}return text;};
 const size=text=>new TextEncoder().encode(text).length;
 function parse(raw,limit=LIMITS.message){
  if(!Number.isInteger(limit)||limit<1||limit>LIMITS.message)fail('PARAMS');
  if(typeof raw!=='string')fail('PROTOCOL');if(size(raw)>limit)fail('MESSAGE_LIMIT');
  let at=0,nodes=0;
  const ws=()=>{while(/[\x20\t\r\n]/.test(raw[at]||'!'))at++;};
  function string(){const begin=at++;let escaped=false;while(at<raw.length){const c=raw[at++];if(!escaped&&c==='"'){try{return unicode(JSON.parse(raw.slice(begin,at)));}catch(error){if(error instanceof CameraError)throw error;fail('PROTOCOL');}}if(!escaped&&c==='\\')escaped=true;else escaped=false;}fail('PROTOCOL');}
  function value(depth){
   ws();if(depth>16||++nodes>2048)fail('MESSAGE_LIMIT');const c=raw[at];
   if(c==='"')return string();
   if(c==='{'){
    ++at;ws();const object={},seen=new Set();if(raw[at]==='}'){++at;return object;}
    do{ws();if(raw[at]!=='"')fail('PROTOCOL');const key=string();if(seen.has(key))fail('JSON_DUPLICATE');if(seen.size>=128)fail('MESSAGE_LIMIT');if(['__proto__','prototype','constructor'].includes(key))fail('PROTOCOL');seen.add(key);ws();if(raw[at++]!==':')fail('PROTOCOL');Object.defineProperty(object,key,{value:value(depth+1),enumerable:true});ws();if(raw[at]==='}'){++at;return object;}if(raw[at++]!==',')fail('PROTOCOL');}while(at<raw.length);fail('PROTOCOL');
   }
   if(c==='['){++at;ws();const array=[];if(raw[at]===']'){++at;return array;}do{if(array.length>=128)fail('MESSAGE_LIMIT');array.push(value(depth+1));ws();if(raw[at]===']'){++at;return array;}if(raw[at++]!==',')fail('PROTOCOL');}while(at<raw.length);fail('PROTOCOL');}
   for(const [token,result]of [['true',true],['false',false],['null',null]])if(raw.startsWith(token,at)){at+=token.length;return result;}
   const number=/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(raw.slice(at));if(!number)fail('PROTOCOL');at+=number[0].length;const result=Number(number[0]);if(!Number.isFinite(result))fail('PROTOCOL');return result;
  }
  const output=value(0);ws();if(at!==raw.length||!plain(output))fail('PROTOCOL');return output;
 }
 function id(value){if(typeof value!=='string'||value.length<1||value.length>128||!/^[A-Za-z0-9_.:-]+$/.test(value))fail('PROTOCOL');return value;}
 function sdp(value){if(typeof value!=='string'||!value.startsWith('v=0')||value.includes('\0')||size(value)>LIMITS.sdp)fail('SDP_INVALID');return unicode(value);}
 function ice(value){keys(value,['candidate','sdpMLineIndex'],['candidate','sdpMLineIndex']);if(typeof value.candidate!=='string'||!value.candidate.startsWith('candidate:')||/[\r\n\0]/.test(value.candidate)||size(value.candidate)>LIMITS.candidate||!Number.isInteger(value.sdpMLineIndex)||value.sdpMLineIndex<0||value.sdpMLineIndex>31)fail('ICE_INVALID');return Object.freeze({candidate:unicode(value.candidate),sdpMLineIndex:value.sdpMLineIndex});}
 function producers(value){
  if(!Array.isArray(value)||value.length>LIMITS.producers)fail('PRODUCER_LIMIT');const seen=new Set();
  return Object.freeze(value.map(peer=>{keys(peer,['id','meta'],['id']);const peerId=id(peer.id);if(seen.has(peerId))fail('PROTOCOL');seen.add(peerId);const meta=plain(peer.meta)?peer.meta:{};
   const name=typeof meta.name==='string'?meta.name.replace(/[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g,' ').slice(0,64):'Unnamed producer';
   return Object.freeze({id:peerId,name,advertisedApiVersion:Number.isInteger(meta.api_version)&&meta.api_version>=1&&meta.api_version<=255?meta.api_version:null});
  }));
 }
 function signal(raw){
  const m=parse(raw);
  switch(m.type){
   case 'welcome':keys(m,['type','peerId'],['peerId']);return {type:m.type,peerId:id(m.peerId)};
   case 'list':keys(m,['type','producers'],['producers']);return {type:m.type,producers:producers(m.producers)};
   case 'sessionStarted':keys(m,['type','peerId','sessionId'],['peerId','sessionId']);return {type:m.type,peerId:id(m.peerId),sessionId:id(m.sessionId)};
   case 'endSession':keys(m,['type','sessionId'],['sessionId']);return {type:m.type,sessionId:id(m.sessionId)};
   case 'peer':{
    keys(m,['type','sessionId','sdp','ice'],['sessionId']);id(m.sessionId);if(Object.hasOwn(m,'sdp')===Object.hasOwn(m,'ice'))fail('PROTOCOL');
    if(m.sdp){keys(m.sdp,['type','sdp'],['type','sdp']);if(!['offer','answer'].includes(m.sdp.type))fail('SDP_INVALID');return {type:m.type,sessionId:m.sessionId,sdp:{type:m.sdp.type,sdp:sdp(m.sdp.sdp)}};}
    return {type:m.type,sessionId:m.sessionId,ice:ice(m.ice)};
   }
   case 'peerStatusChanged':keys(m,['type','peerId','roles','meta'],['roles']);if(!Array.isArray(m.roles)||m.roles.length>3||m.roles.some(role=>!['producer','listener','consumer'].includes(role)))fail('PROTOCOL');return {type:m.type,peerId:m.peerId==null?null:id(m.peerId),roles:[...m.roles]};
   case 'error':keys(m,['type','details'],['details']);if(typeof m.details!=='string')fail('PROTOCOL');return {type:'error'}; // Never expose remote error text.
   default:fail('SIGNAL_METHOD_DENIED');
  }
 }
 function geometry(value){
  keys(value,['width','height','rotate','mono_ns','real_ns','intrinsics'],['width','height','rotate']);
  if(!Number.isInteger(value.width)||!Number.isInteger(value.height)||value.width<1||value.height<1||value.width>8192||value.height>8192||value.width*value.height>16777216||![0,90,180,270].includes(value.rotate))fail('METADATA_INVALID');
  for(const key of ['mono_ns','real_ns'])if(Object.hasOwn(value,key)&&(!Number.isInteger(value[key])||value[key]<0))fail('METADATA_INVALID');
  return Object.freeze({reportedWidth:value.width,reportedHeight:value.height,reportedRotateClockwise:value.rotate,origin:'unattested-remote'});
 }
 function encode(value){const output=JSON.stringify(value);if(size(output)>LIMITS.message)fail('MESSAGE_LIMIT');return output;}
 const api=Object.freeze({CameraError,LIMITS,parse,id,sdp,ice,signal,geometry,encode,safeCode});if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckCameraProtocol=api;
})(typeof globalThis==='object'?globalThis:this);
