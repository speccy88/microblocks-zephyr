/* SPDX-License-Identifier: MIT */
// Real RpcClient/NDJSON with an internal in-memory fixture; no GATT or network.
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const simulation=require('../web/microduck/simulation.js');
const code=expected=>error=>error.code===expected;

test('simulation is explicit and exercises real framed API44 handshake only on start',async()=>{
 const session=simulation.createSession();
 assert.equal(session.simulation,true);assert.ok(Object.isFrozen(session));
 assert.equal(session.snapshot().phase,'new');assert.equal(session.snapshot().stats.requests,0);
 await assert.rejects(session.request('robot.health'),code('AUTH_REQUIRED'));
 assert.deepEqual(await session.start(),{api_version:44,daemon_version:'0.0.0-simulation',revision:null});
 const state=session.snapshot();assert.equal(state.phase,'ready');
 assert.deepEqual(state.trace,[{id:1,method:'hello'},{id:2,method:'system.authenticate'}]);
 assert.equal(state.stats.maxWriteBytes,20);assert.ok(state.stats.writeChunks>2);assert.ok(state.stats.replyChunks>2);
 assert.doesNotMatch(JSON.stringify(state),/000000|"pin"/);session.close();
});

test('identity, health and Wi-Fi fixtures are marked fictional with API-shaped values',async()=>{
 const session=simulation.createSession();await session.start();
 const info=await session.request('system.info');assert.equal(info.simulated,true);assert.match(info.name,/SIMULATION/);assert.equal(info.serial,null);
 const health=await session.request('robot.health');assert.equal(health.healthy,false);assert.match(health.reason,/fictional/);
 assert.deepEqual(health.battery,{volts:7.8,percent:73.25});assert.deepEqual(Object.keys(health.battery).sort(),['percent','volts']);
 assert.equal((await session.request('net.status')).ip4,null);
 assert.deepEqual((await session.request('net.scan')).networks,[{ssid:simulation.SSID,signal:88,security:'open',saved:false}]);
 await assert.rejects(session.request('net.connect',{ssid:simulation.SSID}),code('CONFIRMATION_REQUIRED'));
 const result=await session.request('net.connect',{ssid:simulation.SSID},{confirmed:true});assert.equal(result.ip4,'192.0.2.44');
 const status=await session.request('net.status');assert.equal(status.ip4,simulation.IP);assert.equal(status.state,'connected');assert.equal(session.snapshot().joined,true);
 assert.deepEqual(session.snapshot().trace.map(q=>q.id),Array.from({length:session.snapshot().stats.requests},(_,i)=>i+1));session.close();
});

test('public fixture API rejects secret fields, real SSIDs and unsupported methods before writes',async()=>{
 const session=simulation.createSession();await session.start();const before=session.snapshot().stats.requests;
 for(const method of ['system.authenticate','system.setName','update.apply','update.rollback','robot.init','robot.enable','robot.move','robot.stop','media.frame','exec']){
  await assert.rejects(session.request(method,{},{confirmed:true}),code('METHOD_DENIED'));
 }
 await assert.rejects(session.request('net.connect',{ssid:simulation.SSID,psk:'fictional-test-key'},{confirmed:true}),code('SIMULATION_INPUT'));
 await assert.rejects(session.request('net.connect',{ssid:'not-the-demo-SSID'},{confirmed:true}),code('SIMULATION_INPUT'));
 await assert.rejects(session.request('robot.health',{pin:'123456'}),code('PARAMS'));
 assert.equal(session.snapshot().stats.requests,before);assert.deepEqual(session.snapshot().actions,[]);session.close();
});

test('mock actions require individual confirmation and skill discovery',async()=>{
 const session=simulation.createSession();await session.start();
 await assert.rejects(session.request('robot.sound',{tag:'chirp'}),code('CONFIRMATION_REQUIRED'));
 await assert.rejects(session.request('robot.do',{skill:simulation.SKILLS[0]},{confirmed:true}),code('UNDISCOVERED_SKILL'));
 const policies=await session.request('robot.policies'),details=await session.request('robot.skills');
 assert.deepEqual(policies.skills,details.skills.map(s=>s.name));assert.equal(policies.enabled,false);
 await assert.rejects(session.request('robot.do',{skill:'not_advertised'},{confirmed:true}),code('UNDISCOVERED_SKILL'));
 await assert.rejects(session.request('robot.do',{skill:policies.skills[0]}),code('CONFIRMATION_REQUIRED'));
 const parameters={skill:policies.skills[0]};const result=await session.request('robot.do',parameters,{confirmed:true});
 assert.equal(result.simulated,true);assert.match(result.reason,/no physical action/);parameters.skill='modified-after-call';
 assert.equal(session.snapshot().actions[0].params.skill,simulation.SKILLS[0]);
 await session.request('robot.sound',{tag:'coo'},{confirmed:true});
 assert.deepEqual(session.snapshot().actions.map(q=>q.method),['robot.do','robot.sound']);session.close();
});

test('action history and metadata are bounded copies and action limit does not replay',async()=>{
 const session=simulation.createSession();await session.start();
 for(let i=0;i<simulation.MAX_ACTIONS;i++)await session.request('robot.sound',{tag:'chirp'},{confirmed:true});
 const before=session.snapshot().stats.requests;
 await assert.rejects(session.request('robot.sound',{tag:'chirp'},{confirmed:true}),code('ACTION_LIMIT'));
 assert.equal(session.snapshot().stats.requests,before);assert.equal(session.snapshot().actions.length,32);
 for(let i=0;i<40;i++)await session.request('hello');
 assert.equal(session.snapshot().trace.length,simulation.TRACE_LIMIT);
 const changed=session.snapshot();changed.actions.length=0;changed.trace.length=0;changed.stats.requests=0;
 assert.equal(session.snapshot().actions.length,32);assert.equal(session.snapshot().trace.length,64);
 while(session.snapshot().stats.requests<simulation.MAX_REQUESTS)await session.request('hello');
 await assert.rejects(session.request('hello'),code('WRITE_FAILED'));
 assert.equal(session.snapshot().phase,'closed');assert.equal(session.snapshot().actions.length,32);
 await assert.rejects(session.request('hello'),code('DISCONNECTED'));session.close();
});

test('closing a pending start cannot reopen or replay and replacement starts fresh',async()=>{
 const session=simulation.createSession(),pending=session.start();session.close();
 await assert.rejects(pending,code('DISCONNECTED'));assert.equal(session.snapshot().phase,'closed');
 await assert.rejects(session.start(),code('DISCONNECTED'));await assert.rejects(session.request('hello'),code('DISCONNECTED'));
 const next=simulation.createSession();await next.start();assert.deepEqual(next.snapshot().actions,[]);assert.equal(next.snapshot().stats.requests,2);next.close();
});

test('standalone files have no network/GATT/storage entry point or caller transport',()=>{
 const source=fs.readFileSync(require.resolve('../web/microduck/simulation.js'),'utf8')+fs.readFileSync(require.resolve('../web/microduck/simulation-panel.js'),'utf8');
 assert.doesNotMatch(source,/\b(?:fetch|XMLHttpRequest|WebSocket|EventSource|Worker)\s*\(|\b(?:navigator|localStorage|sessionStorage|indexedDB)\b|\.gatt\b|\.sendBeacon\s*\(|require\(['"]\.\/bluetooth/);
 assert.doesNotMatch(source,/innerHTML|insertAdjacentHTML|eval\s*\(|new Function/);
 const html=fs.readFileSync(require.resolve('../web/microduck/simulation.html'),'utf8');
 assert.match(html,/connect-src 'none'/);assert.match(html,/form-action 'none'/);assert.match(html,/SIMULATION|Simulation/);
 assert.doesNotMatch(html,/<script[^>]*src=["']https?:|\bon\w+\s*=|type=["']password|<iframe/i);
 assert.deepEqual([...html.matchAll(/<script src="([^"]+)"/g)].map(x=>x[1]),['commands.js','rpc.js','simulation.js','simulation-panel.js']);
});
