// SPDX-License-Identifier: MPL-2.0
// Real pinned BlockMorph/MB_Editor hooks in the headless fixture, not a browser.
'use strict';
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto'),assert=require('node:assert/strict');
const {load}=require('./support/js_preview_headless.cjs');
const folder=path.join(process.argv[2],'js-preview/propeller2');
const h=load(folder,{readback:false,Socket:class {constructor(){throw Error('Network forbidden');}}});
const manifest=JSON.parse(fs.readFileSync(path.join(folder,'source-manifest.json')));
for(const name of ['engine/mb-help-strings.js','engine/mb-help.js']) {
    const data=fs.readFileSync(path.join(folder,name)),entry=manifest.files.find(e=>e.path===name);
    assert(entry);assert.equal(crypto.createHash('sha256').update(data).digest('hex'),entry.sha256);
    h.evaluate(data.toString());
}
const original=h.evaluate('MB_editor.helpURLFor("setUserLED")');
assert(original.endsWith('output#set-user-led'));
for(const name of ['block-help-index.js','block-help.js'])h.evaluate(fs.readFileSync(path.join(folder,name),'utf8'));
h.evaluate('globalThis.helpOpened=[];window.open=(url,target)=>helpOpened.push([url,target]);globalThis.beforeHelp=MB_editor.project;globalThis.beforeDirty=MB_editor.unsavedEdits;');
const selectors=Array.from(h.evaluate('MicroBlocksBlockHelpIndex'));
assert(selectors.length>300);
for(const selector of selectors) {
    h.set('helpSelector',selector);
    const result=h.evaluate(`(()=>{const block=new CommandBlockMorph();block.selector=helpSelector;
        const available=block.hasHelp();block.openHelp();return [available,MB_editor.helpURLFor(helpSelector)];})()`);
    assert.equal(result[0],true,selector);
    assert.equal(decodeURIComponent(result[1].split('#')[1]),selector);
    assert.match(result[1],/^block-help\.html\?v=[a-f0-9]{16}#/);
}
const opened=Array.from(h.evaluate('helpOpened'),row=>Array.from(row));
assert.equal(opened.length,selectors.length);assert(opened.every(row=>row[1]==='_blank'));
assert.equal(h.evaluate('MB_editor.helpURLFor("setUserLED")'),original);
assert(h.evaluate('MB_editor.project===beforeHelp && MB_editor.unsavedEdits===beforeDirty'));
h.evaluate('globalThis.testHelpModule=new MB_Module("New user library");testHelpModule.blockSpecs.set("[future:custom]",[]);MB_editor.project.libraries.set(testHelpModule.moduleName,testHelpModule);');
assert(h.evaluate('MB_editor.helpURLFor("[future:custom]")').endsWith('#%5Bfuture%3Acustom%5D'));
console.log(JSON.stringify({selectors:selectors.length,native_has_help:true,native_open_help_new_tab:true,
    upstream_preserved:true,project_identity_and_dirty_flag_preserved:true,headless_only:true,graphical_acceptance:false}));
