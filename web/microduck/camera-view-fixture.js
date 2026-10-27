/* SPDX-License-Identifier: MIT */
/* Fictional callbacks only: never constructs browser video, RTC or media APIs. */
((root)=>{
 'use strict';
 const common=typeof module==='object'&&module.exports;
 const {createFixture}=common?require('./camera-fixture.js'):root.MicroDuckCameraFixture;
 const {VideoViewer,ViewerError}=common?require('./camera-viewer.js'):root.MicroDuckCameraViewer;
 const FAULTS=Object.freeze(['no-frames','play-blocked','play-pending','stall','unsupported','media-error']);
 function createViewFixture(options={}){
  if(!options||Object.getPrototypeOf(options)!==Object.prototype||Object.keys(options).some(key=>!['fault','frameIntervalMs','firstFrameTimeoutMs','stallTimeoutMs','durationMs','maxFrames','onState'].includes(key)))throw new ViewerError('PARAMS');
  const {fault=null,frameIntervalMs=200,firstFrameTimeoutMs=5000,stallTimeoutMs=5000,durationMs=60000,maxFrames=1800,onState=()=>{}}=options;
  if(fault!==null&&!FAULTS.includes(fault)||!Number.isInteger(frameIntervalMs)||frameIntervalMs<1||frameIntervalMs>1000||typeof onState!=='function')throw new ViewerError('PARAMS');
  let viewer,closed=false,timer=null,nextId=0,presented=0;
  const callbacks=new Map(),listeners=new Map(),counts={play:0,pause:0,load:0,requested:0,cancelled:0,callbacks:0};
  const video={srcObject:null,currentSrc:'',readyState:0,videoWidth:0,videoHeight:0,paused:true,style:{},
   getAttribute(){return null;},removeAttribute(){},
   addEventListener(name,handler){if(!listeners.has(name))listeners.set(name,new Set());listeners.get(name).add(handler);},
   removeEventListener(name,handler){listeners.get(name)?.delete(handler);},
   play(){counts.play++;if(fault==='play-blocked')return Promise.reject({name:'NotAllowedError'});if(fault==='play-pending')return new Promise(()=>{});this.paused=false;this.readyState=2;this.videoWidth=1280;this.videoHeight=720;schedule();return Promise.resolve();},
   pause(){counts.pause++;this.paused=true;clearTimeout(timer);timer=null;},load(){counts.load++;this.readyState=0;this.videoWidth=this.videoHeight=0;},
   requestVideoFrameCallback(handler){counts.requested++;const id=++nextId;callbacks.set(id,handler);schedule();return id;},
   cancelVideoFrameCallback(id){counts.cancelled++;callbacks.delete(id);if(!callbacks.size){clearTimeout(timer);timer=null;}}
  };
  if(fault==='unsupported')video.requestVideoFrameCallback=undefined;
  function schedule(){
   if(closed||timer!==null||video.paused||!callbacks.size||fault==='no-frames'||fault==='stall'&&presented>=1)return;
   timer=setTimeout(()=>{timer=null;if(closed||video.paused)return;
    if(fault==='media-error'){for(const handler of [...listeners.get('error')||[]])handler();return;}
    const entry=callbacks.entries().next().value;if(!entry)return;callbacks.delete(entry[0]);presented++;counts.callbacks++;entry[1](presented*frameIntervalMs,{width:1280,height:720,presentedFrames:presented,mediaTime:0});
   },frameIntervalMs);
  }
  const transport=createFixture({durationMs,onVideo:stream=>viewer.attach(stream),onState:state=>{if(viewer){viewer.setGeometry(state.geometry);if(state.phase==='closed')viewer.close('SESSION_CLOSED');}}});
  try{viewer=new VideoViewer({video,simulation:true,firstFrameTimeoutMs,stallTimeoutMs,durationMs,maxFrames,onState,onClose:()=>{closed=true;clearTimeout(timer);timer=null;callbacks.clear();transport.close();}});}
  catch(error){transport.close();throw error;}
  return Object.freeze({simulation:true,session:transport.session,viewer,snapshot(){return Object.freeze({simulation:true,physicalMicroDuckTested:false,nativeDecoderExecuted:false,transport:transport.snapshot(),media:Object.freeze({...counts,pendingCallbacks:callbacks.size,closed})});},close(){viewer.close();transport.close();}});
 }
 const api=Object.freeze({createViewFixture,FAULTS});if(common)module.exports=api;else root.MicroDuckCameraViewFixture=api;
})(typeof globalThis==='object'?globalThis:this);
