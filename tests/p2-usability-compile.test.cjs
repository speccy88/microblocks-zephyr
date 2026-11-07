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
 h.set('bundle',receipt.bundle);await h.evaluate('MB_Files.initialize().then(()=>MB_editor.openLibraryFile(bundle))');
 h.evaluate('MB_editor.codeManager.assignFunctionIDs()');
 const functions=h.evaluate('MB_editor.project.allFunctions().map(f=>({name:f.functionName,bytes:MB_editor.codeManager.compiledBytesFor(f).length}))');
 assert.equal(functions.length,82);assert(functions.every(f=>f.bytes>0&&f.bytes<1000));
 assert.deepEqual(Array.from(functions,f=>f.name),receipt.function_names);
 assert.equal(receipt.required_extension_revision,8);
 const source=fs.readFileSync(path.join(__dirname,'fixtures/propeller2/usability.ubp'),'utf8');
 const library=fs.readFileSync(path.join(__dirname,'../boards/propeller2/integration/P2_Hardware.ubl'),'utf8');
 const grouped=fs.readFileSync(path.join(folder,receipt.bundle),'utf8');
 const old=load(folder,{readback:false,Socket:class{constructor(){throw Error('Network forbidden');}}});
 old.set('canonical',library);await old.evaluate('MB_editor.importLibraryFromString(canonical,"P2 Hardware.ubl")');
 const api=editor=>editor.evaluate('({functions:MB_editor.project.allFunctions().map(f=>[f.functionName,f.codeString()]).sort(),specs:Array.from(MB_editor.project.blockSpecs,([name,spec])=>[name,specDefinitionString(spec)]).sort()})');
 assert.deepEqual(JSON.parse(JSON.stringify(api(h))),JSON.parse(JSON.stringify(api(old))));
 for(const module of receipt.modules){
  const single=load(folder,{readback:false,Socket:class{constructor(){throw Error('Network forbidden');}}});
  single.set('one','Libraries/P2/'+module+'.ubl');await single.evaluate('MB_Files.initialize().then(()=>MB_editor.openLibraryFile(one))');
  single.evaluate('MB_editor.codeManager.assignFunctionIDs()');
  const required=new Set([module]);
  function dependencies(name){for(const dep of receipt.library_dependencies[name]){if(!required.has(dep)){required.add(dep);dependencies(dep);}}}
  dependencies(module);
  assert.deepEqual(Array.from(single.evaluate('Array.from(MB_editor.project.libraries.keys()).sort()')),[...required].sort());
  assert(single.evaluate('MB_editor.project.allFunctions().every(f=>MB_editor.codeManager.compiledBytesFor(f).length>0)'));
 }
 old.evaluate('MB_editor.codeManager.assignFunctionIDs();globalThis.savedP2IDs=JSON.stringify(Array.from(MB_editor.codeManager.functionChunkIDs));globalThis.savedP2Functions=new Map(MB_editor.project.allFunctions().map(f=>[f.functionName,f]));globalThis.dispatchEvent=()=>{};');
 old.evaluate(fs.readFileSync(path.join(folder,'target-blocks.js'),'utf8'));
 await old.evaluate('MicroBlocksTargetBlocks.ensure(MB_editor)');
 assert.equal(old.evaluate('MB_editor.project.libraryNamed("P2 Hardware")'),null);
 assert.deepEqual(Array.from(old.evaluate('Array.from(MB_editor.project.libraries.keys())')),receipt.modules);
 assert(old.evaluate('MB_editor.project.allFunctions().every(f=>savedP2Functions.get(f.functionName)===f)'));
 assert(old.evaluate('savedP2IDs===JSON.stringify(Array.from(MB_editor.codeManager.functionChunkIDs))'));
 assert.deepEqual(JSON.parse(JSON.stringify(api(h))),JSON.parse(JSON.stringify(api(old))));
 const stateful=load(folder,{readback:false,Socket:class{constructor(){throw Error('Network forbidden');}}});
 stateful.set('canonical',library);await stateful.evaluate('MB_editor.importLibraryFromString(canonical,"P2 Hardware.ubl")');
 stateful.evaluate('MB_editor.project.libraryNamed("P2 Hardware").variableNames.push("savedP2Private");globalThis.dispatchEvent=()=>{};');
 stateful.evaluate(fs.readFileSync(path.join(folder,'target-blocks.js'),'utf8'));
 await stateful.evaluate('MicroBlocksTargetBlocks.ensure(MB_editor)');
 assert.deepEqual(Array.from(stateful.evaluate('Array.from(MB_editor.project.libraries.keys())')),['P2 Hardware']);
 assert.deepEqual(Array.from(stateful.evaluate('MB_editor.project.libraryNamed("P2 Hardware").variableNames')),['savedP2Private']);
 // Saved five-library layouts and old subsets must not be silently replaced.
 for(const savedNames of [['P2 Core','P2 Signals','P2 Serial','P2 Analog','P2 Capture'],['P2 Analog'],['P2 Core','P2 Signals','P2 Frequency']]){
  const saved=load(folder,{readback:false,Socket:class{constructor(){throw Error('Network forbidden');}}});
  saved.set('canonical',library);saved.set('savedNames',savedNames);
  await saved.evaluate('MB_editor.importLibraryFromString(canonical,"P2 Hardware.ubl")');
  saved.evaluate(`const original=MB_editor.project.libraryNamed('P2 Hardware');
   MB_editor.project.libraries.delete('P2 Hardware');
   savedNames.forEach((name,index)=>{const lib=new MB_Module(name);MB_editor.project.libraries.set(name,lib);
    if(index===0){lib.functions=original.functions;lib.blockSpecs=original.blockSpecs;lib.blockList=original.blockList;lib.choices=original.choices;}});
   MB_editor.codeManager.assignFunctionIDs();
   globalThis.savedIDs=JSON.stringify(Array.from(MB_editor.codeManager.functionChunkIDs));
   globalThis.savedFunctions=new Map(MB_editor.project.allFunctions().map(f=>[f.functionName,f]));
   globalThis.savedLibraries=new Map(MB_editor.project.libraries);globalThis.dispatchEvent=()=>{};`);
  saved.evaluate(fs.readFileSync(path.join(folder,'target-blocks.js'),'utf8'));
  await saved.evaluate('MicroBlocksTargetBlocks.ensure(MB_editor)');
  assert.deepEqual(Array.from(saved.evaluate('Array.from(MB_editor.project.libraries.keys())')),savedNames);
  assert(saved.evaluate('Array.from(savedLibraries).every(([name,lib])=>MB_editor.project.libraryNamed(name)===lib)'));
  assert(saved.evaluate('MB_editor.project.allFunctions().every(f=>savedFunctions.get(f.functionName)===f)'));
  assert(saved.evaluate('savedIDs===JSON.stringify(Array.from(MB_editor.codeManager.functionChunkIDs))'));
  saved.set('bundle',receipt.bundle);
  await saved.evaluate('MB_Files.initialize().then(()=>MB_editor.openLibraryFile(bundle))');
  const refreshed=Array.from(saved.evaluate('MB_editor.project.allFunctions().map(f=>f.functionName)'));
  assert.equal(refreshed.length,82);assert.equal(new Set(refreshed).size,82);
  assert(saved.evaluate('MicroBlocksJSProfile.target_library_modules.every(name=>MB_editor.project.libraryNamed(name))'));
  saved.evaluate('MB_editor.codeManager.assignFunctionIDs()');
  assert(saved.evaluate('MB_editor.project.allFunctions().every(f=>MB_editor.codeManager.compiledBytesFor(f).length>0)'));
 }
 const groupedProgram=compile(folder,source+'\n'+grouped);
 assert.equal(groupedProgram.chunks.length,100);assert.equal(groupedProgram.scripts.length,14);
 const p=compile(folder,source+'\n'+library);
 assert.equal(p.scripts.length,14);assert.equal(p.chunks.length,100);
 for(const name of ['p2PWMPercent','p2ServoPulseUS','p2ServoAngle','p2WaitPinReady','p2ReadReady','p2MeasureHighUS','p2MeasureDutyPermille','p2CountWindowMS'])assert(p.chunks.some(c=>c.name===name));
 console.log(JSON.stringify({functions:functions.length,fixture:'usability',chunks:p.chunks.length,scripts:p.scripts.length,
  modules:receipt.modules,legacy_api_identical:true,legacy_functions_and_ids_preserved:true,
  required_extension_revision:8,compiled:true,graphical:false,physical:false,network_allocations:0}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
