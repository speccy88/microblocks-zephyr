// SPDX-License-Identifier: MIT
// Load optional libraries through the real pinned editor's ordinary library API.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {load}=require('./support/js_preview_headless.cjs');
const {compile}=require('../tools/compile_propeller2_project.cjs');
async function main(){
 const folder=path.join(process.argv[2],'js-preview/propeller2');
 const source=path.join(__dirname,'../boards/propeller2/integration');
 const results=[];
 for(const name of fs.readdirSync(path.join(source,'libraries')).filter(n=>n.endsWith('.ubl'))){
  const warnings=[];
  const capture=(...parts)=>{const line=parts.join(' ');if(/Skipping unknown op|error|warning/i.test(line))warnings.push(line);};
  const h=load(folder,{readback:false,console:{...console,log:capture,warn:capture,error:capture},Socket:class{constructor(){throw Error('Network forbidden');}}});
  h.set('optional','Libraries/P2/'+name);
  await h.evaluate('MB_Files.initialize().then(()=>MB_editor.openLibraryFile(optional))');
  h.evaluate('MB_editor.codeManager.assignFunctionIDs()');
  const functions=h.evaluate('MB_editor.project.allFunctions().map(f=>({name:f.functionName,bytes:MB_editor.codeManager.compiledBytesFor(f).length}))');
  assert(functions.length>0,name);assert(functions.every(f=>f.bytes>0),name);
  assert.equal(warnings.length,0,warnings.join('\n'));
  results.push({library:name,functions:functions.length});
 }
 const libraries=fs.readdirSync(path.join(source,'libraries')).filter(n=>n.endsWith('.ubl')).map(n=>fs.readFileSync(path.join(source,'libraries',n),'utf8')).join('\n');
 const baseline=fs.readFileSync(path.join(source,'P2_Hardware.ubl'),'utf8');
 for(const name of fs.readdirSync(path.join(source,'examples')).filter(n=>n.endsWith('.ubp'))){
  const p=compile(folder,fs.readFileSync(path.join(source,'examples',name),'utf8')+'\n'+baseline+'\n'+libraries);
  assert(p.scripts.length>0,name);
  assert(!p.chunks.some(c=>c.kind>=4),name+' must not automatically start');
 }
 console.log(JSON.stringify({optional:results,examples_compiled:true,network:false,physical:false}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
