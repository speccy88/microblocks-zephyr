/* SPDX-License-Identifier: MIT */
// Actual SD UI/client, synthetic DOM and native operations. No hardware/browser.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),vm=require('node:vm'),fs=require('node:fs');
const core=require('../web/device-files-core.js'),SD=require('../web/device-sd-core.js'),{fixture}=require('./device_sd_fakes.js');
class Element {
 constructor(tag){this.tag=tag;this.children=[];this.dataset={};this.events={};this.hidden=false;this.disabled=false;this.value='';this.textContent='';}
 append(...children){for(const child of children){child.parent=this;this.children.push(child);}}
 prepend(child){child.parent=this;this.children.unshift(child);}
 replaceChildren(...children){this.children=children;}
 setAttribute(name,value){this[name]=value;}
 removeAttribute(name){delete this[name];}
 addEventListener(name,fn){this.events[name]=fn;}
 querySelectorAll(tag){return this.children.flatMap(child=>[...(child.tag===tag?[child]:[]),...child.querySelectorAll(tag)]);}
 querySelector(tag){return this.querySelectorAll(tag)[0]||null;}
 closest(){return null;}
 showModal(){this.open=true;}
 close(){this.open=false;}
 focus(){}
}
async function until(predicate){for(let i=0;i<300;i++){if(predicate())return;await new Promise(resolve=>setImmediate(resolve));}assert.fail('SD synthetic UI did not settle');}
function setup(){
 const dialog=new Element('dialog'),messages=[],window={MicroBlocksFiles:core,MicroBlocksSDFiles:SD};
 const document={createElement:tag=>new Element(tag)};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/device-sd-ui.js'),'utf8'),{window,document,Uint8Array});
 const ui=window.MicroBlocksSDUI.mount({dialog,report:(message,error)=>messages.push({message,error}),changed(){}});
 const {native,client}=fixture();ui.bind(client,'device');
 const button=label=>{const found=dialog.querySelectorAll('button').find(node=>node.textContent===label);assert.ok(found,label);return found;};
 const path=dialog.querySelectorAll('input')[0],text=dialog.querySelectorAll('textarea')[0];
 return {ui,native,client,dialog,messages,button,path,text};
}
test('actual SD view creates, reopens and explicitly removes only its own file',async()=>{
 const {ui,native,dialog,messages,button,path,text}=setup();ui.select('SD');await until(()=>!ui.busy);
 assert.equal(native.calls.includes('sdCreate'),false,'Opening the SD panel is read-only');
 button('New SD text file').onclick();path.value='TRIAL.TXT';text.value='SD café';text.events.input();assert.equal(button('Save as new SD file').disabled,false);
 button('Save as new SD file').onclick();await until(()=>!ui.busy);
 assert.equal(new TextDecoder().decode(native.files.get('TRIAL.TXT')),'SD café');assert.equal(ui.dirty(),false);
 ui.clear();const row=dialog.querySelectorAll('button').find(node=>node['aria-label']==='Open SD TRIAL.TXT');row.onclick();await until(()=>!ui.busy);
 assert.equal(path.value,'TRIAL.TXT');assert.equal(text.value,'SD café');assert.equal(button('Save as new SD file').disabled,true,'Cannot overwrite a created name');
 button('Remove file created here').onclick();assert.equal(native.files.has('TRIAL.TXT'),true,'Removal waits for its explicit confirmation');
 button('Keep file').onclick();assert.equal(native.files.has('TRIAL.TXT'),true);
 button('Remove file created here').onclick();button('Confirm remove').onclick();await until(()=>!ui.busy);
 assert.equal(native.files.has('TRIAL.TXT'),false);assert.equal(native.files.has('SOURCE.TXT'),true);
 assert.ok(messages.some(item=>item.message.includes('Removed only')));
});
test('stale SD list completion cannot overwrite a replacement connection UI',async()=>{
 const {ui,client,native,dialog}=setup();let release;
 const original=client.transport.request.bind(client.transport);
 client.transport.request=async(r,o)=>{const reply=await original(r,o);if(r.op==='sdList')await new Promise(resolve=>{release=resolve;});return reply;};
 ui.select('SD');await until(()=>!!release);assert.equal(ui.busy,true);
 ui.bind(new core.Client(), 'disconnected');release();await new Promise(resolve=>setTimeout(resolve,15));
 assert.equal(ui.busy,false);assert.equal(dialog.querySelectorAll('button').some(node=>node['aria-label']==='Open SD SOURCE.TXT'),false);
 assert.equal(native.calls.includes('sdCreate'),false);
});
test('SD draft survives disconnect and cannot silently save into a new connection',async()=>{
 const {ui,path,text,button}=setup();ui.select('SD');await until(()=>!ui.busy);button('New SD text file').onclick();
 path.value='DRAFT.TXT';text.value='unfinished';text.events.input();assert.equal(ui.dirty(),true);
 ui.bind(new core.Client(),'disconnected');assert.equal(text.value,'unfinished');assert.equal(path.value,'DRAFT.TXT');
 assert.equal(button('Save as new SD file').disabled,true);assert.equal(ui.dirty(),true);
});
test('actual Device files application switches RAM and SD through one controller without automatic writes',async()=>{
 const body=new Element('body'),panel=new Element('details');body.append(panel);const events={};
 const document={body,visibilityState:'visible',createElement:tag=>new Element(tag),addEventListener:(name,fn)=>{events[name]=fn;},
  querySelector:selector=>selector==='[data-device-project-panel]'?panel:null,getElementById:id=>body.querySelectorAll('dialog').find(node=>node.id===id)||null};
 const native=fixture().native,ram=require('../web/device-files-fixture.js').create({latency:0,empty:true});
 const transport={request:(r,o)=>r.op.startsWith('sd')?native.request(r,o):ram.request(r,o)};
 const connection={epoch:0,state:'available',listeners:[],subscribe(fn){this.listeners.push(fn);fn({state:this.state,transport:null});return()=>{};},
  notify(state,link=null){this.state=state;for(const fn of this.listeners)fn({state,transport:link});},async open(){this.notify('ready',transport);},async close(){this.notify('available');}};
 const window={MicroBlocksFiles:core,MicroBlocksSDFiles:SD,MicroBlocksFilesConnection:connection,addEventListener:(name,fn)=>{events['window:'+name]=fn;}};
 const context={window,document,queueMicrotask,setTimeout,clearTimeout,URL,Blob,Uint8Array,location:{protocol:'http:',hostname:'192.0.2.1'}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/device-sd-ui.js'),'utf8'),context);
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/device-files.js'),'utf8'),context);
 events['board-ide-ready']();await until(()=>body.querySelectorAll('button').some(node=>node.textContent==='Device files'));
 const button=label=>body.querySelectorAll('button').find(node=>node.textContent===label);
 button('Device files').onclick();button('Connect files').onclick();await until(()=>body.querySelectorAll('p').some(node=>node.textContent==='File list refreshed.'));
 assert.equal(native.calls.length,0);const selector=body.querySelectorAll('select')[0];assert.equal(selector.children.find(node=>node.value==='SD').disabled,false);
 selector.value='SD';selector.events.change();await until(()=>!button('New SD text file').disabled);
 assert.ok(body.querySelectorAll('p').some(node=>node.textContent==='Connected device SD - files stay on the card.'));
 assert.equal(button('New text file').hidden,true);assert.equal(native.calls.includes('sdCreate'),false);
 button('New SD text file').onclick();const path=body.querySelectorAll('input').find(node=>node['aria-label']==='SD filename'),text=body.querySelectorAll('textarea').find(node=>node['aria-label']==='SD file text');
 path.value='APP.TXT';text.value='One shared controller';text.events.input();button('Save as new SD file').onclick();
 await until(()=>native.files.has('APP.TXT')&&!button('Refresh SD').disabled);
 selector.value='RAM';selector.events.change();assert.equal(button('New text file').hidden,false);assert.equal(button('New text file').disabled,false);
 assert.ok(body.querySelectorAll('p').some(node=>node.textContent==='Connected device RAM - temporary; files are lost on reboot.'));
 assert.equal(native.calls.filter(op=>op==='sdCreate').length,1);
 events['window:pagehide']();
});
