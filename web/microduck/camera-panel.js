/* SPDX-License-Identifier: MIT */
/* Standalone fictional viewer lab; no live endpoints or media capture. */
((root)=>{
 'use strict';
 const common=typeof module==='object'&&module.exports;
 const {createViewFixture}=common?require('./camera-view-fixture.js'):root.MicroDuckCameraViewFixture;
 function mount(container,{lifecycleTarget=root,visibilityTarget=root.document,frameIntervalMs=200,firstFrameTimeoutMs=5000,stallTimeoutMs=5000,durationMs=60000,maxFrames=1800}={}){
  const doc=container?.ownerDocument;if(!doc||typeof doc.createElement!=='function')throw Error('PARAMS');
  let fixture=null,rows=[],generation=0,busy=false,disposed=false;
  const make=(tag,name,text)=>{const node=doc.createElement(tag);node.className='camera-'+name;if(text!==undefined)node.textContent=text;return node;};
  const panel=make('section','panel');panel.setAttribute('aria-label','Fictional camera viewer');
  const badge=make('p','badge','SIMULATION / NO REAL CAMERA');
  const title=make('h2','title','Observe a fictional camera session');
  const notice=make('p','notice','This test card and its frame callbacks are simulated. No camera, video decoder, robot, Bluetooth or network connection is used.');
  const controls=make('fieldset','controls'),legend=make('legend','legend','Simulation session');controls.append(legend);
  const faultLabel=make('label','fault-label','Scenario'),fault=make('select','fault');
  for(const [value,label]of [['','Normal callbacks'],['no-frames','No frames arrive'],['play-blocked','Playback blocked'],['play-pending','Playback remains pending'],['stall','One frame, then stall'],['unsupported','Frame callbacks unavailable'],['media-error','Media error']]){const option=make('option','fault-option',label);option.value=value;fault.append(option);}fault.value='';faultLabel.append(fault);
  const discover=make('button','discover','Discover simulation');discover.type='button';
  const producerLabel=make('label','producer-label','Fictional producer'),producer=make('select','producer');producerLabel.append(producer);
  const start=make('button','start','Start selected preview');start.type='button';
  const stop=make('button','stop','Close preview');stop.type='button';controls.append(faultLabel,discover,producerLabel,start,stop);
  const status=make('p','status','Detached. Discover the internal simulation to begin.');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const stage=make('div','stage'),canvas=make('canvas','canvas');canvas.width=640;canvas.height=360;canvas.setAttribute('role','img');canvas.setAttribute('aria-label','Locally drawn fictional camera test card; no decoded video');stage.append(canvas);
  const measurements=make('dl','measurements');
  const details={};for(const [key,label]of [['frames','Frame observation'],['rotation','Reported rotation'],['dimensions','Frame / display dimensions'],['transport','Transport boundary']]){const term=make('dt',key+'-term',label),value=make('dd',key);measurements.append(term,value);details[key]=value;}
  const boundary=make('p','boundary','Closing clears local resources; it is not camera power-off, robot shutdown or emergency stop. Nothing is recorded or exported.');
  panel.append(badge,title,notice,controls,status,stage,measurements,boundary);container.append(panel);
  let context=null;try{context=canvas.getContext?.('2d');}catch{}
  function card(frame,waiting=false){
   if(!context)return;
   context.fillStyle='#101d29';context.fillRect(0,0,640,360);
   if(frame){const colors=['#9ce5ce','#6eb5e0','#e6c46b','#dc9396'];for(let i=0;i<4;i++){context.fillStyle=colors[i];context.fillRect(i*160,0,160,230);}context.fillStyle='#101d29';context.font='bold 25px system-ui';context.fillText('SIMULATION',25,48);context.font='18px system-ui';context.fillText('TOP / reported mounting rotation',25,88);}
   context.fillStyle='#ecf3f3';context.font='20px system-ui';context.fillText(frame?'Fictional callback '+frame:waiting?'Awaiting fictional frame':'Preview closed',25,285);context.font='15px system-ui';context.fillText('No captured or decoded camera pixels',25,320);
  }
  function selection(){const blank=make('option','producer-option','Select a discovered simulation');blank.value='';producer.replaceChildren(blank);for(const row of rows){const option=make('option','producer-option',row.name);option.value=row.id;producer.append(option);}producer.value='';}
  function update(){
   const phase=fixture?.session.snapshot().phase,hidden=visibilityTarget?.hidden===true;
   discover.disabled=disposed||busy||hidden;fault.disabled=disposed||busy||!!fixture&&phase!=='closed';producer.disabled=disposed||busy||phase!=='listed';start.disabled=disposed||busy||hidden||phase!=='listed'||!rows.some(row=>row.id===producer.value);stop.disabled=disposed||!fixture;
  }
  function render(){
   if(disposed||!fixture)return;const view=fixture.viewer.snapshot(),source=fixture.snapshot();
   details.frames.textContent=view.frameObservations+' simulated callback(s); native decoding unverified'+(view.frameFresh?' / fresh simulation':' / no fresh frame');
   details.rotation.textContent=view.reportedGeometry?'Reported '+view.reportedGeometry.reportedRotateClockwise+' degrees clockwise / unattested':'Unknown / display unadjusted';
   details.dimensions.textContent=view.lastFrame?view.lastFrame.width+' x '+view.lastFrame.height+' media pixels / '+view.lastFrame.displayWidth+' x '+view.lastFrame.displayHeight+' display pixels':'Unknown';
   details.transport.textContent='Internal fake RTC / '+source.transport.controlRequests+' media.video query / zero robot commands';
   if(view.phase==='closed')status.textContent='Simulation closed: '+view.code+'. No automatic retry.';
   else if(view.frameFresh)status.textContent='Simulated frame callback observed. No native decoding or physical footage was tested.';
   else if(view.phase==='waiting-frame')status.textContent='Track attached; waiting for a simulated frame callback. Playback alone is not frame evidence.';
   else status.textContent='Simulation listed. Select a producer, then start explicitly.';
   const layout=view.phase==='closed'?null:view.layout;
   stage.style.aspectRatio=layout?layout.aspectWidth+' / '+layout.aspectHeight:'16 / 9';
   stage.style.maxWidth=layout?Math.min(640,460*layout.aspectWidth/layout.aspectHeight)+'px':'640px';
   Object.assign(canvas.style,{width:layout?layout.videoWidthPercent+'%':'100%',height:layout?layout.videoHeightPercent+'%':'100%',transform:layout?layout.transform:'translate(-50%, -50%)'});
   card(view.phase==='closed'?0:view.frameObservations,view.phase!=='closed');update();
  }
  function detach(message='Preview closed. Local media and session resources cleared.'){
   generation++;const old=fixture;fixture=null;rows=[];busy=false;old?.close();selection();status.textContent=message;
   details.frames.textContent='No active frame observation';details.rotation.textContent='Unknown / display unadjusted';details.dimensions.textContent='Unknown';details.transport.textContent='Detached / no network or robot connection';
   stage.style.aspectRatio='16 / 9';stage.style.maxWidth='640px';Object.assign(canvas.style,{width:'100%',height:'100%',transform:'translate(-50%, -50%)'});card(0);update();
  }
  discover.addEventListener('click',async()=>{
   if(disposed||busy||visibilityTarget?.hidden===true)return;detach();busy=true;const ticket=generation;let created;
   try{
    created=createViewFixture({fault:fault.value||null,frameIntervalMs,firstFrameTimeoutMs,stallTimeoutMs,durationMs,maxFrames,onState:()=>{if(fixture===created)render();}});fixture=created;update();status.textContent='Discovering the internal fictional producer.';
    const found=await created.session.discover();if(disposed||ticket!==generation){created.close();return;}rows=found;selection();render();
   }catch{if(!disposed&&ticket===generation)detach('Simulation discovery refused. No live connection was attempted.');}
   finally{if(ticket===generation){busy=false;update();}}
  });
  producer.addEventListener('change',update);
  start.addEventListener('click',async()=>{
   if(disposed||busy||visibilityTarget?.hidden===true||!fixture||!rows.some(row=>row.id===producer.value))return;
   const current=fixture,ticket=generation;busy=true;update();
   try{await current.session.start(producer.value,{confirmed:true});if(!disposed&&ticket===generation)render();}
   catch{if(!disposed&&ticket===generation)render();}
   finally{if(ticket===generation){busy=false;update();}}
  });
  stop.addEventListener('click',()=>{if(!disposed)detach();});
  const pagehide=()=>{if(!disposed)detach('Preview closed on page exit. No session is replayed.');};
  const visibility=()=>{if(!disposed&&visibilityTarget?.hidden===true)detach('Preview closed while the page is hidden. Start a new session explicitly.');else update();};
  lifecycleTarget?.addEventListener?.('pagehide',pagehide);visibilityTarget?.addEventListener?.('visibilitychange',visibility);
  selection();detach();
  return Object.freeze({snapshot(){return fixture?Object.freeze({viewer:fixture.viewer.snapshot(),fixture:fixture.snapshot()}):Object.freeze({detached:true,simulation:true});},destroy(){if(disposed)return;detach('Viewer closed.');disposed=true;lifecycleTarget?.removeEventListener?.('pagehide',pagehide);visibilityTarget?.removeEventListener?.('visibilitychange',visibility);panel.remove();}});
 }
 const api=Object.freeze({mount});if(common)module.exports=api;else root.MicroDuckCameraPanel=api;
 const target=root.document?.currentScript?.dataset?.mount;if(target){const container=root.document.getElementById(target);if(container)mount(container);}
})(typeof globalThis==='object'?globalThis:this);
