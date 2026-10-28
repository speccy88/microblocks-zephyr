// SPDX-License-Identifier: MPL-2.0
// Faithful RPC208/209 fixture; no camera, microphone, robot or P4 hardware.
'use strict';
const assert=require('node:assert/strict'),{load}=require('./support/js_editor_headless.cjs');
const core=require('../web/p4-media-core.js'),{Client}=require('../web/js-editor/p4-media-client.js');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function until(check){for(let i=0;i<1000;i++){if(check())return;await tick();}throw Error('Media fixture deadline exceeded.');}
const caps={protocol:1,slots:4,budget:524288,image_width:160,image_height:90,audio_frames:128000,chunk_bytes:512};
const image={kind:1,width:3,height:2,source_width:3,source_height:2,format:3,bytes:18};
const pcm={kind:2,frames:32,rate:16000,channels:1,bytes:64};
function brokerFixture(){
 const listeners=new Set(),states=new Set(),sent=[],slots=new Map();let state={epoch:0,verified:false},hold=false,capsValue=caps,short=false;
 function frame(type,body){const f=new Uint8Array([251,type,0,body.length&255,body.length>>8,...body]);for(const fn of listeners)fn(f);}
 const broker={subscribe(fn){listeners.add(fn);return()=>listeners.delete(fn);},subscribeState(fn){states.add(fn);fn(state);return()=>states.delete(fn);},available:()=>state.verified,
  send(bytes){const f=new Uint8Array(bytes);sent.push(f);if(!hold)queueMicrotask(()=>reply(f));return f.length;}};
 function reply(f,{data,status=0,op,id,session,token}={}){
  const v=new DataView(f.buffer,f.byteOffset),action=f[9],uid=v.getUint32(29,true),slot=slots.get(uid),offset=v.getUint32(23,true),count=v.getUint16(27,true);
  if(data===undefined){if(action===0||action===1)data=Buffer.from(JSON.stringify(capsValue));
   else if(action===2&&slot)data=Buffer.from(JSON.stringify(slot.meta));
   else if(action===3&&slot)data=slot.raw.slice(offset,offset+count-(short?1:0));
   else data=new Uint8Array();}
  const body=new Uint8Array(14+data.length),out=new DataView(body.buffer);out.setUint32(0,id??v.getUint32(11,true),true);body[4]=status;body[5]=op??action;
  out.setUint32(6,session??v.getUint32(15,true),true);out.setUint32(10,token??v.getUint32(19,true),true);body.set(data,14);frame(208,body);
 }
 return {broker,sent,slots,reply,set hold(v){hold=v;},set short(v){short=v;},set caps(v){capsValue=v;},
  state(verified){state={epoch:state.epoch+1,verified};for(const fn of states)fn(state);},
  event(session,uid,token){const b=new Uint8Array(12),v=new DataView(b.buffer);v.setUint32(0,session,true);v.setUint32(4,uid,true);v.setUint32(8,token,true);frame(209,b);},
  get subscriptions(){return listeners.size+states.size;}};
}
async function clientFixture(options={}){
 const f=brokerFixture(),results=[],expired=[],messages=[];
 const client=new Client(f.broker,core,{known:uid=>uid<200,result:(uid,meta,raw)=>results.push({uid,meta,copy:[...raw],raw}),expired:uid=>expired.push(uid),status:m=>messages.push(m),timeout:100,...options});
 f.state(true);await until(()=>client.session||messages.length);return {...f,f,client,results,expired,messages};
}
async function actual(){
 const h=load(process.argv[2]),f=brokerFixture(),revoked=[],played=[];
 class FakeAudio{constructor(){this.paused=true;}pause(){this.paused=true;}async play(){played.push(this);this.paused=false;}removeAttribute(){}load(){}}
 h.set('mediaBroker',f.broker);h.set('fixtureURL',{createObjectURL:()=> 'blob:fixture-'+Math.random(),revokeObjectURL:u=>revoked.push(u)});h.set('FixtureAudio',FakeAudio);
 h.evaluate(`MB_editor.project=new MB_Project();MB_editor.scripts=new ScriptsMorph();
  globalThis.media=MicroBlocksP4Media.install({Compiler:MB_Compiler,Decompiler:MB_Decompiler,CodeManager:MB_CodeManager,Morph,Point,Scripts:ScriptsMorph,editor:()=>MB_editor,profile:MicroBlocksJSProfile,broker:mediaBroker,URL:fixtureURL,Audio:FixtureAudio});`);
 const media=h.evaluate('media');f.state(true);await until(()=>media.session);return {h,f,media,revoked,played,close:()=>media.close()};
}
function project(h,text='module main\nscript 20 30 ([p4:imageGrayscale] ([p4:imageTestPattern] 3 2 3))\n'){
 h.set('sourceText',text);h.evaluate(`MB_editor.project.loadFromString(sourceText);globalThis.block=MB_editor.project.main.scripts[0][2];MB_editor.scripts.add(block);globalThis.beforeText=MB_editor.project.codeString();`);
}
async function main(){let passed=0;async function test(name,fn){try{await fn();passed++;}catch(e){e.message=name+': '+e.message;throw e;}}
 await test('negotiation, exact transfer, raw zeroing and token release',async()=>{const t=await clientFixture();try{
  assert(t.client.session>0);t.f.slots.set(7,{meta:image,raw:new Uint8Array(18).fill(71)});t.f.event(t.client.session,7,39);
  await until(()=>!t.client.fetching&&t.results.length===1);assert.deepEqual(t.results[0].copy,new Array(18).fill(71));assert(t.results[0].raw.every(x=>x===0));assert.equal(t.sent.at(-1)[9],4);
 }finally{t.client.close();assert.equal(t.f.subscriptions,0);}});
 await test('reject unavailable metadata, short data, wrong reply and stale events',async()=>{const t=await clientFixture();try{
  t.f.slots.set(2,{meta:image,raw:new Uint8Array(18)});t.f.short=true;t.f.event(t.client.session,2,21);await until(()=>!t.client.fetching);assert(t.expired.includes(2));assert.equal(t.results.length,0);
  t.f.event(t.client.session+1,2,22);t.f.event(t.client.session,999,23);await tick();assert.equal(t.client.queued.size,0);
  t.f.hold=true;const request=t.client.request(2,9,2);t.f.reply(t.sent.at(-1),{op:3});await assert.rejects(request,/does not match/);
  t.f.hold=false;t.f.slots.set(2,{meta:{...image,bytes:9999999},raw:new Uint8Array(18)});t.f.event(t.client.session,2,24);await until(()=>!t.client.fetching);assert.equal(t.results.length,0);
 }finally{t.client.close();}});
 await test('disconnect cancels pending reads and never releases into a new session',async()=>{const t=await clientFixture();try{
  t.f.hold=true;t.f.slots.set(1,{meta:image,raw:new Uint8Array(18)});t.f.event(t.client.session,1,5);await until(()=>t.client.pending?.op===2);const old=t.sent.at(-1);
  t.f.state(false);await until(()=>!t.client.fetching);assert.equal(t.client.session,0);t.f.reply(old);assert.equal(t.results.length,0);
  t.f.hold=false;t.f.state(true);await until(()=>t.client.session);assert.equal(t.sent.filter(x=>x[9]===4).length,0);
 }finally{t.client.close();}});
 await test('capability refusal and deadlines do not enable instrumentation',async()=>{
  const f=brokerFixture(),messages=[],c=new Client(f.broker,core,{timeout:10,status:m=>messages.push(m)});f.caps=null;f.state(true);await until(()=>messages.length);assert.equal(c.session,0);assert.match(messages[0],/require review/);c.close();
  const g=brokerFixture(),d=new Client(g.broker,core,{timeout:10});g.hold=true;g.state(true);await tick();d.discard();await tick();await assert.rejects(d.request('3'),/bounds/);await assert.rejects(d.request(2),/timed out/);d.close();
 });
 await test('notification queue and site table are bounded and zero tokens expire',async()=>{const t=await clientFixture();try{
  t.f.hold=true;for(let i=1;i<=199;i++)t.f.event(t.client.session,i,i);assert(t.client.queued.size<=16);assert(t.client.latest.size<=128);
  t.f.event(t.client.session,2,0);assert(t.expired.includes(2));t.client.discard();assert.equal(t.client.latest.size,0);assert.equal(t.client.queued.size,0);
 }finally{t.client.close();await until(()=>!t.client.fetching);}});
 await test('rerun sessions reject delayed notifications after clear and renewal',async()=>{const t=await clientFixture();try{
  const old=t.client.session;t.client.discard();t.f.event(old,1,5);assert.equal(t.client.latest.size,0);
  await t.client.renew();assert.notEqual(t.client.session,old);t.f.event(old,1,6);assert.equal(t.client.latest.size,0);
  t.f.slots.set(1,{meta:image,raw:new Uint8Array(18)});t.f.event(t.client.session,1,7);await until(()=>t.results.length===1&&!t.client.fetching);
 }finally{t.client.close();}});
 await test('actual compiler nested instrumentation and source invariance',async()=>{const t=await actual();try{project(t.h);
  const ir=t.h.evaluate('new MB_Compiler(MB_editor.project).instructionsForExpression(block)');assert.equal(ir.filter(x=>x[0]==='reporterPrimitive'&&x[1]==='mediaSnapshot').length,2);
  assert.equal(t.media.sites.size,2);assert.equal(t.h.evaluate('MB_editor.project.codeString()===beforeText'),true);assert.equal(t.h.evaluate('block.inputs().length'),1);
  const detached=t.h.evaluate('block.fullCopy()');t.h.set('detached',detached);const plain=t.h.evaluate('new MB_Compiler(MB_editor.project).instructionsForExpression(detached)');assert.equal(plain.filter(x=>x[1]==='mediaSnapshot').length,0);
  t.f.state(false);const offline=t.h.evaluate('new MB_Compiler(MB_editor.project).instructionsForExpression(block)');assert.equal(offline.filter(x=>x[1]==='mediaSnapshot').length,0);
 }finally{t.close();}});
 await test('actual bytecode readback strips generated sites and canonicalizes namespace',async()=>{const t=await actual();try{project(t.h);
  t.h.evaluate('globalThis.bytes=new MB_Compiler(MB_editor.project).compiledBytesFor(block);while(bytes.length%4)bytes.push(0);globalThis.decoder=new MB_Decompiler();decoder.addChunk(0,2,new Uint8Array(bytes));');
  const decoded=await t.h.evaluate('decoder.decompileProject()');t.h.set('decoded',decoded);const text=t.h.evaluate('decoded.codeString()');assert(!text.includes('mediaSnapshot'));assert(!text.includes('[io:'));assert(text.includes('[p4:imageGrayscale]'));assert(text.includes('[p4:imageTestPattern]'));
  t.h.evaluate('globalThis.badDecoder=new MB_Decompiler();badDecoder.stack=[{selector:"+",args:[1,2],isReporter:true},3,4];');assert.throws(()=>t.h.evaluate('badDecoder.buildCmdOrReporter("[p4:mediaSnapshot]",3,true)'),/Unsupported/);
 }finally{t.close();}});
 await test('preserved named helper wraps its returned handle; hidden body stays unchanged',async()=>{const t=await actual();try{
  const fs=require('node:fs'),path=require('node:path'),profile=JSON.parse(fs.readFileSync(path.join(process.argv[2],'target-profile.json')));
  const bundle=fs.readFileSync(path.join(process.argv[2],profile.bundle),'utf8');project(t.h,'module main\nscript 20 30 (p4TakePicture)\n');t.h.set('helperBundle',bundle);
  t.h.evaluate('MB_editor.project.addLibraryFromString(helperBundle,"P4","//Libraries/P4");beforeText=MB_editor.project.codeString();');
  t.h.evaluate('globalThis.helperManager=new MB_CodeManager(MB_editor.project);helperManager.functionChunkIDs.set("p4TakePicture",23);globalThis.helperCompiler=new MB_Compiler(MB_editor.project,helperManager);');
  const ir=t.h.evaluate('helperCompiler.instructionsForExpression(block)');assert.equal(ir[0][0],'callFunction');assert.equal(ir[0][1],23<<8);assert.equal(ir.filter(x=>x[1]==='mediaSnapshot').length,1);
  const before=t.media.sites.size;t.h.evaluate('helperCompiler.instructionsFor(MB_editor.project.functionNamed("p4TakePicture"))');assert.equal(t.media.sites.size,before);
  assert.equal(t.h.evaluate('MB_editor.project.codeString()===beforeText'),true);
 }finally{t.close();}});
 await test('actual code manager recompiles before each explicit run with fresh media IDs',async()=>{const t=await actual();try{project(t.h);
  t.h.evaluate(`globalThis.manager=new MB_CodeManager(MB_editor.project);MB_editor.codeManager=manager;globalThis.calls={sync:0,run:0};
   MB_editor.saveBeforeRun=async()=>true;MB_connection.updateConnection=()=> 'connected';
   manager.syncScripts=async()=>{calls.sync++;manager.chunkIDs.set(manager.chunkKeyFor(block),[17,null,2,'',false,false]);};manager.runChunk=()=>calls.run++;`);
  const initial=t.media.session;await t.h.evaluate('manager.evalOnBoard(block)');const first=t.media.session;assert.notEqual(initial,first);
  await t.h.evaluate('manager.evalOnBoard(block)');assert.notEqual(first,t.media.session);assert.equal(t.h.evaluate('calls.sync'),2);assert.equal(t.h.evaluate('calls.run'),2);
  t.h.evaluate('MB_editor.saveBeforeRun=async()=>false');await t.h.evaluate('manager.evalOnBoard(block)');assert.equal(t.h.evaluate('calls.run'),2);assert.equal(t.h.evaluate('calls.sync'),2);
  t.h.evaluate('MB_editor.saveBeforeRun=async()=>{MB_editor.project=new MB_Project();return true;}');await t.h.evaluate('manager.evalOnBoard(block)');assert.equal(t.h.evaluate('calls.run'),2);assert.equal(t.h.evaluate('calls.sync'),2);
 }finally{t.close();}});
 await test('actual morph copies have no result/identity; restore, deletion and project cleanup',async()=>{const t=await actual();try{project(t.h);t.h.evaluate('new MB_Compiler(MB_editor.project).instructionsForExpression(block)');const top=t.media.ensure(t.h.evaluate('block'));
  t.media.apply(top.uid,image,new Uint8Array(18));const source=t.h.evaluate('block.codeString()');t.h.evaluate('globalThis.copy=block.fullCopy();MB_editor.scripts.add(copy);');const copied=t.media.ensure(t.h.evaluate('copy'));
  assert.notEqual(copied.uid,top.uid);assert.equal(copied.item,null);assert.equal(t.h.evaluate('copy.codeString()'),source);assert.equal(copied.view.parent,copied.block);
  t.h.evaluate('block.destroy()');t.media.tick();assert(!t.media.sites.has(top.uid));assert.equal(top.item,null);
  t.h.evaluate('MB_editor.scripts.add(block)');const restored=t.media.ensure(t.h.evaluate('block'));assert.notEqual(restored.uid,top.uid);assert.equal(restored.item,null);
  t.h.evaluate('MB_editor.project=new MB_Project()');t.media.tick();assert.equal(t.media.sites.size,0);assert.equal(t.media.cache.bytes,0);
 }finally{t.close();}});
 await test('collapse, zoom, explicit audio, eviction and URL disposal',async()=>{const t=await actual();try{
  project(t.h,'module main\nscript 20 30 ([p4:audioResult])\n');const first=t.media.ensure(t.h.evaluate('block'));t.media.apply(first.uid,pcm,new Uint8Array(64));assert.equal(t.played.length,0);assert(first.expanded);
  t.media.toggle(first.uid);t.media.clearResults();t.media.apply(first.uid,pcm,new Uint8Array(64));assert(!first.expanded);assert.equal(t.revoked.length,1);await t.media.play(first.uid);assert.equal(t.played.length,1);
  for(let i=0;i<2;i++){t.h.evaluate('globalThis.extra=block.fullCopy();MB_editor.scripts.add(extra);');const m=t.media.ensure(t.h.evaluate('extra'));t.media.apply(m.uid,pcm,new Uint8Array(64));}
  assert.equal(t.media.cache.items.size,2);assert.equal(first.item,null);assert(t.played[0].paused);assert(t.revoked.length>=2);
  const last=[...t.media.sites.values()].at(-1);const oldHeight=last.view.height();last.block.scale=2;t.media.tick();assert.equal(last.view.height(),oldHeight*2);
  t.media.close();assert.equal(t.media.cache.bytes,0);assert.equal(t.revoked.length,4);
 }finally{t.close();}});
 console.log(JSON.stringify({passed,actual_pinned_compiler_decompiler_morphs:true,protocol_fixture:true,physical_hardware:false,graphical:false}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
