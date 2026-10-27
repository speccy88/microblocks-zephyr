/* SPDX-License-Identifier: MIT */
// Actual viewer and simulation panel, with fake DOM/media/callbacks only.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),vm=require('node:vm');
const {VideoViewer}=require('../web/microduck/camera-viewer.js');
const {createViewFixture}=require('../web/microduck/camera-view-fixture.js');
const panelAPI=require('../web/microduck/camera-panel.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const delay=milliseconds=>new Promise(resolve=>setTimeout(resolve,milliseconds));
async function until(predicate){const deadline=Date.now()+1000;while(!predicate()){if(Date.now()>=deadline)assert.fail('bounded fixture outcome was not observed');await delay(2);}}
const code=value=>error=>error.code===value;
const reported={reportedWidth:1280,reportedHeight:720,reportedRotateClockwise:90,origin:'unattested-remote'};
const frame={width:1280,height:720,presentedFrames:1,mediaTime:0};
class Events{
 constructor(){this.listeners=new Map();}
 addEventListener(name,fn){if(!this.listeners.has(name))this.listeners.set(name,new Set());this.listeners.get(name).add(fn);}
 removeEventListener(name,fn){this.listeners.get(name)?.delete(fn);}
 emit(name,event={}){for(const fn of [...this.listeners.get(name)||[]])fn(event);}
 get listenerCount(){return [...this.listeners.values()].reduce((sum,set)=>sum+set.size,0);}
}
class Track extends Events{
 constructor(kind='video'){super();this.kind=kind;this.readyState='live';this.stops=0;}
 stop(){if(this.readyState==='ended')return;this.stops++;this.readyState='ended';this.emit('ended');}
}
class Stream extends Events{constructor(tracks){super();this.tracks=tracks;}getTracks(){return [...this.tracks];}}
class Media extends Events{
 constructor(options={}){super();this.options=options;this.style={};this.srcObject=null;this.currentSrc='';this.attrs=new Map();this.readyState=2;this.videoWidth=1280;this.videoHeight=720;this.paused=true;this.plays=0;this.pauses=0;this.loads=0;this.pending=new Map();this.cancelled=[];this.id=0;}
 getAttribute(name){return this.attrs.get(name)??null;}
 removeAttribute(name){this.attrs.delete(name);}
 querySelector(){return this.options.childSource?{}:null;}
 play(){this.plays++;this.paused=false;if(this.options.playError)return Promise.reject(this.options.playError);if(this.options.pendingPlay)return this.options.pendingPlay;return Promise.resolve();}
 pause(){this.pauses++;if(this.options.throwPause)throw Error('PRIVATE pause');this.paused=true;}
 load(){this.loads++;if(this.options.throwLoad)throw Error('PRIVATE load');}
 requestVideoFrameCallback(fn){const id=++this.id;this.pending.set(id,fn);return id;}
 cancelVideoFrameCallback(id){this.cancelled.push(id);this.pending.delete(id);}
 deliver(data=frame){const entry=this.pending.entries().next().value;assert.ok(entry,'a single callback must be pending');this.pending.delete(entry[0]);entry[1](0,data);return entry[1];}
 set src(_){throw Error('URL media assignment prohibited');}
}
function harness(options={}){
 const video=new Media(options.media),track=new Track(),stream=new Stream([track]),states=[],closed=[];
 const viewer=new VideoViewer({video,simulation:true,firstFrameTimeoutMs:1000,stallTimeoutMs:1000,...options.viewer,onState:value=>{states.push(value);options.onState?.(value);},onClose:value=>{closed.push(value);options.onClose?.(value);}});
 return {video,track,stream,states,closed,viewer};
}

test('viewer construction is passive and validates finite bounds',()=>{
 const h=harness();assert.equal(h.video.plays,0);assert.equal(h.video.pending.size,0);assert.equal(h.video.listenerCount,0);assert.equal(h.viewer.snapshot().frameEvidence,'none');h.viewer.close();
 for(const options of [{firstFrameTimeoutMs:0},{stallTimeoutMs:30001},{durationMs:300001},{maxFrames:18001},{simulation:'true'}])assert.throws(()=>new VideoViewer({video:new Media(),...options}),code('PARAMS'));
});
test('occupied media elements are refused without stopping or replacing existing media',()=>{
 for(const kind of ['srcObject','src','currentSrc','source']){const video=new Media({childSource:kind==='source'}),prior=new Stream([new Track()]);if(kind==='srcObject')video.srcObject=prior;if(kind==='src')video.attrs.set('src','PRIVATE');if(kind==='currentSrc')video.currentSrc='PRIVATE';assert.throws(()=>new VideoViewer({video}),code('MEDIA_ELEMENT_BUSY'));assert.equal(prior.tracks[0].stops,0);assert.equal(video.plays,0);}
});
test('attach refuses audio, mixed, ended or multiple tracks and leaves unaccepted streams alone',()=>{
 for(const tracks of [[new Track('audio')],[new Track(),new Track('audio')],[],[new Track(),new Track()]]){const h=harness();assert.throws(()=>h.viewer.attach(new Stream(tracks)),code('STREAM_POLICY'));assert.equal(h.video.plays,0);assert.ok(tracks.every(track=>track.stops===0));h.viewer.close();}
 const h=harness(),track=new Track();track.stop();assert.throws(()=>h.viewer.attach(new Stream([track])),code('STREAM_POLICY'));h.viewer.close();
});
test('owned attach is muted and inline, plays once, and has one pending callback',async t=>{
 const h=harness();t.after(()=>h.viewer.close());h.viewer.attach(h.stream);await tick();assert.equal(h.video.muted,true);assert.equal(h.video.defaultMuted,true);assert.equal(h.video.playsInline,true);assert.equal(h.video.autoplay,false);assert.equal(h.video.srcObject,h.stream);assert.equal(h.video.plays,1);assert.equal(h.video.pending.size,1);assert.equal(h.viewer.snapshot().playResolved,true);assert.equal(h.viewer.snapshot().frameObservations,0);assert.throws(()=>h.viewer.attach(h.stream),code('BUSY'));
});
test('dimensions, loadeddata/playing/timeupdate and play resolution never count as frame evidence',async t=>{
 const h=harness();t.after(()=>h.viewer.close());h.viewer.attach(h.stream);for(const event of ['loadedmetadata','loadeddata','canplay','playing','timeupdate'])h.video.emit(event);await tick();assert.equal(h.viewer.snapshot().frameObservations,0);assert.equal(h.viewer.snapshot().frameFresh,false);assert.equal(h.viewer.snapshot().frameEvidence,'none');
});
test('valid callbacks count without persisting timestamps or inventing native decoding',async t=>{
 const h=harness();t.after(()=>h.viewer.close());h.viewer.attach(h.stream);h.video.deliver({...frame,captureTime:'PRIVATE',receiveTime:'PRIVATE',processingDuration:999});await tick();const state=h.viewer.snapshot();assert.equal(state.frameObservations,1);assert.equal(state.frameFresh,true);assert.equal(state.frameEvidence,'simulated-callback');assert.equal(state.browserFrameCallbackObserved,false);assert.equal(state.decodedFramesVerified,false);assert.ok(!JSON.stringify(state).includes('PRIVATE'));assert.ok(!Object.hasOwn(state.lastFrame,'mediaTime'));assert.equal(h.video.pending.size,1);
});
test('browser callback evidence remains separate from physical camera attestation',t=>{
 const h=harness({viewer:{simulation:false}});t.after(()=>h.viewer.close());h.viewer.attach(h.stream);h.video.deliver();assert.equal(h.viewer.snapshot().frameEvidence,'browser-frame-callback');assert.equal(h.viewer.snapshot().browserFrameCallbackObserved,true);assert.equal(h.viewer.snapshot().physicalMicroDuckTested,false);assert.equal(h.viewer.snapshot().decodedFramesVerified,false);
});
test('reported rotation uses display dimensions and tolerates anamorphic media dimensions',t=>{
 const h=harness();t.after(()=>h.viewer.close());h.viewer.attach(h.stream);h.video.videoWidth=1440;h.viewer.setGeometry(reported);h.video.deliver();const state=h.viewer.snapshot();assert.equal(state.lastFrame.width,1280);assert.equal(state.layout.aspectWidth,720);assert.equal(state.layout.aspectHeight,1440);assert.equal(state.layout.reportedRotation,90);assert.equal(h.video.style.width,'200%');assert.match(h.video.style.transform,/rotate\(90deg\)/);
 for(const turn of [0,90,180,270]){h.viewer.setGeometry({...reported,reportedRotateClockwise:turn});assert.equal(h.viewer.snapshot().layout.reportedRotation,turn);}
});
test('missing or malformed geometry stays unknown and removes an earlier rotation',t=>{
 const h=harness();t.after(()=>h.viewer.close());h.viewer.attach(h.stream);h.video.deliver();assert.equal(h.viewer.snapshot().layout.rotationKnown,false);h.viewer.setGeometry(reported);h.viewer.setGeometry({...reported,reportedRotateClockwise:45});assert.equal(h.viewer.snapshot().reportedGeometry,null);assert.equal(h.viewer.snapshot().layout.rotationKnown,false);assert.equal(h.viewer.snapshot().geometryError,'GEOMETRY_INVALID');assert.match(h.video.style.transform,/rotate\(0deg\)/);h.viewer.setGeometry(null);assert.equal(h.viewer.snapshot().geometryError,null);
});
test('invalid dimensions, readiness, paused state and frame metadata close cleanly',()=>{
 for(const change of [h=>{h.video.readyState=1;},h=>{h.video.paused=true;},h=>{h.video.videoWidth=0;},h=>{h.video.videoHeight=8193;}]){const h=harness();h.viewer.attach(h.stream);change(h);h.video.deliver();assert.equal(h.viewer.snapshot().code,'FRAME_INVALID');assert.equal(h.video.srcObject,null);assert.equal(h.track.stops,1);}
 for(const data of [{...frame,width:0},{...frame,height:8193},{...frame,width:8192,height:8192},{...frame,presentedFrames:0},{...frame,presentedFrames:Infinity},{...frame,presentedFrames:2**32},{...frame,presentedFrames:2**54},{...frame,mediaTime:NaN},null]){const h=harness();h.viewer.attach(h.stream);h.video.deliver(data);assert.equal(h.viewer.snapshot().code,'FRAME_INVALID');assert.equal(h.viewer.snapshot().frameObservations,0);}
});
test('presented counters must increase while valid zero or negative media timestamps are ignored',()=>{
 const h=harness();h.viewer.attach(h.stream);h.video.deliver({...frame,mediaTime:-1});h.video.deliver({...frame,presentedFrames:4,mediaTime:0});assert.equal(h.viewer.snapshot().frameObservations,2);h.video.deliver({...frame,presentedFrames:4});assert.equal(h.viewer.snapshot().code,'FRAME_INVALID');assert.equal(h.viewer.snapshot().frameFresh,false);
});
test('unsupported callback or cancellation APIs fail explicitly without a play retry',()=>{
 for(const key of ['requestVideoFrameCallback','cancelVideoFrameCallback']){const h=harness();h.video[key]=undefined;h.viewer.attach(h.stream);assert.equal(h.viewer.snapshot().code,'FRAME_CALLBACK_UNAVAILABLE');assert.equal(h.video.plays,0);assert.equal(h.track.stops,1);}
});
test('frame registration failure closes without play and stopping from a frame observer cannot rearm',()=>{
 const broken=harness();broken.video.requestVideoFrameCallback=()=>{throw Error('PRIVATE');};broken.viewer.attach(broken.stream);assert.equal(broken.viewer.snapshot().code,'FRAME_CALLBACK_UNAVAILABLE');assert.equal(broken.video.plays,0);assert.equal(broken.track.stops,1);
 let h;h=harness({onState:state=>{if(state.frameObservations)h.viewer.close();}});h.viewer.attach(h.stream);h.video.deliver();assert.equal(h.viewer.snapshot().phase,'closed');assert.equal(h.video.pending.size,0);assert.equal(h.closed.length,1);
});
test('blocked and failed playback expose fixed codes, no browser messages or automatic retry',async()=>{
 for(const error of [{name:'NotAllowedError',message:'PRIVATE'},{name:'NotSupportedError',message:'PRIVATE'}]){const h=harness({media:{playError:error}});h.viewer.attach(h.stream);await tick();assert.equal(h.viewer.snapshot().code,error.name==='NotAllowedError'?'PLAYBACK_BLOCKED':'PLAYBACK_FAILED');assert.equal(h.video.plays,1);assert.equal(h.video.pending.size,0);assert.ok(!JSON.stringify(h.viewer.snapshot()).includes('PRIVATE'));}
});
test('pending playback and absent callbacks hit the first-frame deadline without hanging',async()=>{
 for(const pending of [false,true]){const h=harness({media:pending?{pendingPlay:new Promise(()=>{})}:{},viewer:{firstFrameTimeoutMs:5}});h.viewer.attach(h.stream);await delay(15);assert.equal(h.viewer.snapshot().code,'FIRST_FRAME_TIMEOUT');assert.equal(h.video.srcObject,null);assert.equal(h.video.plays,1);assert.equal(h.video.pending.size,0);}
});
test('pause/wait/stall removes freshness immediately and a valid callback can restore it',t=>{
 const h=harness();t.after(()=>h.viewer.close());h.viewer.attach(h.stream);let counter=0;
 for(const event of ['pause','waiting','stalled']){h.video.paused=false;h.video.deliver({...frame,presentedFrames:++counter});assert.equal(h.viewer.snapshot().frameFresh,true);h.video.emit(event);assert.equal(h.viewer.snapshot().frameFresh,false);assert.equal(h.viewer.snapshot().phase,'waiting-frame');}
});
test('a stopped frame stream and finite total duration each close the owned resources',async()=>{
 const stalled=harness({viewer:{stallTimeoutMs:5}});stalled.viewer.attach(stalled.stream);stalled.video.deliver();await delay(15);assert.equal(stalled.viewer.snapshot().code,'FRAME_STALLED');assert.equal(stalled.video.cancelled.length,1);
 const leased=harness({viewer:{durationMs:5}});leased.viewer.attach(leased.stream);await delay(15);assert.equal(leased.viewer.snapshot().code,'VIEW_TIME_LIMIT');assert.equal(leased.track.stops,1);
});
test('frame count bounds stop instead of scheduling another callback',()=>{
 const h=harness({viewer:{maxFrames:2}});h.viewer.attach(h.stream);h.video.deliver();h.video.deliver({...frame,presentedFrames:2});assert.equal(h.viewer.snapshot().code,'FRAME_LIMIT');assert.equal(h.video.pending.size,0);assert.equal(h.viewer.snapshot().frameObservations,2);assert.equal(h.viewer.snapshot().frameFresh,false);
});
test('track and media failures detach and callbacks cannot revive a closed viewer',()=>{
 for(const event of ['error','ended','emptied','track']){const h=harness();h.viewer.attach(h.stream);const callback=[...h.video.pending.values()][0];if(event==='track')h.track.stop();else h.video.emit(event);callback(0,frame);assert.equal(h.viewer.snapshot().phase,'closed');assert.equal(h.viewer.snapshot().frameObservations,0);assert.equal(h.video.listenerCount,0);assert.equal(h.track.listenerCount,0);assert.equal(h.stream.listenerCount,0);assert.equal(h.closed.length,1);}
});
test('source replacement is refused without pausing, detaching or stopping the foreign source',()=>{
 const h=harness();h.viewer.attach(h.stream);const foreign=new Stream([new Track()]);h.video.srcObject=foreign;h.video.deliver();assert.equal(h.viewer.snapshot().code,'SOURCE_CHANGED');assert.equal(h.video.srcObject,foreign);assert.equal(h.video.pauses,0);assert.equal(h.track.stops,1);assert.equal(foreign.tracks[0].stops,0);
});
test('new audio or extra tracks cannot join the owned stream unnoticed',()=>{
 const h=harness();h.viewer.attach(h.stream);h.stream.tracks.push(new Track('audio'));h.stream.emit('addtrack');assert.equal(h.viewer.snapshot().code,'STREAM_POLICY');assert.equal(h.video.srcObject,null);assert.equal(h.track.stops,1);
});
test('a newly inserted source child is refused without loading its URL during cleanup',()=>{
 const h=harness();h.viewer.attach(h.stream);h.video.options.childSource=true;h.video.deliver();assert.equal(h.viewer.snapshot().code,'SOURCE_CHANGED');assert.equal(h.video.srcObject,null);assert.equal(h.video.loads,0);assert.equal(h.track.stops,1);
});
test('late play resolution/rejection and callback exceptions cannot prevent idempotent cleanup',async()=>{
 let resolve;const pending=new Promise(r=>{resolve=r;});const h=harness({media:{pendingPlay:pending,throwPause:true,throwLoad:true},onState(){throw Error('consumer');},onClose(){throw Error('consumer');}});h.viewer.attach(h.stream);h.viewer.close();h.viewer.close();resolve();await tick();assert.equal(h.viewer.snapshot().phase,'closed');assert.equal(h.viewer.snapshot().playResolved,false);assert.equal(h.video.srcObject,null);assert.equal(h.video.loads,1);assert.equal(h.track.stops,1);assert.equal(h.closed.length,1);
 let reject;const next=harness({media:{pendingPlay:new Promise((_,r)=>{reject=r;})}});next.viewer.attach(next.stream);next.viewer.close();reject(Error('PRIVATE'));await tick();assert.equal(next.viewer.snapshot().code,'STOPPED');
});
test('complete viewer fixture composes real modules and never claims native decoding',async()=>{
 const f=createViewFixture({frameIntervalMs:2,maxFrames:3,firstFrameTimeoutMs:100,stallTimeoutMs:100});try{assert.equal(f.snapshot().transport.signalMessages,0);assert.equal(f.snapshot().media.requested,0);const rows=await f.session.discover();await f.session.start(rows[0].id,{confirmed:true});await until(()=>f.viewer.snapshot().phase==='closed');assert.equal(f.viewer.snapshot().frameObservations,3);assert.equal(f.viewer.snapshot().code,'FRAME_LIMIT');assert.deepEqual(f.snapshot().transport.controlMethods,['media.video']);assert.equal(f.snapshot().media.pendingCallbacks,0);assert.equal(f.snapshot().nativeDecoderExecuted,false);assert.equal(f.snapshot().transport.peerCloses,1);}finally{f.close();}
});
test('named fixture faults cover unavailable, blocked, pending, absent, stalled and failed playback',async()=>{
 for(const [fault,expected]of [['unsupported','FRAME_CALLBACK_UNAVAILABLE'],['play-blocked','PLAYBACK_BLOCKED'],['play-pending','FIRST_FRAME_TIMEOUT'],['no-frames','FIRST_FRAME_TIMEOUT'],['stall','FRAME_STALLED'],['media-error','MEDIA_ERROR']]){
  const f=createViewFixture({fault,frameIntervalMs:1,firstFrameTimeoutMs:8,stallTimeoutMs:8});try{const rows=await f.session.discover();await f.session.start(rows[0].id,{confirmed:true}).catch(()=>{});await until(()=>f.viewer.snapshot().phase==='closed');assert.equal(f.viewer.snapshot().code,expected,fault);assert.equal(f.snapshot().transport.closed,true);assert.equal(f.snapshot().media.pendingCallbacks,0);assert.ok(f.snapshot().transport.controlMethods.every(method=>method==='media.video'));}finally{f.close();}
 }
});
test('viewer fixture cannot accept real URLs, credentials, transport or media providers',()=>{
 for(const options of [{url:'PRIVATE'},{pin:'000000'},{token:'PRIVATE'},{video:new Media()},{link:{}},{RTCPeerConnection:()=>{}},{fault:'unknown'}])assert.throws(()=>createViewFixture(options),code('PARAMS'));
});

class Element extends Events{
 constructor(tag,document){super();this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.attributes={};this.style={};this.value='';this.disabled=false;this._text='';this.draws=[];}
 set innerHTML(_){throw Error('HTML insertion prohibited');}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 append(...nodes){for(const node of nodes){node.parentNode=this;this.children.push(node);}}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 setAttribute(key,value){this.attributes[key]=String(value);}
 getContext(){return {fillRect:()=>{},fillText:(...args)=>this.draws.push(args[0])};}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(node=>node!==this);}
 find(fn){if(fn(this))return this;for(const child of this.children){const found=child.find(fn);if(found)return found;}}
 all(fn){return [...(fn(this)?[this]:[]),...this.children.flatMap(child=>child.all(fn))];}
 async fire(name){for(const fn of [...this.listeners.get(name)||[]])await fn({preventDefault(){}});}
}
function panelHarness(options={}){
 const document={createElement(tag){return new Element(tag,this);}},container=new Element('main',document),lifecycle=new Events(),visibility=new Events();visibility.hidden=false;
 const panel=panelAPI.mount(container,{lifecycleTarget:lifecycle,visibilityTarget:visibility,frameIntervalMs:2,firstFrameTimeoutMs:100,stallTimeoutMs:100,...options});
 const field=name=>container.find(node=>node.className==='camera-'+name);
 return {panel,container,lifecycle,visibility,field,async discover(){await field('discover').fire('click');},async start(){field('producer').value='simulation-camera-1';await field('producer').fire('change');await field('start').fire('click');}};
}
test('panel mount is detached with no media, network controls or auto-selected producer',()=>{
 const h=panelHarness();assert.equal(h.panel.snapshot().detached,true);assert.equal(h.field('start').disabled,true);assert.equal(h.field('producer').value,'');assert.equal(h.container.all(node=>['INPUT','VIDEO'].includes(node.tagName)).length,0);assert.match(h.field('badge').textContent,/SIMULATION/);h.panel.destroy();assert.equal(h.lifecycle.listenerCount,0);assert.equal(h.visibility.listenerCount,0);
});
test('explicit discovery, selection and start exercise the viewer with fictional callback labels',async()=>{
 const h=panelHarness();try{await h.discover();assert.equal(h.field('producer').value,'');assert.equal(h.field('start').disabled,true);assert.equal(h.panel.snapshot().fixture.transport.controlRequests,0);await h.start();await delay(12);const snapshot=h.panel.snapshot();assert.ok(snapshot.viewer.frameObservations>0);assert.equal(snapshot.viewer.frameEvidence,'simulated-callback');assert.match(h.field('status').textContent,/No native decoding/);assert.match(h.field('rotation').textContent,/90 degrees/);assert.deepEqual(snapshot.fixture.transport.controlMethods,['media.video']);assert.ok(h.field('canvas').draws.some(text=>text==='SIMULATION'));assert.equal(h.field('stage').style.aspectRatio,'720 / 1280');assert.equal(h.field('stage').style.maxWidth,'258.75px');}finally{h.panel.destroy();}
});
test('panel stop clears display/state and requires another explicit discovery',async()=>{
 const h=panelHarness();await h.discover();await h.start();await delay(8);await h.field('stop').fire('click');assert.equal(h.panel.snapshot().detached,true);assert.equal(h.field('producer').value,'');assert.equal(h.field('start').disabled,true);assert.match(h.field('frames').textContent,/No active/);assert.equal(h.field('canvas').draws.at(-2),'Preview closed');h.panel.destroy();
});
test('closing during discovery or start prevents late media from attaching to the panel',async()=>{
 for(const start of [false,true]){const h=panelHarness();try{if(start)await h.discover();h.field('producer').value='simulation-camera-1';const pending=h.field(start?'start':'discover').fire('click');await h.field('stop').fire('click');await pending;await tick();assert.equal(h.panel.snapshot().detached,true);assert.equal(h.field('start').disabled,true);}finally{h.panel.destroy();}}
});
test('pagehide and hidden-page changes close the fixture without automatic resume',async()=>{
 for(const event of ['pagehide','visibilitychange']){const h=panelHarness();await h.discover();await h.start();if(event==='pagehide')h.lifecycle.emit(event);else{h.visibility.hidden=true;h.visibility.emit(event);}assert.equal(h.panel.snapshot().detached,true);h.visibility.hidden=false;h.visibility.emit('visibilitychange');assert.equal(h.panel.snapshot().detached,true);h.panel.destroy();assert.equal(h.lifecycle.listenerCount,0);assert.equal(h.visibility.listenerCount,0);}
});
test('hidden initial page cannot begin discovery',async()=>{
 const h=panelHarness();h.visibility.hidden=true;h.visibility.emit('visibilitychange');await h.discover();assert.equal(h.panel.snapshot().detached,true);assert.equal(h.field('discover').disabled,true);h.panel.destroy();
});
test('fixture failure shows a fixed code and does not schedule a replacement session',async()=>{
 const h=panelHarness({firstFrameTimeoutMs:8});try{h.field('fault').value='no-frames';await h.discover();await h.start();await delay(20);assert.match(h.field('status').textContent,/FIRST_FRAME_TIMEOUT/);assert.equal(h.panel.snapshot().fixture.transport.peerConstructions,1);assert.equal(h.panel.snapshot().fixture.media.pendingCallbacks,0);assert.equal(h.field('start').disabled,true);}finally{h.panel.destroy();}
});
test('a closed failure permits changing scenario but never restarts until discovery is clicked',async()=>{
 const h=panelHarness({firstFrameTimeoutMs:8});try{h.field('fault').value='no-frames';await h.discover();await h.start();await delay(20);assert.equal(h.field('fault').disabled,false);h.field('fault').value='';await tick();assert.equal(h.panel.snapshot().fixture.transport.peerConstructions,1);await h.discover();assert.equal(h.panel.snapshot().fixture.transport.peerConstructions,0);await h.start();await delay(10);assert.ok(h.panel.snapshot().viewer.frameObservations>0);}finally{h.panel.destroy();}
});
test('browser-global lab works with external RTC/media/network APIs prohibited',async()=>{
 const forbidden=()=>{throw Error('External API forbidden');};const context=vm.createContext({TextEncoder,setTimeout,clearTimeout,queueMicrotask,WebSocket:forbidden,RTCPeerConnection:forbidden,MediaStream:forbidden,navigator:new Proxy({},{get:forbidden})});
 for(const name of ['camera-protocol.js','camera-peer.js','camera-session.js','camera-fixture.js','camera-viewer.js','camera-view-fixture.js'])vm.runInContext(fs.readFileSync(require.resolve('../web/microduck/'+name),'utf8'),context);
 await vm.runInContext('(async()=>{globalThis.fixture=MicroDuckCameraViewFixture.createViewFixture({frameIntervalMs:2,maxFrames:1});const rows=await fixture.session.discover();await fixture.session.start(rows[0].id,{confirmed:true});})()',context);await delay(15);assert.equal(vm.runInContext('fixture.viewer.snapshot().frameEvidence',context),'simulated-callback');assert.equal(vm.runInContext('fixture.snapshot().nativeDecoderExecuted',context),false);vm.runInContext('fixture.close()',context);
});
test('standalone lab references only local scripts and forbids network, media URLs and inline script',()=>{
 const html=fs.readFileSync(require.resolve('../web/microduck/camera.html'),'utf8');for(const policy of ["default-src 'none'","connect-src 'none'","media-src 'none'","object-src 'none'","form-action 'none'"])assert.ok(html.includes(policy));assert.doesNotMatch(html,/<script\b(?![^>]*\bsrc=)[^>]*>/i);assert.doesNotMatch(html,/\son[a-z]+\s*=/i);assert.doesNotMatch(html,/<(?:video|input|iframe)\b/i);assert.match(html,/not captured, encoded or decoded video/);
 for(const [,name]of html.matchAll(/<script src="([^"]+)"/g)){assert.match(name,/^camera-[a-z-]+\.js$/);assert.ok(fs.existsSync(require.resolve('../web/microduck/'+name)));}
});
