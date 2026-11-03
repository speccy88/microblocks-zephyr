// SPDX-License-Identifier: MPL-2.0
// Compile real MicroBlocks source with the pinned editor; the DOM is test-only.
'use strict';
const fs=require('node:fs');
const {load}=require('../tests/support/js_preview_headless.cjs');
function compile(assets,source){
    const h=load(assets,{readback:false});
    h.set('source',source);
    h.evaluate('MB_editor.project=new MB_Project();MB_editor.project.loadFromString(source);MB_editor.codeManager=new MB_CodeManager(MB_editor.project);');
    return h.evaluate(`(()=>{
        const p=MB_editor.project,m=MB_editor.codeManager;
        m.assignFunctionIDs();
        const functions=p.allFunctions(),scripts=p.allScripts().filter(b=>b&&!b.isFunctionDefinition());
        const chunks=[...functions,...scripts].map(item=>({
            id:item instanceof MB_Function?m.functionChunkIDs.get(item.functionName):m.ensureChunkIdFor(item),
            name:item instanceof MB_Function?item.functionName:null,
            kind:m.chunkTypeFor(item),bytes:m.compiledBytesFor(item)}));
        return {compiler:'pinned MicroBlocks JavaScript 5564b1e',chunks,
            variables:Object.fromEntries(p.allVariableNames().map(n=>[n,p.indexForVar(n)])),
            scripts:scripts.map(b=>m.ensureChunkIdFor(b)),source:p.codeString()};
    })()`);
}
module.exports={compile};
if(require.main===module){
    const result=compile(process.argv[2],fs.readFileSync(process.argv[3],'utf8'));
    fs.writeFileSync(process.argv[4],JSON.stringify(result,null,2)+'\n');
    console.log(JSON.stringify({chunks:result.chunks.map(c=>({id:c.id,name:c.name,kind:c.kind,bytes:c.bytes.length})),variables:result.variables,scripts:result.scripts}));
}
