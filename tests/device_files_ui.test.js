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
 events['board-ide-ready']();await until(()=>body.querySelectorAll('dialog').length===1);
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

test('file UI survives a microtask checkpoint before the later portal ready listener',async()=>{
 const body=new Element('body'),panel=new Element('details'),events={};let panelReady=false;
 const document={body,visibilityState:'visible',createElement:tag=>new Element(tag),
  addEventListener:(name,fn)=>{events[name]=fn;},
  querySelector:selector=>panelReady&&selector==='[data-device-project-panel]'?panel:null,
  getElementById:id=>body.querySelectorAll('dialog').find(node=>node.id===id)||null};
 const window={MicroBlocksFiles:core,addEventListener(){}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/device-files.js'),'utf8'),
  {window,document,queueMicrotask,setTimeout,clearTimeout,URL,Blob,location:{protocol:'http:',hostname:'192.0.2.1'}});
 events['board-ide-ready']();
 await Promise.resolve(); // Browser checkpoint before the portal's listener.
 assert.equal(body.querySelectorAll('dialog').length,0);
 body.append(panel);panelReady=true;
 await until(()=>body.querySelectorAll('dialog').length===1);
 assert.equal(panel.querySelectorAll('button').filter(node=>node.textContent==='Device files').length,1);
 events['board-ide-ready']();await new Promise(resolve=>setTimeout(resolve,5));
 assert.equal(body.querySelectorAll('dialog').length,1,'Repeated readiness must not duplicate the dialog');
});
