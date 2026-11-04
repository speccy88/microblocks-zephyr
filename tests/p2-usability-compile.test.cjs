// SPDX-License-Identifier: MIT
// Actual pinned compiler and target-library packaging; no hardware operations.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {load}=require('./support/js_preview_headless.cjs');
const {compile}=require('../tools/compile_propeller2_project.cjs');
async function main(){
 const folder=path.join(process.argv[2],'js-preview/propeller2');
 const receipt=JSON.parse(fs.readFileSync(path.join(folder,'target-library-source.json')));
 const h=load(folder,{readback:false,Socket:class{constructor(){throw Error('Network forbidden');}}});
 h.set('bundle',receipt.bundle);await h.evaluate('MB_Files.initialize();MB_editor.openLibraryFile(bundle)');
 h.evaluate('MB_editor.codeManager.assignFunctionIDs()');
 const functions=h.evaluate('MB_editor.project.allFunctions().map(f=>({name:f.functionName,bytes:MB_editor.codeManager.compiledBytesFor(f).length}))');
 assert.equal(functions.length,79);assert(functions.every(f=>f.bytes>0&&f.bytes<1000));
 assert.deepEqual(Array.from(functions,f=>f.name),receipt.function_names);
 assert.equal(receipt.required_extension_revision,8);
 const source=fs.readFileSync(path.join(__dirname,'fixtures/propeller2/usability.ubp'),'utf8');
 const library=fs.readFileSync(path.join(__dirname,'../boards/propeller2/integration/P2_Hardware.ubl'),'utf8');
 const p=compile(folder,source+'\n'+library);
 assert.equal(p.scripts.length,14);assert.equal(p.chunks.length,97);
 for(const name of ['p2PWMPercent','p2ServoPulseUS','p2ServoAngle','p2WaitPinReady','p2ReadReady','p2MeasureHighUS','p2MeasureDutyPermille','p2CountWindowMS'])assert(p.chunks.some(c=>c.name===name));
 console.log(JSON.stringify({functions:functions.length,fixture:'usability',chunks:p.chunks.length,scripts:p.scripts.length,
  required_extension_revision:8,compiled:true,graphical:false,physical:false,network_allocations:0}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
