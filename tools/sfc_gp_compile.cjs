#!/usr/bin/env node
/* SPDX-License-Identifier: MIT - genuine pinned GP compiler, no GUI or devices. */
'use strict';
const {Worker,isMainThread,parentPort,workerData}=require('node:worker_threads');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const sha=data=>crypto.createHash('sha256').update(data).digest('hex');
if(isMainThread){
 const [assetsArg,inputArg,outputArg,checksArg]=process.argv.slice(2);if(!assetsArg||!inputArg||!outputArg)throw Error('Usage: node sfc_gp_compile.cjs PACKAGED_EDITOR INPUT.ubp NEW_REPORT.json [HEADLESS_CHECKS.gp]');
 const assets=path.resolve(assetsArg),input=path.resolve(inputArg),output=path.resolve(outputArg);if(fs.existsSync(output))throw Error('Report already exists; inspect it before a new run.');
 const hashes=Object.fromEntries(['gp_wasm.js','gp_wasm.wasm','gp_wasm.data'].map(n=>[n,sha(fs.readFileSync(path.join(assets,n)))]));
 const report={status:'RUNNING',input_sha256:sha(fs.readFileSync(input)),engine_hashes:hashes,compiler:'packaged genuine GP 2.5.8',host_mounts:false,browser_access:false,hardware_access:false,dependency_upgrade:false,messages:[]};
 const checks=checksArg?fs.readFileSync(path.resolve(checksArg),'utf8'):'';if(checks)report.checks_sha256=sha(checks);
 const w=new Worker(__filename,{workerData:{assets,input,checks}});let finished=false;
 const finish=(status,error)=>{if(finished)return;finished=true;clearTimeout(timer);report.status=status;if(error)report.error=error;fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');w.terminate();process.exitCode=status==='PASS'?0:1;};
 const timer=setTimeout(()=>finish('FAIL','GP worker exceeded 20 seconds'),20000);
 w.on('message',m=>{if(m.message!==undefined){report.messages.push(m.message);if(/Undefined function|Stopped at|Error:|Syntax error|Operator must be|missing parentheses/i.test(m.message))finish('FAIL','GP compiler rejected the program');}if(m.result){report.result=m.result;const warnings=report.messages.filter(s=>/Skipping unknown op|Undefined function|Stopped at|Warning:|Error:|Syntax error|Operator must be|missing parentheses/i.test(s));
   const tooLarge=m.result.chunks.filter(c=>c.bytes.length>1000);report.warnings=warnings;report.oversized_chunks=tooLarge.map(c=>({name:c.name,bytes:c.bytes.length}));
   finish(warnings.length||tooLarge.length||!m.result.save_load_equal?'FAIL':'PASS');}});
 w.on('error',e=>finish('FAIL',e.name+': '+e.message));w.on('exit',code=>{if(!finished)finish('FAIL','GP worker exited before result: '+code);});
}else{
 const vm=require('node:vm'),{assets,input,checks}=workerData;let context;
 const gp=`to startup {
 p = (newMicroBlocksProject)
 s = (new 'MicroBlocksScripter')
 setField s 'mbProject' p
 setField s 'embeddedLibraries' (dictionary)
 r = (smallRuntime s)
 loadFromString p (readFile '/fixture.ubp') false
 assignFunctionIDs r
 result = (dictionary)
 atPut result 'metadata_catalog' 'empty; conservative library metadata retained'
 atPut result 'globals' (allVariableNames p)
 atPut result 'save_load_equal' (saveLoadTest p)
 atPut result 'unused_globals' (unusedGlobals p)
 nativeSpecs = (list)
 for item (microBlocksSpecs (initialize (new 'SmallCompiler'))) {
  if (isClass item 'Array') {
   if (beginsWith (at item 2) 'sfc') { add nativeSpecs item }
  }
 }
 atPut result 'native_specs' nativeSpecs
 ${checks?"atPut result 'headless_checks' (sfcHeadlessChecks p r)":''}
 chunks = (list)
 for f (allFunctions p) {
  entry = (dictionary)
  atPut entry 'name' (functionName f)
  atPut entry 'id' (lookupChunkID r (functionName f))
  atPut entry 'kind' 3
  atPut entry 'bytes' (compiledBytesFor r f)
  add chunks entry
 }
 index = 128
 for script (scripts (main p)) {
  entry = (dictionary)
  body = (last script)
  atPut entry 'name' (join 'script-' index)
  atPut entry 'id' index
  block = (new 'Block')
  setField block 'expression' body
  atPut entry 'kind' (chunkTypeFor r block)
  atPut entry 'op' (primName body)
  atPut entry 'bytes' (compiledBytesFor r body)
  add chunks entry
  index += 1
 }
 atPut result 'worker_plans' (sfcPlansForReport r)
 atPut result 'chunks' chunks
 atPut result 'variables' (getField p 'varIndices')
 atPut result 'canonical_source' (codeString p)
 print 'SFC_COMPILED_JSON' (jsonStringify result)
}
`;
 const config={noInitialRun:true,preRun:[],locateFile:n=>path.join(assets,n),wasmBinary:fs.readFileSync(path.join(assets,'gp_wasm.wasm')),
  print:s=>{const line=String(s);if(line.startsWith('SFC_COMPILED_JSON '))parentPort.postMessage({result:JSON.parse(line.slice(18))});else parentPort.postMessage({message:line});},
  printErr:s=>parentPort.postMessage({message:'STDERR: '+s}),
  onRuntimeInitialized(){context.NODEFS=context.MEMFS;context.FS.writeFile('/runtime/startup.gp',checks+'\n'+gp);context.FS.writeFile('/fixture.ubp',fs.readFileSync(input));context.callMain([]);}};
 const nodeProcess={versions:process.versions,argv:['node','gp_wasm.js'],on:()=>{},env:{},cwd:()=>assets,exitCode:0,
  stdout:{write:s=>parentPort.postMessage({message:String(s)})},stderr:{write:s=>parentPort.postMessage({message:'STDERR: '+s})}};
 context=vm.createContext({Module:config,require,process:nodeProcess,console:{log:s=>parentPort.postMessage({message:String(s)}),error:s=>parentPort.postMessage({message:'STDERR: '+s})},Buffer,TextEncoder,TextDecoder,Uint8Array,ArrayBuffer,WebAssembly,
  setTimeout,clearTimeout,setInterval,clearInterval,performance,__dirname:assets,__filename:path.join(assets,'gp_wasm.js'),module:{exports:{}},GP:{},GetText:{ready:Promise.resolve()}});
 vm.runInContext(fs.readFileSync(path.join(assets,'gp_wasm.js'),'utf8'),context,{filename:'pinned_gp_wasm.js'});
}
