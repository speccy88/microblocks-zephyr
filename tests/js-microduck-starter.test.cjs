// SPDX-License-Identifier: MPL-2.0
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{load}=require('./support/js_editor_headless.cjs');
async function main(){
 const assets=process.argv[2],h=load(assets),meta=JSON.parse(fs.readFileSync(path.join(assets,'microduck-starter-libraries.json')));
 h.set('starterPath',meta.bundle);await h.evaluate('MB_Files.initialize();MB_editor.openLibraryFile(starterPath)');
 assert.equal(h.evaluate('MB_editor.project.libraries.size'),10);
 h.evaluate('MB_editor.codeManager.assignFunctionIDs();globalThis.compiler=new MB_Compiler(MB_editor.project,MB_editor.codeManager);');
 const functions=h.evaluate('MB_editor.project.allFunctions().map(f=>({name:f.functionName,id:MB_editor.codeManager.functionChunkIDs.get(f.functionName),bytes:compiler.compiledBytesFor(f)}))');
 assert.equal(new Set(functions.map(f=>f.id)).size,functions.length);assert(functions.every(f=>f.id<240&&f.bytes.length>0&&f.bytes.length<=1000));
 for(const name of ['microduckEasyRange','microduckDepthCapture','microduckSimMotionRun','microduckEasySimForward','microduckSimHead','microduckEasySimStop'])assert(functions.some(f=>f.name===name),name);
 for(const selector of ['microduckEasySimForward','microduckEasySimTurnLeft','microduckEasySimStop','microduckEasySimChirp','microduckEasySimSkill']){
  h.set('sel',selector);assert.equal(h.evaluate('MB_Specs.specArrayForSelector(sel,true,0).at(-1)'),false,selector+' confirmation default');
 }
 const probes={
  unavailableBattery:'microduckEasyStatus (microduckEasyBattery)',unavailableRange:'microduckEasyStatus (microduckEasyRange 4 4)',
  unavailableButton:'microduckEasyStatus (microduckEasyButton 1)',unavailableHead:'microduckEasyStatus (microduckEasyHeadTemperature)',
  invalidRange:'microduckEasyStatus (microduckEasyRange 0 9)',invalidButton:'microduckEasyStatus (microduckEasyButton 257)',
  batteryStatus:'microduckEasyStatus (microduckEasyBattery)',batteryValue:'microduckEasyValue (microduckEasyBattery)',batteryUnit:'microduckEasyUnit (microduckEasyBattery)',
  rangeValue:'microduckEasyValue (microduckEasyRange 1 1)',rangeNoTarget:'microduckEasyStatus (microduckEasyRange 1 2)',
  headValue:'microduckEasyValue (microduckEasyHeadTemperature)',buttonValue:'microduckEasyValue (microduckEasyButton 1)',
  advancedBattery:`local 's' (microduckRobotHealthCapture)\nlocal 'r' (microduckRobotBatteryPercent s)\nmicroduckRobotStateRelease s\nreturn (microduckReadingStatus r)`,
  falseForward:'microduckEasySimForward 100 500 false',forward:'microduckEasySimForward 100 500 true',turn:'microduckEasySimTurnLeft 250 500 true',
  cancel:'microduckEasySimCancel',advancedStatus:'microduckSimMotionStatus',badSpeed:'microduckEasySimForward 301 500 true',
  falseStop:'microduckEasySimStop false',stop:'microduckEasySimStop true',chirp:'microduckEasySimChirp true',skill:'microduckEasySimSkill \'simulation_bow\' true',
  advancedStop:'microduckSimStop true',badSkill:'microduckEasySimSkill \'not_advertised\' true'
 };
 const compiled={};for(const [name,source] of Object.entries(probes)){
  h.set('probe',source);h.set('reporter',name!=='advancedBattery');compiled[name]=h.evaluate('(()=>{const nodes=MB_Parser.parse(probe);return compiler.compiledBytesFor(MB_Parser.blockFor(reporter?nodes[0]:nodes,reporter));})()');
 }
 h.evaluate(`MB_editor.project.main.scripts=[
  [20,20,MB_Parser.blockFor(MB_Parser.parse('microduckEasySimForward 100 500 false')[0],true)],
  [20,120,MB_Parser.blockFor(MB_Parser.parse('microduckSimMotionRun 0 0 0 500 false')[0],true)],
  [20,220,MB_Parser.blockFor(MB_Parser.parse('microduckEasyKnown (microduckEasyBattery)')[0],true)]];
  globalThis.saved=MB_editor.project.codeString();globalThis.reopened=new MB_Project();reopened.loadFromString(saved);`);
 assert.equal(h.evaluate('reopened.allFunctions().length'),functions.length);assert.equal(h.evaluate('reopened.codeString()===saved'),true);
 assert.equal(h.evaluate('reopened.main.scripts.length'),3);
 console.log(JSON.stringify({modules:10,functions,probes:compiled,roundtrip:true,physical_hardware:false}));
}
main().catch(e=>{console.error(e);process.exitCode=1;});
