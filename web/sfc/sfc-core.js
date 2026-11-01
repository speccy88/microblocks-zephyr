/* SPDX-License-Identifier: MIT
 * Connected authoring graph; the existing C step engine defines scan semantics. */
(function(root,factory){
 'use strict';const api=factory();
 if(typeof module==='object'&&module.exports)module.exports=api;
 else root.MicroBlocksSFC=api;
})(typeof globalThis==='object'?globalThis:this,function(){
 'use strict';
 const LIMITS=Object.freeze({steps:16,transitions:24,links:128,delay:86400000,bytes:131072,coordinate:2200});
 class SFCError extends Error{constructor(code,message){super(message);this.name='SFCError';this.code=code;}}
 const fail=(code,message)=>{throw new SFCError(code,message);};
 const copy=value=>JSON.parse(JSON.stringify(value));
 const integer=(value,min,max)=>Number.isSafeInteger(value)&&value>=min&&value<=max;
 const record=value=>!!value&&typeof value==='object'&&!Array.isArray(value)&&
  (Object.getPrototypeOf(value)===Object.prototype||Object.getPrototypeOf(value)===null);
 const fields=(value,allowed)=>record(value)&&Object.keys(value).every(key=>allowed.includes(key));
 const text=(value,max)=>typeof value==='string'&&value.trim().length>0&&[...value].length<=max&&!/[\u0000-\u001f\u007f]/.test(value);
 const key=node=>(node.kind==='step'?'s':'t')+node.id;
 const bit=id=>1<<(id-1);
 const ids=mask=>Array.from({length:16},(_,i)=>i+1).filter(id=>(mask&bit(id))!==0);
 function validate(graph,{complete=true}={}){
  const issues=[];const issue=(code,message)=>issues.push({code,message});
  if(!fields(graph,['version','name','nodes','links'])||graph.version!==1||!text(graph.name,80)||
     !Array.isArray(graph.nodes)||!Array.isArray(graph.links))return [{code:'DOCUMENT',message:'Use a version 1 chart with a name, nodes and connections.'}];
  if(graph.nodes.length>40||graph.links.length>LIMITS.links)return [{code:'CAPACITY',message:'A chart supports 16 steps, 24 transitions and 128 connections.'}];
  const nodes=new Map();let initial=0,stepCount=0,transitionCount=0;
  for(const node of graph.nodes){
   if(!record(node)||!['step','transition'].includes(node.kind)){issue('NODE','Unknown chart element.');continue;}
   const step=node.kind==='step';
   if(!fields(node,step?['kind','id','label','x','y','initial']:['kind','id','label','x','y','guard','afterMs'])||
      !integer(node.id,1,step?16:24)||!text(node.label,48)||!integer(node.x,40,LIMITS.coordinate)||!integer(node.y,40,LIMITS.coordinate)||
      (step?typeof node.initial!=='boolean':!['input','always','never'].includes(node.guard)||!integer(node.afterMs,0,LIMITS.delay))){
    issue('NODE','Invalid '+node.kind+' properties; check its ID, label, position and timing.');continue;
   }
   const id=key(node);if(nodes.has(id))issue('DUPLICATE','Element '+id.toUpperCase()+' is defined twice.');
   nodes.set(id,node);if(step){stepCount++;if(node.initial)initial++;}else transitionCount++;
  }
  if(stepCount>16||transitionCount>24)issue('CAPACITY','Too many steps or transitions.');
  const connections=new Set();
  for(const link of graph.links){
   if(!fields(link,['from','to'])||typeof link.from!=='string'||typeof link.to!=='string'){
    issue('LINK','A connection needs two element IDs.');continue;
   }
   const from=nodes.get(link.from),to=nodes.get(link.to);
   if(!from||!to){issue('ENDPOINT','Connection endpoint is missing.');continue;}
   if(from.kind===to.kind)issue('ALTERNATION','Connect a step to a transition, or a transition to a step.');
   const id=link.from+'>'+link.to;if(connections.has(id))issue('DUPLICATE_LINK','This connection already exists.');connections.add(id);
  }
  if(complete){
   if(initial!==1)issue('INITIAL','Choose exactly one initial step.');
   for(const [id,node] of nodes)if(node.kind==='transition'){
    if(!graph.links.some(link=>link.to===id))issue('SOURCE','Transition T'+node.id+' needs a preceding step.');
    if(!graph.links.some(link=>link.from===id))issue('TARGET','Transition T'+node.id+' needs a following step.');
   }
   if(!issues.length){
    const reached=new Set([...nodes].filter(([,n])=>n.kind==='step'&&n.initial).map(([id])=>id));
    let changed=true;while(changed){changed=false;for(const link of graph.links)if(reached.has(link.from)&&!reached.has(link.to)){reached.add(link.to);changed=true;}}
    for(const [id] of nodes)if(!reached.has(id))issue('UNREACHABLE',id.toUpperCase()+' has no path from the initial step.');
   }
  }
  return issues;
 }
 function checked(graph,complete=false){const issues=validate(graph,{complete});if(issues.length){const error=new SFCError(issues[0].code,issues[0].message);error.issues=issues;throw error;}return graph;}
 const empty=()=>({version:1,name:'My steps chart',nodes:[],links:[]});
 function nodeAt(graph,id){const node=graph.nodes.find(n=>key(n)===id);if(!node)fail('MISSING','Element '+id+' is missing.');return node;}
 function edit(graph,fn){checked(graph);const next=copy(graph);fn(next);checked(next);return next;}
 function add(graph,kind,{x=360,y=80}={}){
  if(!['step','transition'].includes(kind))fail('NODE','Choose a step or a transition.');
  let added;
  const result=edit(graph,next=>{
   const max=kind==='step'?16:24;let id=1;while(next.nodes.some(n=>n.kind===kind&&n.id===id))id++;
   if(id>max)fail('CAPACITY','No free '+kind+' slot.');
   added={kind,id,label:(kind==='step'?'Step ':'Transition ')+id,x,y,...(kind==='step'?{initial:!next.nodes.some(n=>n.kind==='step')}:{guard:'input',afterMs:0})};
   next.nodes.push(added);
  });return {graph:result,id:key(added)};
 }
 function update(graph,id,properties){return edit(graph,next=>{const node=nodeAt(next,id);Object.assign(node,properties);if(key(node)!==id)fail('IDENTITY','Element IDs and kinds cannot be changed.');});}
 function initial(graph,id){return edit(graph,next=>{if(nodeAt(next,id).kind!=='step')fail('INITIAL','Select a step.');for(const node of next.nodes)if(node.kind==='step')node.initial=key(node)===id;});}
 function connect(graph,from,to){
  checked(graph);const a=nodeAt(graph,from),b=nodeAt(graph,to);
  if(a.kind===b.kind)fail('ALTERNATION','Connections must alternate step and transition.');
  if(graph.links.some(link=>link.from===from&&link.to===to))fail('DUPLICATE_LINK','This connection already exists.');
  return edit(graph,next=>next.links.push({from,to}));
 }
 function connectPins(graph,a,b){
  if(!a||!b||!['in','out'].includes(a.side)||!['in','out'].includes(b.side)||a.side===b.side)fail('DIRECTION','Choose an output pin and an input pin.');
  return a.side==='out'?connect(graph,a.id,b.id):connect(graph,b.id,a.id);
 }
 function disconnect(graph,from,to){return edit(graph,next=>{const i=next.links.findIndex(l=>l.from===from&&l.to===to);if(i<0)fail('MISSING','Connection is missing.');next.links.splice(i,1);});}
 function remove(graph,id){return edit(graph,next=>{nodeAt(next,id);next.nodes=next.nodes.filter(n=>key(n)!==id);next.links=next.links.filter(l=>l.from!==id&&l.to!==id);});}
 function parse(source){
  if(typeof source!=='string'||source.length>LIMITS.bytes||new TextEncoder().encode(source).length>LIMITS.bytes)fail('SIZE','Chart JSON exceeds 128 KiB.');
  let graph;try{graph=JSON.parse(source);}catch{fail('JSON','Chart JSON is not valid.');}checked(graph);return copy(graph);
 }
 const serialize=graph=>JSON.stringify(checked(graph),null,2)+'\n';
 function compile(graph){
  checked(graph,true);
  const steps=graph.nodes.filter(n=>n.kind==='step').sort((a,b)=>a.id-b.id).map(n=>({id:n.id,initial:n.initial}));
  const transitions=graph.nodes.filter(n=>n.kind==='transition').sort((a,b)=>a.id-b.id).map(node=>{
   const from=graph.links.filter(l=>l.to===key(node)).reduce((mask,l)=>mask|bit(nodeAt(graph,l.from).id),0);
   const to=graph.links.filter(l=>l.from===key(node)).reduce((mask,l)=>mask|bit(nodeAt(graph,l.to).id),0);
   return {id:node.id,from,to,afterMs:node.afterMs,guard:node.guard};
  });return {steps,transitions,initial:steps.reduce((mask,s)=>mask|(s.initial?bit(s.id):0),0)};
 }
 class Runtime{
  constructor(graph,now=0){this.config=compile(graph);this.now=0;this.running=false;this.active=this.entered=this.exited=this.fired=0;this.entryMs=Array(16).fill(0);this.time(now);this.now=now;}
  time(now){if(!integer(now,0,Number.MAX_SAFE_INTEGER)||now<this.now)fail('TIME','Use monotonic integer milliseconds.');}
  start(now=this.now){this.time(now);if(this.running)fail('RUNNING','Stop/reset before starting again.');this.stop();this.now=now;this.running=true;this.active=this.entered=this.config.initial;for(const id of ids(this.active))this.entryMs[id-1]=now;return this.state();}
  restartAt(id,now=this.now){this.time(now);if(!Number.isInteger(id)||!this.config.steps.some(s=>s.id===id))fail('MISSING','Restart target must be a defined step.');this.stop();this.now=now;this.running=true;this.active=this.entered=bit(id);this.entryMs[id-1]=now;return this.state();}
  stop(){this.running=false;this.active=this.entered=this.exited=this.fired=0;this.entryMs.fill(0);return this.state();}
  scan(now,inputs={}){
   this.time(now);if(!record(inputs)||Object.entries(inputs).some(([id,value])=>!this.config.transitions.some(t=>String(t.id)===id)||typeof value!=='boolean'))fail('INPUT','Conditions must be current Boolean transition inputs.');
   this.now=now;this.entered=this.exited=this.fired=0;
   let consumed=0,targets=0;const snapshot=this.active;
   if(this.running)for(const t of this.config.transitions){
    const condition=t.guard==='always'||t.guard==='input'&&inputs[t.id]===true;
    if(!condition||(snapshot&t.from)!==t.from||(consumed&t.from))continue;
    if(ids(t.from).some(id=>now-this.entryMs[id-1]<t.afterMs))continue;
    consumed|=t.from;targets|=t.to;this.fired|=1<<(t.id-1);
   }
   if(this.running){this.active=((snapshot&~consumed)|targets)&65535;this.entered=targets;this.exited=consumed;for(const id of ids(targets))this.entryMs[id-1]=now;}
   return this.state();
  }
  elapsed(id,now=this.now){this.time(now);if(!this.config.steps.some(s=>s.id===id))fail('MISSING','Step is not defined.');return this.active&bit(id)?now-this.entryMs[id-1]:0;}
  state(){return {running:this.running,now:this.now,active:this.active,entered:this.entered,exited:this.exited,fired:this.fired,entryMs:this.entryMs.slice()};}
 }
 class History{
  constructor(graph,limit=50){checked(graph);if(!integer(limit,1,50))fail('HISTORY','History supports 1 to 50 edits.');this.present=copy(graph);this.past=[];this.future=[];this.limit=limit;}
  commit(graph){checked(graph);if(serialize(graph)===serialize(this.present))return this.present;this.past.push(this.present);if(this.past.length>this.limit)this.past.shift();this.present=copy(graph);this.future=[];return this.present;}
  undo(){if(this.past.length){this.future.push(this.present);this.present=this.past.pop();}return this.present;}
  redo(){if(this.future.length){this.past.push(this.present);this.present=this.future.pop();}return this.present;}
 }
 function program(graph,library){
  const config=compile(graph);if(typeof library!=='string'||!library.startsWith("module 'Steps & Transitions'"))fail('LIBRARY','The existing Steps & Transitions library is required.');
  const guards=config.transitions.filter(t=>t.guard==='input');
  const lines=['module main'];if(guards.length)lines.push('variables '+guards.map(t=>'sfc_t'+t.id).join(' '));
  lines.push("description 'Logical SFC chart. Boolean sfc_t variables supply current transition conditions. Numbered transition priority. No physical output actions.'",'', 'script 30 30 {','    whenStarted','    stepsStop','    stepsClear');
  for(const t of guards)lines.push('    sfc_t'+t.id+' = false');
  for(const s of config.steps)lines.push('    stepsAdd '+s.id+' '+s.initial);
  for(const t of config.transitions)lines.push('    stepsGroups '+t.id+' '+t.from+' '+t.to+' '+t.afterMs);
  lines.push('    stepsStart','    forever {');
  for(const t of config.transitions)lines.push('        stepsCondition '+t.id+' '+(t.guard==='input'?'sfc_t'+t.id:t.guard==='always'?'true':'false'));
  lines.push('        stepsScan','        waitMillis 50','    }','}','','script 450 30 {','    stepsStop','}','',library.trim(),'');
  return lines.join('\n');
 }
 function example(kind='parallel'){
  const s=(id,x,y,initial=false)=>({kind:'step',id,label:['','Ready','Left branch','Right branch','Together'][id]||'Step '+id,x,y,initial});
  const t=(id,x,y,guard='input')=>({kind:'transition',id,label:'Condition '+id,x,y,guard,afterMs:0});
  if(kind==='sequence')return {version:1,name:'Two steps',nodes:[s(1,360,60,true),t(1,360,190),s(2,360,320),t(2,150,320)],links:[{from:'s1',to:'t1'},{from:'t1',to:'s2'},{from:'s2',to:'t2'},{from:'t2',to:'s1'}]};
  if(kind==='selection')return {version:1,name:'Choose one path',nodes:[s(1,360,60,true),t(1,200,210),t(2,520,210),s(2,200,360),s(3,520,360)],links:[{from:'s1',to:'t1'},{from:'s1',to:'t2'},{from:'t1',to:'s2'},{from:'t2',to:'s3'}]};
  return {version:1,name:'Work together',nodes:[s(1,360,60,true),t(1,360,180),s(2,180,330),s(3,540,330),t(2,360,490),s(4,360,620)],links:[{from:'s1',to:'t1'},{from:'t1',to:'s2'},{from:'t1',to:'s3'},{from:'s2',to:'t2'},{from:'s3',to:'t2'},{from:'t2',to:'s4'}]};
 }
 return Object.freeze({LIMITS,SFCError,key,bit,ids,copy,validate,checked,empty,nodeAt,add,update,initial,connect,connectPins,disconnect,remove,parse,serialize,compile,Runtime,History,program,example});
});
