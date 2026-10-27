/* SPDX-License-Identifier: MIT */
// Actual console/core/RPC/Bluetooth logic with mock DOM and in-memory transports.
// No graphical browser, radio, network, daemon or physical robot is exercised.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const panelAPI=require('../web/microduck/console-panel.js');
const core=require('../web/microduck/console-core.js');
const {RpcClient}=require('../web/microduck/rpc.js');
const bluetooth=require('../web/microduck/bluetooth.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

class Element{
 constructor(tag,document){this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.listeners=new Map();this.attributes={};this._text='';this.value='';this.checked=false;this.disabled=false;this.hidden=false;}
 set innerHTML(_){throw Error('Console must render text, never HTML');}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 append(...nodes){for(const node of nodes){node.parentNode=this;this.children.push(node);}}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 setAttribute(key,value){this.attributes[key]=String(value);}
 addEventListener(key,fn){if(!this.listeners.has(key))this.listeners.set(key,[]);this.listeners.get(key).push(fn);}
 async fire(key){for(const fn of this.listeners.get(key)||[])await fn({type:key,preventDefault(){}});}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(child=>child!==this);}
 find(fn){if(fn(this))return this;for(const child of this.children){const found=child.find(fn);if(found)return found;}}
 all(fn){return [...(fn(this)?[this]:[]),...this.children.flatMap(child=>child.all(fn))];}
}
class Lifecycle extends EventTarget{
 constructor(){super();this.handlers=new Set();}
 addEventListener(name,fn,options){if(name==='pagehide')this.handlers.add(fn);super.addEventListener(name,fn,options);}
 removeEventListener(name,fn,options){this.handlers.delete(fn);super.removeEventListener(name,fn,options);}
}
function harness(options={}){
 const document={createElement(tag){return new Element(tag,this);}},container=new Element('section',document),lifecycle=new Lifecycle();
 const panel=panelAPI.mount(container,{bluetooth:null,lifecycleTarget:lifecycle,...options});
 const field=name=>container.find(node=>node.className==='console-'+name);
 return {panel,container,lifecycle,field,
  async select(method,params){field('method').value=method;await field('method').fire('change');if(params!==undefined){field('params').value=params;await field('params').fire('input');}},
  async prepare(){await field('prepare').fire('click');},
  async confirm(){field('confirm').checked=true;await field('confirm').fire('change');},
  async execute(){await field('execute').fire('click');},
  async request(method,params){await this.select(method,params);await this.prepare();if(panel.controller.snapshot().prepared?.mutation)await this.confirm();await this.execute();}
 };
}
function recordingClient({confidential=true,timeoutMs=500,delay=new Set(),response,stream=false}={}){
 const requests=[],pending=[],transport={closed:false,writes:0,buffer:'',receive:null,
  subscribe(receive,dropped){this.receive=receive;this.dropped=dropped;return ()=>{this.receive=null;};},
  async write(bytes){
   this.writes++;this.buffer+=new TextDecoder().decode(bytes);
   if(!this.buffer.endsWith('\n'))return;
   const request=JSON.parse(this.buffer);this.buffer='';requests.push(request);if(stream&&request.method==='update.subscribe')return;
   const deliver=()=>{
    if(this.closed)return;
    const result=response?response(request):request.method==='system.authenticate'?{authenticated:true}:request.method==='robot.policies'?{skills:['mock_bow','mock_look'],enabled:false}:request.method==='hello'?{api_version:44}:{ok:true,method:request.method};
    this.receive?.(new TextEncoder().encode(JSON.stringify({jsonrpc:'2.0',id:request.id,result})+'\n'));
   };
   if(delay.has(request.method))pending.push(deliver);else queueMicrotask(deliver);
  },
  close(){this.closed=true;},drop(){this.dropped?.();}
 };
 Object.defineProperty(transport,'confidential',{value:confidential,enumerable:true});
 return {client:new RpcClient(transport,{timeoutMs}),transport,requests,pending};
}
async function authenticated(h,fixture){
 h.panel.attach(fixture.client,{apiVersion:44,simulation:false});
 h.field('pin').value='123456';await h.field('authenticate').fire('click');
 assert.equal(h.panel.controller.snapshot().authenticated,true);
}
function gatt({apiVersion=44}={}){
 const device=new EventTarget(),characteristic=new EventTarget(),counts={chooser:0,connect:0,disconnect:0,writes:0};device.name='MOCK GATT';
 const server={async getPrimaryService(id){assert.equal(id,bluetooth.SERVICE_UUID);return {async getCharacteristic(uuid){assert.equal(uuid,bluetooth.RPC_UUID);return characteristic;}};}};
 Object.assign(characteristic,{properties:{read:true,write:true,notify:true},async readValue(){return new DataView(Uint8Array.of(apiVersion).buffer);},async startNotifications(){},async writeValueWithResponse(){counts.writes++;throw Error('No automatic RPC write allowed');}});
 device.gatt={connected:false,async connect(){counts.connect++;this.connected=true;return server;},disconnect(){counts.disconnect++;const old=this.connected;this.connected=false;if(old)device.dispatchEvent(new Event('gattserverdisconnected'));}};
 return {device,characteristic,counts,server,provider:{async requestDevice(filters){counts.chooser++;assert.deepEqual(filters,{filters:[{services:[bluetooth.SERVICE_UUID]}]});return device;}}};
}

test('mount and direct attach are passive; raw secrets, stream and unreviewed methods are absent',()=>{
 const f=recordingClient({confidential:false}),h=harness();
 assert.equal(h.panel.controller.snapshot().phase,'disconnected');assert.equal(f.transport.writes,0);
 assert.equal(h.field('bluetooth').disabled,true);assert.match(h.field('status').textContent,/unavailable/);
 assert.ok(h.panel.controller instanceof core.Controller);h.panel.attach(f.client,{apiVersion:44});
 assert.deepEqual(f.requests,[]);assert.equal(f.transport.writes,0);assert.equal(h.field('pin'),undefined);assert.equal(h.field('psk'),undefined);
 assert.equal(h.container.all(node=>node.tagName==='INPUT').length,1);assert.equal(h.field('confirm').type,'checkbox');
 const names=h.field('method').children.map(node=>node.value);
 for(const denied of ['system.authenticate','net.connect','update.subscribe','system.reboot','motor.set'])assert.ok(!names.includes(denied));
 assert.match(h.field('confidentiality').textContent,/forms are absent/);h.panel.destroy();assert.equal(f.client.closed,true);assert.equal(h.lifecycle.handlers.size,0);
});

test('real Bluetooth chooser is explicit and attachment reads API44 without sending RPC or showing secrets',async()=>{
 const f=gatt(),h=harness({bluetooth:f.provider});assert.equal(f.counts.chooser,0);assert.equal(f.counts.connect,0);
 await h.field('bluetooth').fire('click');assert.equal(f.counts.chooser,1);assert.equal(f.device.gatt.connected,true);assert.equal(f.counts.writes,0);
 assert.equal(h.panel.controller.snapshot().confidential,false);assert.equal(h.field('pin'),undefined);assert.equal(h.field('psk'),undefined);
 await h.select('robot.health');await h.prepare();assert.match(h.field('status').textContent,/AUTH_REQUIRED/);assert.equal(f.counts.writes,0);
 h.lifecycle.dispatchEvent(new Event('pagehide'));assert.equal(f.device.gatt.connected,false);assert.equal(h.panel.controller.snapshot().phase,'disconnected');h.panel.destroy();
});

test('API mismatch and cancelled chooser close safely without requests',async()=>{
 const f=gatt({apiVersion:43}),h=harness({bluetooth:f.provider});await h.field('bluetooth').fire('click');
 assert.equal(f.counts.writes,0);assert.equal(f.device.gatt.connected,false);assert.equal(h.panel.controller.snapshot().phase,'disconnected');assert.match(h.field('status').textContent,/API_VERSION/);h.panel.destroy();
 const cancelled=harness({bluetooth:{async requestDevice(){const error=Error('untrusted detail');error.name='NotFoundError';throw error;}}});await cancelled.field('bluetooth').fire('click');assert.match(cancelled.field('status').textContent,/chooser cancelled/);assert.doesNotMatch(cancelled.container.textContent,/untrusted detail/);cancelled.panel.destroy();
 const direct=recordingClient(),other=harness();assert.throws(()=>other.panel.attach(direct.client,{apiVersion:45}),error=>error.code==='API_VERSION');assert.equal(direct.client.closed,true);assert.equal(direct.transport.writes,0);other.panel.destroy();
});

test('explicit in-memory fixture attaches without auth; fixed auth and fictional open SSID have no secret inputs',async()=>{
 const h=harness();await h.field('simulation').fire('click');
 assert.equal(h.panel.controller.snapshot().simulation,true);assert.equal(h.panel.controller.snapshot().authenticated,false);assert.deepEqual(h.panel.controller.snapshot().history,[]);
 assert.match(h.field('result').textContent,/SIMULATION \/ FICTIONAL/);
 assert.equal(h.field('pin'),undefined);assert.equal(h.field('psk'),undefined);assert.equal(h.field('ssid').tagName,'SELECT');assert.deepEqual(h.field('ssid').children.map(node=>node.value),[core.FIXTURE_SSID]);
 assert.match(h.field('identity').textContent,/SIMULATION \/ FICTIONAL/);await h.field('authenticate').fire('click');assert.equal(h.panel.controller.snapshot().authenticated,true);
 await h.request('system.info');assert.match(h.field('result').textContent,/SIMULATION \/ FICTIONAL/);
 await h.field('provision-prepare').fire('click');assert.equal(h.panel.controller.snapshot().prepared.method,'net.connect');await h.confirm();await h.execute();
 assert.match(h.field('status').textContent,/SIMULATION \/ FICTIONAL/);assert.equal(h.field('confirm').checked,false);h.panel.destroy();
});

test('prepare is local, mutation confirmation is specific and edits, refresh and execution consume it',async()=>{
 const h=harness(),f=recordingClient();await authenticated(h,f);const before=f.requests.length;
 await h.select('system.setName','{"name":"Mock Duck"}');await h.prepare();assert.equal(f.requests.length,before);assert.equal(h.field('execute').disabled,true);assert.match(h.container.textContent,/I confirm system.setName/);
 await h.execute();assert.equal(f.requests.length,before);await h.confirm();
 h.field('params').value='{"name":"Edited Duck"}';await h.field('params').fire('input');assert.equal(h.field('confirm').checked,false);assert.equal(h.panel.controller.snapshot().prepared,null);
 await h.prepare();await h.confirm();await h.field('refresh').fire('click');assert.equal(f.requests.length,before);assert.equal(h.field('execute').disabled,true);
 await h.prepare();await h.confirm();await h.execute();assert.equal(f.requests.filter(item=>item.method==='system.setName').length,1);assert.equal(h.field('confirm').checked,false);assert.equal(h.field('execute').disabled,true);
 await h.execute();assert.equal(f.requests.filter(item=>item.method==='system.setName').length,1);h.panel.destroy();
});

test('duplicate JSON, raw secret fields and forged method values cannot reach the RPC client',async()=>{
 const h=harness(),f=recordingClient();await authenticated(h,f);const before=f.requests.length;
 for(const [method,text,code] of [['system.setName','{"name":"A","name":"B"}','JSON_DUPLICATE'],['system.info','{"pin":"654321"}','SECRET_INPUT_DENIED'],['system.authenticate','{"pin":"654321"}','METHOD_DENIED'],['update.subscribe','{}','METHOD_DENIED']]){
  await h.select(method,text);await h.prepare();assert.equal(h.field('execute').disabled,true);assert.match(h.field('status').textContent,new RegExp(code));assert.equal(f.requests.length,before);
 }
 assert.doesNotMatch(h.field('preview').textContent,/654321/);assert.doesNotMatch(h.field('audit').textContent,/654321/);h.panel.destroy();
});

test('skills use discovered select choices and actual core rechecks latest policies before dispatch',async()=>{
 let skills=['mock_bow','mock_look'];
 const f=recordingClient({response:request=>request.method==='system.authenticate'?{authenticated:true}:request.method==='robot.policies'?{skills}: {ok:true}}),h=harness();await authenticated(h,f);
 await h.select('robot.do');assert.equal(h.field('prepare').disabled,true);await h.request('robot.policies');
 await h.select('robot.do');assert.deepEqual(h.field('skill').children.map(node=>node.value),skills);assert.equal(h.field('params').parentNode.hidden,true);assert.equal(h.field('skill').parentNode.hidden,false);
 h.field('skill').value='not_discovered';await h.field('skill').fire('change');await h.prepare();assert.match(h.field('status').textContent,/UNDISCOVERED_SKILL/);
 h.field('skill').value='mock_bow';await h.field('skill').fire('change');await h.prepare();assert.match(h.field('confirm').parentNode.textContent,/may cause motion/);await h.confirm();skills=['mock_look'];await h.execute();
 assert.match(h.field('status').textContent,/UNDISCOVERED_SKILL/);assert.equal(f.requests.filter(request=>request.method==='robot.do').length,0);
 h.field('skill').value='mock_look';await h.field('skill').fire('change');await h.prepare();await h.confirm();await h.execute();assert.equal(f.requests.filter(request=>request.method==='robot.do').length,1);h.panel.destroy();
});

test('confidential PIN/PSK fields are transient and provisioning preview, result and audit are redacted',async()=>{
 const f=recordingClient({response:request=>request.method==='system.authenticate'?{authenticated:true}:request.method==='net.connect'?{psk:request.params.psk,echo:'echo '+request.params.psk,ok:true}:{ok:true}}),h=harness();
 h.panel.attach(f.client,{apiVersion:44});const pin=h.field('pin');assert.equal(pin.type,'password');pin.value='123456';const auth=h.field('authenticate').fire('click');assert.equal(pin.value,'');await auth;
 const ssid=h.field('ssid'),psk=h.field('psk');assert.equal(psk.type,'password');ssid.value='PRIVATE-NET';psk.value='private-passphrase';await h.field('provision-prepare').fire('click');
 assert.equal(ssid.value,'');assert.equal(psk.value,'');assert.match(h.field('preview').textContent,/redacted/);assert.doesNotMatch(h.container.textContent,/private-passphrase|123456/);await h.confirm();await h.execute();
 assert.deepEqual(f.requests.at(-1).params,{ssid:'PRIVATE-NET',psk:'private-passphrase'});assert.doesNotMatch(h.field('result').textContent,/private-passphrase/);assert.doesNotMatch(h.field('audit').textContent,/PRIVATE-NET|private-passphrase|123456|params|result/);
 pin.value='999999';psk.value='forgotten-secret';h.panel.detach();assert.equal(pin.value,'');assert.equal(psk.value,'');assert.equal(h.field('pin'),undefined);h.panel.destroy();
});

test('credential errors clear fields and replacing confidential session with BLE-like client removes forms',async()=>{
 const h=harness(),f=recordingClient();h.panel.attach(f.client,{apiVersion:44});const pin=h.field('pin');pin.value='invalid';await h.field('authenticate').fire('click');assert.equal(pin.value,'');assert.match(h.field('status').textContent,/PARAMS/);assert.equal(f.requests.length,0);
 const replacement=recordingClient({confidential:false});h.panel.attach(replacement.client,{apiVersion:44});assert.equal(f.client.closed,true);assert.equal(h.field('pin'),undefined);assert.equal(h.field('psk'),undefined);assert.equal(replacement.requests.length,0);h.panel.destroy();
});

test('discarded credential form events cannot invalidate or authenticate a replacement session',async()=>{
 const h=harness(),first=recordingClient();h.panel.attach(first.client,{apiVersion:44});
 const oldPin=h.field('pin'),oldAuth=h.field('authenticate'),oldNetwork=h.field('provision-prepare');oldPin.value='123456';
 const replacement=recordingClient({confidential:false});h.panel.attach(replacement.client,{apiVersion:44});assert.equal(oldPin.value,'');
 await h.select('hello');await h.prepare();const preview=h.panel.controller.snapshot().prepared;
 await oldPin.fire('input');await oldAuth.fire('click');await oldNetwork.fire('click');
 assert.equal(h.panel.controller.snapshot().prepared,preview);assert.equal(replacement.transport.writes,0);assert.equal(replacement.client.authenticated,false);h.panel.destroy();
});

test('updates share the specific review/confirm path and are never replayed',async()=>{
 const h=harness(),f=recordingClient();await authenticated(h,f);
 for(const [method,params] of [['update.apply','{"component":"robotd","target":"latest"}'],['update.rollback','{"component":"robotd"}'],['update.select','{"component":"robotd","version":"1.2.3"}']]){
  await h.select(method,params);await h.prepare();assert.match(h.field('confirm').parentNode.textContent,new RegExp(method.replace('.','\\.')));const before=f.requests.length;await h.execute();assert.equal(f.requests.length,before);await h.confirm();await h.execute();assert.equal(f.requests.length,before+1);assert.equal(h.field('execute').disabled,true);
 }
 h.panel.destroy();
});

test('late completion after editing or replacing a session cannot replace current transient UI',async()=>{
 const f=recordingClient({delay:new Set(['system.info'])}),h=harness();await authenticated(h,f);await h.select('system.info');await h.prepare();const pending=h.execute();await tick();assert.equal(f.pending.length,1);
 h.field('params').value='{}';await h.field('params').fire('input');f.pending.shift()();await pending;assert.equal(h.field('result').textContent,'No transient result.');assert.match(h.field('status').textContent,/Inputs changed/);
 await h.prepare();const second=h.execute();await tick();const next=recordingClient({confidential:false});h.panel.attach(next.client,{apiVersion:44});await second;assert.equal(h.panel.controller.snapshot().authenticated,false);assert.equal(h.field('result').textContent,'No transient result.');assert.match(h.field('status').textContent,/Client attached/);assert.equal(next.transport.writes,0);h.panel.destroy();
});

test('cancel and timeout close pending real RPC without retry; timeout keeps unknown outcome visible',async()=>{
 const f=recordingClient({delay:new Set(['robot.sound'])}),h=harness();await authenticated(h,f);await h.select('robot.sound');await h.prepare();await h.confirm();const pending=h.execute();await tick();await h.field('cancel').fire('click');await pending;
 assert.equal(f.client.closed,true);assert.equal(f.requests.filter(request=>request.method==='robot.sound').length,1);assert.match(h.field('status').textContent,/not an emergency stop/);assert.equal(h.field('execute').disabled,true);h.panel.destroy();
 const slow=recordingClient({timeoutMs:20,delay:new Set(['system.info'])}),other=harness();await authenticated(other,slow);await other.request('system.info');assert.equal(slow.client.closed,true);assert.match(other.field('status').textContent,/TIMEOUT \/ unknown/);assert.match(other.field('status').textContent,/Inspect the remote state/);assert.equal(slow.requests.filter(request=>request.method==='system.info').length,1);other.panel.destroy();
});

test('disconnect during a pending RPC retains unknown-outcome warning across session replacement and edits',async()=>{
 const f=recordingClient({delay:new Set(['robot.sound'])}),h=harness();await authenticated(h,f);await h.select('robot.sound');await h.prepare();await h.confirm();const pending=h.execute();await tick();
 await h.field('disconnect').fire('click');await pending;assert.equal(f.client.closed,true);assert.match(h.field('status').textContent,/unknown outcome; inspect remote state/);assert.equal(f.requests.filter(request=>request.method==='robot.sound').length,1);
 const replacement=recordingClient({confidential:false});h.panel.attach(replacement.client,{apiVersion:44});assert.match(h.field('status').textContent,/unknown outcome; inspect remote state/);await h.select('hello');assert.match(h.field('status').textContent,/unknown outcome; inspect remote state/);assert.equal(replacement.transport.writes,0);h.panel.destroy();
});

test('a GATT drop during pending hello closes RPC and preserves explicit unknown-outcome guidance',async()=>{
 const f=gatt();f.characteristic.writeValueWithResponse=async()=>{f.counts.writes++;};
 const h=harness({bluetooth:f.provider,timeoutMs:200});await h.field('bluetooth').fire('click');await h.select('hello');await h.prepare();const pending=h.execute();await tick();assert.ok(f.counts.writes>0);
 f.device.gatt.disconnect();await pending;assert.equal(h.panel.controller.snapshot().phase,'disconnected');assert.match(h.field('status').textContent,/Bluetooth disconnected/);assert.match(h.field('status').textContent,/unknown outcome; inspect remote state/);const writes=f.counts.writes;await h.execute();assert.equal(f.counts.writes,writes);h.panel.destroy();
});

test('remote text renders only as bounded ephemeral text; audit contains metadata and stays bounded',async()=>{
 const f=recordingClient({response:request=>request.method==='system.authenticate'?{authenticated:true}:{html:'<img src=x onerror=alert(1)>',password:'HIDDEN',log:'x'.repeat(20000),extra:Array(16).fill('y'.repeat(2500))}}),h=harness();await authenticated(h,f);
 await h.request('system.info');assert.match(h.field('result').textContent,/<img src=x onerror=alert\(1\)>/);assert.doesNotMatch(h.field('result').textContent,/HIDDEN/);assert.ok(h.field('result').textContent.length<8300);assert.equal(h.container.all(node=>node.tagName==='IMG').length,0);
 for(let count=0;count<34;count++)await h.request('system.info');const audit=JSON.parse(h.field('audit').textContent);assert.equal(audit.length,32);assert.deepEqual(Object.keys(audit[0]),['sequence','method','outcome','code','simulation']);assert.doesNotMatch(h.field('audit').textContent,/HIDDEN|onerror|log|params/);
 await h.field('refresh').fire('click');assert.equal(h.field('result').textContent,'No transient result.');h.panel.destroy();assert.equal(h.container.children.length,0);
});

test('pagehide/destroy cancel pending chooser and discard late device before GATT; listeners are removed',async()=>{
 let choose;const provider={requestDevice(){return new Promise(resolve=>{choose=resolve;});}},f=gatt(),h=harness({bluetooth:provider});const pending=h.field('bluetooth').fire('click');assert.equal(h.field('bluetooth').disabled,true);h.lifecycle.dispatchEvent(new Event('pagehide'));choose(f.device);await pending;assert.equal(f.counts.connect,0);assert.equal(f.counts.writes,0);assert.equal(h.panel.controller.snapshot().phase,'disconnected');h.panel.destroy();h.panel.destroy();assert.equal(h.lifecycle.handlers.size,0);assert.equal(h.container.children.length,0);
});

test('GATT timeout closes late connection and allows a fresh explicit session without RPC writes',async()=>{
 const f=gatt();let finish;
 f.device.gatt.connect=()=>new Promise(resolve=>{f.counts.connect++;finish=()=>{f.device.gatt.connected=true;resolve(f.server);};});
 const h=harness({bluetooth:f.provider,timeoutMs:10});await h.field('bluetooth').fire('click');assert.match(h.field('status').textContent,/discovery timed out/);assert.equal(h.panel.controller.snapshot().phase,'disconnected');
 finish();await tick();assert.equal(f.device.gatt.connected,false);assert.equal(f.counts.writes,0);
 f.device.gatt.connect=async()=>{f.counts.connect++;f.device.gatt.connected=true;return f.server;};await h.field('bluetooth').fire('click');assert.equal(f.device.gatt.connected,true);assert.equal(h.panel.controller.snapshot().apiVersion,44);
 await h.field('disconnect').fire('click');assert.equal(f.device.gatt.connected,false);assert.equal(f.counts.writes,0);h.panel.destroy();
});

test('standalone page uses only local scripts, no inline JavaScript, and forbids network connections',()=>{
 const directory=path.resolve(__dirname,'../web/microduck'),html=fs.readFileSync(path.join(directory,'console.html'),'utf8');assert.match(html,/<link rel="stylesheet" href="\.\.\/portal\.css">/);assert.match(html,/connect-src 'none'/);assert.match(html,/default-src 'none'/);assert.match(html,/form-action 'none'/);assert.doesNotMatch(html,/<script\b(?![^>]*\bsrc=)[^>]*>/i);assert.doesNotMatch(html,/\son[a-z]+\s*=/i);
 for(const [,source]of html.matchAll(/<script src="([^"]+)"/g)){assert.ok(!source.includes('://'));assert.ok(fs.existsSync(path.join(directory,source)),source);}
 const source=fs.readFileSync(path.join(directory,'console-panel.js'),'utf8');assert.doesNotMatch(source,/\b(?:fetch|WebSocket|XMLHttpRequest|localStorage|sessionStorage)\b|\.innerHTML\s*=/);assert.match(html,/graphical browser acceptance remain pending/);
});

test('watch controls are passive and real unauthenticated BLE cannot start an observation',async()=>{
 const f=gatt(),h=harness({bluetooth:f.provider});assert.equal(h.field('watch').disabled,true);assert.equal(h.field('watch-stop').disabled,true);
 await h.field('bluetooth').fire('click');assert.equal(h.field('watch').disabled,true);await h.field('watch').fire('click');assert.equal(f.counts.writes,0);assert.equal(h.field('pin'),undefined);h.panel.destroy();assert.equal(f.device.gatt.connected,false);
});

test('fictional console watch consumes staged confirmations and advances only fictional samples',async()=>{
 const h=harness();await h.field('simulation').fire('click');await h.field('authenticate').fire('click');
 await h.select('robot.sound','{"tag":"chirp"}');await h.prepare();await h.confirm();assert.equal(h.field('confirm').checked,true);
 await h.field('watch').fire('click');assert.equal(h.panel.controller.snapshot().prepared,null);assert.equal(h.panel.controller.snapshot().busy,true);assert.equal(h.field('confirm').checked,false);assert.equal(h.field('method').disabled,true);assert.equal(h.field('execute').disabled,true);assert.equal(h.field('watch-stop').disabled,false);assert.equal(h.field('watch-advance').disabled,false);
 assert.match(h.field('watch-result').textContent,/SIMULATION \/ FICTIONAL/);assert.match(h.field('watch-result').textContent,/"phase": "idle"/);assert.match(h.field('watch-status').textContent,/do not prove/);
 await h.field('watch-advance').fire('click');await h.field('watch-advance').fire('click');assert.match(h.field('watch-result').textContent,/downloading/);
 assert.ok(!h.panel.controller.snapshot().history.some(entry=>entry.method==='robot.sound'));
 await h.field('watch-stop').fire('click');assert.match(h.field('watch-status').textContent,/WATCH_STOPPED/);assert.match(h.field('watch-status').textContent,/not an update outcome/);assert.doesNotMatch(h.field('status').textContent,/unknown outcome/);assert.equal(h.panel.controller.snapshot().phase,'closed');
 assert.equal(h.field('refresh').disabled,false);await h.field('refresh').fire('click');assert.equal(h.field('watch-result').textContent,'No progress samples.');h.panel.destroy();
});

test('watch keeps eight typed samples, omits daemon detail and cannot issue overlapping commands',async()=>{
 const f=recordingClient({stream:true}),h=harness();await authenticated(h,f);await h.field('watch').fire('click');
 for(let count=0;count<20;count++)f.transport.receive(new TextEncoder().encode(JSON.stringify({jsonrpc:'2.0',method:'update.progress',params:{component:'robotd',phase:'downloading',percent:count,detail:'<img src=x onerror=alert(1)> PRIVATE-DETAIL'}})+'\n'));
 const rows=JSON.parse(h.field('watch-result').textContent);assert.equal(rows.length,8);assert.deepEqual(rows.map(row=>row.percent),[12,13,14,15,16,17,18,19]);assert.ok(rows.every(row=>row.detailOmitted));assert.doesNotMatch(h.field('watch-result').textContent,/PRIVATE|onerror/);assert.equal(h.container.all(node=>node.tagName==='IMG').length,0);
 await h.field('watch').fire('click');await h.field('execute').fire('click');assert.deepEqual(f.requests.map(row=>row.method),['system.authenticate','update.subscribe']);await h.field('watch-stop').fire('click');assert.equal(f.client.closed,true);h.panel.destroy();
});

test('watch session replacement and late callbacks cannot change the new console or claim a mutation outcome',async()=>{
 const first=recordingClient({stream:true}),second=recordingClient(),h=harness();await authenticated(h,first);await h.field('watch').fire('click');
 const late=first.transport.receive;h.panel.attach(second.client,{apiVersion:44});assert.equal(first.client.closed,true);assert.equal(h.field('watch').disabled,true);assert.equal(h.field('watch-result').textContent,'No progress samples.');
 late?.(new TextEncoder().encode(JSON.stringify({jsonrpc:'2.0',method:'update.progress',params:{component:'robotd',phase:'idle',percent:100}})+'\n'));
 assert.equal(h.field('watch-result').textContent,'No progress samples.');assert.doesNotMatch(h.field('status').textContent,/unknown outcome/);assert.deepEqual(second.requests,[]);h.panel.destroy();
});

test('watch duration closes read-only observation without a fabricated updater success or retry',async()=>{
 const f=recordingClient({stream:true}),h=harness({watchDurationMs:10});await authenticated(h,f);await h.field('watch').fire('click');
 await new Promise(resolve=>setTimeout(resolve,25));assert.equal(f.client.closed,true);assert.match(h.field('watch-status').textContent,/WATCH_TIME_LIMIT/);assert.match(h.field('watch-status').textContent,/not an update outcome/);assert.doesNotMatch(h.field('status').textContent,/unknown outcome/);assert.equal(f.requests.length,2);h.panel.destroy();
});

test('matching watch refusal is bounded text and does not become a pending mutation warning',async()=>{
 const f=recordingClient({stream:true}),h=harness();await authenticated(h,f);await h.field('watch').fire('click');
 f.transport.receive(new TextEncoder().encode(JSON.stringify({jsonrpc:'2.0',id:2,error:{code:-32003,message:'PRIVATE-ERROR',data:'PRIVATE-DATA'}})+'\n'));
 assert.match(h.field('watch-status').textContent,/REMOTE_-32003/);assert.doesNotMatch(h.container.textContent,/PRIVATE-ERROR|PRIVATE-DATA|unknown outcome/);assert.equal(f.requests.length,2);assert.equal(f.client.closed,true);h.panel.destroy();
});

test('page exit closes a watch and drops its visible metadata without retry or updater action',async()=>{
 const f=recordingClient({stream:true}),h=harness();await authenticated(h,f);await h.field('watch').fire('click');h.lifecycle.dispatchEvent(new Event('pagehide'));
 assert.equal(f.client.closed,true);assert.equal(h.field('watch-result').textContent,'No progress samples.');assert.equal(h.panel.controller.snapshot().phase,'disconnected');assert.equal(f.requests.length,2);assert.doesNotMatch(h.field('status').textContent,/unknown outcome/);h.panel.destroy();assert.equal(h.lifecycle.handlers.size,0);
});
