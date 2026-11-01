/* SPDX-License-Identifier: MIT */
'use strict';
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const C=require('../web/sfc/sfc-core.js');
const E=require('../web/sfc/sfc-execution.js');
const {trace}=require('../tools/sfc_trace.cjs');
const error=code=>e=>e.code===code;
const plan=(graph=C.example('sequence'),bindings=[])=>({version:1,graph,signals:Array.from({length:16},(_,i)=>({id:i+1,label:'Signal '+(i+1)})),bindings});
const bind=(step,signal,qualifier)=>({step,signal,qualifier});
test('execution plan roundtrips separately and old graph import/export reject it',()=>{
 const p=E.example();assert.deepEqual(E.parse(E.serialize(p)),p);
 assert.throws(()=>C.parse(E.serialize(p)),error('DOCUMENT'));
 assert.throws(()=>C.program(p,"module 'Steps & Transitions'"),error('DOCUMENT'));
 assert.throws(()=>E.parse(C.serialize(p.graph)),error('PLAN'));
});
test('strict action schema rejects unsupported qualifiers, undefined IDs and duplicates',()=>{
 const mutations=[p=>p.bindings.push(bind(1,1,'D')),p=>p.bindings.push(bind(1,1,'P')),p=>p.bindings.push(bind(16,1,'N')),p=>p.bindings.push(bind(1,17,'N')),p=>p.signals.push(p.signals[0]),p=>p.bindings.push(bind(1,1,'N'),bind(1,1,'N')),p=>p.extra=true,p=>p.signals[0].extra=true,p=>p.signals[0].label='bad\nlabel',p=>p.bindings.push({...bind(1,1,'N'),ignored:true})];
 for(const mutate of mutations){const p=plan(),before=C.serialize(p.graph);mutate(p);assert.throws(()=>new E.Execution(p));assert.equal(C.serialize(p.graph),before);}
 assert.throws(()=>E.parse('{'),error('JSON'));assert.throws(()=>E.parse(' '.repeat(131073)),error('SIZE'));
 const p=plan();p.signals[0].label='a'.repeat(49);assert.throws(()=>E.checked(p),error('SIGNAL'));
});
test('binding capacities and boundary masks are exact and empty actions are valid',()=>{
 let p=plan();p.signals=[];assert.equal(new E.Execution(p).start().actions.requested,0);
 p=plan();p.graph=C.example('sequence');p.graph.nodes.find(n=>n.kind==='step'&&n.id===2).id=16;
 p.graph.links=p.graph.links.map(l=>({from:l.from==='s2'?'s16':l.from,to:l.to==='s2'?'s16':l.to}));
 p.bindings=[bind(16,16,'N')];const r=new E.Execution(p);r.start();assert.equal(r.scan(1,{1:true}).actions.requested,32768);
 p=plan();p.bindings=Array.from({length:64},(_,i)=>bind(i<32?1:2,i%16+1,i%32<16?'N':'S'));E.checked(p);
 p.bindings.push(bind(1,1,'R'));assert.throws(()=>E.checked(p),error('CAPACITY'));
});
test('explicit priority is an exact permutation of logical transition IDs',()=>{
 for(const priority of [[],[1],[1,1],[2,3],[2,1,3],['2',1],null]){
  const p=plan(C.example('selection'));p.priority=priority;assert.throws(()=>E.checked(p),error('PRIORITY'));
 }
 const p=plan(C.example('selection'));p.priority=[2,1];const original=E.serialize(p),compiled=E.compile(p);
 assert.deepEqual(compiled.order,[2,1]);assert.equal(E.serialize(p),original);
});
test('OR uses explicit priority, preserves logical fired IDs and ignores geometry/order',()=>{
 const p=plan(C.example('selection'));p.priority=[2,1];p.graph.nodes.reverse();p.graph.links.reverse();
 const r=new E.Execution(p);assert.deepEqual(r.mapping(),[{transition:2,slot:1},{transition:1,slot:2}]);r.start();
 const s=r.scan(0,{1:true,2:true});assert.equal(s.active,4);assert.equal(s.fired,2);
 const fallback=plan(C.example('selection')),d=new E.Execution(fallback);d.start();assert.equal(d.scan(0,{1:true,2:true}).active,2);
});
test('priority mapping is sparse-safe through logical T24',()=>{
 const p=plan(C.example('selection'));p.graph.nodes.find(n=>n.kind==='transition'&&n.id===2).id=24;
 p.graph.links=p.graph.links.map(l=>({from:l.from==='t2'?'t24':l.from,to:l.to==='t2'?'t24':l.to}));p.priority=[24,1];
 const r=new E.Execution(p);r.start();assert.equal(r.scan(0,{1:true,24:true}).fired,1<<23);
 assert.throws(()=>r.scan(1,{2:true}),error('INPUT'));
});
test('N P1 P0 S R truth table uses boundary state and clears pulse on the next scan',()=>{
 const r=new E.Execution(plan(undefined,[bind(1,1,'N'),bind(1,2,'P1'),bind(1,3,'P0'),bind(1,4,'S'),bind(2,4,'R'),bind(2,5,'N')]));
 assert.deepEqual(r.start(0).actions,{normal:1,entryPulse:2,exitPulse:0,stored:8,reset:0,requested:11});
 assert.equal(r.scan(0).actions.requested,9);
 assert.deepEqual(r.scan(10,{1:true}).actions,{normal:16,entryPulse:0,exitPulse:4,stored:0,reset:8,requested:20});
 assert.equal(r.scan(20).actions.requested,16);assert.equal(r.scan(30,{2:true}).actions.requested,11);
});
test('stored request survives ordinary steps and R only removes its stored component',()=>{
 const r=new E.Execution(plan(undefined,[bind(1,1,'S'),bind(2,1,'N')]));r.start();assert.equal(r.scan(1,{1:true}).actions.stored,1);
 const q=new E.Execution(plan(undefined,[bind(1,1,'S'),bind(2,1,'R'),bind(2,1,'N'),bind(2,1,'P1')]));q.start();
 assert.deepEqual(q.scan(1,{1:true}).actions,{normal:1,entryPulse:1,exitPulse:0,stored:0,reset:1,requested:1});
});
test('R dominates simultaneous S, does not rearm S until a new entry',()=>{
 const p=plan(C.example(),[bind(2,1,'S'),bind(3,1,'R')]);
 p.graph.nodes.push({kind:'step',id:5,label:'Reset done',x:800,y:500,initial:false},{kind:'transition',id:3,label:'Leave reset',x:800,y:350,guard:'input',afterMs:0});
 p.graph.links.push({from:'s3',to:'t3'},{from:'t3',to:'s5'});
 const r=new E.Execution(p);r.start();assert.equal(r.scan(1,{1:true}).actions.stored,0);
 const s=r.scan(2,{3:true});assert.equal(s.active,18);assert.equal(s.actions.reset,0);assert.equal(s.actions.stored,0);
 assert.equal(r.scan(3).actions.stored,0);assert.equal(r.restartAt(2,4).actions.stored,1);
});
test('parallel shared N stays active while either branch remains',()=>{
 const p=plan(C.example(),[bind(2,1,'N'),bind(3,1,'N')]);
 p.graph.nodes.push({kind:'transition',id:3,label:'Finish left',x:800,y:350,guard:'input',afterMs:0});p.graph.links.push({from:'s2',to:'t3'},{from:'t3',to:'s4'});
 const r=new E.Execution(p);r.start();assert.equal(r.scan(1,{1:true}).actions.normal,1);assert.equal(r.scan(2,{3:true}).active,12);assert.equal(r.state().actions.normal,1);
 r.restartAt(4,3);assert.equal(r.state().actions.normal,0);
});
test('AND cannot cascade and every source timer must be ready after reentry',()=>{
 const p=plan(C.example());p.graph=C.update(p.graph,'t2',{afterMs:100});
 p.graph.nodes.push({kind:'transition',id:3,label:'Reenter left',x:800,y:350,guard:'input',afterMs:0});p.graph.links.push({from:'s2',to:'t3'},{from:'t3',to:'s2'});
 const r=new E.Execution(p);r.start();assert.equal(r.scan(10,{1:true,2:true}).active,6);r.scan(60,{3:true});
 assert.equal(r.scan(110,{2:true}).active,6);assert.equal(r.scan(160,{2:true}).active,8);
});
test('independent transitions are concurrent despite a total priority order',()=>{
 const p=plan(C.example());p.graph.links=p.graph.links.filter(l=>l.to!=='t2');p.graph.links.push({from:'s2',to:'t2'});
 p.graph.nodes.push({kind:'transition',id:3,label:'Right done',x:800,y:350,guard:'input',afterMs:0});p.graph.links.push({from:'s3',to:'t3'},{from:'t3',to:'s4'});p.priority=[3,2,1];
 const r=new E.Execution(p);r.start();r.scan(1,{1:true});const s=r.scan(2,{2:true,3:true});assert.equal(s.fired,6);assert.equal(s.active,8);assert.equal(s.entered,8);
});
test('self-loop has both edge pulses and restarts the elapsed time',()=>{
 const p=plan(C.example('sequence'),[bind(1,1,'P1'),bind(1,2,'P0')]);p.graph.links=p.graph.links.filter(l=>l.from!=='t1'||l.to!=='s2');p.graph.links.push({from:'t1',to:'s1'},{from:'t2',to:'s2'});
 // Keep S2 reachable without affecting self-loop condition.
 p.graph.links.push({from:'t1',to:'s2'});
 const r=new E.Execution(p);r.start();const s=r.scan(10,{1:true});assert.equal(s.entered&1,1);assert.equal(s.exited&1,1);assert.equal(s.actions.requested,3);assert.equal(r.elapsed(1,15),5);
});
test('stopAndClear cancels requests without P0 and restart publishes only new entry',()=>{
 const r=new E.Execution(plan(undefined,[bind(1,1,'S'),bind(1,2,'P0'),bind(2,3,'P1')]));r.start();
 assert.equal(r.stopAndClear().actions.requested,0);assert.equal(r.state().active,0);
 const s=r.restartAt(2,50);assert.equal(s.actions.requested,4);assert.equal(s.actions.exitPulse,0);assert.equal(s.entryMs[1],50);
 assert.equal(r.resetInitial(60).actions.stored,1);assert.equal(r.state().active,1);
 r.restartAt(2,70);r.stopAndClear();assert.equal(r.start(80).active,1);
});
test('invalid restart, rewind, non-Boolean input and repeated start leave all state intact',()=>{
 const r=new E.Execution(E.example());r.start(10);const before=r.state();
 for(const fn of [()=>r.restartAt(16,11),()=>r.restartAt('2',11),()=>r.restartAt(2,9),()=>r.resetInitial(9),()=>r.scan(11,{1:1}),()=>r.scan(11,{99:true}),()=>r.scan(9,{}),()=>r.start(11)]){assert.throws(fn);assert.deepEqual(r.state(),before);}
 assert.throws(()=>r.scan(11,Object.create({1:true})),error('INPUT'));assert.deepEqual(r.state(),before);
});
test('terminal step stays active, stored request persists and input conditions are fresh',()=>{
 const p=E.example(),r=new E.Execution(p);r.start();r.scan(1,{1:true});assert.equal(r.scan(2).active,6);
 const done=r.scan(3,{2:true});assert.equal(done.active,8);assert.equal(done.actions.stored,0);assert.equal(done.actions.entryPulse,4);
 assert.equal(r.scan(4,{1:true,2:true}).active,8);assert.equal(r.state().actions.requested,0);
});
test('caller mutations cannot change an execution already compiled or returned state',()=>{
 const p=E.example(),r=new E.Execution(p);p.priority.reverse();p.bindings[0].qualifier='R';p.graph.nodes.length=0;
 const s=r.start();assert.equal(s.actions.stored,1);s.actions.stored=0;s.entryMs[0]=55;const m=r.mapping();m[0].transition=24;
 assert.equal(r.state().actions.stored,1);assert.equal(r.state().entryMs[0],0);assert.equal(r.mapping()[0].transition,1);
});
test('offline trace validates operations and preserves action data without executing labels',()=>{
 const p=E.example();p.signals[0].label='process.exit(99)';const input=E.serialize(p),ops=[{op:'start',now:0},{op:'scan',now:50,inputs:{1:true}},{op:'scan',now:100,inputs:{2:true}},{op:'resetInitial',now:150},{op:'stopAndClear'}];
 const report=trace(p,ops);assert.equal(report.states.length,5);assert.equal(report.states[2].state.actions.entryPulse,4);assert.equal(report.states[4].state.actions.requested,0);assert.equal(E.serialize(p),input);
 for(const invalid of [[{op:'eval',now:0}],[{op:'start',now:0,extra:1}],[{op:'start'}],Array(1001).fill({op:'stopAndClear'})])assert.throws(()=>trace(p,invalid));
});
test('documented CLI runs the action/reset example as a local trace',()=>{
 const root=path.join(__dirname,'..'),args=[path.join(root,'tools/sfc_trace.cjs'),path.join(root,'examples/sfc/actions-and-reset.sfc-plan.json'),path.join(root,'examples/sfc/actions-and-reset.trace.json')];
 const run=spawnSync(process.execPath,args,{encoding:'utf8',timeout:5000});assert.equal(run.status,0,run.stderr);assert.equal(run.stderr,'');
 const report=JSON.parse(run.stdout);assert.deepEqual(report.states.map(s=>s.state.active),[1,6,8,1,0]);
 assert.deepEqual(report.states.map(s=>s.state.actions.stored),[1,1,0,1,0]);assert.deepEqual(report.states.map(s=>s.state.actions.requested),[1,3,4,1,0]);
});
test('actual C action kernel and unchanged step core agree with JS across full traces',()=>{
 const binary=process.env.MB_SFC_EXECUTION_HOST;assert.ok(binary,'Run tools/test_sfc_execution.py; no hardware fallback.');
 let seed=0x2741;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed;};
 const plans=[E.example(),plan(C.example('selection'),[bind(2,1,'P1'),bind(3,2,'P0')]),plan(C.example('sequence'),[bind(1,1,'S'),bind(2,1,'R')]),
  plan(C.example('sequence'),[bind(1,1,'N'),bind(1,2,'P1'),bind(1,3,'P0'),bind(1,4,'S'),bind(2,4,'R'),bind(2,5,'N')])];
 plans[1].priority=[2,1];
 for(let chart=0;chart<30;chart++){
  const p=plan({version:1,name:'Native seed '+chart,nodes:[],links:[]});
  for(let id=1;id<=6;id++)p.graph.nodes.push({kind:'step',id,label:'S'+id,x:100*id,y:80,initial:id===1});
  for(let id=1;id<=8;id++){
   p.graph.nodes.push({kind:'transition',id,label:'T'+id,x:100*id,y:240,guard:['input','always','never'][random()%3],afterMs:random()%3*50});
   for(const source of id<=6?[id]:[2,4])p.graph.links.push({from:'s'+source,to:'t'+id});
   for(const target of id<=6?[id%6+1]:[1,6])p.graph.links.push({from:'t'+id,to:'s'+target});
  }
  const used=new Set();while(p.bindings.length<24){const b=bind(random()%6+1,random()%16+1,E.QUALIFIERS[random()%5]),key=JSON.stringify(b);if(!used.has(key)){used.add(key);p.bindings.push(b);}}
  p.priority=[1,2,3,4,5,6,7,8];for(let i=7;i>0;i--){const j=random()%(i+1);[p.priority[i],p.priority[j]]=[p.priority[j],p.priority[i]];}plans.push(p);
 }
 const commands=[],expected=[],contexts=[];
 for(const [index,p] of plans.entries()){
  const compiled=E.compile(p),cfg=C.compile(compiled.graph),r=new E.Execution(p),stepMask=cfg.steps.reduce((m,s)=>m|C.bit(s.id),0),signalMask=p.signals.reduce((m,s)=>m|C.bit(s.id),0);
  commands.push(['INIT',0,stepMask,signalMask].join(' '));
  for(const s of cfg.steps)commands.push('ADD '+s.id+' '+Number(s.initial));
  for(const t of cfg.transitions)commands.push(['EDGE',t.id,t.from,t.to,t.afterMs].join(' '));
  for(const m of r.mapping())commands.push('MAP '+m.slot+' '+m.transition);
  for(const b of p.bindings)commands.push(['BIND',b.step,b.signal,E.QUALIFIERS.indexOf(b.qualifier)].join(' '));commands.push('SEAL');
  const record=(cmd,state)=>{commands.push(cmd);expected.push({error:0,...state});contexts.push('plan '+index+' '+cmd);};
  record('START 0',r.start(0));
  for(let scan=1;scan<=60;scan++){
   const now=scan*50;
   if(scan%13===0){const target=cfg.steps[random()%cfg.steps.length].id;record('RESTART '+target+' '+now,r.restartAt(target,now));}
   else if(scan%17===0)record('RESET '+now,r.resetInitial(now));
   else if(scan===29)record('STOP',r.stopAndClear());
   else if(scan===30)record('START '+now,r.start(now));
   else {
    const inputs={};for(const t of C.compile(p.graph).transitions)if(t.guard==='input')inputs[t.id]=(random()&3)!==0;
    for(const t of cfg.transitions){const original=compiled.order[t.id-1],flag=t.guard==='always'||t.guard==='input'&&inputs[original]===true;commands.push('COND '+t.id+' '+Number(flag));}
    record('SCAN '+now,r.scan(now,inputs));
   }
  }
  record('STOP',r.stopAndClear());
 }
 const args=process.env.MB_SFC_WSL?['wsl.exe',['-d',process.env.MB_SFC_WSL,'--',binary]]:[binary,[]];
 const run=spawnSync(...args,{input:commands.join('\n')+'\n',encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024});assert.equal(run.status,0,run.stderr||String(run.error));assert.equal(run.stderr,'');
 const actual=run.stdout.trim().split('\n').map(JSON.parse);assert.equal(actual.length,expected.length);actual.forEach((s,i)=>assert.deepEqual(s,expected[i],contexts[i]));assert.equal(expected.length,2108);
 if(process.env.MB_SFC_PARITY_EVIDENCE)fs.writeFileSync(process.env.MB_SFC_PARITY_EVIDENCE,JSON.stringify({result:'PASS',plans:plans.length,states:expected.length,seed:'0x2741',hardware_access:false},null,2)+'\n');
});
