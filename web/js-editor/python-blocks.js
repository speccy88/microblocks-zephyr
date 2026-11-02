// SPDX-License-Identifier: MPL-2.0
// Normal domain blocks. Python/RPC lifecycle stays outside user programs.
(() => {
    'use strict';
    const source=MicroBlocksPythonLibrary.source,name='Python Extensions';
    const commands=MB_Parser.parse(source),specs=[];
    const literal=value=>typeof value==='string'&&value[0]==="'"?value.slice(1,-1):value;
    for(const command of commands){if(command[0]==='advanced')break;if(command[0]==='spec')specs.push(command.slice(1).map(literal));}
    const selectors=new Set(specs.map(s=>s[1]));
    const functions=commands.filter(c=>c[0]==='to').map(c=>literal(c[1]));
    const blockSpecs=MB_Specs.mbBlockSpecs;
    MB_Specs.mbBlockSpecs=function(){
        const result=blockSpecs.call(this).slice(),index=result.indexOf('cat;Data-Advanced');
        if(index<0)throw Error('Review changed Python domain palette anchor');
        result.splice(index,0,'-',...specs);return result;
    };
    if(MB_Specs.selectorToSpec instanceof Map)for(const spec of specs){MB_Specs.selectorToSpec.set(spec[1],spec);MB_Specs.selectorToCategory.set(spec[1],'Data');}
    MB_Specs.cachedPaletteSpecs=null;
    function ensure(project){
        if(!project||project.libraryNamed(name))return;
        let needed=false;
        for(const root of [...project.allScripts(),...project.allFunctions().map(f=>f.cmdList)])root?.forAllBlocks(block=>{if(selectors.has(block.selector))needed=true;});
        if(!needed)return;
        if(functions.some(selector=>project.functionNamed(selector)))throw Error('Python block function name conflicts with this project; rename that function first');
        project.addLibraryFromString(source,name,null);
        project.libraryNamed(name).beImplementation();
    }
    const assign=MB_CodeManager.prototype.assignFunctionIDs;
    MB_CodeManager.prototype.assignFunctionIDs=function(){ensure(this.project);return assign.call(this);};
    // Save an ordinary self-contained library once a domain block is used.
    // An empty editor stays empty: no startup project overwrite or prompt.
    const update=MB_Editor.prototype.updateProject;
    MB_Editor.prototype.updateProject=function(){const result=update.call(this);ensure(this.project);return result;};
    globalThis.MicroBlocksPythonBlocks=Object.freeze({ensure,selectors:[...selectors]});
})();
