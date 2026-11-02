// SPDX-License-Identifier: MPL-2.0
// Shared domain registries; saved Python1.0 libraries remain unchanged.
(() => {
    'use strict';
    const literal=value=>typeof value==='string'&&value[0]==="'"?value.slice(1,-1):value;
    function registry(source,name){
        const commands=MB_Parser.parse(source),specs=[];
        for(const command of commands){if(command[0]==='advanced')break;if(command[0]==='spec')specs.push(command.slice(1).map(literal));}
        return {source,name,specs,selectors:new Set(specs.map(s=>s[1])),functions:commands.filter(c=>c[0]==='to').map(c=>literal(c[1]))};
    }
    const core=registry(MicroBlocksPythonLibrary.source,'Python Extensions');
    const inference=MicroBlocksPythonLibrary.inferenceSource?registry(MicroBlocksPythonLibrary.inferenceSource,'Neural Inference'):null;
    const registries=[core,...(inference?[inference]:[])],specs=registries.flatMap(r=>r.specs),selectors=new Set(specs.map(s=>s[1]));
    const blockSpecs=MB_Specs.mbBlockSpecs;
    MB_Specs.mbBlockSpecs=function(){
        const result=blockSpecs.call(this).slice(),index=result.indexOf('cat;Data-Advanced');
        if(index<0)throw Error('Review changed Python domain palette anchor');
        result.splice(index,0,'-',...specs);return result;
    };
    if(MB_Specs.selectorToSpec instanceof Map)for(const spec of specs){MB_Specs.selectorToSpec.set(spec[1],spec);MB_Specs.selectorToCategory.set(spec[1],'Data');}
    MB_Specs.cachedPaletteSpecs=null;
    function needed(project,which){
        let found=false;
        for(const root of [...project.allScripts(),...project.allFunctions().map(f=>f.cmdList)])root?.forAllBlocks(block=>{if(which.has(block.selector))found=true;});
        return found;
    }
    function add(project,entry){
        if(project.libraryNamed(entry.name))return;
        if(entry.functions.some(selector=>project.functionNamed(selector)))throw Error('Python block function name conflicts with this project; rename that function first');
        project.addLibraryFromString(entry.source,entry.name,null);project.libraryNamed(entry.name).beImplementation();
    }
    function ensure(project){
        if(!project||!needed(project,selectors))return;
        const needInference=inference&&needed(project,inference.selectors);
        add(project,core);
        if(needInference){
            if(!project.functionNamed('pythonCall'))throw Error('Review the existing Python Extensions library: inference requires its shared pythonCall helper');
            add(project,inference);
        }
    }
    const assign=MB_CodeManager.prototype.assignFunctionIDs;
    MB_CodeManager.prototype.assignFunctionIDs=function(){ensure(this.project);return assign.call(this);};
    const update=MB_Editor.prototype.updateProject;
    MB_Editor.prototype.updateProject=function(){const result=update.call(this);ensure(this.project);return result;};
    globalThis.MicroBlocksPythonBlocks=Object.freeze({ensure,selectors:[...selectors]});
})();
