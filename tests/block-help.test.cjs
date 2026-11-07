// SPDX-License-Identifier: MPL-2.0
const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const base = path.resolve(__dirname, '../web/js-editor');
class Editor {
    constructor() { this.project = {functionNamed: selector => selector === 'user<block>'}; }
    helpURLFor(selector) { return selector === 'digitalWrite' ? 'https://wiki.microblocks.fun/output' : null; }
}
const doc = {label: '<img src=x onerror=alert(1)>', modules:['Example'], summary:'Summary',
    prerequisites:['No hardware required'], inputs:[], returns:'Number', sources:['example.ubl'], notes:[],
    examples:[{title:'Example',code:'<script>alert(1)</script>',explanation:'Read only'}]};
const sandbox = {MB_Editor: Editor, MicroBlocksBlockHelpIndex:['custom'], MicroBlocksBlockHelpVersion:'test', console};
vm.runInNewContext(fs.readFileSync(path.join(base,'block-help.js'),'utf8'),sandbox);
const editor = new Editor();
assert.equal(editor.helpURLFor('custom'),'block-help.html?v=test#custom');
assert.equal(editor.helpURLFor('user<block>'),'block-help.html?v=test#user%3Cblock%3E');
assert.equal(editor.helpURLFor('digitalWrite'),'https://wiki.microblocks.fun/output');
assert.equal(editor.helpURLFor('missing'),null);
assert.equal(editor.helpURLFor('__proto__'),null);
assert.deepEqual(Object.keys(editor.project),['functionNamed']);
editor.project.libraries = new Map([['New library',{blockSpecs:new Map([['[future:native]',[]]])}]]);
assert.equal(editor.helpURLFor('[future:native]'),'block-help.html?v=test#%5Bfuture%3Anative%5D');
class Element {
    constructor(tag) { this.tag=tag; this.children=[]; this.textContent=''; this.value=''; }
    appendChild(child) { this.children.push(child); }
    replaceChildren() { this.children=[]; }
    setAttribute() {}
    addEventListener() {}
    set innerHTML(_) { throw Error('Unsafe HTML sink'); }
}
const main = new Element('main'), location={hash:'#custom'};
let change;
const page = {MicroBlocksBlockHelpData:{blocks:{custom:doc}},location,
    document:{getElementById:()=>main,createElement:tag=>new Element(tag)},
    addEventListener:(_,fn)=>{change=fn;}};
vm.runInNewContext(fs.readFileSync(path.join(base,'block-help-page.js'),'utf8'),page);
assert.equal(main.children[0].textContent,doc.label);
assert.equal(main.children.find(node=>node.tag==='pre').textContent,doc.examples[0].code);
location.hash='#user%3Cblock%3E';change();
assert.equal(main.children[0].textContent,'Documentation not yet authored');
location.hash='#%invalid';change();
assert.equal(main.children[0].textContent,'Documentation not yet authored');
location.hash='';change();assert.equal(main.children[0].textContent,'Custom block reference');
console.log('PASS: help adapter routing, fallback, safe rendering, no project writes');
