// SPDX-License-Identifier: MPL-2.0
// Linux-profile adaptation; pinned upstream engine files stay unchanged.
(function (root) {
    'use strict';
    const installed = new WeakSet(), protectedConnections = new WeakSet(), evaluations = new WeakMap();
    const projectBindings = new WeakMap(), editorBindings = new WeakMap();
    function signature(project) {
        return JSON.stringify([project.allVariableNames(),
            project.allFunctions().map(f => [f.functionName, f.codeString()]).sort(([a], [b]) => a.localeCompare(b)),
            project.main.scripts.map(entry => entry[2].codeString()).sort()]);
    }
    function install(Decompiler, CodeManager, Scripts, editor, {primitiveSets = {}} = {}) {
        if (typeof Decompiler !== 'function' || typeof CodeManager !== 'function' ||
            typeof Scripts !== 'function' || typeof editor !== 'function') {
            throw Error('Upstream readback hooks changed; review the Linux adapter');
        }
        if (installed.has(CodeManager)) return;
        const names = Decompiler.prototype.primSetNameForIndex;
        const aliases = Object.entries(primitiveSets);
        if (aliases.some(([name,index])=>!/^[A-Za-z][A-Za-z0-9_]*$/.test(name)||!Number.isInteger(index)||index<0||index>63)) throw Error('Invalid readback primitive namespace.');
        if (typeof names === 'function') Decompiler.prototype.primSetNameForIndex = function(compiler,index) {
            return aliases.find(([,value])=>value===index)?.[0] || names.call(this,compiler,index);
        };
        const addHat = Decompiler.prototype.addHatBlock;
        const evaluate = CodeManager.prototype.evalOnBoard;
        const decompile = Decompiler.prototype.decompileProject;
        const assign = CodeManager.prototype.assignFunctionIDs;
        if (typeof addHat !== 'function' || typeof evaluate !== 'function' ||
            typeof decompile !== 'function' || typeof assign !== 'function' ||
            typeof CodeManager.prototype.syncScripts !== 'function' || typeof editor !== 'function') {
            throw Error('Upstream readback hooks changed; review the Linux adapter');
        }
        Decompiler.prototype.addHatBlock = function (id, kind, node) {
            const result = addHat.call(this, id, kind, node);
            if (kind === 2 && result?.selector === 'return' && result.next == null &&
                result.args?.length === 1 && result.args[0]?.isReporter === true) {
                return result.args[0];
            }
            return result;
        };
        Decompiler.prototype.decompileProject = async function (...args) {
            const project = await decompile.apply(this, args);
            const chunks = this.chunks || [], scripts = chunks.filter(c => c[1] !== 3);
            // A skipped/unknown chunk must not be guessed into another script's
            // slot. Keep the normal reader result, without adopting bindings.
            if (scripts.length === project.main.scripts.length && chunks.length <= 256 &&
                new Set(chunks.map(c => c[0])).size === chunks.length &&
                chunks.every(c => Number.isInteger(c[0]) && c[0] >= 0 && c[0] < 256)) {
                projectBindings.set(project, {signature: signature(project),
                    functions: [...this.funcs].filter(([, name]) => project.functionNamed(name)),
                    scripts: scripts.map((c, i) => [c[0], c[1], project.main.scripts[i][2].codeString()])});
            }
            return project;
        };
        CodeManager.prototype.assignFunctionIDs = function (...args) {
            const current = editor(), pending = current && editorBindings.get(current);
            if (pending && current.project === this.project && this.chunkIDs.size === 0 && this.functionChunkIDs.size === 0) {
                editorBindings.delete(current);
                if (pending.valid() && signature(this.project) === pending.plan.signature) {
                    // openProjectFromBoard clones the decompiled document and
                    // rearranges its scripts. Match content, not positions or
                    // morph identity, and reserve the VM's existing slots before
                    // assigning source-only library functions new free slots.
                    for (const [id, name] of pending.plan.functions) {
                        this.chunkIDs.set(name, [id, null, 3, '', true, true]);
                        this.functionChunkIDs.set(name, id);
                    }
                    const remaining = this.project.main.scripts.map(entry => entry[2]);
                    for (const [id, kind, source] of pending.plan.scripts) {
                        const index = remaining.findIndex(block => block.codeString() === source);
                        const block = remaining.splice(index, 1)[0];
                        this.chunkIDs.set(this.chunkKeyFor(block), [id, null, kind, '', false, false]);
                    }
                }
            }
            return assign.apply(this, args);
        };
        CodeManager.prototype.evalOnBoard = function (block, showBytes) {
            const current = editor();
            const inPane = () => block?.parent instanceof Scripts && block.parent.children.includes(block);
            const active = () => editor() === current && current?.codeManager === this && current.project === this.project && inPane();
            const wasInPane = inPane();
            // Fast explicit clicks can all pass saveBeforeRun before the first
            // sync increments savesInProgress. Keep one initial rebind/download
            // and run at a time, including palette evaluations in this manager.
            const previous = evaluations.get(this) || Promise.resolve();
            const pending = previous.then(async () => {
                if (editor() !== current || current?.codeManager !== this || current.project !== this.project || (wasInPane && !active())) return;
                if (active() && this.lookupChunkID(block) == null) {
                    if (!(await current.saveBeforeRun()) || !active()) return;
                    if (this.lookupChunkID(block) == null) await this.syncScripts();
                    if (!active()) return;
                }
                return evaluate.call(this, block, showBytes);
            });
            // A failed evaluation remains visible to its caller; it must not
            // poison the next explicit request or retain a manager indefinitely.
            evaluations.set(this, pending.catch(() => {}));
            return pending;
        };
        installed.add(CodeManager);
    }
    function protectRead(Connection, CodeManager, connection, editor=()=>null) {
        if (protectedConnections.has(Connection)) return;
        const proto=Connection.prototype,read=proto.readCodeFromBoard,send=proto.sendMsg,cancel=proto.stopDecompilation,disconnect=proto.disconnect,sync=CodeManager.prototype.syncScripts,evaluate=CodeManager.prototype.evalOnBoard;
        if ([read,send,cancel,disconnect,sync,evaluate,connection].some(fn=>typeof fn!=='function')) throw Error('Pinned non-writing readback hooks changed.');
        const queries=new Set(['pingMsg','getVersionMsg','getVarNamesMsg','getAllCodeMsg']);
        proto.sendMsg=function(name,...args){
            if(this.readbackInProgress&&!queries.has(name)){
                if(this.readbackBlockedWrites.length<32)this.readbackBlockedWrites.push(String(name));
                return Promise.resolve(false);
            }return send.call(this,name,...args);
        };
        proto.readCodeFromBoard=async function(...args){
            if(this.readbackInProgress)throw Error('Board project readback is already active.');
            if(!this.isConnected()||this.vmVersion==null)throw Error('Connect and identify the board before reading its project.');
            const port=this.port,current=editor(),previousProject=current?.project,generation=(this.readbackGeneration||0)+1;this.readbackGeneration=generation;
            this.readbackInProgress=true;this.readbackBlockedWrites=[];
            try{await this.sendQueue;const project=await read.apply(this,args);
                if(this.readbackGeneration!==generation||this.port!==port||!this.isConnected()||editor()!==current||current?.project!==previousProject)return null;
                const plan=project&&projectBindings.get(project);
                if(plan&&current)editorBindings.set(current,{plan,valid:()=>this.readbackGeneration===generation&&this.port===port&&this.isConnected()});
                return project;}
            finally{this.readbackInProgress=false;}
        };
        proto.stopDecompilation=function(...args){
            if(this.readbackInProgress){this.readbackGeneration++;this.decompiler=null;const current=editor();if(current)current.readFromBoard=false;return Promise.resolve();}
            return cancel.apply(this,args);
        };
        proto.disconnect=function(...args){if(this.readbackInProgress)this.decompiler=null;return disconnect.apply(this,args);};
        CodeManager.prototype.syncScripts=function(...args){
            if(connection()?.readbackInProgress){this.recompileAll=true;return Promise.resolve();}
            return sync.apply(this,args);
        };
        CodeManager.prototype.evalOnBoard=function(...args){
            if(connection()?.readbackInProgress)return Promise.reject(Error('Finish or cancel board readback before running blocks.'));
            return evaluate.apply(this,args);
        };
        protectedConnections.add(Connection);
    }
    const api = Object.freeze({install,protectRead});
    root.MicroBlocksReadback = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
