// SPDX-License-Identifier: MIT
'use strict';
const assert=require('node:assert/strict'),{load}=require('./support/js_editor_headless.cjs');
const h=load(process.argv[2],{console:{log(){},warn(){},error:console.error}});let checks=0;
h.evaluate(`globalThis.calls={read:0,erase:0,sync:0};
MB_editor.project=new MB_Project();MB_editor.boardTurn=Promise.resolve();
MB_editor.takeBoardTurn=MB_Editor.prototype.takeBoardTurn;
MB_editor.openProjectFromBoard=()=>{calls.read++;};
MB_editor.showDownloadProgress=()=>{};MB_editor.reportError=e=>{throw e;};
MB_editor.codeManager={recompileNeeded(){},async boardHasSameProject(){return false;},async stopAndSyncScripts(){calls.sync++;}};
MB_connection.clearBoardIfConnected=async()=>{calls.erase++;};MB_connection.sendMsg=()=>{};
class FixtureConnection{async connect(type){await MB_Editor.prototype.justConnected.call(MB_editor);return type;}}
globalThis.FixtureConnection=FixtureConnection;globalThis.fixture=new FixtureConnection();`);
async function reset(source='module main\n') {h.set('text',source);h.evaluate('MB_editor.project=new MB_Project();MB_editor.project.loadFromString(text);MB_editor.readFromBoard=false;MB_editor.autosave=null;calls={read:0,erase:0,sync:0};');}
async function main(){
 await reset();await h.evaluate("fixture.connect('linux-loopback')");assert.equal(h.evaluate('calls.erase'),1);checks++;
 h.evaluate('globalThis.fixtureEditor=MB_editor;MicroBlocksReadback.preserveEmptyConnect(FixtureConnection,()=>fixtureEditor);');
 await reset();await h.evaluate("fixture.connect('linux-loopback')");assert.equal(h.evaluate('JSON.stringify(calls)'),'{"read":1,"erase":0,"sync":0}');checks++;
 await reset('module main\nscript 20 30 (+ 20 22)\n');await h.evaluate("fixture.connect('linux-loopback')");assert.equal(h.evaluate('calls.read'),0);assert.equal(h.evaluate('calls.sync'),1);assert.equal(h.evaluate('MB_editor.project.main.scripts.length'),1);checks++;
 await reset();await h.evaluate("fixture.connect('serial')");assert.equal(h.evaluate('calls.erase'),1);checks++;
 await reset();h.evaluate("MB_editor.autosave={offer:Promise.resolve().then(()=>MB_editor.project.loadFromString('module main\\nscript 20 30 (+ 20 22)\\n'))};");await h.evaluate("fixture.connect('linux-loopback')");assert.equal(h.evaluate('calls.read'),0);assert.equal(h.evaluate('calls.sync'),1);checks++;
 await reset();h.evaluate('MB_editor.autosave={offer:Promise.resolve().then(()=>{fixtureEditor={};})};');await assert.rejects(h.evaluate("fixture.connect('linux-loopback')"),/Editor changed/);checks++;
 const prior=h.evaluate('FixtureConnection.prototype.connect');h.evaluate('MicroBlocksReadback.preserveEmptyConnect(FixtureConnection,()=>MB_editor);');assert.equal(h.evaluate('FixtureConnection.prototype.connect'),prior);checks++;
 console.log(JSON.stringify({passed:checks,actual_pinned_editor:true,physical:false}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
