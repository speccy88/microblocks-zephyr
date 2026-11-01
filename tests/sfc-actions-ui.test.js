/* SPDX-License-Identifier: MIT */
'use strict';
const {test}=require('node:test');const assert=require('node:assert/strict');
const C=require('../web/sfc/sfc-core.js'),E=require('../web/sfc/sfc-execution.js'),UI=require('../web/sfc/sfc-studio.js');
const {harness}=require('./support/sfc_dom.cjs');
function plan(h){h.click(h.text('Execution JSON'));return E.parseDraft(h.aria('Execution JSON source').value);}
function add(h,step,signal,qualifier){const n=h.graph().nodes.find(n=>n.kind==='step'&&n.id===step);h.click(h.aria('Step S'+step+' '+n.label));h.change(h.aria('Action signal'),signal);h.change(h.aria('Action qualifier'),qualifier);h.click(h.text('Add action'));}
test('UI binds N/P1/P0/S/R and previews stored request through AND until R',()=>{
 const h=harness();h.click(h.text('+ Signal'));h.change(h.aria('Signal A1 label'),'Fan');add(h,1,1,'S');add(h,4,1,'R');
 h.click(h.text('+ Signal'));add(h,2,2,'N');add(h,3,2,'N');add(h,4,2,'P1');add(h,1,2,'P0');
 assert.equal(plan(h).bindings.length,6);h.click(h.text('Start preview'));assert(h.aria('Logical action requests').textContent.includes('A1 Fan = true (stored)'));
 h.change(h.aria('T1 condition'),true);h.click(h.text('One scan'));assert(h.aria('Logical action requests').textContent.includes('A2 Signal 2 = true'));
 h.change(h.aria('T2 condition'),true);h.click(h.text('One scan'));assert(h.aria('Logical action requests').textContent.includes('A1 Fan = false'));
 h.click(h.text('Stop / reset'));assert(!h.aria('Logical action requests').textContent.includes('= true'));
});
test('whole-plan undo restores removed signals, bindings and step deletions',()=>{
 const h=harness();h.click(h.text('+ Signal'));add(h,2,1,'N');const original=E.serializeDraft(plan(h));
 h.click(h.text('Delete signal A1'));assert.equal(plan(h).bindings.length,0);h.click(h.text('Undo'));assert.equal(E.serializeDraft(plan(h)),original);
 h.click(h.aria('Step S2 Left branch'));h.click(h.text('Delete element'));assert.equal(plan(h).bindings.length,0);h.click(h.text('Undo'));assert.equal(E.serializeDraft(plan(h)),original);
 h.click(h.aria('Step S2 Left branch'));h.click(h.text('Remove action A1 N'));assert.equal(plan(h).bindings.length,0);h.click(h.text('Undo'));assert.equal(E.serializeDraft(plan(h)),original);
});
test('explicit priority edits persist, undo and drive OR selection in preview',()=>{
 const h=harness();h.change(h.aria('Chart example'),'selection');h.click(h.aria('Transition T2 Condition 2'));h.click(h.text('Higher priority'));
 assert.deepEqual(plan(h).priority,[2,1]);h.click(h.text('Undo'));assert.equal(plan(h).priority,undefined);h.click(h.text('Redo'));assert.deepEqual(plan(h).priority,[2,1]);
 h.click(h.text('Start preview'));h.change(h.aria('T1 condition'),true);h.change(h.aria('T2 condition'),true);h.click(h.text('One scan'));assert(h.document.body.textContent.includes('active S3'));
});
test('priority reconciles added/deleted transitions without reordering survivors',()=>{
 const p=E.fromGraph(C.example('selection'));p.priority=[2,1];const h=harness({entries:{[UI.PLAN_STORAGE]:E.serializeDraft(p)}});
 h.click(h.aria('Transition T1 Condition 1'));h.click(h.text('Delete element'));assert.deepEqual(plan(h).priority,[2]);h.click(h.text('+ Transition'));assert.deepEqual(plan(h).priority,[2,1]);
});
test('legacy chart migrates only to the new plan key on explicit edit',()=>{
 const old=C.serialize(C.example('sequence')),h=harness({entries:{[UI.STORAGE]:old}});assert.equal(h.writes.length,0);assert.equal(h.graph().name,'Two steps');
 h.click(h.text('+ Signal'));assert.deepEqual(h.writeKeys,[UI.PLAN_STORAGE]);assert.equal(h.values.get(UI.STORAGE),old);assert.equal(E.parseDraft(h.values.get(UI.PLAN_STORAGE)).signals.length,1);
});
test('incomplete execution draft persists losslessly while preview/export stay disabled',()=>{
 const h=harness();h.click(h.text('New chart'));h.click(h.text('+ Step'));h.click(h.text('+ Signal'));add(h,1,1,'P1');h.click(h.text('+ Transition'));
 const p=plan(h);assert.equal(p.bindings.length,1);assert(h.text('Start preview').disabled);assert(h.text('MicroBlocks blocks').disabled);assert.deepEqual(E.parseDraft(h.values.get(UI.PLAN_STORAGE)),p);
});
test('invalid execution JSON remains in field and preserves action draft',()=>{
 const h=harness();h.click(h.text('+ Signal'));const before=E.serializeDraft(plan(h));h.aria('Execution JSON source').value='{"broken":';const count=h.writes.length;h.click(h.text('Load execution JSON'));
 assert.equal(h.aria('Execution JSON source').value,'{"broken":');assert.equal(h.writes.length,count);assert.equal(E.serializeDraft(plan(h)),before);
});
test('graph-only load cancellation cannot erase stored action metadata',()=>{
 const p=E.example(),h=harness({confirm:false,entries:{[UI.PLAN_STORAGE]:E.serialize(p)}});const before=E.serializeDraft(plan(h));h.aria('Chart JSON source').value=C.serialize(C.example('selection'));h.click(h.text('Load JSON'));assert.equal(E.serializeDraft(plan(h)),before);
});
test('action edits are locked while running, restart clears requests without P0',()=>{
 const h=harness();h.click(h.text('+ Signal'));add(h,1,1,'S');add(h,1,1,'P0');h.click(h.text('Start preview'));
 assert(h.text('+ Signal').disabled);assert(h.text('Add action').disabled);assert(h.aria('Signal A1 label').disabled);assert(h.aria('Action qualifier').disabled);assert(h.text('Load execution JSON').disabled);
 h.change(h.aria('Preview restart step'),4);h.click(h.text('Restart at step'));assert(h.document.body.textContent.includes('active S4'));assert(h.aria('Logical action requests').textContent.includes('= false'));
 h.click(h.text('Reset to initial'));assert(h.document.body.textContent.includes('active S1'));assert(h.aria('Logical action requests').textContent.includes('= true (stored)'));
});
test('export includes action data and priority without invoking an editor callback',()=>{
 let calls=0;const p=E.example();p.priority=[2,1];const h=harness({entries:{[UI.PLAN_STORAGE]:E.serialize(p)},onOpenProgram:()=>calls++});h.click(h.text('MicroBlocks blocks'));
 const source=h.aria('Generated MicroBlocks project').value;assert(source.includes('sfc_a1'));assert(source.includes("'[steps:groups]' 1 6 8 0"));assert(source.includes('sfcPublishActions'));assert.equal(calls,0);assert.deepEqual(plan(h),p);
});
