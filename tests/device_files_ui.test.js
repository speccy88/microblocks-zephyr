/* SPDX-License-Identifier: MIT */
// Actual UI module with a minimal synthetic DOM/connection. No browser/board I/O.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const core=require('../web/device-files-core.js'),fixture=require('../web/device-files-fixture.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function until(fn){for(let i=0;i<200;i++){if(fn())return;await tick();}assert.fail('Synthetic UI did not settle');}

class Element {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.events={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';this.open=false;}
 append(...nodes){for(const node of nodes){node.parent=this;this.children.push(node);}}
 prepend(node){node.parent=this;this.children.unshift(node);}
 replaceChildren(...nodes){this.children=[];this.append(...nodes);}
 setAttribute(name,value){this[name]=value;}
 removeAttribute(name){delete this[name];}
 addEventListener(name,fn){this.events[name]=fn;}
 querySelectorAll(tag){return this.children.flatMap(c=>[...(c.tag===tag?[c]:[]),...c.querySelectorAll(tag)]);}
 querySelector(tag){return this.querySelectorAll(tag)[0]||null;}
 closest(){return null;}
 showModal(){this.open=true;}
 close(){this.open=false;}
 focus(){}
}

test('actual file UI renews visible leases and preserves drafts through expiry/reconnect',async()=>{
 const body=new Element('body'),panel=new Element('details');body.append(panel);
 const events={},timers=new Map(),ops=[];let serial=0,clientTransport=null;
 const document={body,visibilityState:'visible',createElement:tag=>new Element(tag),
  addEventListener:(name,fn)=>{events[name]=fn;},
  querySelector:selector=>selector==='[data-device-project-panel]'?panel:null,
  getElementById:id=>body.querySelectorAll('dialog').find(n=>n.id===id)||null};
 const connection={epoch:0,state:'available',listeners:[],subscribe(fn){this.listeners.push(fn);fn({state:this.state,transport:null});return ()=>{};},
  notify(state,transport=null,error=null){this.state=state;for(const fn of this.listeners)fn({state,transport,error});},
  async open(){this.notify('connecting');clientTransport=fixture.create({latency:0,empty:true});
   const request=clientTransport.request.bind(clientTransport);clientTransport.request=(r,o)=>{ops.push(r.op);return request(r,o);};
   this.notify('ready',clientTransport);},
  async close(){this.epoch++;this.notify('available');}};
 const window={MicroBlocksFiles:core,MicroBlocksFilesConnection:connection,addEventListener:(name,fn)=>{events['window:'+name]=fn;}};
 const context={window,document,queueMicrotask,setTimeout:(fn,ms)=>{
  if(ms!==10000)return setTimeout(fn,ms);const id={heartbeat:++serial};timers.set(id,fn);return id;
 },clearTimeout:id=>{if(timers.has(id))timers.delete(id);else clearTimeout(id);},URL,Blob,location:{protocol:'http:',hostname:'192.0.2.1'}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/device-files.js'),'utf8'),context);
 events['board-ide-ready']();await tick();
 const button=label=>{const found=body.querySelectorAll('button').find(n=>n.textContent===label);assert.ok(found,label);return found;};
 const fields=()=>({path:body.querySelectorAll('input')[0],text:body.querySelectorAll('textarea')[0]});
 const dialog=body.querySelectorAll('dialog')[0];
 button('Device files').onclick();button('Connect files').onclick();
 await until(()=>body.querySelectorAll('p').some(n=>n.textContent==='File list refreshed.'));
 assert.equal(timers.size,1);button('New text file').onclick();
 const draft=fields();draft.path.value='/RAM/draft.txt';draft.text.value='unsaved accent: é';draft.text.events.input();
 assert.equal(button('Create file').disabled,false);
 const callback=[...timers.values()][0];timers.clear();callback();
 await until(()=>timers.size===1);assert.equal(ops.at(-1),'capabilities');
 assert.equal(ops.filter(op=>['begin','append','finish'].includes(op)).length,0,'Lease check is read-only');
 assert.equal(draft.text.value,'unsaved accent: é');
 const original=clientTransport.request;clientTransport.request=()=>new Promise(()=>{});
 button('Refresh').onclick();const beforeBusyCheck=ops.length;
 const busyTick=[...timers.values()][0];timers.clear();busyTick();
 assert.equal(ops.length,beforeBusyCheck,'Heartbeat does not race a foreground operation');
 clientTransport.request=original;button('Cancel operation').onclick();
 await until(()=>!button('Refresh').disabled);
 connection.notify('available',null,'DISCONNECTED');
 assert.equal(draft.text.value,'unsaved accent: é');assert.equal(draft.path.value,'/RAM/draft.txt');
 assert.equal(button('Create file').disabled,true);assert.equal(timers.size,0);
 button('Connect files').onclick();await until(()=>timers.size===1&&!button('New text file').disabled);
 assert.equal(draft.text.value,'unsaved accent: é');assert.equal(button('Create file').disabled,true,'Old draft is not silently rebound to a new session');
 button('New text file').onclick();button('Keep editing').onclick();assert.equal(draft.text.value,'unsaved accent: é');
 button('New text file').onclick();button('Discard edits').onclick();assert.equal(draft.text.value,'');
 assert.equal(draft.path.value,'/RAM/');
 document.visibilityState='hidden';events.visibilitychange();assert.equal(timers.size,0);
 document.visibilityState='visible';events.visibilitychange();assert.equal(timers.size,1);
 button('Close').onclick();assert.equal(dialog.open,false);assert.equal(timers.size,0);
 events['window:pagehide']();assert.equal(timers.size,0);
});

async function mountRAM({empty=true}={}){
 const body=new Element('body'),panel=new Element('details');body.append(panel);
 const events={},timers=new Map(),ops=[];let opened=0,intercept=null;
 const document={body,visibilityState:'visible',createElement:tag=>new Element(tag),
  addEventListener:(name,fn)=>{events[name]=fn;},querySelector:()=>panel,
  getElementById:id=>body.querySelectorAll('dialog').find(n=>n.id===id)||null};
 const connection={epoch:0,state:'available',listeners:[],subscribe(fn){this.listeners.push(fn);fn({state:this.state,transport:null});return ()=>{this.listeners=this.listeners.filter(f=>f!==fn);};},
  notify(state,transport=null,error=null){this.state=state;for(const fn of this.listeners)fn({state,transport,error});},
  async open(){this.notify('connecting');const transport=fixture.create({latency:0,empty:opened++?true:empty}),request=transport.request.bind(transport);
   transport.request=(r,o)=>{ops.push(r.op);return intercept?.(r,o,()=>request(r,o))??request(r,o);};this.notify('ready',transport);},
  async close(){this.epoch++;this.notify('available');}};
 const window={MicroBlocksFiles:core,MicroBlocksFilesConnection:connection,addEventListener:(name,fn)=>{events['window:'+name]=fn;}};
 const context={window,document,queueMicrotask,setTimeout:(fn,ms)=>{
  if(ms!==10000)return setTimeout(fn,ms);const id={};timers.set(id,fn);return id;
 },clearTimeout:id=>{if(timers.has(id))timers.delete(id);else clearTimeout(id);},URL,Blob,location:{protocol:'http:',hostname:'192.0.2.1'}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/device-files.js'),'utf8'),context);events['board-ide-ready']();await tick();
 const button=label=>{const value=body.querySelectorAll('button').find(n=>n.textContent===label);assert.ok(value,label);return value;};
 const status=()=>body.querySelectorAll('p').find(n=>n.role==='status').textContent;
 const fields=()=>({path:body.querySelectorAll('input')[0],text:body.querySelectorAll('textarea')[0]});
 const dialog=body.querySelectorAll('dialog')[0];
 return {body,button,status,fields,dialog,connection,timers,ops,
  intercept(value){intercept=value;},
  fireHeartbeat(){assert.equal(timers.size,1);const fn=timers.values().next().value;timers.clear();fn();},
  visible(value){document.visibilityState=value?'visible':'hidden';events.visibilitychange();},
  cleanup(){events['window:pagehide']();},
  async connect(){button('Device files').onclick();button('Connect files').onclick();await until(()=>status()==='File list refreshed.');},
  draft(){button('New text file').onclick();const value=fields();value.path.value='/RAM/draft.txt';value.text.value='unsaved text';value.text.events.input();return value;},
 };
}

test('renewal failure pauses checks; opening the dialog never reconnects or replays a write',async()=>{
 const ui=await mountRAM();try{
  await ui.connect();const draft=ui.draft(),before=ui.ops.length;
  ui.intercept(r=>r.op==='capabilities'?Promise.resolve({version:1,id:r.id,ok:false,code:'TIMEOUT'}):undefined);
  ui.fireHeartbeat();await until(()=>ui.status().includes('timed out'));
  assert.equal(ui.timers.size,0);assert.equal(draft.text.value,'unsaved text');
  assert.deepEqual(ui.ops.slice(before),['capabilities']);assert.equal(ui.connection.state,'ready');
  ui.button('Device files').onclick();ui.visible(false);ui.visible(true);assert.equal(ui.timers.size,0);
  assert.equal(ui.ops.filter(op=>['begin','append','finish','open'].includes(op)).length,0);
 }finally{ui.cleanup();}
});

test('late old list replies cannot replace the new connection list, draft or status',async()=>{
 const ui=await mountRAM({empty:false});let release,oldReply;
 try{
  ui.intercept(async(r,o,next)=>{if(r.op!=='list')return next();oldReply=await next();return new Promise(resolve=>{release=()=>resolve(oldReply);});});
  ui.button('Device files').onclick();ui.button('Connect files').onclick();await until(()=>release);
  assert.ok(oldReply.data.files.length>0);
  ui.connection.notify('available',null,'DISCONNECTED');ui.intercept(null);ui.button('Connect files').onclick();
  await until(()=>ui.status()==='File list refreshed.');const draft=ui.draft(),status=ui.status();
  release();await tick();await tick();
  assert.equal(ui.body.querySelectorAll('button').filter(n=>n['aria-label']?.startsWith('Open /RAM/')).length,0);
  assert.equal(draft.text.value,'unsaved text');assert.equal(draft.path.value,'/RAM/draft.txt');assert.equal(ui.status(),status);
  assert.equal(ui.ops.filter(op=>['begin','append','finish'].includes(op)).length,0);
 }finally{release?.();ui.cleanup();}
});

test('a pending old heartbeat cannot restart timers after page cleanup',async()=>{
 const ui=await mountRAM();let release;
 try{
  await ui.connect();ui.intercept(async(r,o,next)=>{const reply=await next();return new Promise(resolve=>{release=()=>resolve(reply);});});
  ui.fireHeartbeat();await until(()=>release);ui.cleanup();assert.equal(ui.timers.size,0);
  release();await tick();await tick();assert.equal(ui.timers.size,0);
 }finally{release?.();ui.cleanup();}
});

test('dirty close keeps edits until explicit discard and open/close leaves no heartbeat',async()=>{
 const ui=await mountRAM();try{
  await ui.connect();const draft=ui.draft();ui.button('Close').onclick();assert.equal(ui.dialog.open,true);
  ui.button('Keep editing').onclick();assert.equal(draft.text.value,'unsaved text');assert.equal(ui.timers.size,1);
  ui.button('Close').onclick();ui.button('Discard edits').onclick();assert.equal(ui.dialog.open,false);assert.equal(ui.timers.size,0);
  ui.button('Device files').onclick();assert.equal(ui.timers.size,1);ui.button('Close').onclick();assert.equal(ui.timers.size,0);
 }finally{ui.cleanup();}
});
