#!/usr/bin/env node
/* SPDX-License-Identifier: MIT - deterministic local trace, no hardware. */
'use strict';
const fs=require('node:fs');
const E=require('../web/sfc/sfc-execution.js');
function trace(plan,operations){
 if(!Array.isArray(operations)||operations.length>1000)throw new Error('Use at most 1000 explicit operations.');
 const r=new E.Execution(plan),states=[];
 const keys={start:['op','now'],scan:['op','now','inputs'],stopAndClear:['op'],restartAt:['op','step','now'],resetInitial:['op','now']};
 for(const [index,o] of operations.entries()){
  if(!o||typeof o!=='object'||!Object.hasOwn(keys,o.op)||Object.keys(o).some(k=>!keys[o.op].includes(k)))throw new Error('Invalid operation '+index);
  if(o.op!=='stopAndClear'&&!Number.isSafeInteger(o.now))throw new Error('Explicit integer time required at operation '+index);
  const state=o.op==='scan'?r.scan(o.now,o.inputs):o.op==='restartAt'?r.restartAt(o.step,o.now):o.op==='stopAndClear'?r.stopAndClear():r[o.op](o.now);
  states.push({index,op:o.op,state});
 }
 return {version:1,mapping:r.mapping(),states};
}
if(require.main===module){
 try{
  if(process.argv.length!==4)throw new Error('Usage: node tools/sfc_trace.cjs PLAN.json OPERATIONS.json');
  const [planFile,traceFile]=process.argv.slice(2),source=fs.readFileSync(traceFile);
  if(source.length>1048576)throw new Error('Trace JSON exceeds 1 MiB.');
  process.stdout.write(JSON.stringify(trace(E.parse(fs.readFileSync(planFile,'utf8')),JSON.parse(source.toString('utf8'))),null,2)+'\n');
 }catch(e){process.stderr.write(e.name+': '+e.message+'\n');process.exitCode=1;}
}
module.exports={trace};
