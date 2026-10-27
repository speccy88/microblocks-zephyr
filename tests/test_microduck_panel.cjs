// SPDX-License-Identifier: MIT
// Actual Bluetooth/RPC client with mocked GATT and DOM. No radio or robot claim.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const panelAPI=require('../web/microduck/panel.js');
const ble=require('../web/microduck/bluetooth.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

class Element{
 constructor(tag,document){this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.listeners=new Map();this.attributes={};this._text='';this.disabled=false;}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 append(...nodes){for(const node of nodes){node.parentNode=this;this.children.push(node);}}
 setAttribute(name,value){this.attributes[name]=String(value);}
 addEventListener(name,callback){if(!this.listeners.has(name))this.listeners.set(name,[]);this.listeners.get(name).push(callback);}
 async fire(name){for(const callback of this.listeners.get(name)||[])await callback({type:name,preventDefault(){}});}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(child=>child!==this);}
 find(predicate){if(predicate(this))return this;for(const child of this.children){const found=child.find(predicate);if(found)return found;}}
}
class TrackedTarget extends EventTarget{
 constructor(){super();this.handlers=new Map();}
 addEventListener(name,callback,options){if(!this.handlers.has(name))this.handlers.set(name,new Set());this.handlers.get(name).add(callback);super.addEventListener(name,callback,options);}
 removeEventListener(name,callback,options){this.handlers.get(name)?.delete(callback);super.removeEventListener(name,callback,options);}
 count(name){return this.handlers.get(name)?.size||0;}
}
function gattFixture({apiVersion=44,name='Mock Duck',order=[]}={}){
 const device=new TrackedTarget(),characteristic=new TrackedTarget(),calls={chooser:0,writes:0,connect:0,disconnect:0};device.name=name;
 const service={async getCharacteristic(id){assert.equal(id,ble.RPC_UUID);order.push('characteristic:'+name);return characteristic;}};
 const server={async getPrimaryService(id){assert.equal(id,ble.SERVICE_UUID);order.push('service:'+name);return service;}};
 Object.assign(characteristic,{properties:{read:true,write:true,notify:true},
  async readValue(){order.push('read:'+name);return new DataView(Uint8Array.of(apiVersion).buffer);},
  async startNotifications(){order.push('notify:'+name);},
  async writeValueWithResponse(){calls.writes++;throw Error('Discovery panel must never write');}
 });
 device.gatt={connected:false,async connect(){calls.connect++;order.push('connect:'+name);this.connected=true;return server;},
  disconnect(){calls.disconnect++;order.push('disconnect:'+name);const wasConnected=this.connected;this.connected=false;if(wasConnected)device.dispatchEvent(new Event('gattserverdisconnected'));}};
 const bluetooth={async requestDevice(filters){calls.chooser++;order.push('chooser:'+name);assert.deepEqual(filters,{filters:[{services:[ble.SERVICE_UUID]}]});return device;}};
 return {device,characteristic,server,bluetooth,calls,order};
}
function harness(bluetooth,options={}){
 const document={createElement(tag){return new Element(tag,this);}},container=new Element('section',document),lifecycle=new TrackedTarget();
 const panel=panelAPI.mount(container,{bluetooth,lifecycleTarget:lifecycle,...options});
 return {panel,container,lifecycle,
  discover:()=>container.find(e=>e.tagName==='BUTTON'&&['Discover MicroDuck','Choose another MicroDuck'].includes(e.textContent)),
  disconnect:()=>container.find(e=>e.tagName==='BUTTON'&&e.textContent==='Disconnect'),
  status:()=>container.find(e=>e.className==='microduck-discovery-status'),
  name:()=>container.find(e=>e.className==='microduck-device-name'),
  version:()=>container.find(e=>e.className==='microduck-api-version')};
}

test('mount performs no chooser/request/write and has no secret or motion inputs',async()=>{
 const f=gattFixture(),h=harness(f.bluetooth);
 assert.equal(panelAPI.EXPECTED_API,44);assert.equal(f.calls.chooser,0);assert.equal(f.calls.connect,0);assert.equal(f.calls.writes,0);
 assert.equal(h.container.find(e=>e.tagName==='INPUT'),undefined);
 assert.equal(h.container.find(e=>e.tagName==='FORM'),undefined);
 assert.equal(h.discover().disabled,false);assert.equal(h.disconnect().disabled,true);
 assert.match(h.container.textContent,/mock devices/);assert.match(h.container.textContent,/No physical MicroDuck/);
 assert.match(h.container.textContent,/Authentication and Wi-Fi provisioning remain unavailable/);
 const source=fs.readFileSync(require.resolve('../web/microduck/panel.js'),'utf8');
 assert.doesNotMatch(source,/\.(?:request|authenticate)\s*\(/);
 h.panel.destroy();assert.equal(h.lifecycle.count('pagehide'),0);assert.equal(f.calls.chooser,0);
});

test('explicit discovery uses actual client, reads API 44 and never writes RPC',async()=>{
 const f=gattFixture(),h=harness(f.bluetooth);await h.discover().fire('click');
 assert.equal(f.calls.chooser,1);assert.equal(f.device.gatt.connected,true);assert.equal(f.calls.writes,0);
 assert.match(h.name().textContent,/Mock Duck/);assert.match(h.version().textContent,/API 44 matches/);
 assert.match(h.status().textContent,/discovery only/);assert.match(h.status().textContent,/confidentiality is unverified/);
 assert.equal(h.disconnect().disabled,false);
 assert.equal(f.characteristic.count('characteristicvaluechanged'),1);
 await h.disconnect().fire('click');
 assert.equal(f.device.gatt.connected,false);assert.equal(f.characteristic.count('characteristicvaluechanged'),0);assert.equal(f.device.count('gattserverdisconnected'),0);
 assert.equal(f.calls.writes,0);h.panel.destroy();
});

test('chooser cancellation is handled without GATT or RPC side effects',async()=>{
 let chooser=0;
 const h=harness({async requestDevice(){chooser++;throw new DOMException('User cancelled','NotFoundError');}});
 await h.discover().fire('click');assert.equal(chooser,1);
 assert.match(h.status().textContent,/chooser cancelled/);assert.equal(h.discover().disabled,false);assert.equal(h.disconnect().disabled,true);
 h.panel.destroy();
});

test('unsupported provider has useful status and no automatic fallback',async()=>{
 const h=harness({});assert.equal(h.discover().disabled,true);
 assert.match(h.status().textContent,/Web Bluetooth is unavailable/);assert.match(h.status().textContent,/HTTPS or localhost/);
 await h.discover().fire('click');assert.equal(h.disconnect().disabled,true);h.panel.destroy();
});

test('API mismatch disconnects, preserves observed metadata and never sends a command',async()=>{
 const f=gattFixture({apiVersion:43,name:'Old API fixture'}),h=harness(f.bluetooth);
 await h.discover().fire('click');
 assert.equal(f.device.gatt.connected,false);assert.equal(f.calls.writes,0);
 assert.match(h.status().textContent,/API version mismatch.*Expected 44, observed 43/);
 assert.match(h.name().textContent,/Old API fixture/);assert.match(h.version().textContent,/Observed GATT API: 43/);
 assert.equal(f.characteristic.count('characteristicvaluechanged'),0);assert.equal(f.device.count('gattserverdisconnected'),0);
 assert.equal(h.disconnect().disabled,true);h.panel.destroy();
});

test('GATT read timeout closes discovery connection and enables a fresh attempt',async()=>{
 const f=gattFixture(),h=harness(f.bluetooth,{timeoutMs:10});f.characteristic.readValue=()=>new Promise(()=>{});
 await h.discover().fire('click');
 assert.match(h.status().textContent,/timed out/);assert.equal(f.device.gatt.connected,false);assert.equal(f.calls.writes,0);
 assert.equal(h.discover().disabled,false);assert.equal(h.disconnect().disabled,true);h.panel.destroy();
});

test('a GATT connect completing after timeout is disconnected, not shown as connected',async()=>{
 const f=gattFixture(),h=harness(f.bluetooth,{timeoutMs:10});let complete;
 f.device.gatt.connect=()=>new Promise(resolve=>{complete=()=>{f.device.gatt.connected=true;resolve(f.server);};});
 await h.discover().fire('click');assert.match(h.status().textContent,/timed out/);
 complete();await tick();assert.equal(f.device.gatt.connected,false);assert.equal(f.calls.writes,0);
 assert.doesNotMatch(h.status().textContent,/GATT connected/);h.panel.destroy();
});

test('new explicit session closes old one before opening chooser and ignores stale drop events',async()=>{
 const order=[],first=gattFixture({name:'First Duck',order}),second=gattFixture({name:'Second Duck',order});let choice=0;
 const bluetooth={requestDevice(filters){return (++choice===1?first:second).bluetooth.requestDevice(filters);}},h=harness(bluetooth);
 await h.discover().fire('click');await h.discover().fire('click');
 assert.equal(choice,2);assert.equal(first.device.gatt.connected,false);assert.equal(second.device.gatt.connected,true);
 assert.ok(order.indexOf('disconnect:First Duck')<order.indexOf('chooser:Second Duck'));
 assert.equal(first.device.count('gattserverdisconnected'),0);assert.equal(first.characteristic.count('characteristicvaluechanged'),0);
 first.device.dispatchEvent(new Event('gattserverdisconnected'));assert.match(h.name().textContent,/Second Duck/);assert.match(h.status().textContent,/GATT connected/);
 assert.equal(first.calls.writes+second.calls.writes,0);h.panel.destroy();assert.equal(second.device.gatt.connected,false);
});

test('cancelling an open chooser rejects its late result before any GATT connect',async()=>{
 const f=gattFixture();let select;const h=harness({requestDevice(){return new Promise(resolve=>{select=()=>resolve(f.device);});}});
 const pending=h.discover().fire('click');await tick();assert.equal(h.discover().disabled,true);
 await h.disconnect().fire('click');assert.equal(h.discover().disabled,true);assert.match(h.status().textContent,/Close any open browser chooser/);
 select();await pending;assert.equal(f.calls.connect,0);assert.equal(f.device.gatt.connected,false);assert.equal(f.calls.writes,0);
 assert.equal(h.discover().disabled,false);assert.equal(h.disconnect().disabled,true);assert.match(h.status().textContent,/Discovery cancelled/);h.panel.destroy();
});

test('pagehide and destroy close sessions and detach their listeners',async()=>{
 const f=gattFixture(),h=harness(f.bluetooth);assert.equal(h.lifecycle.count('pagehide'),1);
 await h.discover().fire('click');h.lifecycle.dispatchEvent(new Event('pagehide'));
 assert.equal(f.device.gatt.connected,false);assert.equal(f.characteristic.count('characteristicvaluechanged'),0);assert.equal(f.device.count('gattserverdisconnected'),0);
 assert.match(h.status().textContent,/leaving the page/);assert.equal(f.calls.writes,0);
 h.panel.destroy();h.panel.destroy();assert.equal(h.lifecycle.count('pagehide'),0);assert.equal(h.container.children.length,0);
});

test('destroy during chooser discards the late selection without radio access',async()=>{
 const f=gattFixture();let select;const h=harness({requestDevice(){return new Promise(resolve=>{select=()=>resolve(f.device);});}});
 const pending=h.discover().fire('click');await tick();h.panel.destroy();select();await pending;
 assert.equal(f.calls.connect,0);assert.equal(f.calls.writes,0);assert.equal(h.lifecycle.count('pagehide'),0);assert.equal(h.container.children.length,0);
});

test('unexpected disconnect cleans session and names are rendered only as bounded text',async()=>{
 const f=gattFixture({name:'<img src=x onerror=evil()>\nDuck\u202e'}),h=harness(f.bluetooth);
 await h.discover().fire('click');assert.ok(h.name().textContent.includes('<img src=x onerror=evil()>'));
 assert.equal(h.container.find(e=>e.tagName==='IMG'),undefined);assert.doesNotMatch(h.name().textContent,/[\n\u202e]/);
 f.device.gatt.disconnect();assert.equal(h.disconnect().disabled,true);assert.match(h.status().textContent,/Bluetooth disconnected/);
 assert.equal(f.characteristic.count('characteristicvaluechanged'),0);assert.equal(f.device.count('gattserverdisconnected'),0);h.panel.destroy();
});
