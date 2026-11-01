/* SPDX-License-Identifier: MIT */
/* Explicit source-shaped camera signaling; accepts an existing link, never dials. */
((root)=>{
 'use strict';
 const common=typeof module==='object'&&module.exports;
 const P=common?require('./camera-protocol.js'):root.MicroDuckCameraProtocol;
 const {BrowserPeer}=common?require('./camera-peer.js'):root.MicroDuckCameraPeer;
 const states=new WeakMap(),fail=code=>{throw new P.CameraError(code);};
 const invoke=(fn,...args)=>{try{fn(...args);}catch{}};
 const state=owner=>{const value=states.get(owner);if(!value)fail('PARAMS');return value;};
 const promise=()=>{const pending={};pending.promise=new Promise((resolve,reject)=>{pending.resolve=resolve;pending.reject=reject;});return pending;};
 class CameraSession{
  constructor({link,makePeer,onVideo=()=>{},onState=()=>{},simulation=false,timeoutMs=10000,durationMs=60000}={}){
   if(!link||['subscribe','send','close'].some(name=>typeof link[name]!=='function')||typeof makePeer!=='function'||typeof onVideo!=='function'||typeof onState!=='function'||typeof simulation!=='boolean'||!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>30000||!Number.isInteger(durationMs)||durationMs<1||durationMs>300000)fail('PARAMS');
   const s={link,makePeer,onVideo,onState,simulation,timeoutMs,durationMs,phase:'attached',closed:false,welcome:false,producers:Object.freeze([]),selected:null,sessionId:null,peer:null,discover:null,start:null,listSent:false,offerSeen:false,answerSent:false,negotiationReady:false,videoSeen:false,stream:null,delivered:false,geometry:null,metadataError:null,timer:null,lease:null,detach:null,queue:[],working:false,remoteIce:[],localIce:[],code:null,endAttempted:false,counters:{received:0,sent:0,ignored:0,localIce:0,remoteIce:0}};states.set(this,s);
   try{s.detach=link.subscribe(raw=>this.#receive(raw),()=>this.#end('DISCONNECTED'));if(s.detach!==undefined&&typeof s.detach!=='function')fail('PARAMS');}
   catch{this.#end('DISCONNECTED');fail('DISCONNECTED');}
  }
  snapshot(){
   const s=state(this);return Object.freeze({phase:s.phase,simulation:s.simulation,producers:s.producers,selected:s.selected,geometry:s.geometry,metadataError:s.metadataError,videoTrackReceived:s.videoSeen,decodedFramesVerified:false,expectedApiVersion:44,identityVerified:false,physicalMicroDuckTested:false,code:s.code,endSessionAttempted:s.endAttempted,counters:Object.freeze({...s.counters}),limits:Object.freeze({timeoutMs:s.timeoutMs,durationMs:s.durationMs,messages:256,queue:P.LIMITS.queue,candidates:P.LIMITS.candidates})});
  }
  #notify(){const s=state(this);invoke(s.onState,this.snapshot());}
  #arm(code){const s=state(this);clearTimeout(s.timer);s.timer=setTimeout(()=>this.#end(code),s.timeoutMs);}
  async #send(message){
   const s=state(this);if(s.closed)fail('DISCONNECTED');if(++s.counters.sent>256)fail('MESSAGE_LIMIT');
   try{await s.link.send(P.encode(message));if(s.closed)fail('DISCONNECTED');}
   catch{if(!s.closed)this.#end('SIGNAL_WRITE_FAILED');fail(s.closed&&s.code!=='SIGNAL_WRITE_FAILED'?'DISCONNECTED':'SIGNAL_WRITE_FAILED');}
  }
  discover(){
   const s=state(this);try{
    if(s.closed)fail('DISCONNECTED');if(s.discover||s.start||s.peer||s.selected)fail('BUSY');
    s.discover=promise();s.phase='discovering';s.listSent=false;this.#arm('DISCOVERY_TIMEOUT');const pending=s.discover.promise;this.#notify();
    if(s.welcome){s.listSent=true;void this.#send({type:'list'}).catch(()=>{});}return pending;
   }catch(error){return Promise.reject(error);}
  }
  start(producerId,options={}){
   const s=state(this);try{
    if(s.closed)fail('DISCONNECTED');if(s.discover||s.start||s.peer||s.selected)fail('BUSY');
    if(!options||Object.getPrototypeOf(options)!==Object.prototype||Object.keys(options).some(name=>name!=='confirmed')||options.confirmed!==true)fail('CONFIRMATION_REQUIRED');
    const selected=s.producers.find(item=>item.id===producerId);if(!selected)fail('UNDISCOVERED_PRODUCER');
    s.selected=selected;s.start=promise();s.phase='starting';const pending=s.start.promise;this.#arm('NEGOTIATION_TIMEOUT');this.#notify();void this.#send({type:'startSession',peerId:selected.id}).catch(()=>{});return pending;
   }catch(error){return Promise.reject(error);}
  }
  #receive(raw){
   const s=state(this);if(s.closed)return;
   try{if(++s.counters.received>256)fail('MESSAGE_LIMIT');const message=P.signal(raw);if(s.queue.length>=P.LIMITS.queue)fail('QUEUE_LIMIT');s.queue.push(message);if(!s.working)void this.#drain();}
   catch(error){this.#end(P.safeCode(error));}
  }
  async #drain(){
   const s=state(this);s.working=true;
   try{while(!s.closed&&s.queue.length)await this.#handle(s.queue.shift());}
   catch(error){if(!s.closed)this.#end(P.safeCode(error));}
   finally{s.working=false;}
  }
  #ready(){
   const s=state(this);if(s.closed||!s.start||!s.answerSent||!s.negotiationReady||!s.videoSeen)return;
   clearTimeout(s.timer);s.phase='track-received';s.lease=setTimeout(()=>this.#end('SESSION_TIME_LIMIT'),s.durationMs);const pending=s.start;s.start=null;
   if(!s.delivered&&s.stream){s.delivered=true;invoke(s.onVideo,s.stream);}this.#notify();if(s.closed)pending.reject(new P.CameraError(s.code));else pending.resolve(this.snapshot());
  }
  async #handle(message){
   const s=state(this);if(s.closed)return;
   switch(message.type){
    case 'welcome':
     if(s.welcome)fail('PROTOCOL');s.welcome=true;
     if(s.discover&&!s.listSent){s.listSent=true;await this.#send({type:'list'});}return;
    case 'list':
     if(!s.discover||!s.listSent){s.counters.ignored++;return;}
     s.producers=message.producers;s.phase='listed';clearTimeout(s.timer);{const pending=s.discover;s.discover=null;pending.resolve(s.producers);}this.#notify();return;
    case 'peerStatusChanged':
     if(message.peerId&&!message.roles.includes('producer')){
      s.producers=Object.freeze(s.producers.filter(item=>item.id!==message.peerId));
      if(s.selected?.id===message.peerId)this.#end('PRODUCER_REMOVED');else this.#notify();
     }return;
    case 'sessionStarted':{
     if(!s.start||s.sessionId||message.peerId!==s.selected?.id)fail('SESSION_MISMATCH');s.sessionId=message.sessionId;s.phase='negotiating';
     const peer=s.makePeer({
      onVideo:stream=>{if(s.closed){try{for(const track of stream.getTracks())track.stop();}catch{}return;}if(s.stream&&s.stream!==stream){this.#end('TRACK_LIMIT');return;}s.stream=stream;s.videoSeen=true;this.#ready();},
      onMetadata:(geometry,code)=>{if(s.closed)return;s.geometry=geometry;s.metadataError=code;this.#notify();},
      onFailure:code=>{if(!s.closed)this.#end(P.safeCode({code}));},
      onIce:candidate=>{
       if(s.closed)return;
       try{const ice=P.ice(candidate);if(++s.counters.localIce>P.LIMITS.candidates)fail('ICE_LIMIT');
        if(!s.answerSent){if(s.localIce.length>=P.LIMITS.queue)fail('ICE_LIMIT');s.localIce.push(ice);}
        else void this.#send({type:'peer',sessionId:s.sessionId,ice}).catch(()=>{});
       }catch(error){this.#end(P.safeCode(error));}
      }
     });
     if(!(peer instanceof BrowserPeer)){try{peer?.close();}catch{}fail('PEER_POLICY');}
     if(s.closed){peer.close();return;}s.peer=peer;this.#notify();return;
    }
    case 'peer':{
     if(!s.sessionId||message.sessionId!==s.sessionId){s.counters.ignored++;return;}
     if(!s.peer)fail('SESSION_MISMATCH');
     if(message.sdp){
      if(message.sdp.type!=='offer')fail('SDP_DIRECTION');if(s.offerSeen)fail('PROTOCOL');s.offerSeen=true;
      const answer=await s.peer.answer(message.sdp.sdp);if(s.closed)return;
      await this.#send({type:'peer',sessionId:s.sessionId,sdp:answer});if(s.closed)return;s.answerSent=true;
      for(const ice of s.remoteIce){await s.peer.addIce(ice);if(s.closed)return;}s.remoteIce=[];
      for(const ice of s.localIce){await this.#send({type:'peer',sessionId:s.sessionId,ice});if(s.closed)return;}s.localIce=[];
      s.negotiationReady=true;s.peer.activate();this.#ready();return;
     }
     if(++s.counters.remoteIce>P.LIMITS.candidates)fail('ICE_LIMIT');
     if(!s.offerSeen){if(s.remoteIce.length>=P.LIMITS.queue)fail('ICE_LIMIT');s.remoteIce.push(message.ice);}
     else await s.peer.addIce(message.ice);return;
    }
    case 'endSession':
     if(message.sessionId===s.sessionId)this.#end('REMOTE_END',false);else s.counters.ignored++;return;
    case 'error':this.#end('SIGNAL_REMOTE_ERROR');return;
    default:fail('SIGNAL_METHOD_DENIED');
   }
  }
  #end(code,sendEnd=true){
   const s=state(this);if(s.closed)return;s.closed=true;s.code=code;s.phase='closed';clearTimeout(s.timer);clearTimeout(s.lease);
   if(sendEnd&&s.sessionId&&!s.endAttempted){s.endAttempted=true;try{const pending=s.link.send(P.encode({type:'endSession',sessionId:s.sessionId}));if(pending&&typeof pending.catch==='function')void pending.catch(()=>{});}catch{}}
   for(const pending of [s.discover,s.start])pending?.reject(new P.CameraError(code));s.discover=s.start=null;
   try{s.detach?.();}catch{}s.detach=null;try{s.peer?.close();}catch{}s.peer=null;
   try{s.link.close();}catch{}try{for(const track of s.stream?.getTracks()||[])if(track.readyState!=='ended')track.stop();}catch{}
   s.producers=Object.freeze([]);s.selected=null;s.sessionId=null;s.stream=null;s.videoSeen=false;s.geometry=null;s.queue=[];s.localIce=[];s.remoteIce=[];this.#notify();
  }
  stop(){this.#end('STOPPED');}
 }
 const api=Object.freeze({CameraSession});if(common)module.exports=api;else root.MicroDuckCameraSession=api;
})(typeof globalThis==='object'?globalThis:this);
