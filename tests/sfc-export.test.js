/* SPDX-License-Identifier: MIT - no actual GP/controller compatibility claim. */
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),{spawnSync}=require('node:child_process');
const C=require('../web/sfc/sfc-core.js'),E=require('../web/sfc/sfc-execution.js'),X=require('../web/sfc/sfc-export.js');
const {parse,Interpreter}=require('./support/sfc_gp_subset.cjs');
const library=fs.readFileSync(path.join(__dirname,'../integration/Steps_Transitions.ubl'),'utf8');
test('export is deterministic, keeps the exact library and never interpolates labels',()=>{
 const p=E.example();p.graph.name="'); dangerousCall 1 //";p.signals[0].label='<script>evil()</script>';
 const source=X.program(p,library);assert(source.endsWith(library));assert(!source.includes('dangerousCall'));assert(!source.includes('<script>'));
 assert.equal(X.program(E.parse(E.serialize(p)),library),source);const parsed=parse(source);assert(parsed.functions.has('sfcResetInitial'));assert.equal(parsed.scripts.length,3);
 assert(!source.includes('digitalWrite'));assert.throws(()=>X.program(p,''),e=>e.code==='LIBRARY');
});
test('draft imports/history stay bounded and execution/export reject incomplete graphs',()=>{
 const p=E.fromGraph(C.empty()),h=new E.DraftHistory(p);assert.deepEqual(E.parseDraft(E.serializeDraft(p)),p);assert.throws(()=>X.program(p,library));assert.throws(()=>new E.Execution(p));
 for(let i=0;i<55;i++){const n=C.copy(h.present);n.graph.name='Draft '+i;h.commit(n);}assert.equal(h.past.length,50);h.undo();h.redo();assert.equal(h.present.graph.name,'Draft 54');
});
test('the owning loop yields before its first scan so initial entry pulses persist',()=>{
 const p=E.example();p.bindings=[{step:1,signal:1,qualifier:'P1'}];
 const v=new Interpreter(X.program(p,library),(name,args)=>name==='[steps:entered]'?args[0]===1:true);v.call('sfcResetInitial');assert.equal(v.vars.sfc_a1,true);
 const loop=v.project.scripts[0].find(s=>s.forever).forever;
 assert.deepEqual(loop[0],{call:'waitMillis',args:[{literal:50}]});assert.deepEqual(loop[1],{call:'sfcScan',args:[]});
 assert(X.program(p,library).includes('red stop does not run this cleanup block'));
});
test('each signal has its own small action publisher at the 64 binding boundary',()=>{
 const p=E.fromGraph(C.example('sequence'));p.signals=Array.from({length:16},(_,i)=>({id:i+1,label:'A'+(i+1)}));
 p.bindings=Array.from({length:64},(_,i)=>({step:i<32?1:2,signal:i%16+1,qualifier:i%32<16?'S':'N'}));
 const project=parse(X.program(p,library));assert.equal(project.variables.length,35);assert.equal([...project.functions.keys()].filter(n=>/^sfcPublishA\d+$/.test(n)).length,16);
});
test('failed native setup or scan clears logical requests and disables further scanning',()=>{
 for(const failure of ['[steps:clear]','[steps:add]','[steps:groups]','[steps:condition]','[steps:scan]']){
  const calls=[],v=new Interpreter(X.program(E.example(),library),(name,args)=>{calls.push([name,args]);if(name===failure)return false;if(['[steps:active]','[steps:entered]'].includes(name))return args[0]===1;return true;});
  v.call('sfcResetInitial');if(!['[steps:clear]','[steps:add]','[steps:groups]'].includes(failure)){assert.equal(v.vars.sfc_a1,true);v.call('sfcScan');}
  assert.equal(v.vars.sfc_ok,false);for(const key of Object.keys(v.vars).filter(k=>/^sfc_[al]/.test(k)))assert.equal(v.vars[key],false);
  const n=calls.length;v.call('sfcScan');assert.equal(calls.length,n);
 }
});
test('emitted GP-subset action code agrees with actual C snapshots and validated JS requests',()=>{
 const binary=process.env.MB_SFC_HOST;assert(binary,'Actual C fixture is required; no hardware fallback.');
 const bind=(step,signal,qualifier)=>({step,signal,qualifier});
 const plans=[E.example(),{version:1,graph:C.example('selection'),signals:[{id:1,label:'Choice'}],bindings:[bind(2,1,'P1'),bind(3,1,'N')],priority:[2,1]},
  {version:1,graph:C.example('sequence'),signals:Array.from({length:5},(_,i)=>({id:i+1,label:'A'+(i+1)})),bindings:[bind(1,1,'N'),bind(1,2,'P1'),bind(1,3,'P0'),bind(1,4,'S'),bind(2,4,'R'),bind(2,5,'N')]}];
 const collision=E.example();collision.bindings=[bind(2,1,'S'),bind(3,1,'R'),bind(2,2,'N'),bind(3,2,'N')];plans.push(collision);
 let seed=0x3027;const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed;};
 const commands=[],jobs=[];let snapshots=0;
 for(const p of plans){
  const compiled=E.compile(p),cfg=C.compile(compiled.graph),ops=[],expected=[],r=new E.Execution(p);
  const configure=now=>{commands.push('INIT '+now);for(const s of cfg.steps)commands.push('ADD '+s.id+' '+Number(s.initial));for(const t of cfg.transitions)commands.push(['EDGE',t.id,t.from,t.to,t.afterMs].join(' '));commands.push('START '+now);snapshots++;};
  commands.push('INIT 0','STOP');snapshots++;configure(0);ops.push({op:'reset',now:0});expected.push(r.start(0));
  for(let scan=1;scan<=40;scan++){
   const now=scan*50;if(scan%13===0){commands.push('STOP');snapshots++;configure(now);ops.push({op:'reset',now});expected.push(r.resetInitial(now));}
   else{
    const inputs={};for(const t of C.compile(p.graph).transitions)if(t.guard==='input')inputs[t.id]=!!(random()&3);
    const conditions=cfg.transitions.map(t=>[t.id,t.guard==='always'||t.guard==='input'&&inputs[compiled.order[t.id-1]]===true]);for(const [id,value] of conditions)commands.push('COND '+id+' '+Number(value));
    commands.push('SCAN '+now);snapshots++;ops.push({op:'scan',inputs,conditions});expected.push(r.scan(now,inputs));
   }
  }commands.push('STOP');snapshots++;ops.push({op:'stop'});expected.push(r.stopAndClear());jobs.push({p,cfg,ops,expected});
 }
 const run=process.env.MB_SFC_WSL?spawnSync('wsl.exe',['-d',process.env.MB_SFC_WSL,'--',binary],{input:commands.join('\n')+'\n',encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024}):spawnSync(binary,[],{input:commands.join('\n')+'\n',encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024});
 assert.equal(run.status,0,run.stderr||String(run.error));assert.equal(run.stderr,'');const states=run.stdout.trim().split('\n').map(JSON.parse);assert.equal(states.length,snapshots);let cursor=0,comparisons=0;
 for(const job of jobs){
  let activeState,op,configured={steps:[],transitions:[]},conditions=[];
  const vm=new Interpreter(X.program(job.p,library),(name,args)=>{
   if(name==='[steps:stop]'){activeState=states[cursor++];assert.equal(activeState.active,0);return true;}
   if(name==='[steps:clear]'){configured={steps:[],transitions:[]};return true;}
   if(name==='[steps:add]'){configured.steps.push({id:args[0],initial:args[1]});return true;}
   if(name==='[steps:groups]'){configured.transitions.push(args);return true;}
   if(name==='[steps:start]'){assert.deepEqual(configured.steps,job.cfg.steps);assert.deepEqual(configured.transitions,job.cfg.transitions.map(t=>[t.id,t.from,t.to,t.afterMs]));activeState=states[cursor++];return true;}
   if(name==='[steps:condition]'){conditions.push(args);return true;}
   if(name==='[steps:scan]'){assert.deepEqual(conditions,op.conditions);conditions=[];activeState=states[cursor++];return true;}
   const field={'[steps:active]':'active','[steps:entered]':'entered','[steps:exited]':'exited'}[name];if(field)return !!(activeState[field]&C.bit(args[0]));throw Error('Unexpected primitive '+name);
  });
  for(let i=0;i<job.ops.length;i++){
   op=job.ops[i];if(op.op==='scan'){for(const t of C.compile(job.p.graph).transitions.filter(t=>t.guard==='input'))vm.vars['sfc_t'+t.id]=op.inputs[t.id];vm.call('sfcScan');}
   else vm.call(op.op==='reset'?'sfcResetInitial':'sfcStopAndClear');
   assert.equal(activeState.active,job.expected[i].active);assert.deepEqual(activeState.entryMs,job.expected[i].entryMs);
   for(const signal of job.p.signals){assert.equal(vm.vars['sfc_a'+signal.id],!!(job.expected[i].actions.requested&C.bit(signal.id)),'requested A'+signal.id);assert.equal(vm.vars['sfc_l'+signal.id],!!(job.expected[i].actions.stored&C.bit(signal.id)),'stored A'+signal.id);}comparisons++;
  }
 }
 assert.equal(cursor,states.length);assert.equal(comparisons,168);
 if(process.env.MB_SFC_EXPORT_EVIDENCE)fs.writeFileSync(process.env.MB_SFC_EXPORT_EVIDENCE,JSON.stringify({result:'PASS',plans:plans.length,states:comparisons,C_snapshots:states.length,actual_GP_VM:false,hardware_access:false},null,2)+'\n');
});
