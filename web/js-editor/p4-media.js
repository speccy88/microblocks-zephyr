// SPDX-License-Identifier: MPL-2.0
// Per-expression transient results. No media or site IDs are project inputs.
(function(root){
 'use strict';
 const images=new Set(['p4TakePicture','p4SmoothResize','p4RotateImage','p4FlipHorizontal','p4FlipVertical',
  '[p4:ppaResult]','[p4:imageTestPattern]','[p4:cameraResult]','[p4:imageCreate]',
  '[p4:imageResize]','[p4:imageGrayscale]','[p4:imageRGBTensor]']);
 const audio=new Set(['p4RecordPCM','[p4:audioResult]']);
 const kind=selector=>images.has(selector)?1:audio.has(selector)?2:0;
 const installed=new WeakMap();
 function install({Compiler,Decompiler,CodeManager,Morph,Point,Scripts,editor,profile,broker,core=root.P4MediaCore,
   Client=root.MicroBlocksP4MediaClient.Client,document=root.document,URL=root.URL,Blob=root.Blob,Audio=root.Audio,status=()=>{},changed=()=>{}}){
  if(profile.id!=='esp32p4')throw Error('Inline media requires the P4 profile.');
  if(installed.has(Compiler))return installed.get(Compiler);
  for(const [object,name] of [[Compiler.prototype,'emitExpression'],[Decompiler.prototype,'buildCmdOrReporter'],
    [Decompiler.prototype,'primSetNameForIndex'],[CodeManager.prototype,'evalOnBoard'],[CodeManager.prototype,'syncAndStartAll']]){
   if(typeof object[name]!=='function')throw Error('Pinned media hooks changed; review upstream.');
  }
  let next=0,session=0,project=editor()?.project,closed=false;
  const sites=new Map(),ids=new WeakMap();
  function attached(block,held=false){
   for(let node=block;node?.parent;node=node.parent){
    if(!node.parent.children.includes(node))return false;
    if(node.parent===editor()?.scripts)return true;
    if(held&&node.parent===editor()?.scripts?.world()?.hand)return true;
   }return false;
  }
  const present=block=>!!block&&attached(block);
  const notify=()=>{try{changed();}catch{}};
  const cache=new core.Cache((uid,item)=>{
   if(item.audio){item.audio.pause();item.audio.removeAttribute?.('src');item.audio.load?.();}
   if(item.url)URL.revokeObjectURL(item.url);
   if(item.canvas){item.canvas.width=0;item.canvas.height=0;}
   const m=sites.get(uid);if(m){m.item=null;m.state='expired';layout(m);}notify();
  });
  function emptyPart(isBreak=false){
   const p=new Morph();p.p4TransientPart=true;p.isBlockLabelBreak=isBreak;p.setExtent(new Point(0,0));
   p.holes=[];p.fixHolesLayout=()=>{};p.getSpec=()=>isBreak?'#BR#':'';
   p.copyRecordingReferences=function(map){const copy=emptyPart(isBreak);map.set(this,copy);return copy;};
   return p;
  }
  function layout(m){
   const scale=m.block.scale||1,item=m.item,w=160,h=item?.kind===1?Math.max(1,Math.round(item.meta.height*Math.min(w/item.meta.width,90/item.meta.height))):24;
   m.view.setExtent(new Point(w*scale,(22+(m.expanded&&item?h:0))*scale));m.view.rerender();
   if(m.view.parent===m.block)m.block.fixLayout();
  }
  function toggle(uid){const m=sites.get(uid);if(!m)return;m.userCollapsed=m.expanded;m.expanded=!m.expanded;layout(m);notify();}
  async function play(uid){
   const m=sites.get(uid),a=m?.item?.audio;if(!a)return;
   if(!a.paused){a.pause();notify();return;}
   for(const item of cache.items.values())if(item.audio&&item.audio!==a)item.audio.pause();
   try{await a.play();}catch(e){status('Audio playback unavailable: '+e.message);}notify();
  }
  function ensure(block){
   if(closed||!kind(block?.selector)||!present(block))return null;
   let m=sites.get(ids.get(block));if(m&&m.view.parent===block)return m;
   if(m)remove(m.uid);
   // Duplicated morph children are deliberately empty and own no result/ID.
   for(const p of [...block.children])if(p.p4TransientPart)p.destroy();
   if(sites.size>=128||next>=root.MicroBlocksP4MediaClient.MAX_ID)throw Error('Too many inline media sites; reopen the project.');
   const uid=++next,br=emptyPart(true),view=emptyPart();
   m={uid,block,br,view,kind:kind(block.selector),state:'empty',expanded:false,userCollapsed:false,item:null};
   sites.set(uid,m);ids.set(block,uid);
   view.isCachingImage=false;
   view.render=function(ctx){
    const s=block.scale||1,item=m.item;ctx.fillStyle='#eef3f6';ctx.fillRect(0,0,this.width(),this.height());
    ctx.fillStyle='#17212b';ctx.font=(12*s)+'px sans-serif';
    const label=item?(m.kind===1?'Image '+item.meta.width+'×'+item.meta.height:'Audio '+(item.meta.frames/item.meta.rate).toFixed(2)+' s'):(m.kind===1?'Image':'Audio')+' ('+m.state+')';
    ctx.fillText((m.expanded?'− ':'+ ')+label,4*s,15*s);
    if(m.expanded&&item){if(item.canvas){const fit=Math.min(160/item.meta.width,90/item.meta.height)*s,w=item.meta.width*fit,h=item.meta.height*fit;ctx.drawImage(item.canvas,(this.width()-w)/2,22*s,w,h);}
     else ctx.fillText(item.audio.paused?'▶ Play':'Ⅱ Pause',4*s,39*s);}
   };
   view.mouseDownLeft=()=>{};
   view.mouseClickLeft=pos=>{if(m.expanded&&m.item?.audio&&pos.y-view.top()>22*(block.scale||1))void play(uid);else toggle(uid);};
   block.add(br);block.add(view);layout(m);notify();return m;
  }
  function expire(uid){cache.drop(uid);const m=sites.get(uid);if(m){m.state='expired';layout(m);}notify();}
  function clearResults(){if(session)client?.discard();cache.clear();for(const m of sites.values()){m.state='expired';layout(m);}notify();}
  function remove(uid){const m=sites.get(uid);if(!m)return;cache.drop(uid);sites.delete(uid);ids.delete(m.block);m.view.destroy();m.br.destroy();m.block.fixLayout();notify();}
  function tick(){
   if(closed)return;
   if(project!==editor()?.project){clearResults();for(const uid of [...sites.keys()])remove(uid);project=editor()?.project;return;}
   for(const [uid,m] of sites){
    // A held morph may temporarily be under the hand, but a detached/deleted
    // morph must not retain result data. Restoring it allocates a fresh site.
    if(!attached(m.block,true)||m.view.parent!==m.block||!m.block.children.includes(m.view))remove(uid);
    else if(m.scale!==m.block.scale){m.scale=m.block.scale;layout(m);}
   }
  }
  function apply(uid,meta,raw){
   const m=sites.get(uid);if(!m||!present(m.block))return;
   core.metadata(meta);if(meta.kind!==m.kind)throw Error('Result kind differs from the producing block.');
   let item;
   if(meta.kind===1){
    const canvas=document.createElement('canvas');canvas.width=meta.width;canvas.height=meta.height;
    const rgba=core.rgba(meta,raw),ctx=canvas.getContext('2d'),pixels=ctx.createImageData(meta.width,meta.height);
    try{pixels.data.set(rgba);ctx.putImageData(pixels,0,0);}finally{rgba.fill(0);pixels.data.fill(0);}
    item={kind:1,meta:{...meta},canvas,cost:raw.length+meta.width*meta.height*4};
   }else{
    const bytes=core.wav(meta,raw);let url;
    try{url=URL.createObjectURL(new Blob([bytes],{type:'audio/wav'}));}finally{bytes.fill(0);}
    try{const sound=new Audio();sound.preload='none';sound.src=url;sound.onended=()=>{m.view.rerender();notify();};
     item={kind:2,meta:{...meta},url,audio:sound,cost:raw.length+44};
    }catch(e){URL.revokeObjectURL(url);throw e;}
   }
   cache.put(uid,item);m.item=item;m.state='ready';m.expanded=!m.userCollapsed;layout(m);notify();
  }
  let client;
  client=new Client(broker,core,{known:uid=>{tick();const m=sites.get(uid);return !!m&&present(m.block);},result:apply,expired:expire,status,
   session:value=>{session=value;cache.clear();if(editor()?.codeManager)editor().codeManager.recompileAll=true;notify();}});
  const emit=Compiler.prototype.emitExpression,names=Decompiler.prototype.primSetNameForIndex,build=Decompiler.prototype.buildCmdOrReporter;
  Compiler.prototype.emitExpression=function(expr){
   const instructions=emit.call(this,expr);if(!session||!kind(expr?.selector)||!present(expr))return instructions;
   tick();const m=ensure(expr);return [...instructions,...emit.call(this,m.uid),...emit.call(this,session),['reporterPrimitive','mediaSnapshot','p4',3],['placeholder',0]];
  };
  Decompiler.prototype.primSetNameForIndex=function(compiler,index){
   const entry=Object.entries(profile.primitive_sets).find(([,value])=>value===index);return entry?entry[0]:names.call(this,compiler,index);
  };
  Decompiler.prototype.buildCmdOrReporter=function(op,count,reporter){
   const node=build.call(this,op,count,reporter);
   if(op!=='[p4:mediaSnapshot]'&&op!=='[io:mediaSnapshot]')return node;
   const [value,uid,sid]=node.args;
   if(!reporter||count!==3||!value?.isReporter||!kind(value.selector)||![uid,sid].every(n=>Number.isInteger(n)&&n>0&&n<=root.MicroBlocksP4MediaClient.MAX_ID))throw Error('Unsupported inline media wrapper in board readback.');
   return value;
  };
  const evaluate=CodeManager.prototype.evalOnBoard,start=CodeManager.prototype.syncAndStartAll,stop=CodeManager.prototype.stopAndSyncScripts;
  let preparing=false;
  async function run(manager,fn,args,sync){
   if(preparing){status('Wait for the current run preparation.');return;}
   preparing=true;const current=editor(),active=()=>editor()===current&&current?.codeManager===manager&&current.project===manager.project;
   try{
    if(!active())return await fn.apply(manager,args);
    if(!(await current.saveBeforeRun())||!active())return;
    clearResults();
    if(active()&&broker.available()){
     try{await client.renew();}catch(e){status('Inline media unavailable: '+e.message);}
     if(!active())return;
     if(sync&&session)await manager.syncScripts();
     if(!active())return;
    }
    if(active())return await fn.apply(manager,args);
   }finally{preparing=false;}
  }
  CodeManager.prototype.evalOnBoard=function(...args){return run(this,evaluate,args,true);};
  CodeManager.prototype.syncAndStartAll=function(...args){return run(this,start,args,false);};
  CodeManager.prototype.stopAndSyncScripts=function(...args){clearResults();return stop.apply(this,args);};
  const timer=root.setInterval(tick,200);
  const api={client,sites,cache,ensure,apply,expire,clearResults,tick,toggle,play,
   get session(){return session;},
   close(){if(closed)return;closed=true;root.clearInterval(timer);client.close();cache.clear();for(const uid of [...sites.keys()])remove(uid);}};
  installed.set(Compiler,api);return api;
 }
 const api=Object.freeze({install,kind});root.MicroBlocksP4Media=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
