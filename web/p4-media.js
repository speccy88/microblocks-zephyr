/* SPDX-License-Identifier: MPL-2.0 */
(()=>{
 'use strict';
 const core=P4MediaCore,decoder=new TextDecoder(),pending=new Map(),latest=new Map(),queued=new Set(),elements=new Map();
 let gp,layer,layout,online=false,session=0,nextRequest=0,epoch=0,fetching=false,activeUID=null,audio=null;
 // GP services the last queued API call first. Serialize our lifecycle calls,
 // otherwise an older expiry can run after a replacement has been displayed.
 const call=core.serialCalls((name,args=[])=>gp?gp.call(name,args):Promise.reject(Error('Editor is loading.')));
 const expire=uid=>{void call('p4.media.expire',[uid]).catch(()=>{});};
 function stopAudio(){if(audio){audio.pause();audio.removeAttribute('src');audio.load();audio=null;}activeUID=null;buttons();}
 const cache=new core.Cache((uid,item,reason)=>{if(activeUID===uid)stopAudio();if(item.url)URL.revokeObjectURL(item.url);if(reason!=='replace')expire(uid);});
 function rpc(op,token=0,uid=0,offset=0,count=0,nonce=session){
  return new Promise((resolve,reject)=>{
   const id=nextRequest=(nextRequest+1)>>>0||1,wire=core.packet(id,op,nonce,token,offset,count,uid);
   const timer=setTimeout(()=>{pending.delete(id);reject(Error('Result transfer timed out.'));},4000);
   pending.set(id,{resolve,reject,timer,op,session:nonce,token});
   if(!window.P4Send||P4Send(wire)!==wire.length){clearTimeout(timer);pending.delete(id);reject(Error('Board is disconnected.'));}
  });
 }
 function reset(){
  epoch++;session=0;queued.clear();latest.clear();stopAudio();cache.clear();
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Result session changed.'));}pending.clear();
  for(const node of elements.values())node.remove();elements.clear();
  void call('p4.media.enable',[0]).catch(()=>{});
 }
 async function negotiate(){
  const stamp=epoch;
  try{
   const caps=JSON.parse(decoder.decode(await rpc(0,0,0,0,0,0)));
   if(caps.protocol!==1||caps.chunk_bytes!==512||stamp!==epoch)return;
   const random=new Uint32Array(1);crypto.getRandomValues(random);session=(random[0]&0x1fffffff)||1;
   await rpc(1);if(stamp!==epoch)return;
   await call('p4.media.enable',[session]);
  }catch{if(stamp===epoch){session=0;void call('p4.media.enable',[0]).catch(()=>{});}}
 }
 window.addEventListener('p4-vm-frame',event=>{
  const frame=event.detail;if(!(frame instanceof Uint8Array)||frame[0]!==251)return;
  const body=frame.subarray(5),v=new DataView(body.buffer,body.byteOffset,body.byteLength);
  if(frame[1]===208 && body.length>=14){
   const id=v.getUint32(0,true),p=pending.get(id);
   if(!p||p.op!==body[5]||p.session!==v.getUint32(6,true)||p.token!==v.getUint32(10,true))return;
   pending.delete(id);clearTimeout(p.timer);body[4]?p.reject(Error('Result expired or unavailable.')):p.resolve(body.slice(14));
  }else if(frame[1]===209 && body.length===12 && session && v.getUint32(0,true)===session){
   const uid=v.getUint32(4,true),token=v.getUint32(8,true);if(!uid||uid>0x1fffffff)return;
   if(latest.size>=512&&!latest.has(uid))latest.delete(latest.keys().next().value);
   latest.set(uid,token);
   if(!token){queued.delete(uid);cache.drop(uid);expire(uid);return;}
   if(queued.size>=16&&!queued.has(uid)){const old=queued.values().next().value;queued.delete(old);expire(old);}
   queued.add(uid);void fetchQueue();
  }
 });
 async function apply(uid,meta,raw,nonce=session,stored=false){
  core.metadata(meta);if(raw.length!==meta.bytes)throw Error('Short result payload.');
  let png='',item={kind:meta.kind,meta,stored,cost:meta.bytes};
  if(meta.kind===1){
   const canvas=document.createElement('canvas');canvas.width=meta.width;canvas.height=meta.height;
   const ctx=canvas.getContext('2d'),pixels=ctx.createImageData(meta.width,meta.height);pixels.data.set(core.rgba(meta,raw));ctx.putImageData(pixels,0,0);
   png=canvas.toDataURL('image/png').split(',')[1];item.cost+=meta.width*meta.height*4;
  }else{
   const bytes=core.wav(meta,raw);item.cost=bytes.length;item.url=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));bytes.fill(0);
  }
  cache.put(uid,item);
  if(!await call('p4.media.result',[uid,nonce,meta.kind,png,meta]))cache.drop(uid);
  place();
 }
 async function fetchQueue(){
  if(fetching)return;fetching=true;
  try{while(queued.size){
   const uid=queued.values().next().value;queued.delete(uid);
   const token=latest.get(uid),nonce=session,stamp=epoch;let raw;
   try{
    if(!token||!nonce)continue;
    const meta=core.metadata(JSON.parse(decoder.decode(await rpc(2,token,uid))));raw=new Uint8Array(meta.bytes);
    for(let offset=0;offset<raw.length;offset+=512){
     if(stamp!==epoch||latest.get(uid)!==token)throw Error('Newer result replaced this transfer.');
     const count=Math.min(512,raw.length-offset),chunk=await rpc(3,token,uid,offset,count,nonce);
     if(chunk.length!==count)throw Error('Short result chunk.');raw.set(chunk,offset);
    }
    if(stamp===epoch&&latest.get(uid)===token)await apply(uid,meta,raw,nonce);
   }catch{if(stamp===epoch&&latest.get(uid)===token){cache.drop(uid);expire(uid);}}
   finally{if(raw)raw.fill(0);if(nonce===session)void rpc(4,token,uid).catch(()=>{});}
  }}finally{fetching=false;}
 }
 function buttons(){
  for(const [uid,node]of elements){const play=node.querySelector('[data-play]');if(play)play.textContent=activeUID===uid&&audio&&!audio.paused?'Pause':'Play';}
 }
 async function play(uid){
  const item=cache.get(uid);if(!item?.url)return;
  if(activeUID===uid&&audio){if(!audio.paused)audio.pause();else await audio.play().catch(()=>{});buttons();return;}
  stopAudio();audio=new Audio(item.url);audio.preload='none';activeUID=uid;
  const instance=audio;audio.onended=()=>{if(audio===instance)instance.currentTime=0;buttons();};audio.onpause=buttons;
  await audio.play().catch(()=>{stopAudio();});buttons();
 }
 function make(uid){
  const node=document.createElement('section');node.className='p4-inline-result';node.dataset.block=uid;node.setAttribute('role','group');
  const title=document.createElement('span');title.dataset.title='';node.append(title);
  const toggle=document.createElement('button');toggle.type='button';toggle.dataset.toggle='';node.append(toggle);
  toggle.onclick=event=>{event.stopPropagation();const row=layout?.views.find(v=>v[0]===uid);if(!row)return;if(row[6]&&activeUID===uid)stopAudio();void call('p4.media.toggle',[uid,!row[6]]).catch(()=>{});};
  const playButton=document.createElement('button');playButton.type='button';playButton.dataset.play='';playButton.textContent='Play';node.append(playButton);
  playButton.onclick=event=>{event.stopPropagation();void play(uid);};
  for(const button of[toggle,playButton]){button.onpointerdown=e=>e.stopPropagation();button.onkeydown=e=>e.stopPropagation();}
  layer.append(node);return node;
 }
 function place(){
  if(!layer||!layout)return;const canvas=document.getElementById('canvas');if(!canvas||!canvas.width)return;
  layer.hidden=!!document.querySelector('.portal-tools[open]');
  const rect=canvas.getBoundingClientRect(),sx=rect.width/canvas.width,sy=rect.height/canvas.height,clip=layout.clip;
  const seen=new Set();
  for(const row of layout.views){
   const[uid,kind,x,y,w,h,expanded,state,sourceW,sourceH,frames,rate,op]=row;
   if(!Number.isInteger(uid)||uid<1||![1,2].includes(kind)||![x,y,w,h].every(Number.isFinite))continue;
   seen.add(uid);let node=elements.get(uid);if(!node){node=make(uid);elements.set(uid,node);}
   const width=w*sx,height=h*sy,zoom=width/160;
   node.style.cssText=`left:${rect.left+x*sx}px;top:${rect.top+y*sy}px;width:${width}px;height:${height}px;--zoom:${zoom};`;
   const inset=[Math.max(0,(clip[1]-y)*sy),Math.max(0,(x+w-clip[0]-clip[2])*sx),Math.max(0,(y+h-clip[1]-clip[3])*sy),Math.max(0,(clip[0]-x)*sx)];
   node.style.clipPath=`inset(${inset.map(n=>n+'px').join(' ')})`;
   const cached=cache.items.get(uid),name=kind===1?'Image':'Audio';node.setAttribute('aria-label',`${name} result for ${op}`);
   const text=state==='ready'?(kind===1?`${sourceW} × ${sourceH}`:`${(frames/rate).toFixed(2)} s`):state==='expired'?'Result expired':`No ${name.toLowerCase()} yet`;
   node.querySelector('[data-title]').textContent=(cached?.stored?'Stored · ':'')+text;
   const toggle=node.querySelector('[data-toggle]');toggle.textContent=expanded?'−':'+';toggle.disabled=state!=='ready';toggle.setAttribute('aria-expanded',String(!!expanded));toggle.setAttribute('aria-label',`${expanded?'Hide':'Show'} ${name.toLowerCase()} result`);
   const player=node.querySelector('[data-play]');player.hidden=kind!==2||!expanded;player.disabled=!cached?.url;player.style.top=(24*zoom)+'px';player.setAttribute('aria-label','Play or pause captured audio');
  }
  for(const[uid,node]of elements)if(!seen.has(uid)){node.remove();elements.delete(uid);}
  buttons();
 }
 document.addEventListener('p4.media.layout',event=>{const value=event.detail.value;if(value&&Array.isArray(value.views)&&value.views.length<=128&&Array.isArray(value.clip)&&value.clip.length===4){layout=value;place();}});
 document.addEventListener('p4.media.reset',()=>{reset();if(online)void negotiate();});
 document.addEventListener('p4.media.run',()=>{stopAudio();for(const[uid,item]of[...cache.items])if(item.kind===2)cache.drop(uid);});
 document.addEventListener('board.type',event=>{const type=event.detail.value;if(typeof type==='string'&&type.startsWith('Waveshare ESP32-P4')){if(!online){online=true;void negotiate();}}else if(!type||type==='Connect'){if(online){online=false;reset();}}});
 document.addEventListener('board-ide-ready',()=>{gp=new MicroBlocksPortal.EditorAPI(GP,document);layer=document.createElement('div');layer.id='p4-inline-results';document.body.append(layer);place();});
 window.addEventListener('resize',place);window.addEventListener('pagehide',()=>{online=false;reset();});
 document.addEventListener('toggle',place,true);
 // Explicit local stored-result import used by renderer acceptance tests. It
 // targets existing real block IDs, never creates cards or executes blocks.
 window.P4Media={loadStored:async(uid,meta,bytes)=>apply(uid,meta,new Uint8Array(bytes),session,true),
  stats:()=>({session,cacheBytes:cache.bytes,cacheEntries:cache.items.size,pending:pending.size,queued:queued.size,playing:activeUID}),
  clear:()=>{cache.clear();stopAudio();}};
})();
