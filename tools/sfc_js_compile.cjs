// SPDX-License-Identifier: MPL-2.0
// Genuine pinned JS importer, Morphs, project and compiler. Test-only fake DOM.
'use strict';
const fs=require('node:fs'),path=require('node:path'),vm=require('node:vm');
const {load}=require('../tests/support/js_editor_headless.cjs');
function open(assets,text){
    const h=load(assets);
    for(const name of ['sfc-core.js','sfc-editor.js'])vm.runInContext(fs.readFileSync(path.join(__dirname,'../web/js-editor',name),'utf8'),h.context,{filename:name});
    h.set('text',text);h.evaluate('MB_editor.project=new MB_Project();MB_editor.project.loadFromString(text);MB_editor.codeManager=new MB_CodeManager(MB_editor.project);');
    return h;
}
function compile(assets,text){
    const h=open(assets,text);
    const result=h.evaluate(`(()=>{
        const p=MB_editor.project,m=MB_editor.codeManager,state=MicroBlocksSFC.preflight(m);
        const functions=p.allFunctions(),scripts=p.allScripts().filter(b=>b&&!b.isFunctionDefinition());
        const chunks=[...functions,...scripts].map(item=>({id:item instanceof MB_Function?m.functionChunkIDs.get(item.functionName):m.ensureChunkIdFor(item),
            kind:m.chunkTypeFor(item),bytes:m.compiledBytesFor(item)}));
        return {chunks,variables:Object.fromEntries(p.allVariableNames().map(n=>[n,p.indexForVar(n)])),
            script_ids:scripts.map(b=>m.ensureChunkIdFor(b)),worker_plans:state.graphs.filter(p=>p.generated).map(p=>({prefix:p.prefix,
                steps:p.graph.steps.map(s=>[s.id,s.name]),edges:p.graph.edges.map(e=>[e.from,e.to,e.guards]),initial:p.graph.initial,worker_count:p.graph.steps.length})),source:p.codeString()};
    })()`);
    const saved=result.source,again=open(assets,saved);
    again.evaluate('MicroBlocksSFC.preflight(MB_editor.codeManager)');
    result.save_load_equal=again.evaluate('MB_editor.project.codeString()')===saved;
    if(!result.save_load_equal)throw Error('SFC source did not roundtrip canonically');
    return result;
}
module.exports={open,compile};
if(require.main===module){
    let report;
    try{report={status:'PASS',compiler:'genuine pinned MicroBlocks JavaScript',result:compile(process.argv[2],fs.readFileSync(process.argv[3],'utf8'))};}
    catch(error){report={status:'FAIL',error:String(error.stack||error)};}
    fs.writeFileSync(process.argv[4],JSON.stringify(report,null,2)+'\n');
    console.log(JSON.stringify({status:report.status,error:report.error}));
}
