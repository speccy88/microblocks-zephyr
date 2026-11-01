/* SPDX-License-Identifier: MIT
 * Boundary request signals only. No action callbacks or device operations. */
(function(root,factory){
 'use strict';if(typeof module==='object'&&module.exports)module.exports=factory(require('./sfc-core.js'));
 else root.MicroBlocksSFCExecution=factory(root.MicroBlocksSFC);
})(typeof globalThis==='object'?globalThis:this,function(C){
 'use strict';
 const LIMITS=Object.freeze({signals:16,bindings:64,bytes:131072});
 const QUALIFIERS=Object.freeze(['N','P1','P0','S','R']);
 const fail=(code,message)=>{throw new C.SFCError(code,message);};
 const integer=(n,max)=>Number.isSafeInteger(n)&&n>=1&&n<=max;
 const fields=(v,keys)=>v!==null&&typeof v==='object'&&!Array.isArray(v)&&
  [Object.prototype,null].includes(Object.getPrototypeOf(v))&&Object.keys(v).every(k=>keys.includes(k));
 const label=v=>typeof v==='string'&&v.trim().length>0&&[...v].length<=48&&!/[\u0000-\u001f\u007f]/.test(v);
 function checked(plan,{complete=true}={}){
  if(!fields(plan,['version','graph','signals','bindings','priority'])||plan.version!==1||!Array.isArray(plan.signals)||!Array.isArray(plan.bindings))fail('PLAN','Use a version 1 execution plan.');
  C.checked(plan.graph,complete);
  const flow={steps:plan.graph.nodes.filter(n=>n.kind==='step'),transitions:plan.graph.nodes.filter(n=>n.kind==='transition')};
  if(plan.signals.length>16||plan.bindings.length>64)fail('CAPACITY','Use at most 16 signals and 64 bindings.');
  const signals=new Set(),bindings=new Set(),steps=new Set(flow.steps.map(s=>s.id));
  for(const s of plan.signals){
   if(!fields(s,['id','label'])||!integer(s.id,16)||!label(s.label))fail('SIGNAL','Invalid signal ID or label.');
   if(signals.has(s.id))fail('DUPLICATE','Signal is defined twice.');signals.add(s.id);
  }
  for(const b of plan.bindings){
   if(!fields(b,['step','signal','qualifier'])||!integer(b.step,16)||!integer(b.signal,16)||!QUALIFIERS.includes(b.qualifier))fail('BINDING','Use a defined step, signal and N/P1/P0/S/R qualifier.');
   if(!steps.has(b.step)||!signals.has(b.signal))fail('MISSING','Binding refers to a missing step or signal.');
   const key=b.step+':'+b.signal+':'+b.qualifier;if(bindings.has(key))fail('DUPLICATE','Binding is defined twice.');bindings.add(key);
  }
  if(Object.hasOwn(plan,'priority')){
   const ids=new Set(flow.transitions.map(t=>t.id)),seen=new Set();
   if(!Array.isArray(plan.priority)||plan.priority.length!==ids.size)fail('PRIORITY','Priority must list every transition exactly once.');
   for(const id of plan.priority){if(!integer(id,24)||!ids.has(id)||seen.has(id))fail('PRIORITY','Priority must list every transition exactly once.');seen.add(id);}
  }
  return plan;
 }
 function compile(plan){
  checked(plan);const graph=C.copy(plan.graph),order=plan.priority?plan.priority.slice():C.compile(graph).transitions.map(t=>t.id);
  const slots=new Map(order.map((id,i)=>[id,i+1]));
  for(const n of graph.nodes)if(n.kind==='transition')n.id=slots.get(n.id);
  for(const l of graph.links)for(const side of ['from','to'])if(l[side][0]==='t')l[side]='t'+slots.get(Number(l[side].slice(1)));
  return {graph,order,signals:C.copy(plan.signals),bindings:C.copy(plan.bindings)};
 }
 function decode(source,complete){
  if(typeof source!=='string'||source.length>LIMITS.bytes||new TextEncoder().encode(source).length>LIMITS.bytes)fail('SIZE','Execution JSON exceeds 128 KiB.');
  let plan;try{plan=JSON.parse(source);}catch{fail('JSON','Execution JSON is not valid.');}return C.copy(checked(plan,{complete}));
 }
 const parse=source=>decode(source,true),parseDraft=source=>decode(source,false);
 const encode=(plan,complete)=>{checked(plan,{complete});const source=JSON.stringify(plan,null,2)+'\n';if(new TextEncoder().encode(source).length>LIMITS.bytes)fail('SIZE','Execution JSON exceeds 128 KiB.');return source;};
 const serialize=plan=>encode(plan,true),serializeDraft=plan=>encode(plan,false);
 const fromGraph=graph=>C.copy(checked({version:1,graph,signals:[],bindings:[]},{complete:false}));
 function withGraph(plan,graph){
  const next=C.copy(plan);next.graph=C.copy(graph);
  next.bindings=next.bindings.filter(b=>graph.nodes.some(n=>n.kind==='step'&&n.id===b.step));
  if(next.priority){const ids=graph.nodes.filter(n=>n.kind==='transition').map(n=>n.id).sort((a,b)=>a-b);next.priority=next.priority.filter(id=>ids.includes(id));next.priority.push(...ids.filter(id=>!next.priority.includes(id)));}
  return C.copy(checked(next,{complete:false}));
 }
 class DraftHistory{
  constructor(plan){checked(plan,{complete:false});this.present=C.copy(plan);this.past=[];this.future=[];}
  commit(plan){checked(plan,{complete:false});if(serializeDraft(plan)===serializeDraft(this.present))return;this.past.push(this.present);if(this.past.length>50)this.past.shift();this.present=C.copy(plan);this.future=[];}
  undo(){if(this.past.length){this.future.push(this.present);this.present=this.past.pop();}}
  redo(){if(this.future.length){this.past.push(this.present);this.present=this.future.pop();}}
 }
 const blank=()=>({normal:0,entryPulse:0,exitPulse:0,stored:0,reset:0,requested:0});
 class Execution{
  #flow;#order;#bindings;#actions;#initial;
  constructor(plan,now=0){const config=compile(plan);this.#order=config.order;this.#bindings=config.bindings;this.#flow=new C.Runtime(config.graph,now);this.#initial=C.ids(this.#flow.config.initial)[0];this.#actions=blank();}
  mapping(){return this.#order.map((id,i)=>({transition:id,slot:i+1}));}
  #publish(){
   if(!this.#flow.running){this.#actions=blank();return this.state();}
   const a=blank();let sets=0;
   for(const b of this.#bindings){const step=C.bit(b.step),signal=C.bit(b.signal);
    if(b.qualifier==='N'&&(this.#flow.active&step))a.normal|=signal;
    if(b.qualifier==='P1'&&(this.#flow.entered&step))a.entryPulse|=signal;
    if(b.qualifier==='P0'&&(this.#flow.exited&step))a.exitPulse|=signal;
    if(b.qualifier==='S'&&(this.#flow.entered&step))sets|=signal;
    if(b.qualifier==='R'&&(this.#flow.active&step))a.reset|=signal;
   }
   a.stored=(this.#actions.stored|sets)&~a.reset&65535;
   a.requested=a.normal|a.entryPulse|a.exitPulse|a.stored;this.#actions=a;return this.state();
  }
  start(now){this.#flow.start(now);this.#actions=blank();return this.#publish();}
  scan(now,inputs={}){
   if(!fields(inputs,this.#order.map(String))||Object.values(inputs).some(v=>typeof v!=='boolean'))fail('INPUT','Conditions must be current Boolean transition inputs.');
   const mapped={};for(const [id,value] of Object.entries(inputs))mapped[this.#order.indexOf(Number(id))+1]=value;
   this.#flow.scan(now,mapped);return this.#publish();
  }
  stopAndClear(){this.#flow.stop();this.#actions=blank();return this.state();}
  restartAt(step,now){this.#flow.restartAt(step,now);this.#actions=blank();return this.#publish();}
  resetInitial(now){return this.restartAt(this.#initial,now);}
  elapsed(step,now){return this.#flow.elapsed(step,now);}
  state(){const s=this.#flow.state();s.fired=this.#order.reduce((mask,id,i)=>mask|((s.fired&(1<<i))?(1<<(id-1)):0),0);return {...s,actions:{...this.#actions}};}
 }
 function example(){return {version:1,graph:C.example(),signals:[{id:1,label:'Fan request'},{id:2,label:'Parallel request'},{id:3,label:'Arrival pulse'}],bindings:[
  {step:1,signal:1,qualifier:'S'},{step:4,signal:1,qualifier:'R'},
  {step:2,signal:2,qualifier:'N'},{step:3,signal:2,qualifier:'N'},{step:4,signal:3,qualifier:'P1'}],priority:[1,2]};}
 return Object.freeze({LIMITS,QUALIFIERS,checked,compile,parse,serialize,parseDraft,serializeDraft,fromGraph,withGraph,DraftHistory,Execution,example});
});
