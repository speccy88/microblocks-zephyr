// SPDX-License-Identifier: MPL-2.0
// SFC adapter for the pinned MicroBlocks JavaScript editor. No upstream edits.
(function (root) {
    'use strict';
    const M=root.MicroBlocksSFCModel, moduleName='_SFC workers', marker='Generated cooperative SFC workers v1';
    const fail=message=>{throw new Error('SFC: '+message);};
    const reserved=name=>/^_sfc\d+_/.test(name);
    const specs=[
        [' ','sfcSequence','SFC sequence _','cmd'],
        [' ','sfcStep','step _ setup _ loop _','menu.sfcSharedVarsMenu cmd cmd','Step1'],
        [' ','sfcTransition','transition _','menu.sfcSharedVarsMenu','Transition1'],
        [' ','sfcAnd','parallel ═ _ _ : branch _ : ...','cmd cmd cmd'],
        [' ','sfcAndJoin','═ join all transition _','menu.sfcSharedVarsMenu','Join'],
        [' ','sfcOr','OR ─ transition _ _ transition _ _ : transition _ _ : ...','menu.sfcSharedVarsMenu cmd menu.sfcSharedVarsMenu cmd menu.sfcSharedVarsMenu cmd','Choice1',null,'Choice2',null,'Choice3'],
        [' ','sfcOrJoin','─ merge transition _','menu.sfcSharedVarsMenu','Merge']
    ];
    const oldSpecs=MB_Specs.mbBlockSpecs;
    MB_Specs.mbBlockSpecs=function(){
        const result=oldSpecs.call(this).slice(), at=result.indexOf('cat;Control-Advanced');
        result.splice(at<0?result.length:at,0,'-',...specs);return result;
    };
    if(MB_Specs.selectorToSpec instanceof Map)for(const s of specs){MB_Specs.selectorToSpec.set(s[1],s);MB_Specs.selectorToCategory.set(s[1],'Control');}
    MB_Specs.cachedPaletteSpecs=null;
    SyntaxElementMorph.prototype.sfcSharedVarsMenu=function(){return Object.fromEntries((MB_editor?.project?.allVariableNames()||[]).filter(n=>!reserved(n)).map(n=>[n,n]));};
    const slotMenu=InputSlotMorph.prototype.mbMenu;
    InputSlotMorph.prototype.mbMenu=function(name){
        if(name!=='sfcSharedVarsMenu')return slotMenu.call(this,name);
        const menu=new MenuMorph(choice=>{if(choice!==undefined){this.setContents(choice);this.scriptChanged();}});
        menu.fontSize=this.fontSize;
        for(const variable of Object.keys(this.sfcSharedVarsMenu()))menu.addItem(variable,variable,null,null,false,false,null,null,true);
        if(menu.items.length)menu.addLine();
        menu.addItem('Add a variable',()=>{MB_editor.promptForVariable().then(variable=>{if(variable){this.setContents(variable);this.scriptChanged();}});});
        return menu;
    };
    const buildBlock=MB_Parser.prototype.blockWithArgs;
    MB_Parser.prototype.blockWithArgs=function(selector,args,...rest){
        if(rest[2]!==false){
            if((selector==='sfcAnd'&&(args.length<2||args.length>6))||(selector==='sfcOr'&&(args.length<4||args.length>12||args.length%2)))fail('choose two through six complete branches');
            const arity={sfcSequence:1,sfcStep:3,sfcTransition:1,sfcAndJoin:1,sfcOrJoin:1}[selector];
            if(arity!==undefined&&args.length!==arity)fail('incomplete '+selector+' block');
            const bodies=selector==='sfcSequence'?[0]:selector==='sfcStep'?[1,2]:selector==='sfcAnd'?args.map((_,i)=>i):selector==='sfcOr'?args.map((_,i)=>i).filter(i=>i%2):[];
            for(const i of bodies)if(args[i]!=null&&args[i]!==MB_Specs.emptyCommandList&&!(args[i] instanceof CommandBlockMorph))fail('setup, loop and branch sections must contain commands');
        }
        return buildBlock.call(this,selector,args,...rest);
    };
    const maxInputs=BlockMorph.prototype.maxInputCount;
    BlockMorph.prototype.maxInputCount=function(){if(this.selector==='sfcAnd')return 6;if(this.selector==='sfcOr')return 12;return maxInputs.call(this);};

    const states=new WeakMap(), stoppedOwners=new WeakSet();
    function sequences(block){const result=[];if(block)block.forAllBlocks(b=>{if(b.selector==='sfcSequence')result.push(b);});return result;}
    function locals(block,args=[]){const result=new Set(args);if(block)block.forAllBlocks(b=>{if(['local','for'].includes(b.selector))result.add(b.inputs()[0].evaluate());});return [...result];}
    const sourceFor=b=>b.expression();
    function prepare(project){
        const existing=project.libraries.get(moduleName);
        if(existing && existing.description!==marker)fail('reserved implementation module already exists');
        if(existing && (existing.variableNames.some(n=>!reserved(n))||existing.functions.some(f=>!reserved(f.functionName))||existing.scripts.length))fail('unexpected user code in generated implementation module');
        const userFunctions=project.allFunctions().filter(f=>!existing?.functions.includes(f));
        const userVars=[...new Set([...project.main.variableNames,...[...project.libraries.values()].filter(l=>l!==existing).flatMap(l=>l.variableNames)])];
        if(userVars.some(reserved)||userFunctions.some(f=>reserved(f.functionName)))fail('reserved generated name is used by user code');
        const entries=[];
        for(const block of project.allScripts()) {
            if(!block || block.isFunctionDefinition())continue;
            for(const sequence of sequences(block))entries.push({sequence,block,locals:locals(block),inFunction:false});
        }
        for(const f of userFunctions)for(const sequence of sequences(f.cmdList))entries.push({sequence,block:f,locals:locals(f.cmdList,f.argNames),inFunction:true});
        const fingerprint=JSON.stringify([userVars,entries.map(e=>[sourceFor(e.sequence),e.locals,e.inFunction])]);
        const previous=states.get(project);
        if(previous?.fingerprint===fingerprint && entries.every((e,i)=>e.sequence===previous.entries[i]?.sequence))return previous;
        const graphs=[],plans=new Map(), stepOwners=new Set(),guards=new Set();let workers=0;
        const impl=new MB_Module(moduleName);impl.description=marker;impl.beImplementation();impl.author='MicroBlocks Zephyr';
        const knownSelector=selector=>!!MB_Specs.specArrayForSelector(selector)||!!project.functionNamed(selector)||selector==='noop';
        for(const entry of entries){
            const graph=M.graphFor(sourceFor(entry.sequence),userVars,entry.locals,{knownSelector});
            for(const s of graph.steps){if(stepOwners.has(s.name))fail('step variable belongs to more than one chart: '+s.name);stepOwners.add(s.name);}
            graph.guards.forEach(g=>guards.add(g));
            let generated=null,prefix=null;
            if(graph.branched){
                if(entry.inFunction)fail('branch charts must be in top-level scripts, outside user functions');
                workers+=graph.steps.length;
                prefix='_sfc'+(graphs.length+1)+'_';generated=M.generate(graph,prefix);
                impl.variableNames.push(...generated.variables);
                for(const f of generated.functions)impl.functions.push(new MB_Function(f.name,f.args,MB_Parser.blockForDecompiled(f.body)));
            }
            const plan={...entry,graph,prefix,generated};graphs.push(plan);plans.set(entry.sequence,plan);
        }
        if([...stepOwners].some(n=>guards.has(n)))fail('step and guard variables must be disjoint across charts');
        if(workers>8)fail('at most eight concurrent step workers across the project');
        const scripts=project.allScripts().filter(b=>b&&!b.isFunctionDefinition());
        if(workers && scripts.length+workers>10)fail('worker and script admission exceeds ten VM task entries');
        if(userVars.length+impl.variableNames.length>128)fail('project exceeds 128 shared variables');
        if(userFunctions.length+impl.functions.length+scripts.length>256)fail('project exceeds 256 VM code chunks');
        if(impl.functions.length)project.libraries.set(moduleName,impl);else project.libraries.delete(moduleName);
        // Recycle deleted indices together, before compilation or variable-name writes.
        const all=project.allVariableNames();
        if(project.nextVarIndex+all.filter(n=>!project.varIndices.has(n)).length>128){project.varIndices=new Map();project.nextVarIndex=0;MB_editor?.codeManager?.recompileNeeded();}
        const state={fingerprint,entries,graphs,plans};states.set(project,state);clearLive();return state;
    }
    const assign=MB_CodeManager.prototype.assignFunctionIDs;
    MB_CodeManager.prototype.assignFunctionIDs=function(){
        let state;
        if(this.project&&!this.sfcPreparing){this.sfcPreparing=true;try{state=prepare(this.project);}finally{this.sfcPreparing=false;}}
        const result=assign.call(this);
        if(state&&this.sfcGeneration!==state){
            // The normal uploader skips hidden, unchanged library functions.
            // Regenerated actions must participate in its source/CRC comparison.
            for(const plan of state.graphs)for(const f of plan.generated?.functions||[]){const entry=this.chunkIDs.get(f.name);if(entry)entry[4]=true;}
            this.sfcGeneration=state;
        }
        return result;
    };
    const unused=MB_Project.prototype.unusedFunctions;
    MB_Project.prototype.unusedFunctions=function(palette){
        // SFC calls are compiler lowering, absent from the editable syntax tree.
        // The existing analyser already traverses native setup/loop sections,
        // including their user helper calls and dynamic broadcasts.
        const result=unused.call(this,palette);
        return prepare(this).graphs.length?result.filter(n=>!reserved(n)):result;
    };
    const emit=MB_Compiler.prototype.emitCmd;
    const compileBytes=MB_CodeManager.prototype.compiledBytesFor;
    MB_CodeManager.prototype.compiledBytesFor=function(item){
        // Undo and locale changes replace project while retaining this manager.
        // The pinned compiler otherwise keeps the previous project's bindings.
        if(this.compiler)this.compiler.project=this.project;
        return compileBytes.call(this,item);
    };
    MB_Compiler.prototype.emitCmd=function(cmd){
        if(cmd.selector==='sfcSequence'){
            const state=prepare(this.project),plan=state.plans.get(cmd);
            if(!plan)fail('place the complete sequence in a project script before running it');
            const shadow=[...this.argNames.keys(),...this.localVars.keys()];
            if([...plan.graph.steps.map(s=>s.name),...plan.graph.guards].some(n=>shadow.includes(n)))fail('step/transition variables cannot be local variables or parameters');
            const lowered=plan.generated?.invocation||M.serialBody(sourceFor(cmd),this.project.allVariableNames(),shadow);
            return this.instructionsForCmdList(MB_Parser.blockForDecompiled(M.copy(lowered)));
        }
        if(cmd.selector.startsWith('sfc'))fail('flow block outside a complete SFC sequence');
        return emit.call(this,cmd);
    };
    function preflight(manager){
        const state=prepare(manager.project);if(!state.graphs.length)return state;
        manager.assignFunctionIDs();
        const unused=new Set(manager.project.unusedFunctions());
        for(const item of [...manager.project.allFunctions().filter(f=>!unused.has(f.functionName)),...manager.project.allScripts().filter(b=>b&&!b.isFunctionDefinition())]){
            // Inspect the real result, before upstream's oversize-error stub.
            const bytes=manager.compiledBytesFor(item),length=1+Math.ceil(bytes.length/4)*4;
            if(length>1000)fail('compiled function/script exceeds the 1000-byte transfer bound');
        }
        return state;
    }
    const save=MB_CodeManager.prototype.saveAllChunksNow;
    MB_CodeManager.prototype.saveAllChunksNow=async function(...args){preflight(this);return save.apply(this,args);};
    const run=MB_CodeManager.prototype.runChunk;
    MB_CodeManager.prototype.runChunk=function(id){preflight(this);return run.call(this,id);};
    const evaluate=MB_CodeManager.prototype.evalOnBoard;
    MB_CodeManager.prototype.evalOnBoard=async function(block,...args){
        try{preflight(this);return await evaluate.call(this,block,...args);}
        catch(error){MB_editor.showError(block,String(error.message||error));}
    };
    const stop=MB_CodeManager.prototype.stopRunningChunk;
    MB_CodeManager.prototype.stopRunningChunk=function(id){
        const state=states.get(this.project);
        for(const plan of state?.graphs||[])if(this.lookupChunkID(plan.block)===id){
            stoppedOwners.add(plan.block);
            if(plan.generated){
                for(const s of plan.graph.steps)stop.call(this,this.functionChunkIDs.get(plan.prefix+'worker'+s.id));
                for(const [name,value] of [[plan.prefix+'run',false],[plan.prefix+'active',0],[plan.prefix+'status',-3]])this.setVar(this.project.indexForVar(name),value);
            }
            for(const s of plan.graph.steps)this.setVar(this.project.indexForVar(s.name),false);
        }
        clearLive();return stop.call(this,id);
    };

    // Render only from solicited real VM values. Never alter saved block colors.
    const live=new Map(),pending=new Map();let currentProject=null,cursor=0;
    function clearLive(){for(const b of live.keys()){delete b.sfcActive;b.changed();}live.clear();pending.clear();}
    const render=BlockMorph.prototype.render;
    BlockMorph.prototype.render=function(ctx){const color=this.color;try{if(this.sfcActive===true)this.color=new Color(35,185,75);return render.call(this,ctx);}finally{this.color=color;}};
    const handle=MB_Connection.prototype.handleMessage;
    MB_Connection.prototype.handleMessage=function(msg){
        if(msg[1]===this.msgNameToID('taskErrorMsg')){
            const editor=MB_editor,manager=editor?.codeManager;
            for(const plan of states.get(editor?.project)?.graphs||[])if(manager.lookupChunkID(plan.block)===msg[2]||plan.generated?.functions.some(f=>manager.functionChunkIDs.get(f.name)===msg[2]))stoppedOwners.add(plan.block);
            clearLive();
        }
        if(msg[1]===this.msgNameToID('varValueMsg')){
            const request=pending.get(msg[2]);pending.delete(msg[2]);
            if(request&&request.project===MB_editor?.project&&Date.now()-request.sent<1500){
                request.block.sfcActive=this.returnedValue(msg)===true;
                live.set(request.block,Date.now());request.block.changed();
            }
        }
        return handle.call(this,msg);
    };
    function poll(){
        const editor=MB_editor,project=editor?.project,now=Date.now();
        if(project!==currentProject){clearLive();currentProject=project;}
        if(!project||!MB_connection?.isConnected()){clearLive();return;}
        for(const [b,t] of live)if(now-t>1500||!b.parent){delete b.sfcActive;b.changed();live.delete(b);}
        for(const [id,r]of pending)if(now-r.sent>1500)pending.delete(id);
        const state=states.get(project);if(!state)return;
        const blocks=[];
        for(const plan of state.graphs)if(!stoppedOwners.has(plan.block)&&editor.runningChunks?.has(plan.block))plan.sequence.inputs()[0].nestedBlock()?.forAllBlocks(b=>{if(b.selector==='sfcStep')blocks.push(b);});
        if(!blocks.length){clearLive();return;}
        for(let i=0;i<Math.min(4,blocks.length);i++){
            const b=blocks[cursor++%blocks.length],name=b.inputs()[0].evaluate(),id=project.varIndices.get(name);
            if(id!==undefined&&!pending.has(id)){pending.set(id,{project,block:b,sent:now});editor.codeManager.getVar(id);}
        }
    }
    const clear=MB_Editor.prototype.clearRunningHighlights;
    MB_Editor.prototype.clearRunningHighlights=function(...args){clearLive();return clear.apply(this,args);};
    const running=MB_Editor.prototype.updateRunning;
    MB_Editor.prototype.updateRunning=function(id,value){
        const block=this.codeManager?.blockForChunkID(id);
        if(value&&block)stoppedOwners.delete(block);
        if(!value){for(const p of states.get(this.project)?.graphs||[])if(p.block===block){stoppedOwners.add(block);clearLive();}}
        return running.call(this,id,value);
    };
    root.MicroBlocksSFC=Object.freeze({prepare,preflight,poll,clearLive,specs,moduleName,marker});
    if(typeof setInterval==='function')setInterval(poll,250);
})(globalThis);
