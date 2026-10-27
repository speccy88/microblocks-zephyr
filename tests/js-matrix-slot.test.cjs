// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert = require('node:assert/strict'), fs = require('node:fs');
const {load} = require('./support/js_editor_headless.cjs');
const model = require('../web/js-editor/legacy-slots.js');
let passed = 0;
function test(name, f) { f(); passed++; }
const empty = '0'.repeat(104);
test('strict String ABI and GP presets', () => {
    for (const name of ['Heart','Smile','Checkerboard','Diagonal','All on','Clear']) assert.ok(model.valid(model.preset(name)), name);
    for (const value of [null, 0, [], '0'.repeat(103), '0'.repeat(105), empty+'\n', '8'+empty.slice(1)]) assert.equal(model.valid(value), false);
});
test('GP hit-test boundaries, gaps and dropdown exclusion', () => {
    assert.equal(model.pixelIndexAt(3,3),1); assert.equal(model.pixelIndexAt(130,80),104);
    for (const point of [[2,3],[3,2],[11,3],[3,11],[133,3],[3,83],[140,40],[NaN,3],['3',3]]) assert.equal(model.pixelIndexAt(...point),null);
});
const h = load(process.argv[2]);
test('actual upstream slot construction and atomic invalid input', () => {
    h.evaluate('globalThis.slot = new UnoQMatrixSlotMorph();');
    assert.equal(h.evaluate('slot.evaluate()'),empty);
    assert.equal(h.evaluate('slot instanceof MicroBitDisplaySlotMorph'),true);
    h.evaluate('slot.setContents("7".repeat(104))');
    assert.equal(h.evaluate('slot.setContents("9".repeat(104))'),false);
    assert.equal(h.evaluate('slot.evaluate()'),'7'.repeat(104));
    h.evaluate('slot.focusCalls=0;slot.lockMouseFocus=()=>{slot.focusCalls++};slot.mouseDownLeft(slot.topLeft().add(new Point(11*slot.scale,3*slot.scale)))');
    assert.equal(h.evaluate('slot.focusCalls'),0);
});
test('independent copy, drag interpolation and toggle values', () => {
    h.evaluate('slot.setContents(""); slot.paintValue="7"; slot.paintStrokeTo(1);slot.paintStrokeTo(104);globalThis.copied=slot.copyRecordingReferences(new Map());copied.paintPixelAt(1,"0");');
    assert.equal(h.evaluate('slot.evaluate()[0]'),'7'); assert.equal(h.evaluate('copied.evaluate()[0]'),'0');
    assert.equal(h.evaluate('slot.evaluate()[103]'),'7');
    assert.ok(h.evaluate('slot.pixels.filter(x=>x==="7").length')>=13);
    assert.equal(h.evaluate('slot.paintPixelAt(1,"7\\n")'),false);
});
test('scale-aware geometry and all 104 drawing cells', () => {
    h.evaluate('slot.scale=2; slot.fixLayout();');
    assert.equal(h.evaluate('slot.width()'),304); assert.equal(h.evaluate('slot.height()'),172);
    assert.equal(h.evaluate('slot.pixelIndex(slot.topLeft().add(new Point(6,6)))'),1);
    h.set('rects',[]);
    h.evaluate('slot.render({fillRect(...args){rects.push(args)},beginPath(){},moveTo(){},lineTo(){},closePath(){},fill(){}})');
    assert.equal(h.context.rects.length,105);
});
test('legacy boolean palette entries remain saved as b', () => {
    h.evaluate('globalThis.bs=["b","testBool","test boolean"]; globalThis.bb=MB_Specs.blockForSpec(bs,"Input");');
    assert.equal(h.evaluate('bb instanceof ReporterBlockMorph'),true); assert.equal(h.evaluate('bs[0]'),'b');
});
test('actual parser/printing/defaults round-trip the original 104-digit String', () => {
    const image = model.preset('Heart');
    h.set('library',`module 'Matrix Fixture'\nspec 'r' 'matrixLiteral' 'matrix _' 'unoqMatrix' '${image}'\nto matrixLiteral pattern { return pattern }\n`);
    h.evaluate('MB_editor.project.addLibraryFromString(library,"Matrix Fixture",null);globalThis.mb=MB_Specs.blockForSpec(["r","matrixLiteral","matrix _","unoqMatrix",MicroBlocksLegacySlots.preset("Heart")],"Input");');
    assert.equal(h.evaluate('mb.inputs()[0] instanceof UnoQMatrixSlotMorph'),true);
    assert.equal(h.evaluate('mb.inputs()[0].evaluate()'),image);
    const text = h.evaluate('mb.codeString()'); assert.ok(text.includes(image));
    h.set('text',text);
    assert.equal(h.evaluate('MB_Parser.blockFor(MB_Parser.parse(text)[0],true).inputs()[0].evaluate()'),image);
    const bytes=h.evaluate('new MB_Compiler(MB_editor.project).compiledBytesFor(mb)');
    assert.ok(Buffer.from(bytes).includes(Buffer.from(image)));
});
console.log(JSON.stringify({tests:passed,passed,graphical:false,hardware:false,upstream_modified:false}));
