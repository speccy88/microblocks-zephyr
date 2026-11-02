// SPDX-License-Identifier: MPL-2.0
// Real shared editor parser/blocks/compiler; no engine or transport mock.
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {load}=require('../tests/support/js_editor_headless.cjs');
const [assets,output]=process.argv.slice(2),h=load(assets),reports={};
for(const name of ['python-library.js','python-blocks.js'])vm.runInContext(fs.readFileSync(path.join(assets,name),'utf8'),h.context,{filename:name});
const example=fs.readFileSync(path.join(__dirname,'../linux/extensions/examples/inference.ubp'),'utf8');
h.set('legacySource',example);
h.evaluate(`MB_editor.project=new MB_Project();MB_editor.project.loadFromString(legacySource);
MB_editor.project.addLibraryFromString(MicroBlocksPythonLibrary.source,'Python Extensions',null);
MB_editor.project.libraryNamed('Python Extensions').beImplementation();
globalThis.originalPythonCore=MB_editor.project.libraryNamed('Python Extensions');
MB_editor.codeManager=new MB_CodeManager(MB_editor.project);`);
assert(h.evaluate("MB_editor.project.libraryNamed('Python Extensions')===originalPythonCore"));
assert(h.evaluate("MB_editor.project.libraryNamed('Neural Inference').isImplementationLib()"));
for(const backend of ['litert','onnx']){
 h.evaluate('MB_editor.project=new MB_Project();new MB_CodeManager(MB_editor.project)');
 const source=example.replace("'litert'",`'${backend}'`)+`\nscript 40 400 (at 1 NeuralValues)\nscript 40 450 (at 2 NeuralValues)\nscript 40 500 (at 3 NeuralValues)\n`;
 h.set('source',source);h.evaluate('MB_editor.project.loadFromString(source);MB_editor.codeManager=new MB_CodeManager(MB_editor.project)');
 const report=h.evaluate(`(()=>{const p=MB_editor.project,m=MB_editor.codeManager;return {
 chunks:[...p.allFunctions(),...p.allScripts()].map(item=>({id:item instanceof MB_Function?m.functionChunkIDs.get(item.functionName):m.ensureChunkIdFor(item),kind:m.chunkTypeFor(item),bytes:m.compiledBytesFor(item)})),
 variables:Object.fromEntries(p.allVariableNames().map(n=>[n,p.indexForVar(n)])),script_ids:p.allScripts().map(b=>m.ensureChunkIdFor(b)),
 library_loaded:p.libraryNamed('Python Extensions').isImplementationLib(),inference_library_loaded:p.libraryNamed('Neural Inference').isImplementationLib(),user_selectors:p.allScripts().flatMap(b=>b.allBlocks().map(x=>x.selector))};})()`);
 assert(report.library_loaded&&report.inference_library_loaded);assert(report.chunks.every(c=>1+Math.ceil(c.bytes.length/4)*4<=1000));
 assert(!report.user_selectors.some(s=>/python|microduck|Begin|Release/.test(s)));
 assert(h.evaluate('MicroBlocksPythonBlocks.selectors.includes("neuralPredict")'));
 reports[backend]=report;
}
fs.writeFileSync(output,JSON.stringify({real_compiler:true,legacy_python_core_preserved:true,graphical:false,hardware:false,variants:reports},null,2)+'\n');
console.log(JSON.stringify({real_compiler:true,variants:Object.fromEntries(Object.entries(reports).map(([b,r])=>[b,{chunks:r.chunks.length,script_ids:r.script_ids}]))}));
