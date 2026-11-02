// SPDX-License-Identifier: MPL-2.0
// Genuine pinned MicroBlocks parser, native block Morphs and compiler.
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm'),assert=require('node:assert/strict');
const {load}=require('../tests/support/js_editor_headless.cjs');
const [assets,output]=process.argv.slice(2),h=load(assets);
for(const name of ['python-library.js','python-blocks.js'])vm.runInContext(fs.readFileSync(path.join(assets,name),'utf8'),h.context,{filename:name});
assert.equal(h.evaluate('MB_editor.project=new MB_Project();new MB_CodeManager(MB_editor.project);MB_editor.project.hasUserCode()'),false);
const source=fs.readFileSync(path.join(__dirname,'../linux/extensions/examples/sqlite.ubp'),'utf8')+`
script 400 400 (at 2 (at 1 ('[linux:pythonGet]' '{"rows":[["room",21500],["second",0]],"none":null}' '/rows')))
script 400 450 ('[linux:pythonGet]' '{"large":9223372036854775807}' '/large')
script 400 500 ('[linux:pythonType]' '{"none":null}' '/none')
script 400 550 ('[linux:pythonJSON]' ('[data:makeList]' 'quote\'\'text' 0 false))
script 400 600 (at 1 (at 1 (sqliteRows (sqliteQuery 'SELECT 42' ''))))
`;
h.set('source',source);h.evaluate('MB_editor.project.loadFromString(source);MB_editor.codeManager=new MB_CodeManager(MB_editor.project)');
const report=h.evaluate(`(()=>{const p=MB_editor.project,m=MB_editor.codeManager;return {
    chunks:[...p.allFunctions(),...p.allScripts()].map(item=>({id:item instanceof MB_Function?m.functionChunkIDs.get(item.functionName):m.ensureChunkIdFor(item),kind:m.chunkTypeFor(item),bytes:m.compiledBytesFor(item)})),
    variables:Object.fromEntries(p.allVariableNames().map(n=>[n,p.indexForVar(n)])),script_ids:p.allScripts().map(b=>m.ensureChunkIdFor(b)),
    library_loaded:p.libraryNamed('Python Extensions').isImplementationLib(),saved:p.codeString()};})()`);
assert.equal(report.library_loaded,true);assert(report.chunks.every(c=>1+Math.ceil(c.bytes.length/4)*4<=1000));
assert(h.evaluate('MicroBlocksPythonBlocks.selectors.includes("sqliteQuery")'));
report.real_compiler=true;report.graphical=false;report.physical_hardware=false;
fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');
console.log(JSON.stringify({real_compiler:true,chunks:report.chunks.length,script_ids:report.script_ids,library_lazy_loaded:true,physical_hardware:false}));
