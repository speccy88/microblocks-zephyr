// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert=require('node:assert/strict'),{load}=require('./support/js_editor_headless.cjs');
const diagnostics=[],h=load(process.argv[2],{console:{...console,log(...v){diagnostics.push(v.join(' '));},warn(...v){diagnostics.push(v.join(' '));}}});
const cases=[
 ['zero',"local 'n' 0\nwhile false { += n 1 }\nreturn n",0],
 ['three',"local 'n' 0\nwhile (n < 3) {\n+= n 1\nwaitMillis 0\n}\nreturn n",3],
 ['break',"local 'n' 0\nwhile true {\n+= n 1\nif (n == 3) { exitLoop }\n}\nreturn n",3],
 ['nested',"local 'n' 0\nrepeat 2 {\nlocal 'i' 0\nwhile (i < 2) {\n+= i 1\n+= n 1\n}\n}\nreturn n",4]
];
const output=[];
for(const [name,source,expected] of cases){
 h.set('source',source);h.evaluate('globalThis.block=MB_Parser.blockFor(MB_Parser.parse(source),false);globalThis.before=block.codeString();globalThis.compiler=new MB_Compiler(MB_editor.project);globalThis.bytes=compiler.compiledBytesFor(block);');
 assert.equal(h.evaluate('block.codeString()===before'),true);
 const bytes=Array.from(h.evaluate('bytes'));while(bytes.length%4)bytes.push(0);
 h.set('code',bytes);h.evaluate('globalThis.decoder=new MB_Decompiler();decoder.addChunk(250,2,new Uint8Array(code));globalThis.node=decoder.decompile(250,2,new Uint8Array(code));globalThis.decoded=MB_Parser.blockForDecompiled(node);');
 const recompiled=Array.from(h.evaluate('compiler.compiledBytesFor(decoded)'));while(recompiled.length%4)recompiled.push(0);assert.deepEqual(recompiled,bytes,name);
 output.push({name,source,expected,bytes});
}
assert.deepEqual(diagnostics.filter(s=>/Skipping unknown op|Unknown expression type/.test(s)),[]);
console.log(JSON.stringify({cases:output,source_unchanged:true,readback_recompile_identical:true,hardware:false}));
