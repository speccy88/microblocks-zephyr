// SPDX-License-Identifier: MIT
// Actual pinned importer/compiler; fake DOM only. No transport/hardware.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{load}=require('./support/js_preview_headless.cjs');
async function main(){
 const root=process.argv[2],duck=path.join(root,'js-preview/microduck');
 const expected=['raspberry-pi5','microduck','fruit-jam','waveshare','propeller2','esp32p4','xrp-rp2350','unoq'];
 for(const name of expected){const profile=JSON.parse(fs.readFileSync(path.join(root,'js-preview',name,'target-profile.json')));assert.equal(profile.id,name);}
 assert.equal(JSON.parse(fs.readFileSync(path.join(duck,'target-profile.json'))).connection_enabled,false);
 assert(!fs.existsSync(path.join(root,'js-preview/raspberry-pi5/Libraries/MicroDuck Linux.ubl')));
 let providers=0;class Socket{constructor(){providers++;throw Error('Network forbidden in publication test');}}
 const pi=load(path.join(root,'js-preview/raspberry-pi5'),{readback:false,Socket,location:{href:'https://speccy88.github.io/microblocks-zephyr/js-preview/raspberry-pi5/'}});
 assert.throws(()=>pi.evaluate("new MB_CommPort().connect('linux-loopback')"),/WSS is not commissioned/);assert.equal(providers,0);
 const results=[];
 for(const [file,count,modules] of [['MicroDuck Linux.ubl',170,6],['MicroDuck Starter Lab.ubl',213,10],['MicroDuck Camera Lab.ubl',235,12]]){
  const h=load(duck,{readback:false,Socket,location:{href:'https://speccy88.github.io/microblocks-zephyr/js-preview/microduck/'}});h.set('file','Libraries/'+file);
  for(const type of ['serial','BLE','boardie','linux-loopback'])assert.throws(()=>h.evaluate(`new MB_CommPort().connect(${JSON.stringify(type)})`),/offline editing only/);
  assert.equal(providers,0);
  await h.evaluate('MB_Files.initialize();MB_editor.openLibraryFile(file)');
  assert.equal(h.evaluate('MB_editor.project.libraries.size'),modules);
  assert.equal(h.evaluate('MB_editor.project.allFunctions().length'),count);
  assert.equal(h.evaluate('MB_connection.port'),null);
  h.evaluate('MB_editor.codeManager.assignFunctionIDs();globalThis.c=new MB_Compiler(MB_editor.project,MB_editor.codeManager);');
  const funcs=h.evaluate('MB_editor.project.allFunctions().map(f=>({id:MB_editor.codeManager.functionChunkIDs.get(f.functionName),bytes:c.compiledBytesFor(f)}))');
  assert.equal(new Set(funcs.map(f=>f.id)).size,count);assert(funcs.every(f=>f.id<240&&f.bytes.length>0&&f.bytes.length<=1000));
  h.evaluate('globalThis.saved=MB_editor.project.codeString();MB_editor.project=new MB_Project();MB_editor.project.loadFromString(saved);');
  assert.equal(h.evaluate('MB_editor.project.codeString()===saved'),true);
  assert.equal(h.evaluate('MB_editor.project.functionNamed("microduckDepthNearestReported").functionName'),'microduckDepthNearestReported');
  if(count>170)assert.equal(h.evaluate('MB_editor.project.functionNamed("microduckEasyNearestRange").functionName'),'microduckEasyNearestRange');
  results.push({bundle:file,functions:count,modules,compiled:true,roundtrip:true});
 }
 console.log(JSON.stringify({profiles:expected,results,uncommissioned_providers_allocated:providers,physical_hardware:false,graphical:false}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
