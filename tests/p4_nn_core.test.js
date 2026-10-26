// SPDX-License-Identifier: MIT
const {test}=require('node:test'),assert=require('node:assert/strict'),core=require('../web/p4-neural-core.js');
const good=()=>({schema:1,id:'sensor-demo',license:'MIT',source:'local model',sha256:'a'.repeat(64),source_sha256:'b'.repeat(64),source_format:'onnx',artifact_format:'tflite',backend:'tflm-reference-dense-v1',arena_bytes:16384,bytes:512,operators:['FULLY_CONNECTED']});
test('manifest keeps native runtime separate from converted source and preserves hashes',()=>{const m=core.validateManifest(good(),512),bytes=core.metadata(m);assert.equal(bytes.length,68+m.id.length+m.license.length+m.source.length);assert.equal(bytes[64],1);assert.equal(bytes[0],170);assert.equal(bytes[32],187);});
test('rejects unsupported, mismatched, oversized and unsafe metadata before transport',()=>{
 for(const change of [{artifact_format:'onnx'},{bytes:513},{arena_bytes:524289},{operators:['CONV_2D']},{sha256:'bad'},{source_sha256:'bad'},{source:'bad"source'},{license:''},{id:'x'.repeat(33)}])assert.throws(()=>core.validateManifest({...good(),...change},512));
 assert.throws(()=>core.validateManifest(good(),262145));
});
test('binary upload and output read use bounded exact little-endian frames',()=>{const p=core.packet(2,17,29,512,0,new Uint8Array([1,2,3]));assert.equal(p.length,33);const v=new DataView(p.buffer);assert.equal(v.getUint16(3,true),28);assert.equal(v.getUint32(11,true),17);assert.equal(p.at(-1),254);assert.throws(()=>core.packet(2,1,0,0,0,new Uint8Array(513)));assert.throws(()=>core.packet(2,-1));});
