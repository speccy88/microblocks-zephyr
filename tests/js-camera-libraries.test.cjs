// SPDX-License-Identifier: MPL-2.0
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),crypto=require('node:crypto');
const {load}=require('./support/js_editor_headless.cjs');
async function main(){
 const assets=process.argv[2],h=load(assets),meta=JSON.parse(fs.readFileSync(path.join(assets,'microduck-camera-libraries.json')));
 const bundle=fs.readFileSync(path.join(assets,meta.bundle));
 for(const e of meta.sources){const b=fs.readFileSync(path.join(assets,e.packaged_source));assert.equal(crypto.createHash('sha256').update(b).digest('hex'),e.sha256);assert.deepEqual(bundle.subarray(e.bundle_offset,e.bundle_offset+e.bytes),b);}
 h.set('file',meta.bundle);await h.evaluate('MB_Files.initialize();MB_editor.openLibraryFile(file)');
 assert.equal(h.evaluate('MB_editor.project.libraries.size'),12);
 h.evaluate('MB_editor.codeManager.assignFunctionIDs();globalThis.compiler=new MB_Compiler(MB_editor.project,MB_editor.codeManager);');
 const functions=h.evaluate('MB_editor.project.allFunctions().map(f=>({name:f.functionName,id:MB_editor.codeManager.functionChunkIDs.get(f.functionName),bytes:compiler.compiledBytesFor(f)}))');
 assert.equal(functions.length,229);assert.equal(new Set(functions.map(f=>f.id)).size,functions.length);
 assert(functions.every(f=>f.id<240&&f.bytes.length>0&&f.bytes.length<=1000));
 for(const name of ['microduckEasyBrightness','microduckCameraCapture','microduckEasyBattery','microduckRobotHealthCapture','microduckEasySimStop','microduckSimStop'])assert(functions.some(f=>f.name===name));
 assert.equal(h.evaluate('MB_Specs.specArrayForSelector("microduckEasySimStop",true,0).at(-1)'),false);
 const probes={
  simpleZero:'microduckEasyValue (microduckEasyBrightness 1 1)',simpleMax:'microduckEasyValue (microduckEasyBrightness 2 1)',
  simpleRGB:'microduckEasyValue (microduckEasyRGB 1 1)',
  advancedRGB:`local 'f' (microduckCameraCapture)\nlocal 'r' (microduckCameraRGB f 1 1)\nmicroduckCameraRelease f\nreturn (microduckEasyValue r)`,
  outOfRange:'microduckEasyStatus (microduckEasyBrightness 5 1)',invalid:'microduckEasyStatus (microduckEasyBrightness 0 1)',
  unavailable:'microduckEasyStatus (microduckEasyBrightness 1 1)',
  advanced:`local 'f' (microduckCameraCapture)\nlocal 'u' (microduckCameraU f 2 1)\nlocal 'v' (microduckCameraV f 1 1)\nmicroduckCameraRelease f\nreturn ((microduckEasyValue u) + (microduckEasyValue v))`,
  timestamp:`local 'f' (microduckCameraCapture)\nlocal 'r' (microduckCameraTimestamp f)\nmicroduckCameraRelease f\nreturn (microduckEasyValue r)`
 };
 const compiled={};for(const [name,source] of Object.entries(probes)){
  h.set('text',source);h.set('reporter',!['advanced','timestamp','advancedRGB'].includes(name));
  compiled[name]=h.evaluate('(()=>{const n=MB_Parser.parse(text);return compiler.compiledBytesFor(MB_Parser.blockFor(reporter?n[0]:n,reporter));})()');
 }
 h.evaluate(`MB_editor.project.main.scripts=[
  [20,20,MB_Parser.blockFor(MB_Parser.parse('microduckEasyBrightness 1 1')[0],true)],
  [20,120,MB_Parser.blockFor(MB_Parser.parse('microduckCameraCapture')[0],true)],
  [20,220,MB_Parser.blockFor(MB_Parser.parse('microduckEasySimStop false')[0],true)]];
  globalThis.saved=MB_editor.project.codeString();globalThis.reopened=new MB_Project();reopened.loadFromString(saved);`);
 assert.equal(h.evaluate('reopened.allFunctions().length'),229);assert.equal(h.evaluate('reopened.codeString()===saved'),true);
 assert.equal(h.evaluate('reopened.main.scripts.length'),3);assert.equal(h.evaluate('MB_connection.port'),null);
 console.log(JSON.stringify({modules:12,functions,probes:compiled,roundtrip:true,graphical:false,physical_hardware:false}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
