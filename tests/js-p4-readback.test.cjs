// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {load}=require('./support/js_editor_headless.cjs'),{connect,long,tick,until}=require('./support/js_p4_serial.cjs');
const assets=process.argv[2],pad=bytes=>{const result=[...bytes];while(result.length%4)result.push(0);return result;};
async function program(){
 const h=load(assets);await h.evaluate('MB_Files.initialize();MB_editor.openLibraryFile(MicroBlocksJSProfile.bundle)');
 h.evaluate('MB_editor.codeManager.assignFunctionIDs();globalThis.compiler=new MB_Compiler(MB_editor.project,MB_editor.codeManager);');
 const functions=h.evaluate('MB_editor.project.allFunctions().map(f=>({name:f.functionName,id:MB_editor.codeManager.functionChunkIDs.get(f.functionName),kind:3,bytes:compiler.compiledBytesFor(f)}))');
 const specs=JSON.parse(h.evaluate('JSON.stringify([...MB_editor.project.blockSpecs].sort(([a],[b])=>a.localeCompare(b)))'));
 const scripts=[];
 for(const [source,reporter] of [['+ 20 22',true],['p4TakePicture',true],['p4SmoothResize (\'[p4:imageTestPattern]\' 3 2 3) 2 2',true],["repeat 3 { waitMillis 1 }",false]]){
  h.set('source',source);h.set('reporter',reporter);const bytes=h.evaluate('(()=>{const p=MB_Parser.parse(source);return compiler.compiledBytesFor(MB_Parser.blockFor(reporter?p[0]:p,reporter));})()');scripts.push({id:200+scripts.length,kind:reporter?2:1,bytes});
 }
 return {functions,specs,chunks:[...functions,...scripts].map(c=>({...c,bytes:pad(c.bytes)}))};
}
function verify(h,project,p){
 h.set('restored',project);h.set('originals',p.functions);
 assert.equal(h.evaluate('restored.allFunctions().length'),64);
 const specs=JSON.parse(h.evaluate('JSON.stringify([...restored.blockSpecs].sort(([a],[b])=>a.localeCompare(b)))'));assert.deepEqual(specs,p.specs);
 h.evaluate('globalThis.manager=new MB_CodeManager(restored);for(const c of originals)manager.functionChunkIDs.set(c.name,c.id);globalThis.recompiler=new MB_Compiler(restored,manager);');
 const compiled=h.evaluate('originals.map(c=>({name:c.name,bytes:recompiler.compiledBytesFor(restored.functionNamed(c.name))}))');
 for(const c of compiled)assert.deepEqual(pad(c.bytes),pad(p.functions.find(f=>f.name===c.name).bytes),c.name);
 assert.equal(h.evaluate('restored.main.scripts.length'),4);
 const source=h.evaluate('restored.codeString()');assert(!source.includes('[io:'));assert(!source.includes('mediaSnapshot'));
 h.set('saved',source);h.evaluate('globalThis.reopened=new MB_Project();reopened.loadFromString(saved);');assert.equal(h.evaluate('reopened.codeString()'),source);
}
async function board(p){
 const f=await connect(assets);const sent=f.devices[0].messages;let hold=false;
 f.devices[0].onMessage=frame=>{
  if(frame[1]===26)f.devices[0].feed([250,26,frame[2]]);
  if(frame[1]===13&&!hold)for(const c of [...p.chunks].reverse()){
   const reply=long(32,[c.kind,...c.bytes],c.id);f.devices[0].feed(reply.subarray(0,3));f.devices[0].feed(reply.subarray(3));
  }
  setImmediate(()=>f.c.processMessages());
 };
 return {...f,sent,set hold(value){hold=value;}};
}
async function main(){let passed=0;const p=await program();
 async function test(fn){await fn();passed++;}
 await test(async()=>{const f=await board(p);try{
  const start=f.sent.length,pending=f.c.readCodeFromBoard();await until(()=>f.c.readbackInProgress);
  await assert.rejects(f.c.readCodeFromBoard(),/already active/);
  assert.equal(await f.c.sendMsg('deleteAllCodeMsg'),false);assert.equal(await f.c.sendMsg('systemResetMsg'),false);
  assert.equal(f.h.evaluate('MB_boardRuntime.sendFrame(MB_connection,P4MediaCore.packet(5,0))'),0);
  await assert.rejects(f.h.evaluate('MB_editor.codeManager.evalOnBoard(null)'),/Finish or cancel/);
  await f.h.evaluate('MB_editor.codeManager.syncScripts()');
  const project=await pending;verify(f.h,project,p);
  assert(f.sent.slice(start).every(x=>[9,12,13,26].includes(x[1])));
  assert.deepEqual([...f.c.readbackBlockedWrites],['deleteAllCodeMsg','systemResetMsg']);
 }finally{await f.close();}});
 await test(async()=>{const f=await board(p);try{f.hold=true;const start=f.sent.length,reading=f.c.readCodeFromBoard();await until(()=>f.sent.slice(start).some(x=>x[1]===13));await f.c.stopDecompilation();assert.equal(await reading,null);assert(f.sent.slice(start).every(x=>[9,12,13,26].includes(x[1])));assert.equal(f.c.readbackInProgress,false);
 }finally{await f.close();}});
 await test(async()=>{const f=await board(p);try{f.hold=true;const reading=f.c.readCodeFromBoard();await until(()=>f.c.decompiler);f.c.disconnect();assert.equal(await reading,null);await f.open();f.hold=false; // This fixture does not attach responses to the replacement device.
  assert.equal(f.c.readbackInProgress,false);
 }finally{await f.close();}});
 await test(async()=>{const h=load(assets,{readback:false});h.evaluate(fs.readFileSync(path.join(__dirname,'../web/js-editor/readback-libraries.js'),'utf8'));
  const catalog=JSON.parse(fs.readFileSync(path.join(assets,'readback-libraries.json'))),first=Object.keys(catalog.modules)[0];let good=false,calls=0;
  h.set('catalog',catalog);h.set('sourceBytes',entry=>{calls++;const raw=fs.readFileSync(path.join(assets,entry.path));const bytes=new Uint8Array(raw);if(!good)bytes[0]^=1;return Promise.resolve(bytes);});
  h.evaluate('MicroBlocksReadbackLibraries.install(MB_Decompiler,catalog,{fetchBytes:sourceBytes});globalThis.d=new MB_Decompiler();globalThis.target=new MB_Project();');h.set('moduleName',first);
  await assert.rejects(h.evaluate('d.addEmbeddedLibrary(moduleName,target)'),/hash differs/);assert.equal(h.evaluate('target.libraries.size'),0);good=true;await h.evaluate('d.addEmbeddedLibrary(moduleName,target)');assert.equal(calls,2);assert(h.evaluate('target.libraries.size')>0);
 });
 await test(async()=>{const api=require('../web/js-editor/readback-libraries.js');for(const entry of [{path:'sources/target/../secret.ubl',bytes:1,sha256:'0'.repeat(64)},{path:'https://invalid/lib.ubl',bytes:1,sha256:'0'.repeat(64)},{path:'sources/target/a.ubl',bytes:262145,sha256:'0'.repeat(64)}])assert.throws(()=>api.validate({schema:1,modules:{Example:entry}}),/Invalid/);});
 console.log(JSON.stringify({passed,functions:64,specs:189,functions_recompile_byte_identically:true,actual_connection:true,readback_queries_only:true,physical_hardware:false}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
