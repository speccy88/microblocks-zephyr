// SPDX-License-Identifier: MIT
// Load optional libraries through the real pinned editor's ordinary library API.
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {load}=require('./support/js_preview_headless.cjs');
const {compile}=require('../tools/compile_propeller2_project.cjs');
const {fixture}=require('./support/gp_sensor_fixture.cjs');
async function main(){
 const folder=path.join(process.argv[2],'js-preview/propeller2');
 const source=path.join(__dirname,'../boards/propeller2/integration');
 const results=[];
 const parser=load(folder,{readback:false});
 parser.set('sensorSource',fs.readFileSync(path.join(__dirname,'../libraries/sensors/BME680.ubl'),'utf8'));
 const trees=JSON.parse(JSON.stringify(parser.evaluate('MB_Parser.parse(sensorSource)')));
 const registers={0:0x80,2:0x20,4:0xf0,0xe1:0x12,0xe2:0xab,0xe3:0x34,0xe4:0x80,0x89:0x80,0x8a:0,0x8b:0x80};
 const sensor=fixture(trees,{registers,globals:{_bme680:119}});
 assert.equal(sensor.call('_bm680 read int8',0),-128);
 assert.equal(sensor.call('_bme680 read int',1),-32768);
 sensor.call('_bm680 read humidity coefficients');
 assert.equal(sensor.globals._bme680_h[0],0x34b);
 assert.equal(sensor.globals._bme680_h[1],0x12a);
 sensor.call('_read gas coefficients');
 assert.equal(sensor.globals._bme680_g.length,6);
 assert.deepEqual(sensor.globals._bme680_g.slice(3),[2,-128,-1]);
 let gasRange;
 sensor.globals._bme680_raw=Array(15).fill(0);sensor.globals._bme680_raw[13]=128;sensor.globals._bme680_raw[14]=15;
 const gas=fixture(trees,{registers:{0x71:1},globals:sensor.globals,hooks:{'_bme680 read raw':()=>{},'[misc:bme680GasResistance]':(adc,range)=>{gasRange=range;return 244;}}});
 gas.call('bme680 gas');assert.equal(gasRange,15);
 for(const name of fs.readdirSync(path.join(source,'libraries')).filter(n=>n.endsWith('.ubl'))){
  const warnings=[];
  const capture=(...parts)=>{const line=parts.join(' ');if(/Skipping unknown op|error|warning/i.test(line))warnings.push(line);};
  const h=load(folder,{readback:false,console:{...console,log:capture,warn:capture,error:capture},Socket:class{constructor(){throw Error('Network forbidden');}}});
  h.set('optional','Libraries/P2/'+name);
  await h.evaluate('MB_Files.initialize().then(()=>MB_editor.openLibraryFile(optional))');
  h.evaluate('MB_editor.codeManager.assignFunctionIDs()');
  const functions=h.evaluate('MB_editor.project.allFunctions().map(f=>({name:f.functionName,bytes:MB_editor.codeManager.compiledBytesFor(f).length}))');
  assert(functions.length>0,name);assert(functions.every(f=>f.bytes>0&&f.bytes<1000),name);
  assert.equal(warnings.length,0,warnings.join('\n'));
  results.push({library:name,functions:functions.length});
 }
 const combined=load(folder,{readback:false,Socket:class{constructor(){throw Error('Network forbidden');}}});
 await combined.evaluate('MB_Files.initialize().then(()=>MB_editor.openLibraryFile("Libraries/Targets/Propeller 2 Project.ubl"))');
 for(const name of fs.readdirSync(path.join(source,'libraries')).filter(n=>n.endsWith('.ubl'))){
  combined.set('optional','Libraries/P2/'+name);
  await combined.evaluate('MB_editor.openLibraryFile(optional)');
 }
 const libraries=combined.evaluate('Array.from(MB_editor.project.libraries.values(),lib=>lib.codeString(MB_editor.project)).join("\\n")');
 for(const name of fs.readdirSync(path.join(source,'examples')).filter(n=>n.endsWith('.ubp'))){
  const p=compile(folder,fs.readFileSync(path.join(source,'examples',name),'utf8')+'\n'+libraries);
  assert(p.scripts.length>0,name);
  assert(!p.chunks.some(c=>c.kind>=4),name+' must not automatically start');
 }
 console.log(JSON.stringify({optional:results,examples_compiled:true,network:false,physical:false}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
