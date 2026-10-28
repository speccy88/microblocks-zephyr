// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {load} = require('./support/js_editor_headless.cjs');
const assets = process.argv[2];
const sha = value => crypto.createHash('sha256').update(value).digest('hex');
const image = '01234567'.repeat(13);
const fixture = `module 'Matrix Roundtrip Fixture'\ncategory 'Output'\nspec 'r' 'matrixRoundtrip' 'matrix _' 'unoqMatrix' '${image}'\nto matrixRoundtrip pattern { return pattern }\n`;
const bundle = fs.readFileSync(path.join(assets, 'Libraries/MicroDuck Linux.ubl'), 'utf8');
const input = `projectName 'Roundtrip Fixture'\nmodule 'main'\nscript 40 60 (matrixRoundtrip '${image}')\nscript 210 180 (microduckReadingStatus (microduckDepthCapture))\nscript 300 280 (+ 20 22)\n${fixture}\n${bundle}`;
let passed = 0;
function test(name, fn) { fn(); passed++; }
function open(text) {
    const h = load(assets);
    h.set('projectText', text);
    // The real editor assigns its new project before loading: spec lookup uses it.
    h.evaluate('MB_editor.project = new MB_Project(); MB_editor.project.loadFromString(projectText);');
    return h;
}
const h = open(input);
test('matrix default quoting extends only the custom slot dispatch', () => {
    assert.equal(h.evaluate('specDefaultString("num",42)'), '42');
    assert.equal(h.evaluate('specDefaultString("unrecognized", "0123")'), 'nil');
    assert.equal(h.evaluate('specDefaultString("unoqMatrix", "0123")'), "'0123'");
    assert.equal(h.evaluate('specDefaultString("str", "0123")'), "'0123'");
});
test('full project imports main scripts and all embedded modules', () => {
    assert.equal(h.evaluate('MB_editor.project.main.scripts.length'), 3);
    assert.equal(h.evaluate('MB_editor.project.libraries.size'), 7);
    assert.equal(h.evaluate('MB_editor.project.allFunctions().length'), 147);
    assert.equal(h.evaluate('MB_connection.port'), null);
});
test('matrix remains a String and typed script remains a real reporter', () => {
    assert.equal(h.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0] instanceof UnoQMatrixSlotMorph'), true);
    assert.equal(h.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0].evaluate()'), image);
    assert.equal(h.evaluate('MB_editor.project.main.scripts[1][2] instanceof ReporterBlockMorph'), true);
});
const saved = h.evaluate('MB_editor.project.codeString()');
const fresh = open(saved);
test('save then reopen in a fresh editor context is canonical', () => {
    assert.equal(fresh.evaluate('MB_editor.project.codeString()'), saved);
    assert.equal(fresh.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0].evaluate()'), image);
    assert.equal(fresh.evaluate('JSON.stringify(MB_editor.project.main.scripts.map(s=>s.slice(0,2)))'), '[[40,60],[210,180],[300,280]]');
    assert.equal(fresh.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0].getSpec()'), '%unoqMatrix');
});
test('restored matrix edits do not change saved bytes or palette defaults', () => {
    fresh.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0].paintPixelAt(104,"0")');
    assert.equal(fresh.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0].evaluate()'), image.slice(0,103)+'0');
    assert.equal(h.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0].evaluate()'), image);
    assert.equal(fresh.evaluate('MB_Specs.blockForSpec(MB_Specs.specArrayForSelector("matrixRoundtrip",true,1),"Output").inputs()[0].evaluate()'), image,
        fresh.evaluate('JSON.stringify(MB_editor.project.blockSpecs.get("matrixRoundtrip"))'));
});
test('all restored functions and scripts compile without any VM connection', () => {
    fresh.evaluate('MB_editor.codeManager=new MB_CodeManager(MB_editor.project); MB_editor.codeManager.assignFunctionIDs();');
    const sizes = fresh.evaluate('(()=>{const c=new MB_Compiler(MB_editor.project,MB_editor.codeManager); return [...MB_editor.project.allFunctions().map(f=>c.compiledBytesFor(f).length),...MB_editor.project.main.scripts.map(s=>c.compiledBytesFor(s[2]).length)];})()');
    assert.equal(sizes.length, 150);
    assert.ok(sizes.every(n=>Number.isInteger(n)&&n>0&&n<=1000));
    assert.equal(fresh.evaluate('MB_connection.port'), null);
});
test('repeated fresh-context saves preserve the original ABI', () => {
    let text=saved;
    for(let i=0;i<3;i++) {
        const again=open(text);
        assert.equal(again.evaluate('MB_editor.project.main.scripts[0][2].inputs()[0].evaluate()'),image);
        text=again.evaluate('MB_editor.project.codeString()');
        assert.equal(text,saved);
    }
});
if(process.argv[3]) fs.writeFileSync(process.argv[3],saved);
console.log(JSON.stringify({tests:passed,passed,modules:7,functions:147,scripts:3,compiled:150,
    canonical_project_sha256:sha(saved),bytes:Buffer.byteLength(saved),graphical:false,hardware:false,
    upstream_modified:false,saved_format:'ordinary .ubp text; 104-character matrix String'}));
