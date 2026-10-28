// SPDX-License-Identifier: MPL-2.0
// Linux-profile adaptation; pinned upstream engine files stay unchanged.
(function (root) {
    'use strict';
    const installed = new WeakSet(), protectedConnections = new WeakSet();
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
        if (typeof addHat !== 'function' || typeof evaluate !== 'function' ||
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
        CodeManager.prototype.evalOnBoard = async function (block, showBytes) {
            const current = editor();
            const inPane = () => block?.parent instanceof Scripts && block.parent.children.includes(block);
            const active = () => editor() === current && current?.codeManager === this && current.project === this.project && inPane();
            if (active() && this.lookupChunkID(block) == null) {
                if (!(await current.saveBeforeRun()) || !active()) return;
                if (this.lookupChunkID(block) == null) await this.syncScripts();
                if (!active()) return;
            }
            return evaluate.call(this, block, showBytes);
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
