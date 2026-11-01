/* SPDX-License-Identifier: MIT */
/* Owned video-only media element. Frame callbacks are evidence, never identity. */
((root)=>{
 'use strict';
 const P=typeof module==='object'&&module.exports?require('./camera-protocol.js'):root.MicroDuckCameraProtocol;
 const states=new WeakMap();
 const CODES=new Set('PARAMS BUSY STOPPED MEDIA_ELEMENT_BUSY STREAM_POLICY SOURCE_CHANGED TRACK_ENDED MEDIA_ERROR MEDIA_ENDED FRAME_CALLBACK_UNAVAILABLE FRAME_INVALID FRAME_LIMIT FIRST_FRAME_TIMEOUT FRAME_STALLED VIEW_TIME_LIMIT PLAYBACK_BLOCKED PLAYBACK_FAILED SESSION_CLOSED PAGE_HIDDEN'.split(' '));
 class ViewerError extends Error{constructor(code){super(code);this.name='ViewerError';this.code=code;}}
 const fail=code=>{throw new ViewerError(code);};
 const invoke=(fn,...args)=>{try{fn(...args);}catch{}};
 const dimension=value=>Number.isInteger(value)&&value>0&&value<=8192;
 const dimensions=(width,height)=>dimension(width)&&dimension(height)&&width*height<=16777216;
 function geometry(value){
  if(value===null)return null;
  if(!value||Object.getPrototypeOf(value)!==Object.prototype||Object.keys(value).some(key=>!['reportedWidth','reportedHeight','reportedRotateClockwise','origin'].includes(key))||value.origin!=='unattested-remote')fail('PARAMS');
  return P.geometry({width:value.reportedWidth,height:value.reportedHeight,rotate:value.reportedRotateClockwise});
 }
 function displayLayout(frame,reported){
  if(!frame||!dimensions(frame.displayWidth,frame.displayHeight))return null;
  const turn=reported?.reportedRotateClockwise??null,quarter=turn===90||turn===270;
  return Object.freeze({rotationKnown:turn!==null,reportedRotation:turn,aspectWidth:quarter?frame.displayHeight:frame.displayWidth,aspectHeight:quarter?frame.displayWidth:frame.displayHeight,
   videoWidthPercent:quarter?100*frame.displayWidth/frame.displayHeight:100,videoHeightPercent:quarter?100*frame.displayHeight/frame.displayWidth:100,
   transform:'translate(-50%, -50%) rotate('+(turn??0)+'deg)'});
 }
 class VideoViewer{
  constructor({video,simulation=false,onState=()=>{},onClose=()=>{},firstFrameTimeoutMs=5000,stallTimeoutMs=5000,durationMs=60000,maxFrames=1800}={}){
   if(!video||['play','pause','load','addEventListener','removeEventListener','getAttribute','removeAttribute'].some(key=>typeof video[key]!=='function')||!video.style||typeof simulation!=='boolean'||typeof onState!=='function'||typeof onClose!=='function')fail('PARAMS');
   for(const value of [firstFrameTimeoutMs,stallTimeoutMs])if(!Number.isInteger(value)||value<1||value>30000)fail('PARAMS');
   if(!Number.isInteger(durationMs)||durationMs<1||durationMs>300000||!Number.isInteger(maxFrames)||maxFrames<1||maxFrames>18000)fail('PARAMS');
   if(video.srcObject||video.getAttribute('src')!==null||video.currentSrc||video.querySelector?.('source'))fail('MEDIA_ELEMENT_BUSY');
   states.set(this,{video,simulation,onState,onClose,firstFrameTimeoutMs,stallTimeoutMs,durationMs,maxFrames,closed:false,phase:'detached',code:null,stream:null,track:null,handlers:[],frameHandle:null,epoch:0,timer:null,lease:null,frames:0,lastPresented:0,lastFrame:null,fresh:false,reported:null,geometryError:null,playAttempts:0,playResolved:false,trackEnded:null,streamChanged:null});
  }
  snapshot(){
   const s=states.get(this);return Object.freeze({phase:s.phase,code:s.code,simulation:s.simulation,frameObservations:s.frames,frameFresh:s.fresh,
    frameEvidence:s.frames?(s.simulation?'simulated-callback':'browser-frame-callback'):'none',browserFrameCallbackObserved:!s.simulation&&s.frames>0,
    decodedFramesVerified:false,physicalMicroDuckTested:false,lastFrame:s.lastFrame,reportedGeometry:s.reported,geometryError:s.geometryError,layout:displayLayout(s.lastFrame,s.reported),playAttempts:s.playAttempts,playResolved:s.playResolved,
    limits:Object.freeze({firstFrameTimeoutMs:s.firstFrameTimeoutMs,stallTimeoutMs:s.stallTimeoutMs,durationMs:s.durationMs,maxFrames:s.maxFrames})});
  }
  #notify(){const s=states.get(this);invoke(s.onState,this.snapshot());}
  #layout(){const s=states.get(this),layout=displayLayout(s.lastFrame,s.reported);if(!layout)return;
   Object.assign(s.video.style,{width:layout.videoWidthPercent+'%',height:layout.videoHeightPercent+'%',transform:layout.transform});
  }
  setGeometry(value){
   const s=states.get(this);if(s.closed)return;
   try{s.reported=geometry(value);s.geometryError=null;}catch{s.reported=null;s.geometryError='GEOMETRY_INVALID';}
   this.#layout();this.#notify();
  }
  #arm(code,milliseconds){const s=states.get(this);clearTimeout(s.timer);s.timer=setTimeout(()=>this.close(code),milliseconds);}
  #owned(){
   const s=states.get(this);if(s.video.srcObject!==s.stream||s.video.getAttribute('src')!==null||s.video.currentSrc||s.video.querySelector?.('source'))fail('SOURCE_CHANGED');
   const tracks=s.stream.getTracks();if(!Array.isArray(tracks)||tracks.length!==1||tracks[0]!==s.track||s.track.kind!=='video'||s.track.readyState!=='live')fail('STREAM_POLICY');
  }
  #request(){
   const s=states.get(this);if(s.closed)return;const epoch=s.epoch;
   try{s.frameHandle=s.video.requestVideoFrameCallback((now,data)=>{
    if(s.closed||epoch!==s.epoch)return;s.frameHandle=null;
    try{
     this.#owned();
     if(s.video.readyState<2||s.video.paused||!dimensions(s.video.videoWidth,s.video.videoHeight)||!data||!dimensions(data.width,data.height)||!Number.isInteger(data.presentedFrames)||data.presentedFrames<=s.lastPresented||data.presentedFrames>0xffffffff||!Number.isFinite(data.mediaTime))fail('FRAME_INVALID');
     s.lastPresented=data.presentedFrames;s.frames++;s.fresh=true;s.phase='frames-observed';
     s.lastFrame=Object.freeze({width:data.width,height:data.height,displayWidth:s.video.videoWidth,displayHeight:s.video.videoHeight,presentedFrames:data.presentedFrames});
     this.#layout();this.#arm('FRAME_STALLED',s.stallTimeoutMs);this.#notify();
     if(s.closed)return;if(s.frames>=s.maxFrames){this.close('FRAME_LIMIT');return;}this.#request();
    }catch(error){this.close(CODES.has(error?.code)?error.code:'FRAME_INVALID');}
   });}catch{this.close('FRAME_CALLBACK_UNAVAILABLE');}
  }
  attach(stream){
   const s=states.get(this);if(s.closed)fail('STOPPED');if(s.stream)fail('BUSY');
   if(!stream||typeof stream.getTracks!=='function')fail('STREAM_POLICY');
   const tracks=stream.getTracks();if(!Array.isArray(tracks)||tracks.length!==1||tracks[0]?.kind!=='video'||tracks[0].readyState!=='live'||typeof tracks[0].stop!=='function'||typeof tracks[0].addEventListener!=='function'||typeof tracks[0].removeEventListener!=='function')fail('STREAM_POLICY');
   if(s.video.srcObject||s.video.getAttribute('src')!==null||s.video.currentSrc)fail('MEDIA_ELEMENT_BUSY');
   s.stream=stream;s.track=tracks[0];s.phase='waiting-frame';s.epoch++;
   try{
    s.trackEnded=()=>this.close('TRACK_ENDED');s.track.addEventListener('ended',s.trackEnded);
    s.streamChanged=()=>{try{this.#owned();}catch{this.close('STREAM_POLICY');}};stream.addEventListener?.('addtrack',s.streamChanged);
    for(const [name,handler]of [['error',()=>this.close('MEDIA_ERROR')],['ended',()=>this.close('MEDIA_ENDED')],['emptied',()=>this.close('SOURCE_CHANGED')],...['pause','waiting','stalled'].map(name=>[name,()=>{if(!s.closed){s.fresh=false;s.phase='waiting-frame';this.#notify();}}])]){s.video.addEventListener(name,handler);s.handlers.push([name,handler]);}
    if(typeof s.video.requestVideoFrameCallback!=='function'||typeof s.video.cancelVideoFrameCallback!=='function'){this.close('FRAME_CALLBACK_UNAVAILABLE');return;}
    s.video.muted=true;s.video.defaultMuted=true;s.video.playsInline=true;s.video.controls=false;s.video.autoplay=false;
    s.video.srcObject=stream;this.#arm('FIRST_FRAME_TIMEOUT',s.firstFrameTimeoutMs);s.lease=setTimeout(()=>this.close('VIEW_TIME_LIMIT'),s.durationMs);
    this.#request();if(s.closed)return;s.playAttempts++;
    const playing=s.video.play();
    if(!playing||typeof playing.then!=='function'){this.close('PLAYBACK_FAILED');return;}
    Promise.resolve(playing).then(()=>{if(!s.closed){s.playResolved=true;this.#notify();}},error=>{if(!s.closed)this.close(error?.name==='NotAllowedError'?'PLAYBACK_BLOCKED':'PLAYBACK_FAILED');});
    this.#notify();
   }catch{this.close('PLAYBACK_FAILED');}
  }
  close(code='STOPPED'){
   const s=states.get(this);if(s.closed)return;s.closed=true;s.code=CODES.has(code)?code:'SESSION_CLOSED';s.phase='closed';s.fresh=false;s.epoch++;
   clearTimeout(s.timer);clearTimeout(s.lease);
   if(s.frameHandle!==null){try{s.video.cancelVideoFrameCallback(s.frameHandle);}catch{}s.frameHandle=null;}
   for(const [name,handler]of s.handlers)try{s.video.removeEventListener(name,handler);}catch{}s.handlers=[];
   try{s.track?.removeEventListener('ended',s.trackEnded);s.stream?.removeEventListener?.('addtrack',s.streamChanged);}catch{}
   // Never pause or detach a replacement source supplied by another owner.
   if(s.stream&&s.video.srcObject===s.stream){try{s.video.pause();}catch{}try{s.video.srcObject=null;}catch{}try{s.video.removeAttribute('src');}catch{}try{if(!s.video.querySelector?.('source'))s.video.load();}catch{}}
   try{s.track?.stop();}catch{}s.track=s.stream=null;s.reported=null;
   Object.assign(s.video.style,{width:'100%',height:'100%',transform:'none'});this.#notify();invoke(s.onClose,s.code);
  }
 }
 const api=Object.freeze({VideoViewer,ViewerError,displayLayout});if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckCameraViewer=api;
})(typeof globalThis==='object'?globalThis:this);
