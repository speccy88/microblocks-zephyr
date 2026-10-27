/* SPDX-License-Identifier: MIT */
// Actual RpcClient with a private in-memory API44 fixture; no browser/radio/SSH.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const commands=require('../web/microduck/commands.js');
const rpc=require('../web/microduck/rpc.js');
const fixtureAPI=require('../web/microduck/console-fixture.js');
const {createFixture,FIXTURE_PIN,FIXTURE_SSID,SKILLS,LIMITS}=fixtureAPI;
const code=expected=>error=>error.code===expected;
const tick=()=>new Promise(resolve=>setImmediate(resolve));

test('fixture is passive and returns the real RpcClient with immutable internal transport',async()=>{
 const f=createFixture();assert.equal(f.apiVersion,44);assert.equal(f.simulation,true);
 assert.equal(f.client.constructor,rpc.RpcClient);assert.ok(f.client instanceof rpc.RpcClient);
 assert.ok(Object.isFrozen(f));assert.ok(Object.isFrozen(f.client.transport));
 assert.equal(f.client.transport.confidential,true);assert.equal(f.client.authenticated,false);
 assert.equal(f.snapshot().stats.requests,0);assert.deepEqual(f.snapshot().audit,[]);
 assert.throws(()=>{f.client.transport={};},TypeError);assert.throws(()=>{f.client.request=()=>{};},TypeError);
 await assert.rejects(f.client.request('system.info'),code('AUTH_REQUIRED'));assert.equal(f.snapshot().stats.requests,0);
 const hello=await f.client.request('hello');assert.equal(hello.api_version,44);assert.equal(hello.simulation,true);
 assert.equal(f.client.authenticated,false);assert.deepEqual(f.snapshot().requests,[{id:1,method:'hello'}]);f.close();
});

test('manual fixed authentication is required and credentials are never recorded',async()=>{
 const f=createFixture();
 await assert.rejects(f.client.authenticate('123456'),code('SIMULATION_INPUT'));
 await assert.rejects(f.client.authenticate('not-a-pin'),code('PARAMS'));
 assert.equal(f.snapshot().stats.requests,0);assert.equal(f.snapshot().stats.writeChunks,0);
 const result=await f.client.authenticate(FIXTURE_PIN);
 assert.equal(result.authenticated,true);assert.equal(result.attempts_remaining,3);assert.equal(result.simulation,true);
 assert.equal(f.client.authenticated,true);assert.equal(f.snapshot().authenticated,true);
 assert.doesNotMatch(JSON.stringify(f.snapshot()),/000000|123456|not-a-pin|"pin"|"params"/);f.close();
});

test('real SSIDs, every PSK field, unknown methods and streaming are rejected before recording',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);const before=f.snapshot().stats;
 for(const [method,params,error] of [
  ['net.connect',{ssid:'real-network'},'SIMULATION_INPUT'],['net.forget',{ssid:'real-network'},'SIMULATION_INPUT'],
  ['net.connect',{ssid:FIXTURE_SSID,psk:'do-not-retain-this'},'SIMULATION_INPUT'],
  ['net.connect',{ssid:FIXTURE_SSID,psk:null},'SIMULATION_INPUT'],
  ['update.subscribe',{},'STREAM_REQUIRED'],['exec',{},'METHOD_DENIED'],['robot.move',{},'METHOD_DENIED'],
  ['hello',{api_version:43},'API_VERSION'],['update.check',{component:'actual-service'},'SIMULATION_INPUT'],
  ['system.logs',{unit:'arbitrary-unit'},'SIMULATION_INPUT'],['robot.health',{psk:'do-not-retain-this'},'PARAMS'],
 ])await assert.rejects(f.client.request(method,params,{confirmed:true}),code(error));
 assert.deepEqual(f.snapshot().stats,before);assert.deepEqual(f.snapshot().actions,[]);
 assert.doesNotMatch(JSON.stringify(f.snapshot()),/real-network|do-not-retain-this|actual-service|arbitrary-unit/);f.close();
});

test('every reviewed nonstreaming method has an API-shaped explicitly fictional reply',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);
 const params={
  'system.authenticate':{pin:FIXTURE_PIN},'update.check':{component:'robotd'},'update.listInstalled':{component:'robotd'},
  'system.logs':{unit:'robotd'},'system.setName':{name:'Demo'},'net.forget':{ssid:FIXTURE_SSID},'net.connect':{ssid:FIXTURE_SSID},
  'robot.enable':{on:true},'robot.do':{skill:SKILLS[0]},'robot.sound':{tag:'chirp'},
  'update.rollback':{component:'robotd'},'update.select':{component:'robotd',version:'0.0.0'},'update.apply':{component:'robotd'},
 };
 for(const method of commands.methods.filter(name=>name!=='update.subscribe')){
  const result=await f.client.request(method,params[method]||{},{confirmed:true});
  if(Array.isArray(result)){for(const row of result)assert.equal(row.simulation,true,method);}
  else{assert.equal(result.simulation,true,method);assert.match(result.notice,/SIMULATION ONLY/);}
 }
 assert.equal(f.snapshot().stats.requests,commands.methods.length);
 assert.equal(f.snapshot().stats.maxWriteBytes,20);assert.ok(f.snapshot().stats.replyChunks>f.snapshot().stats.requests);f.close();
});

test('monitoring, network and discovery match pinned source field shapes',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);
 const health=await f.client.request('robot.health');assert.equal(health.healthy,false);assert.equal(health.degraded,true);
 assert.deepEqual(health.battery,{volts:7.8,percent:73.25});assert.match(health.reason,/fictional/);
 assert.deepEqual((await f.client.request('system.services')).map(x=>[x.unit,x.state]),[['robotd.service','inactive']]);
 const log=await f.client.request('system.logs',{unit:'robotd',lines:20,boot:0});assert.equal(log.unit,'robotd.service');assert.equal(log.truncated,false);assert.match(log.lines[0],/SIMULATION ONLY/);
 const policies=await f.client.request('robot.policies'),details=await f.client.request('robot.skills');assert.deepEqual(policies.skills,details.skills.map(x=>x.name));
 const scan=await f.client.request('net.scan');assert.deepEqual(scan.networks,[{ssid:FIXTURE_SSID,security:'open',signal:88,saved:false}]);
 await assert.rejects(f.client.request('net.connect',{ssid:FIXTURE_SSID}),code('CONFIRMATION_REQUIRED'));
 assert.equal((await f.client.request('net.connect',{ssid:FIXTURE_SSID},{confirmed:true})).ip4,'192.0.2.44');
 assert.equal((await f.client.request('net.status')).state,'connected');
 assert.equal((await f.client.request('net.forget',{ssid:FIXTURE_SSID},{confirmed:true})).removed,true);
 assert.equal((await f.client.request('net.status')).ip4,null);f.close();
});

test('update read shapes and simulated mutations preserve official normalized options',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);
 const status=await f.client.request('update.status');assert.ok(Array.isArray(status));assert.equal(status[0].component,'robotd');assert.equal(status[0].installed,'0.0.0');assert.equal(status[0].phase,'idle');
 const check=await f.client.request('update.check',{component:'robotd'});assert.equal(check.state,'available');assert.equal(check.candidate,'0.0.1-simulation');assert.equal(check.mandatory,false);
 const installed=await f.client.request('update.listInstalled',{component:'robotd'});assert.deepEqual(installed.map(x=>[x.version,x.active,x.golden]),[['0.0.0',true,true]]);
 const input={component:'robotd',target:{exact:'1.2.3'}};
 await assert.rejects(f.client.request('update.apply',input),code('CONFIRMATION_REQUIRED'));
 const applied=await f.client.request('update.apply',input,{confirmed:true});assert.equal(applied.outcome,'applied');assert.equal(applied.from,'0.0.0');assert.equal(applied.to,'1.2.3');assert.equal(applied.simulation,true);
 assert.deepEqual(input,{component:'robotd',target:{exact:'1.2.3'}});
 assert.equal((await f.client.request('update.status'))[0].installed,'1.2.3');
 const selected=await f.client.request('update.select',{component:'robotd',version:'0.0.0'},{confirmed:true});assert.equal(selected.outcome,'applied');
 assert.equal((await f.client.request('update.rollback',{component:'robotd'},{confirmed:true})).outcome,'already_current');
 const logs=await f.client.request('update.log',{limit:1});assert.equal(logs.length,1);assert.deepEqual(logs[0].outcome,{kind:'success'});
 const transcript=await f.client.request('update.show');assert.equal(transcript.component,'robotd');assert.ok(Array.isArray(transcript.available));assert.equal(transcript.events[0].event,'note');assert.match(transcript.events[0].text,/SIMULATION/);
 assert.doesNotMatch(JSON.stringify(f.snapshot()),/1\.2\.3|"params"|"target"|"pin"|"psk"/);f.close();
});

test('raw fixture wire rejects secret credentials and every nonempty or nonobject updater option before audit',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);const before=f.snapshot().stats.requests;
 for(const [method,params,error] of [
  ['system.authenticate',{pin:'123456'},'SIMULATION_INPUT'],
  ['net.connect',{ssid:FIXTURE_SSID,psk:'never-retain-this'},'SIMULATION_INPUT'],
  ...[true,[],{dry_run:true},{from_dir:'/fictional'},{interrupt_sessions:true}].map(options=>['update.apply',{component:'robotd',target:'latest',options},'PARAMS']),
 ]){
  const bytes=new TextEncoder().encode(JSON.stringify({jsonrpc:'2.0',id:99,method,params})+'\n');
  await assert.rejects(async()=>{for(let at=0;at<bytes.length;at+=20)await f.client.transport.write(bytes.slice(at,at+20));},code(error));
 }
 assert.equal(f.snapshot().stats.requests,before);assert.deepEqual(f.snapshot().actions,[]);
 assert.doesNotMatch(JSON.stringify(f.snapshot()),/123456|never-retain-this|\/fictional|dry_run|from_dir|interrupt_sessions/);f.close();
});

test('fixed subset skill hook supports removed capability discovery without invented names',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);
 assert.deepEqual((await f.client.request('robot.policies')).skills,SKILLS);f.setSkills([]);
 assert.deepEqual((await f.client.request('robot.policies')).skills,[]);
 assert.throws(()=>f.setSkills(['bow']),code('PARAMS'));assert.throws(()=>f.setSkills([SKILLS[0],SKILLS[0]]),code('PARAMS'));
 const selected=[SKILLS[1]];f.setSkills(selected);selected.length=0;
 assert.deepEqual((await f.client.request('robot.skills')).skills.map(x=>x.name),[SKILLS[1]]);f.close();
});

test('responses before final acknowledgement never overlap writes or chained requests',async()=>{
 const f=createFixture(),first=f.client.request('hello');
 const next=first.then(()=>f.client.request('hello'));await next;
 assert.equal(f.snapshot().stats.maxAckInFlight,1);assert.deepEqual(f.snapshot().requests,[{id:1,method:'hello'},{id:2,method:'hello'}]);f.close();
});

test('approved deterministic faults use actual RPC matching, deadlines and disconnect cleanup',async()=>{
 for(const [fault,error] of [['timeout','TIMEOUT'],['disconnect','DISCONNECTED'],['remote_error','REMOTE_-32003'],['malformed','PROTOCOL'],['wrong_id','TIMEOUT']]){
  const f=createFixture({timeoutMs:15,fault,faultMethod:'system.info'});await f.client.authenticate(FIXTURE_PIN);
  await assert.rejects(f.client.request('system.info'),code(error));await tick();
  assert.equal(f.snapshot().stats.requests,2);assert.equal(f.snapshot().actions.length,0);
  assert.equal(f.snapshot().audit.at(-1).outcome,fault==='remote_error'?'rejected':'unknown');
  assert.equal(f.client.closed,fault!=='remote_error');f.close();
 }
});

test('accepted simulated mutation can have unknown timeout outcome and is never replayed',async()=>{
 const f=createFixture({timeoutMs:10,fault:'timeout',faultMethod:'robot.sound'});await f.client.authenticate(FIXTURE_PIN);
 await assert.rejects(f.client.request('robot.sound',{tag:'chirp'},{confirmed:true}),code('TIMEOUT'));
 assert.deepEqual(f.snapshot().actions,[{sequence:1,method:'robot.sound',simulation:true}]);
 await assert.rejects(f.client.request('robot.sound',{tag:'chirp'},{confirmed:true}),code('DISCONNECTED'));
 assert.equal(f.snapshot().stats.requests,2);assert.equal(f.snapshot().actions.length,1);f.close();
 const rejected=createFixture({fault:'remote_error',faultMethod:'robot.sound'});await rejected.client.authenticate(FIXTURE_PIN);
 await assert.rejects(rejected.client.request('robot.sound',{tag:'chirp'},{confirmed:true}),code('REMOTE_-32003'));assert.deepEqual(rejected.snapshot().actions,[]);rejected.close();
});

test('action/request/audit bounds and snapshots cannot grow or mutate internal state',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);
 for(let i=0;i<LIMITS.actions;i++)await f.client.request('robot.sound',{tag:'coo'},{confirmed:true});
 const before=f.snapshot().stats.requests;await assert.rejects(f.client.request('robot.sound',{tag:'coo'},{confirmed:true}),code('FIXTURE_ACTION_LIMIT'));
 assert.equal(f.snapshot().stats.requests,before);assert.equal(f.snapshot().actions.length,32);assert.equal(f.snapshot().audit.length,32);
 const copy=f.snapshot();copy.actions.length=0;copy.audit.length=0;copy.skills.length=0;assert.equal(f.snapshot().actions.length,32);assert.equal(f.snapshot().audit.length,32);assert.equal(f.snapshot().skills.length,2);
 while(f.snapshot().stats.requests<LIMITS.requests)await f.client.request('hello');
 await assert.rejects(f.client.request('hello'),code('FIXTURE_LIMIT'));assert.equal(f.snapshot().stats.requests,256);assert.equal(f.snapshot().requests.length,32);f.close();
});

test('close during pending request is final and fresh fixture does not replay history',async()=>{
 const f=createFixture(),pending=f.client.request('hello');f.close();f.close();await assert.rejects(pending,code('DISCONNECTED'));await tick();
 assert.equal(f.client.closed,true);assert.equal(f.snapshot().closed,true);assert.equal(f.snapshot().stats.requests,0);
 const next=createFixture();assert.equal(next.snapshot().stats.requests,0);assert.equal(next.client.authenticated,false);next.close();
});

test('options deny external transports, callbacks, URLs and invalid fault configuration',()=>{
 for(const options of [null,[],{url:'https://invalid.example'},{transport:{}},{bluetooth:{}},{provider:()=>{}},{answer:()=>{}},{timeoutMs:0},{timeoutMs:120001},{fault:'arbitrary'},{fault:'timeout',faultMethod:'update.subscribe'},{faultMethod:'exec'}]){
  assert.throws(()=>createFixture(options),code('PARAMS'));
 }
 const source=fs.readFileSync(require.resolve('../web/microduck/console-fixture.js'),'utf8');
 assert.doesNotMatch(source,/\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|Worker)\s*\(|\b(?:navigator|localStorage|sessionStorage|indexedDB)\b|\.gatt\b|require\(['"]\.\/bluetooth/);
});

test('browser global module works with every external I/O surface unavailable',async()=>{
 const forbidden=()=>{throw Error('External I/O must never be used');};
 const context=vm.createContext({TextEncoder,TextDecoder,Uint8Array,AbortSignal,setTimeout,clearTimeout,fetch:forbidden,WebSocket:forbidden,XMLHttpRequest:forbidden,navigator:new Proxy({},{get:forbidden})});
 for(const name of ['commands.js','rpc.js','console-fixture.js'])vm.runInContext(fs.readFileSync(require.resolve('../web/microduck/'+name),'utf8'),context);
 const pending=vm.runInContext('globalThis.fixture=MicroDuckConsoleFixture.createFixture(); fixture.client.authenticate("000000").then(()=>fixture.client.request("robot.health"))',context);
 const health=await pending;assert.equal(health.simulation,true);assert.equal(health.healthy,false);
 assert.equal(vm.runInContext('fixture.snapshot().stats.requests',context),2);vm.runInContext('fixture.close()',context);
});

test('explicit progress watch uses actual notifications with no reply, action or software change',async()=>{
 const f=createFixture(),samples=[],ends=[];assert.throws(()=>f.advanceUpdate(),code('NO_WATCH'));
 await assert.rejects(f.client.watchUpdates(),code('AUTH_REQUIRED'));await f.client.authenticate(FIXTURE_PIN);
 const handle=await f.client.watchUpdates({onProgress:sample=>samples.push(sample),onEnd:end=>ends.push(end)});
 assert.equal(samples.length,1);assert.equal(samples[0].phase,'idle');assert.equal(samples[0].origin,'simulation');assert.equal(f.snapshot().watching,true);
 for(let at=0;at<8;at++)f.advanceUpdate();assert.deepEqual(samples.map(sample=>sample.phase),['idle','preflight','downloading','downloading','downloading','verifying','health_gate','committing','idle']);
 assert.equal(handle.snapshot().phase,'observing');assert.deepEqual(f.snapshot().actions,[]);assert.deepEqual(f.snapshot().requests.map(row=>row.method),['system.authenticate','update.subscribe']);
 handle.stop();assert.equal(ends.length,1);assert.equal(ends[0].code,'WATCH_STOPPED');assert.equal(f.snapshot().watching,false);assert.throws(()=>f.advanceUpdate(),code('NO_WATCH'));assert.equal(f.snapshot().stats.maxAckInFlight,1);
 const next=createFixture();await next.client.authenticate(FIXTURE_PIN);const installed=await next.client.request('update.listInstalled',{component:'robotd'});assert.equal(installed[0].version,'0.0.0');next.close();
});

test('fixture progress is bounded and event exhaustion closes without replay',async()=>{
 const f=createFixture();await f.client.authenticate(FIXTURE_PIN);const events=[],ends=[];
 const handle=await f.client.watchUpdates({maxEvents:3,onProgress:value=>events.push(value),onEnd:value=>ends.push(value)});
 f.advanceUpdate();f.advanceUpdate();assert.equal(events.length,3);assert.equal(ends[0].code,'WATCH_EVENT_LIMIT');assert.equal(handle.snapshot().phase,'closed');assert.equal(f.snapshot().stats.requests,2);assert.equal(f.snapshot().closed,true);assert.equal(f.snapshot().actions.length,0);f.close();
});

test('browser-global watch is also fictional with every external I/O surface unavailable',async()=>{
 const forbidden=()=>{throw Error('No external I/O');};const context=vm.createContext({TextEncoder,TextDecoder,Uint8Array,AbortSignal,setTimeout,clearTimeout,fetch:forbidden,WebSocket:forbidden,navigator:new Proxy({},{get:forbidden})});
 for(const name of ['commands.js','rpc.js','console-fixture.js'])vm.runInContext(fs.readFileSync(require.resolve('../web/microduck/'+name),'utf8'),context);
 await vm.runInContext('globalThis.fixture=MicroDuckConsoleFixture.createFixture(); globalThis.samples=[]; fixture.client.authenticate("000000").then(()=>fixture.client.watchUpdates({onProgress:value=>samples.push(value)})).then(value=>globalThis.watch=value)',context);
 vm.runInContext('fixture.advanceUpdate(); watch.stop()',context);assert.equal(vm.runInContext('samples.length',context),2);assert.equal(vm.runInContext('samples.every(value=>value.origin==="simulation")',context),true);assert.equal(vm.runInContext('fixture.snapshot().actions.length',context),0);
});
