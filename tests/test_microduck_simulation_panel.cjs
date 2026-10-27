/* SPDX-License-Identifier: MIT */
// Mock DOM + in-memory robot; actual client/panel logic, no graphical-browser claim.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const panelAPI=require('../web/microduck/simulation-panel.js');
const simulation=require('../web/microduck/simulation.js');

class Element{
 constructor(tag,document){this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.listeners=new Map();this.attributes={};this._text='';this.value='';this.checked=false;this.disabled=false;}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(c=>c.textContent).join('');}
 append(...nodes){for(const node of nodes){node.parentNode=this;this.children.push(node);}}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 setAttribute(name,value){this.attributes[name]=String(value);}
 addEventListener(name,callback){if(!this.listeners.has(name))this.listeners.set(name,[]);this.listeners.get(name).push(callback);}
 async fire(name){for(const callback of this.listeners.get(name)||[])await callback({type:name,preventDefault(){}});}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(c=>c!==this);}
 find(predicate){if(predicate(this))return this;for(const child of this.children){const found=child.find(predicate);if(found)return found;}}
 all(predicate){return [...(predicate(this)?[this]:[]),...this.children.flatMap(c=>c.all(predicate))];}
}
class Lifecycle extends EventTarget{
 constructor(){super();this.handlers=new Set();}
 addEventListener(type,callback){if(type==='pagehide')this.handlers.add(callback);super.addEventListener(type,callback);}
 removeEventListener(type,callback){this.handlers.delete(callback);super.removeEventListener(type,callback);}
}
function harness(){
 const document={createElement(tag){return new Element(tag,this);}},container=new Element('section',document),lifecycle=new Lifecycle();
 const panel=panelAPI.mount(container,{lifecycleTarget:lifecycle});
 const css=name=>container.find(e=>e.className===name),button=text=>container.find(e=>e.tagName==='BUTTON'&&e.textContent===text);
 return {panel,container,lifecycle,css,start:()=>button('Start SIMULATION'),end:()=>button('End simulation'),refresh:()=>button('Refresh fictional data'),
  group:key=>({choice:css('simulation-'+key+'-choice'),check:css('simulation-'+key+'-confirm'),run:css('simulation-'+key+'-run')})};
}
async function confirm(group){group.check.checked=true;await group.check.fire('change');}

test('mount is passive, has explicit simulation labels and checkbox/select controls only',()=>{
 const h=harness();assert.equal(h.panel.snapshot(),null);assert.equal(h.start().disabled,false);assert.equal(h.refresh().disabled,true);
 assert.match(h.container.textContent,/SIMULATION \/ NO ROBOT/);assert.match(h.container.textContent,/No Bluetooth, network connection, account, PIN or Wi-Fi password/);
 const inputs=h.container.all(e=>e.tagName==='INPUT');assert.equal(inputs.length,3);assert.ok(inputs.every(e=>e.type==='checkbox'));
 assert.equal(h.container.find(e=>['FORM','TEXTAREA'].includes(e.tagName)),undefined);assert.equal(h.lifecycle.handlers.size,1);
 h.panel.destroy();assert.equal(h.container.children.length,0);assert.equal(h.lifecycle.handlers.size,0);
});

test('explicit start uses actual mock RPC and presents fictional identity/battery/discovery',async()=>{
 const h=harness();await h.start().fire('click');
 assert.equal(h.panel.snapshot().stats.requests,8);assert.equal(h.start().disabled,true);assert.equal(h.refresh().disabled,false);
 assert.match(h.css('simulation-identity').textContent,/SIMULATION Duck.*API 44.*simulated: true/);
 assert.match(h.css('simulation-health').textContent,/FICTIONAL battery: 73.25% \/ 7.8 V/);
 assert.match(h.css('simulation-network').textContent,/documentation address/);
 assert.deepEqual(h.group('skill').choice.children.map(e=>e.value),simulation.SKILLS);
 assert.match(h.css('simulation-policies').textContent,/policies enabled: false/);assert.deepEqual(h.panel.snapshot().actions,[]);h.panel.destroy();
});

test('changing a sound invalidates confirmation and every action consumes its checkbox',async()=>{
 const h=harness();await h.start().fire('click');const g=h.group('sound');
 await g.run.fire('click');assert.equal(h.panel.snapshot().actions.length,0);assert.equal(g.run.disabled,true);
 await confirm(g);assert.equal(g.run.disabled,false);g.choice.value='chirp';await g.choice.fire('change');assert.equal(g.check.checked,false);assert.equal(g.run.disabled,true);
 await confirm(g);await g.run.fire('click');assert.equal(g.check.checked,false);assert.equal(g.run.disabled,true);
 assert.deepEqual(h.panel.snapshot().actions.map(q=>q.params),[{tag:'chirp'}]);
 await g.run.fire('click');assert.equal(h.panel.snapshot().actions.length,1);assert.match(h.css('simulation-status').textContent,/No physical action occurred/);h.panel.destroy();
});

test('fictional network join has no password and ending/restarting discards history and IP',async()=>{
 const h=harness();await h.start().fire('click');const g=h.group('network');await confirm(g);await g.run.fire('click');
 assert.match(h.css('simulation-network').textContent,/Fictional IPv4: 192.0.2.44/);
 assert.deepEqual(h.panel.snapshot().actions[0].params,{ssid:simulation.SSID});assert.equal(g.check.checked,false);
 await h.end().fire('click');assert.equal(h.panel.snapshot(),null);assert.equal(h.start().disabled,false);
 await h.start().fire('click');assert.deepEqual(h.panel.snapshot().actions,[]);assert.match(h.css('simulation-network').textContent,/Fictional IPv4: not joined/);h.panel.destroy();
});

test('skill control uses advertised fixtures and refuses a forged selection without replay',async()=>{
 const h=harness();assert.equal(h.group('skill').run.disabled,true);await h.start().fire('click');const g=h.group('skill');
 g.choice.value='not_advertised';await g.choice.fire('change');await confirm(g);await g.run.fire('click');
 assert.equal(h.panel.snapshot().actions.length,0);assert.match(h.css('simulation-status').textContent,/UNDISCOVERED_SKILL/);assert.equal(g.check.checked,false);
 g.choice.value=simulation.SKILLS[1];await g.choice.fire('change');await confirm(g);await g.run.fire('click');
 assert.equal(h.panel.snapshot().actions[0].params.skill,simulation.SKILLS[1]);assert.match(h.css('simulation-log').textContent,/"simulation": true/);h.panel.destroy();
});

test('refresh clears staged confirmations and duplicate start cannot create a second session',async()=>{
 const h=harness();await h.start().fire('click');await confirm(h.group('sound'));const before=h.panel.snapshot().stats.requests;
 await h.start().fire('click');assert.equal(h.panel.snapshot().stats.requests,before);
 await h.refresh().fire('click');assert.equal(h.group('sound').check.checked,false);assert.equal(h.group('sound').run.disabled,true);assert.equal(h.panel.snapshot().stats.requests,before+6);h.panel.destroy();
});

test('pagehide and destroy during pending start discard completion and remove listeners',async()=>{
 const h=harness(),pending=h.start().fire('click');h.lifecycle.dispatchEvent(new Event('pagehide'));await pending;
 assert.equal(h.panel.snapshot(),null);assert.match(h.css('simulation-status').textContent,/SIMULATION ended/);assert.equal(h.start().disabled,false);
 const second=h.start().fire('click');h.panel.destroy();h.panel.destroy();await second;
 assert.equal(h.container.children.length,0);assert.equal(h.lifecycle.handlers.size,0);assert.equal(h.panel.snapshot(),null);
});
