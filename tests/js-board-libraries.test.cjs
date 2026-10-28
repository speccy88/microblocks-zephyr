// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
const {load}=require('./support/js_editor_headless.cjs');
const root=process.argv[2],ids=process.argv.slice(3),sha=bytes=>crypto.createHash('sha256').update(bytes).digest('hex');
async function main(){const results=[];
 for(const id of ids){
  const assets=path.join(root,id),meta=JSON.parse(fs.readFileSync(path.join(assets,'target-libraries.json'))),config=JSON.parse(fs.readFileSync(path.join(assets,'target-profile.json'))),bundle=fs.readFileSync(path.join(assets,meta.bundle));
  for(const entry of meta.sources){const raw=fs.readFileSync(path.join(assets,entry.packaged_source));assert.equal(sha(raw),entry.sha256);assert.deepEqual(bundle.subarray(entry.bundle_offset,entry.bundle_offset+entry.bytes),raw);}
  const diagnostics=[],capture={...console,log(...args){diagnostics.push(args.map(String).join(' '));},warn(...args){diagnostics.push(args.map(String).join(' '));}};
  const h=load(assets,{console:capture});h.set('bundlePath',meta.bundle);await h.evaluate('MB_Files.initialize()');await h.evaluate('MB_editor.openLibraryFile(bundlePath)');
  assert.equal(h.evaluate('MB_connection.port'),null);
  for(const [set,index] of Object.entries(config.primitive_sets)){h.set('setName',set);assert.equal(h.evaluate('new MB_Compiler(MB_editor.project).primsets.get(setName)'),index);assert.equal(h.evaluate('MB_PRIMSET_TABLE.has(setName)'),false);}
  assert.throws(()=>h.evaluate('MicroBlocksLinux.install(MB_Compiler,MB_CommPort,location,WebSocket,{other:3},[])'),/Cannot change installed target compiler/);
  const functions=h.evaluate(`(()=>{MB_editor.codeManager.assignFunctionIDs();const c=new MB_Compiler(MB_editor.project,MB_editor.codeManager);return MB_editor.project.allFunctions().map(f=>({name:f.functionName,id:MB_editor.codeManager.functionChunkIDs.get(f.functionName),size:c.compiledBytesFor(f).length,ops:c.instructionsFor(f).filter(Array.isArray).map(i=>({name:i[0],opcode:c.opcodes.get(i[0])}))}));})()`);
  assert.deepEqual([...config.function_names].sort(),Array.from(functions,f=>f.name).sort(),id+' function dependency inventory');
  assert.equal(new Set(functions.map(f=>f.id)).size,functions.length);assert(functions.every(f=>f.id<250&&f.size>0&&f.size<=1000),JSON.stringify({id,functions}));
  const native=h.evaluate(`(()=>{const c=new MB_Compiler(MB_editor.project,MB_editor.codeManager),out=[];for(const selector of MB_editor.project.blockSpecs.keys()){
   if(!/^\\[[^:]+:[^\\]]+\\]$/.test(selector))continue;
   const spec=MB_Specs.specArrayForSelector(selector,true,0),b=MB_Specs.blockForSpec(spec,'Output');
   const instructions=c.instructionsFor(b),bytes=c.compiledBytesFor(b),calls=instructions.filter(i=>Array.isArray(i)&&['commandPrimitive','reporterPrimitive'].includes(i[0]));
   out.push({selector,size:bytes.length,calls:calls.map(i=>({set:i[2],encodedSet:(i[1]>>>18)&63,args:i[3]})),inputs:b.inputs().length});
  }return out;})()`);
  // XRP's public palette calls ordinary functions; its native calls live in
  // their bodies. A native-only count would miss that valid library shape.
  assert(functions.length+native.length>0,id);
  assert.deepEqual(diagnostics.filter(s=>/Skipping unknown op|Unknown expression type/.test(s)),[],id);
  if(id==='propeller2'){
   // Check used instructions against the preserved v405 native dispatch,
   // independently of the JS compiler's own opcode table.
   const source=fs.readFileSync(path.join(__dirname,'../boards/propeller2/native/vm/interp.c'),'utf8');
   const dispatch=new Map(Array.from(source.matchAll(/case (\d+): goto ([A-Za-z0-9_]+)_op;/g),m=>[Number(m[1]),m[2]]));
   assert(dispatch.size>90);
   for(const f of functions)for(const op of f.ops){
    if(['placeholder','metadata','padding'].includes(op.name))continue;
    assert.equal(dispatch.get(op.opcode),op.name,JSON.stringify({function:f.name,op}));
   }
  }
  for(const item of native){const set=item.selector.slice(1,item.selector.indexOf(':'));const expected=config.primitive_sets[set]??h.evaluate(`MB_PRIMSET_TABLE.get(${JSON.stringify(set)})`);assert(item.calls.some(call=>call.set===set&&call.encodedSet===expected&&call.args===item.inputs),JSON.stringify({id,item,expected}));assert(item.size>0&&item.size<=1000);}
  const saved=h.evaluate('MB_editor.project.codeString()'),fresh=load(assets);fresh.set('savedProject',saved);fresh.evaluate('MB_editor.project=new MB_Project();MB_editor.project.loadFromString(savedProject);');assert.equal(fresh.evaluate('MB_editor.project.codeString()'),saved,id);
  assert.equal(fresh.evaluate('MB_editor.project.allFunctions().length'),functions.length,id);
  if(id==='unoq'){
   const selectors=['unoqShowImage','[unoq:matrixPattern]'];for(const selector of selectors){fresh.set('selector',selector);assert.equal(fresh.evaluate("MB_Specs.blockForSpec(MB_Specs.specArrayForSelector(selector,false,1),'Output').inputs()[0].evaluate().length"),104);}
  }
  if(functions.length){
   const missing=load(assets);missing.set('functionName',functions[0].name);
   missing.set('missingSource',`module 'Missing' Output\nspec 'r' '${functions[0].name}' 'missing dependency'\n`);
   missing.evaluate('MB_editor.project.addLibraryFromString(missingSource,"Missing",null);');
   assert.throws(()=>missing.evaluate('new MB_Compiler(MB_editor.project).compiledBytesFor(MB_Specs.blockForSpec(MB_Specs.specArrayForSelector(functionName,true,0),"Output"))'),/Missing target function dependency/);
  }
  results.push({id,modules:h.evaluate('MB_editor.project.libraries.size'),functions:functions.length,native_specs:native.length,max_function_bytes:Math.max(0,...functions.map(f=>f.size)),project_sha256:sha(Buffer.from(saved))});
 }
 console.log(JSON.stringify({profiles:results.length,actual_pinned_compiler:true,source_copies_exact:true,roundtrip:true,hardware:false,results}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
