// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert = require('node:assert/strict');
const {load} = require('./support/js_editor_headless.cjs');
const adapter = require('../web/js-editor/readback-compat.js');
const assets = process.argv[2];
let passed = 0;
function check(name, run) { return Promise.resolve().then(run).then(() => {passed++;}); }
async function decoded(h, kind = 2) {
    h.set('text', 'module main\nscript 20 30 (+ 20 22)\n');
    h.evaluate(`MB_editor.project=new MB_Project();MB_editor.project.loadFromString(text);
        globalThis.sourceBlock=MB_editor.project.main.scripts[0][2];
        globalThis.code=new MB_Compiler(MB_editor.project).compiledBytesFor(sourceBlock);
        while(code.length%4)code.push(0);
        globalThis.decoder=new MB_Decompiler();`);
    h.set('kind', kind);
    h.evaluate('decoder.addChunk(0,kind,new Uint8Array(code))');
    const project = await h.evaluate('decoder.decompileProject()');
    h.set('decodedProject', project);
    return project;
}
async function setup(options = {}) {
    const h=load(assets,options); await decoded(h);
    h.evaluate(`MB_editor.project=decodedProject;
        globalThis.block=decodedProject.main.scripts[0][2];
        globalThis.pane=new ScriptsMorph();pane.add(block);
        globalThis.manager=new MB_CodeManager(decodedProject);MB_editor.codeManager=manager;
        globalThis.calls={sync:0,run:[],save:0};
        MB_editor.saveBeforeRun=async()=>{calls.save++;return true;};
        MB_connection.updateConnection=()=> 'connected';
        manager.runChunk=id=>calls.run.push(id);
        manager.syncScripts=async()=>{calls.sync++;manager.chunkIDs.set(manager.chunkKeyFor(block),[17,null,2,'',false,false]);};`);
    return h;
}
async function main() {
    await check('unadapted pinned decompiler reproduces the reporter return-wrapper bug', async()=>{
        const h=load(assets,{readback:false});await decoded(h);
        assert.equal(h.evaluate('decodedProject.main.scripts[0][2].selector'),'return');
        assert.equal(h.evaluate('decodedProject.main.scripts[0][2] instanceof CommandBlockMorph'),true);
    });
    await check('actual type2 readback restores a reporter without any connection or write',async()=>{
        const h=load(assets);await decoded(h);
        assert.equal(h.evaluate('decodedProject.main.scripts[0][2] instanceof ReporterBlockMorph'),true);
        assert.equal(h.evaluate('decodedProject.main.scripts[0][2].selector'),'+');
        assert.equal(h.evaluate('MB_connection.port'),null);
    });
    await check('unadapted fresh code manager reproduces silent explicit-run failure',async()=>{
        const h=await setup({readback:false});
        await h.evaluate('manager.evalOnBoard(block)');
        assert.equal(h.evaluate('calls.sync'),0);assert.equal(h.evaluate('calls.run.length'),0);
    });
    await check('command chunk returns retain their original shape',async()=>{
        const h=load(assets);await decoded(h,1);
        assert.equal(h.evaluate('decodedProject.main.scripts[0][2].selector'),'return');
    });
    await check('first explicit run binds through real code-manager evaluation; later runs do not resync',async()=>{
        const h=await setup();
        assert.equal(h.evaluate('manager.lookupChunkID(block)'),null);
        await h.evaluate('manager.evalOnBoard(block)');
        await h.evaluate('manager.evalOnBoard(block)');
        assert.equal(h.evaluate('calls.sync'),1);
        assert.equal(h.evaluate('JSON.stringify(calls.run)'),'[17,17]');
    });
    await check('cancelled save does not sync or execute',async()=>{
        const h=await setup();h.evaluate('MB_editor.saveBeforeRun=async()=>false');
        await h.evaluate('manager.evalOnBoard(block)');
        assert.equal(h.evaluate('calls.sync'),0);assert.equal(h.evaluate('calls.run.length'),0);
    });
    await check('project replacement during sync cancels execution',async()=>{
        const h=await setup();h.evaluate('manager.syncScripts=async()=>{calls.sync++;MB_editor.project=new MB_Project();}');
        await h.evaluate('manager.evalOnBoard(block)');
        assert.equal(h.evaluate('calls.sync'),1);assert.equal(h.evaluate('calls.run.length'),0);
    });
    await check('detaching the script during pending save cancels execution',async()=>{
        const h=await setup();h.evaluate('MB_editor.saveBeforeRun=async()=>{pane.removeChild(block);return true;}');
        await h.evaluate('manager.evalOnBoard(block)');
        assert.equal(h.evaluate('calls.sync'),0);assert.equal(h.evaluate('calls.run.length'),0);
    });
    await check('install is idempotent and incompatible hooks are rejected',async()=>{
        const h=load(assets);h.evaluate('globalThis.beforeEval=MB_CodeManager.prototype.evalOnBoard;MicroBlocksReadback.install(MB_Decompiler,MB_CodeManager,ScriptsMorph,()=>MB_editor)');
        assert.equal(h.evaluate('beforeEval===MB_CodeManager.prototype.evalOnBoard'),true);
        assert.throws(()=>adapter.install(null,class {},class {},()=>null),/hooks changed/);
        assert.throws(()=>adapter.install(class {},class {},class {},()=>null),/hooks changed/);
    });
    console.log(JSON.stringify({tests:passed,passed,actual_pinned_classes:true,graphical:false}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
