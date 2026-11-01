/* SPDX-License-Identifier: MIT — production controller with a synthetic DOM. */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const C=require('../web/sfc/sfc-core.js');
const UI=require('../web/sfc/sfc-studio.js');
const {harness}=require('./support/sfc_dom.cjs');
test('authoring mounts without accessing a device or changing an existing project',()=>{
 let calls=0;const h=harness({onOpenProgram:()=>{calls++;}});assert.equal(h.studio.dialog.open,true);
 assert.equal(h.writes.length,0);assert.equal(calls,0);assert.equal(h.graph().name,'Work together');
});
test('new elements connect alternately, and a connection can be deleted and rebuilt by pins',()=>{
 const h=harness();h.click(h.text('New chart'));h.click(h.text('+ Step'));h.click(h.text('+ Transition'));h.click(h.text('+ Step'));
 assert.deepEqual(C.compile(h.graph()).transitions.map(t=>[t.from,t.to]),[[1,2]]);
 h.click(h.aria('Connection S1 to T1'));h.click(h.text('Delete connection'));assert.equal(h.graph().links.length,1);
 h.click(h.aria('Input pin T1'));h.click(h.aria('Output pin S1'));assert.equal(h.graph().links.length,2);
 const before=C.serialize(h.graph());h.click(h.aria('Output pin S1'));h.click(h.aria('Input pin S2'));assert.equal(C.serialize(h.graph()),before);
});
test('deleting a selected step removes its wires without retaining a stale selection',()=>{
 const h=harness();h.click(h.aria('Step S2 Left branch'));h.click(h.text('Delete element'));
 const g=h.graph();assert(!g.nodes.some(n=>C.key(n)==='s2'));assert(!g.links.some(l=>l.from==='s2'||l.to==='s2'));
 h.click(h.text('Undo'));assert.equal(h.graph().nodes.length,6);h.click(h.text('Redo'));assert.equal(h.graph().nodes.length,5);
});
test('local AND preview consumes fresh signals, stops cleanly and freezes editing',()=>{
 const h=harness(),before=C.serialize(h.graph());h.click(h.text('Start preview'));
 assert(h.text('+ Step').disabled);h.click(h.aria('Output pin S1'));assert.equal(C.serialize(h.graph()),before);
 h.change(h.aria('T1 condition'),true);h.click(h.text('One scan'));
 assert(h.document.body.textContent.includes('active S2, S3'));
 h.change(h.aria('T2 condition'),true);h.click(h.text('One scan'));assert(h.document.body.textContent.includes('active S4'));
 h.click(h.text('Stop / reset'));assert(h.document.body.textContent.includes('active none'));assert(!h.text('+ Step').disabled);
});
test('invalid JSON remains in the editing field and never replaces the draft',()=>{
 const h=harness(),before=C.serialize(h.graph()),area=h.aria('Chart JSON source');h.change(area,'{"bad":');h.click(h.text('Load JSON'));
 assert.equal(area.value,'{"bad":');assert.equal(h.writes.length,0);assert.equal(C.serialize(h.graph()),before);
});
test('invalid stored data is preserved, and save failure keeps the in-memory graph usable',()=>{
 const bad=harness({saved:'broken'});assert.equal(bad.writes.length,0);assert(bad.document.body.textContent.includes('has not been overwritten'));
 const h=harness({failSave:true});h.click(h.aria('Step S2 Left branch'));h.change(h.aria('Element label'),'My branch');
 assert(h.document.body.textContent.includes('Browser save failed'));assert(h.graph().nodes.some(n=>n.label==='My branch'));
});
test('keyboard and committed/cancelled pointer moves preserve chart semantics and history',()=>{
 const h=harness(),g=h.graph(),before=C.compile(g),group=h.aria('Step S1 Ready'),chart=h.aria('Steps chart');
 group.onkeydown({key:'ArrowRight',target:group,preventDefault(){}});assert.equal(h.graph().nodes[0].x,370);
 h.click(h.text('Undo'));assert.equal(h.graph().nodes[0].x,360);
 let target=h.aria('Step S1 Ready');target.onpointerdown({target,clientX:360,clientY:60,pointerId:1,preventDefault(){}});
 chart.onpointermove({clientX:440,clientY:80});chart.onpointercancel();assert.equal(h.graph().nodes[0].x,360);
 target=h.aria('Step S1 Ready');target.onpointerdown({target,clientX:360,clientY:60,pointerId:2,preventDefault(){}});
 chart.onpointermove({clientX:440,clientY:80});chart.onpointerup();assert.equal(h.graph().nodes[0].x,440);assert.deepEqual(C.compile(h.graph()),before);
});
test('program opening requires explicit confirmation, leaves graph JSON intact and calls only the supplied editor callback',async()=>{
 const calls=[];const h=harness({onOpenProgram:async(...args)=>calls.push(args)});
 const before=C.serialize(h.graph());h.click(h.text('MicroBlocks blocks'));assert(h.aria('Generated MicroBlocks project').value.includes("'[steps:groups]' 1 1 6 0"));
 assert.equal(calls.length,0);await h.click(h.text('Open in MicroBlocks'));assert.equal(calls.length,1);assert.equal(calls[0][0],'Work together');assert.equal(h.studio.dialog.open,false);
 assert.equal(C.serialize(h.graph()),before);
 const denied=harness({confirm:false,onOpenProgram:async()=>calls.push('wrong')});denied.click(denied.text('MicroBlocks blocks'));await denied.click(denied.text('Open in MicroBlocks'));assert.equal(calls.length,1);
});
test('standalone controller cannot import into an absent editor',()=>{const h=harness();h.click(h.text('MicroBlocks blocks'));assert(h.text('Open in MicroBlocks').disabled);});
test('chart naming persists and view zoom never changes its configuration',()=>{
 const h=harness();h.change(h.aria('Chart name'),'My sequence');assert.equal(h.graph().name,'My sequence');
 const before=C.serialize(h.graph());h.click(h.aria('Zoom chart in'));assert(h.aria('Steps chart').attributes.style.includes('125%'));
 h.click(h.text('Fit'));assert.equal(C.serialize(h.graph()),before);h.click(h.text('Start preview'));assert(h.aria('Chart name').disabled);
});
