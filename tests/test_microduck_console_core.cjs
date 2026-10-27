/* SPDX-License-Identifier: MIT */
// Real policy/RPC with private in-memory peers only; no radio/network/robot.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const core=require('../web/microduck/console-core.js');
const {RpcClient,Lines}=require('../web/microduck/rpc.js');
const {BleTransport}=require('../web/microduck/bluetooth.js');
const {createFixture}=require('../web/microduck/console-fixture.js');
const tick=()=>new Promise(resolve=>setImmediate(resolve));
function setup(options={}){const fixture=createFixture(options),c=new core.Controller();c.attach(fixture.client,{apiVersion:44,simulation:true});return {c,fixture};}
async function rejects(work,code,outcome){await assert.rejects(work,error=>{assert.equal(error.code,code);if(outcome)assert.equal(error.outcome,outcome);return true;});}
async function call(c,method,params={},confirmed=false){return c.execute(c.preview(method,JSON.stringify(params)),{confirmed});}

test('strict parser bounds complete JSON, decoded duplicate names, prototypes and UTF-16',()=>{
 assert.deepEqual(core.parseParams(' {"a":[0,false,null,"café 🦆"]} '),{a:[0,false,null,'café 🦆']});
 for(const text of ['{}{}','[]','null','{"x":01}','{"x":1e999}','{"x":true,}','{"x":"\\ud800"}','{"__proto__":{}}','{"constructor":1}'])assert.throws(()=>core.parseParams(text),{code:'JSON_PARAMS'});
 assert.throws(()=>core.parseParams('{"a":1,"\\u0061":2}'),{code:'JSON_DUPLICATE'});
 assert.throws(()=>core.parseParams(' '.repeat(4097)),{code:'JSON_LIMIT'});
 assert.throws(()=>core.parseParams('{"x":'+'['.repeat(17)+'0'+']'.repeat(17)+'}'),{code:'JSON_LIMIT'});
 assert.throws(()=>core.parseParams('{"x":['+Array(257).fill('0').join(',')+']}'),{code:'JSON_LIMIT'});
 assert.equal({}.polluted,undefined);
});

test('attach and preview are passive; exact API and existing RpcClient required',async()=>{
 const {c,fixture}=setup();assert.equal(fixture.snapshot().stats.requests,0);
 const p=c.preview('hello');assert.equal(fixture.snapshot().stats.requests,0);assert.equal(p.mutation,false);assert.ok(Object.isFrozen(p));
 assert.equal((await c.execute(p)).result.api_version,44);assert.equal(c.snapshot().authenticated,false);
 assert.throws(()=>c.preview('system.info'),{code:'AUTH_REQUIRED'});
 assert.throws(()=>c.preview('hello','{"api_version":45}'),{code:'API_VERSION'});
 assert.throws(()=>c.attach(fixture.client,{apiVersion:44,confidential:true}),{code:'PARAMS'});
 assert.throws(()=>new core.Controller().attach({}, {apiVersion:44}),{code:'PARAMS'});
 assert.throws(()=>new core.Controller().attach(fixture.client,{apiVersion:45}),{code:'API_VERSION'});
 assert.equal(typeof c.makeStage,'undefined');assert.equal(typeof c.perform,'undefined');c.detach();
});

test('real BLE confidentiality is immutable and no secret/protected write can pass',async()=>{
 const device=new EventTarget(),characteristic=new EventTarget();let writes=0;
 device.gatt={connected:true,disconnect(){this.connected=false;device.dispatchEvent(new Event('gattserverdisconnected'));}};
 characteristic.writeValueWithResponse=async()=>{writes++;};
 const transport=new BleTransport(device,characteristic),client=new RpcClient(transport),c=new core.Controller();
 c.attach(client,{apiVersion:44});assert.equal(Reflect.set(transport,'confidential',true),false);
 await rejects(c.authenticate('000000'),'CONFIDENTIALITY_REQUIRED','not_sent');
 assert.throws(()=>c.previewProvisioning({ssid:'LOCAL-FAKE-NET',psk:'FAKE-PASSWORD'}),{code:'CONFIDENTIALITY_REQUIRED'});
 assert.throws(()=>c.preview('robot.sound','{"tag":"chirp"}'),{code:'AUTH_REQUIRED'});
 assert.equal(writes,0);assert.equal(c.snapshot().confidential,false);c.detach();
});

test('raw console denies secret fields/methods, streaming and unsupported control before writes',async()=>{
 const {c,fixture}=setup();await c.authenticate(core.FIXTURE_PIN);const before=fixture.snapshot().stats.requests;
 for(const method of ['exec','robot.move','robot.loadPolicy','system.reboot','update.pin','update.resetToGolden','update.subscribe'])assert.throws(()=>c.preview(method),{code:'METHOD_DENIED'});
 for(const method of ['net.connect','system.authenticate'])assert.throws(()=>c.preview(method),{code:'SECRET_FORM_REQUIRED'});
 for(const key of ['PIN','password','psk','access_token','authorization'])assert.throws(()=>c.preview('system.info',JSON.stringify({nested:{[key]:'FAKE ONLY'}})),{code:'SECRET_INPUT_DENIED'});
 assert.equal(fixture.snapshot().stats.requests,before);assert.equal(fixture.snapshot().actions.length,0);c.detach();
});

test('each supported mutation requires a fresh exact preview and confirmation',async()=>{
 const {c,fixture}=setup();await c.authenticate(core.FIXTURE_PIN);
 const mutations=['system.setName','net.forget','robot.sound','robot.init','robot.enable','update.apply','update.rollback','update.select'];
 for(const method of mutations){
  const p=c.preview(method,core.EXAMPLES[method]),before=fixture.snapshot().actions.length;
  await rejects(c.execute(p),'CONFIRMATION_REQUIRED','not_sent');assert.equal(fixture.snapshot().actions.length,before);
  await rejects(c.execute(p,{confirmed:true}),'STALE_PREVIEW','not_sent');
  const actual=c.preview(method,core.EXAMPLES[method]);const done=await c.execute(actual,{confirmed:true});
  assert.equal(done.outcome,'completed');assert.equal(done.simulation,true);assert.equal(fixture.snapshot().actions.length,before+1);
  await rejects(c.execute(actual,{confirmed:true}),'STALE_PREVIEW','not_sent');
 }
 assert.equal(fixture.snapshot().actions.length,mutations.length);c.detach();
});

test('every raw-console method runs through policy, normalization, real RPC and fictional backend',async()=>{
 const {c,fixture}=setup();await c.authenticate(core.FIXTURE_PIN);await call(c,'robot.policies');
 for(const method of core.METHODS){
  const preview=c.preview(method,core.EXAMPLES[method]);
  const reply=await c.execute(preview,{confirmed:core.describe(method).mutation});
  assert.equal(reply.method,method);assert.equal(reply.outcome,'completed');assert.equal(reply.simulation,true);
 }
 assert.ok(core.METHODS.length>20);assert.equal(fixture.snapshot().stats.maxAckInFlight,1);c.detach();
});

test('copying/editing/replacing or invalidating a preview cannot reuse consent',async()=>{
 const {c,fixture}=setup();await c.authenticate(core.FIXTURE_PIN);
 const first=c.preview('robot.sound','{"tag":"chirp"}');assert.equal(Reflect.set(first,'method','robot.init'),false);
 await rejects(c.execute({...first},{confirmed:true}),'STALE_PREVIEW','not_sent');
 c.invalidate();await rejects(c.execute(first,{confirmed:true}),'STALE_PREVIEW','not_sent');
 const old=c.preview('robot.sound','{"tag":"chirp"}'),newer=c.preview('robot.sound','{"tag":"coo"}');
 await rejects(c.execute(old,{confirmed:true}),'STALE_PREVIEW','not_sent');
 await c.execute(newer,{confirmed:true});assert.equal(fixture.snapshot().actions.length,1);c.detach();
});

test('review renders directional controls as explicit JSON escapes without changing intended parameters',async()=>{
 const {c}=setup();await c.authenticate(core.FIXTURE_PIN);
 const name='SIMULATION\u202e-visible',p=c.preview('system.setName',JSON.stringify({name}));
 assert.match(p.paramsPreview,/\\u202e/);assert.doesNotMatch(p.paramsPreview,/\u202e/);assert.equal(JSON.parse(p.paramsPreview).name,name);c.detach();
});

test('skill names require discovery and are rechecked immediately before execution',async()=>{
 const {c,fixture}=setup();await c.authenticate(core.FIXTURE_PIN);
 assert.throws(()=>c.preview('robot.do','{"skill":"simulation_bow"}'),{code:'UNDISCOVERED_SKILL'});
 await call(c,'robot.policies');assert.deepEqual(c.snapshot().skills,['simulation_bow','simulation_nod']);
 const p=c.preview('robot.do','{"skill":"simulation_bow"}');fixture.setSkills(['simulation_nod']);
 await rejects(c.execute(p,{confirmed:true}),'UNDISCOVERED_SKILL','not_sent');assert.equal(fixture.snapshot().actions.length,0);
 const valid=c.preview('robot.do','{"skill":"simulation_nod"}');await c.execute(valid,{confirmed:true});
 assert.equal(fixture.snapshot().actions.length,1);assert.equal(c.snapshot().skills.includes('simulation_bow'),false);c.detach();
});

test('fixture provisioning accepts only a confirmed open fictional SSID and no credential input',async()=>{
 const {c,fixture}=setup();await rejects(c.authenticate('123456'),'SIMULATION_INPUT','not_sent');await c.authenticate(core.FIXTURE_PIN);
 assert.throws(()=>c.previewProvisioning({ssid:'NOT-FIXTURE'}),{code:'SIMULATION_INPUT'});
 assert.throws(()=>c.previewProvisioning({ssid:core.FIXTURE_SSID,psk:'FAKE-PASSWORD'}),{code:'SIMULATION_INPUT'});
 const p=c.previewProvisioning({ssid:core.FIXTURE_SSID});await c.execute(p,{confirmed:true});
 assert.equal(fixture.snapshot().actions.length,1);assert.doesNotMatch(JSON.stringify(c.snapshot()),/000000|FAKE-PASSWORD/);c.detach();
});

test('timeout, disconnect, protocol loss and remote rejection never replay a command',async()=>{
 for(const [fault,code,outcome]of [['timeout','TIMEOUT','unknown'],['disconnect','DISCONNECTED','unknown'],['malformed','PROTOCOL','unknown'],['wrong_id','TIMEOUT','unknown'],['remote_error','REMOTE_-32099','rejected']]){
  const {c,fixture}=setup({fault,faultMethod:'robot.sound',timeoutMs:30});await c.authenticate(core.FIXTURE_PIN);
  const p=c.preview('robot.sound','{"tag":"chirp"}');
  await assert.rejects(c.execute(p,{confirmed:true}),error=>{assert.equal(error.outcome,outcome);assert.match(error.code,fault==='remote_error'?/^REMOTE_/:new RegExp('^'+code+'$'));return true;});
  const count=fixture.snapshot().stats.requests;await rejects(c.execute(p,{confirmed:true}),'STALE_PREVIEW','not_sent');assert.equal(fixture.snapshot().stats.requests,count);c.detach();
 }
});

test('cancel or session replacement consumes a pending action and drops stale completion',async()=>{
 const {c,fixture}=setup({fault:'timeout',faultMethod:'robot.sound',timeoutMs:100});await c.authenticate(core.FIXTURE_PIN);
 const p=c.preview('robot.sound','{"tag":"chirp"}'),running=c.execute(p,{confirmed:true});await tick();c.cancel();
 await rejects(running,'CANCELLED','unknown');assert.equal(c.snapshot().phase,'closed');
 const next=createFixture();c.attach(next.client,{apiVersion:44,simulation:true});assert.equal(c.snapshot().authenticated,false);assert.deepEqual(c.snapshot().history,[]);
 await c.authenticate(core.FIXTURE_PIN);const newer=c.preview('robot.sound','{"tag":"coo"}');
 const another=createFixture();c.attach(another.client,{apiVersion:44,simulation:true});await rejects(c.execute(newer,{confirmed:true}),'STALE_PREVIEW','not_sent');
 assert.equal(another.snapshot().stats.requests,0);assert.equal(fixture.snapshot().actions.length<=1,true);c.detach();
});

test('audit is bounded metadata; results are ephemeral and sanitized independently',async()=>{
 const {c}=setup();await c.authenticate(core.FIXTURE_PIN);for(let i=0;i<40;i++)await call(c,'robot.health');
 const s=c.snapshot();assert.equal(s.history.length,32);assert.ok(s.history.every(entry=>Object.keys(entry).sort().join(',')==='code,method,outcome,sequence,simulation'));
 assert.equal(Object.hasOwn(s,'result'),false);assert.equal(Object.hasOwn(s,'client'),false);assert.equal(s.prepared,null);c.detach();assert.deepEqual(c.snapshot().history,[]);
});

function privatePeer(){
 let receive=null;const frames=new Lines(),requests=[];
 const transport=Object.freeze({confidential:true,subscribe(fn){receive=fn;return()=>{receive=null;};},close(){receive=null;},async write(bytes){
  for(const text of frames.push(bytes)){const q=JSON.parse(text);requests.push(q);const result=q.method==='system.authenticate'?{authenticated:true,attempts_remaining:3,pin:q.params.pin,token:'FAKE TOKEN'}:
   {outcome:'connected',ssid:q.params.ssid,psk:q.params.psk,[q.params.psk]:'FAKE key echo',nested:{echo:'FAKE echo '+q.params.psk},html:'<img src=x onerror=evil()>',large:'z'.repeat(12000)};
   receive?.(new TextEncoder().encode(JSON.stringify({jsonrpc:'2.0',id:q.id,result})+'\n'));
  }
 }});return {client:new RpcClient(transport),requests};
}
test('future confidential structured path redacts previews/results and never records credentials',async()=>{
 const peer=privatePeer(),c=new core.Controller();c.attach(peer.client,{apiVersion:44});
 const auth=await c.authenticate('123456');assert.deepEqual(auth,{authenticated:true,attempts_remaining:3});
 const credential='FAKE-PASSPHRASE-ONLY',p=c.previewProvisioning({ssid:'LOCAL-UNIT-TEST',psk:credential});
 assert.match(p.paramsPreview,/redacted/);assert.doesNotMatch(p.paramsPreview,new RegExp(credential));
 const done=await c.execute(p,{confirmed:true});assert.doesNotMatch(JSON.stringify(done),new RegExp(credential));
 assert.equal(done.result.psk,'[redacted]');assert.match(done.result.nested.echo,/redacted/);assert.ok(done.result.large.length<=4096);
 assert.equal(done.result.html,'<img src=x onerror=evil()>');assert.doesNotMatch(JSON.stringify(c.snapshot()),/123456|FAKE-PASSPHRASE-ONLY/);
 assert.equal(peer.requests[1].params.psk,credential);c.detach();
});
