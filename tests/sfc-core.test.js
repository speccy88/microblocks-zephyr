/* SPDX-License-Identifier: MIT */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {spawnSync}=require('node:child_process');
const C=require('../web/sfc/sfc-core.js');
const example=()=>C.example();
const code=name=>e=>e.code===name;
test('bounded connected draft serializes losslessly and compiles AND groups',()=>{
 const g=example(),before=C.serialize(g),compiled=C.compile(g);
 assert.deepEqual(C.parse(before),g);assert.equal(C.serialize(g),before);
 assert.deepEqual(compiled.transitions.map(t=>[t.id,t.from,t.to]),[[1,1,6],[2,6,8]]);
});
test('editor can hold incomplete drafts but execution/export require complete ends',()=>{
 let g=C.empty();g=C.add(g,'step').graph;g=C.add(g,'transition',{y:200}).graph;
 assert.deepEqual(C.validate(g,{complete:false}),[]);assert.throws(()=>C.compile(g),code('SOURCE'));
 assert.throws(()=>C.program(g,"module 'Steps & Transitions'"),code('SOURCE'));
});
test('pin connection is directed in either click order and never links equal kinds',()=>{
 let g=C.empty();g=C.add(g,'step').graph;g=C.add(g,'transition').graph;g=C.add(g,'step').graph;
 g=C.connectPins(g,{id:'t1',side:'in'},{id:'s1',side:'out'});
 g=C.connectPins(g,{id:'t1',side:'out'},{id:'s2',side:'in'});assert.equal(C.compile(g).transitions[0].to,2);
 const raw=C.serialize(g);
 assert.throws(()=>C.connect(g,'s1','s2'),code('ALTERNATION'));
 assert.throws(()=>C.connectPins(g,{id:'s1',side:'in'},{id:'t1',side:'in'}),code('DIRECTION'));
 assert.throws(()=>C.connect(g,'s1','t1'),code('DUPLICATE_LINK'));
 assert.throws(()=>C.connect(g,'missing','t1'),code('MISSING'));assert.equal(C.serialize(g),raw);
});
test('deletion removes exactly the selected links, and undo restores the complete graph',()=>{
 const h=new C.History(example()),original=C.serialize(h.present);
 h.commit(C.remove(h.present,'s2'));assert(!h.present.links.some(l=>l.from==='s2'||l.to==='s2'));
 h.undo();assert.equal(C.serialize(h.present),original);h.redo();assert.equal(h.present.nodes.length,5);
 h.undo();h.commit(C.update(h.present,'s2',{label:'New'}));assert.equal(h.future.length,0);
});
test('initial selection, IDs and positions are explicit and edits are atomic',()=>{
 let g=C.initial(example(),'s3');assert.deepEqual(g.nodes.filter(s=>s.initial).map(s=>s.id),[3]);
 // Reachability is checked separately, because S3 alone cannot reach the fork.
 assert.throws(()=>C.compile(g),code('UNREACHABLE'));
 g=example();const before=C.serialize(g);
 for(const properties of [{id:2},{kind:'transition'},{x:NaN},{y:2201},{initial:1},{label:''}])assert.throws(()=>C.update(g,'s1',properties));
 assert.equal(C.serialize(g),before);
});
test('unknown fields, duplicate IDs, missing endpoints, injection and large imports are rejected',()=>{
 const variants=[g=>{g.nodes.push(C.copy(g.nodes[0]));},g=>{g.links[0].to='t24';},g=>{g.extra='ignored?';},g=>{g.nodes[0].label='bad\nlabel';},g=>{g.nodes[1].afterMs=86400001;},g=>{g.nodes[1].guard='eval';}];
 for(const mutate of variants){const g=example();mutate(g);assert.throws(()=>C.parse(JSON.stringify(g)));}
 assert.throws(()=>C.parse('{'),code('JSON'));assert.throws(()=>C.parse(' '.repeat(131073)),code('SIZE'));
 assert.throws(()=>C.parse('{"version":1,"name":"a","nodes":[],"links":[],"__proto__":{}}'),code('DOCUMENT'));
});
test('boundary step 16 and transition 24 retain exact masks',()=>{
 const g={version:1,name:'Bounds',nodes:[{kind:'step',id:16,label:'Last',x:80,y:80,initial:true},{kind:'transition',id:24,label:'Return',x:80,y:220,guard:'always',afterMs:86400000}],links:[{from:'s16',to:'t24'},{from:'t24',to:'s16'}]};
 const cfg=C.compile(g);assert.equal(cfg.initial,32768);const r=new C.Runtime(g);r.start();r.scan(86399999);assert.equal(r.fired,0);r.scan(86400000);assert.equal(r.fired,1<<23);assert.equal(r.elapsed(16),0);
});
test('AND fork and timed join need every source and do not cascade',()=>{
 let g=example();g=C.update(g,'t2',{afterMs:100});const r=new C.Runtime(g);r.start(10);
 r.scan(20,{1:true,2:true});assert.equal(r.active,6);assert.equal(r.fired,1);
 r.scan(119,{2:true});assert.equal(r.active,6);r.scan(120,{2:true});assert.equal(r.active,8);assert.equal(r.fired,2);
 r.scan(130,{2:true});assert.equal(r.active,8);assert.equal(r.fired,0);
});
test('OR conflict uses transition ID, while geometry and array order do not alter priority',()=>{
 let g=C.example('selection');g.nodes.reverse();g.links.reverse();g=C.update(g,'t1',{x:900});g=C.update(g,'t2',{x:80});
 const r=new C.Runtime(g);r.start();r.scan(0,{1:true,2:true});assert.equal(r.active,2);assert.equal(r.fired,1);
});
test('stop/reset, fresh input values, self-loop entry and monotonic failure are distinct',()=>{
 const g=C.example('sequence'),r=new C.Runtime(g);r.start();r.scan(10,{1:true});r.scan(20);assert.equal(r.active,2);r.scan(30,{2:true});assert.equal(r.active,1);assert.equal(r.elapsed(1,35),5);
 const before=r.state();assert.throws(()=>r.scan(29),code('TIME'));assert.deepEqual(r.state(),before);
 assert.throws(()=>r.scan(31,{1:1}),code('INPUT'));assert.deepEqual(r.state(),before);
 r.stop();assert.equal(r.active,0);r.start(40);assert.equal(r.active,1);assert.throws(()=>r.start(40),code('RUNNING'));
});
test('safe export uses native numbered groups, fresh Boolean variables and the exact library',()=>{
 const g=example();g.name="'); sendToBoard 99 //";g.nodes[0].label='<script>bad</script>';
 const library=fs.readFileSync(path.join(__dirname,'../integration/Steps_Transitions.ubl'),'utf8');const source=C.program(g,library);
 assert(source.includes('stepsGroups 1 1 6 0'));assert(source.includes('stepsCondition 1 sfc_t1'));assert(source.endsWith(library.trim()+'\n'));
 assert(!source.includes('sendToBoard'));assert(!source.includes('<script>'));assert(!source.includes('digitalWrite'));
 assert.throws(()=>C.program(g,''),code('LIBRARY'));
});
test('preview and compiled graph agree with actual C engine across structured and seeded charts',()=>{
 const binary=process.env.MB_SFC_HOST;assert.ok(binary,'Build tools/build_sfc_native_fixture.py; no hardware fallback.');
 let commands=[],expected=[],contexts=[];let seed=0x4571;
 const random=()=>{seed=(Math.imul(seed,1664525)+1013904223)>>>0;return seed;};
 const charts=[C.example(),C.example('selection'),C.example('sequence')];
 for(let n=0;n<30;n++){
  const g={version:1,name:'Seeded '+n,nodes:[],links:[]};
  for(let id=1;id<=6;id++)g.nodes.push({kind:'step',id,label:'Step '+id,x:id*100,y:80,initial:id===1});
  for(let id=1;id<=8;id++){
   g.nodes.push({kind:'transition',id,label:'T'+id,x:id*100,y:240,guard:['input','always','never'][random()%3],afterMs:random()%3*100});
   const from=id<=6?[id]:[2,4],to=id<=6?[id%6+1]:[1,6];
   for(const s of from)g.links.push({from:'s'+s,to:'t'+id});for(const s of to)g.links.push({from:'t'+id,to:'s'+s});
  }charts.push(g);
 }
 for(const [index,g] of charts.entries()){
  const cfg=C.compile(g),r=new C.Runtime(g);commands.push('INIT 0');
  for(const s of cfg.steps)commands.push('ADD '+s.id+' '+Number(s.initial));
  for(const t of cfg.transitions)commands.push(['EDGE',t.id,t.from,t.to,t.afterMs].join(' '));
  commands.push('START 0');expected.push({error:0,...r.start(0)});contexts.push('chart '+index+' start');
  for(let scan=0;scan<35;scan++){
   const inputs={};for(const t of cfg.transitions){const flag=t.guard==='always'||t.guard==='input'&&(random()&3)!==0;commands.push('COND '+t.id+' '+Number(flag));if(t.guard==='input')inputs[t.id]=flag;}
   const now=(scan+1)*50;commands.push('SCAN '+now);expected.push({error:0,...r.scan(now,inputs)});contexts.push('chart '+index+' scan '+scan);
  }
  commands.push('STOP');expected.push({error:0,...r.stop()});contexts.push('chart '+index+' stop');
 }
 const args=process.env.MB_SFC_WSL?['wsl.exe',['-d',process.env.MB_SFC_WSL,'--',binary]]:[binary,[]];
 const run=spawnSync(...args,{input:commands.join('\n')+'\n',encoding:'utf8',timeout:30000,maxBuffer:8*1024*1024});
 assert.equal(run.status,0,run.stderr||String(run.error));assert.equal(run.stderr,'');
 const actual=run.stdout.trim().split('\n').map(line=>JSON.parse(line));assert.equal(actual.length,expected.length);
 actual.forEach((state,i)=>assert.deepEqual(state,expected[i],contexts[i]));
 assert.equal(expected.length,1221);
});
