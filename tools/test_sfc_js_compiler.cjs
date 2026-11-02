// SPDX-License-Identifier: MPL-2.0
'use strict';
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {open,compile}=require('./sfc_js_compile.cjs');
const assets=process.argv[2],output=process.argv[3];
if(fs.existsSync(output))throw Error('Choose a fresh compiler evidence directory');
fs.mkdirSync(output,{recursive:true});
const fixtures=path.join(__dirname,'../tests/fixtures/sfc_native');
const records=[];
for(const name of fs.readdirSync(fixtures).filter(n=>n.endsWith('.ubp')).sort()){
    let report;try{report={status:'PASS',compiler:'genuine pinned JavaScript',result:compile(assets,fs.readFileSync(path.join(fixtures,name),'utf8'))};}
    catch(error){report={status:'FAIL',error:String(error.stack||error)};}
    const expected=name.startsWith('invalid-')?'FAIL':'PASS';
    fs.writeFileSync(path.join(output,name.replace('.ubp','.json')),JSON.stringify(report,null,2)+'\n');
    assert.equal(report.status,expected,name+': '+report.error);
    records.push({case:name,expected,actual:report.status});
}
const source=fs.readFileSync(path.join(fixtures,'and-2.ubp'),'utf8'),h=open(assets,source);
let checks=0;
function check(name,code,expected=true){assert.equal(h.evaluate(code),expected,name);checks++;}
check('all seven native Control specs', 'MicroBlocksSFC.specs.every(s=>MB_Specs.categoryForSelector(s[1])==="Control")');
check('step has real variable menu and two command slots', '(()=>{let b=MB_Specs.blockForSpec(MicroBlocksSFC.specs[1],"Control");return b.inputs().length===3&&b.inputs()[1] instanceof CommandSlotMorph&&b.inputs()[2] instanceof CommandSlotMorph})()');
check('shared-variable name dispatch reaches the native slot menu','(()=>{let b=MB_editor.project.allScripts()[0].allBlocks().find(b=>b.selector==="sfcStep");let m=b.inputs()[0].mbMenu(b.inputs()[0].choices);return !!m&&m.items.some(i=>i[0]==="Choice1")})()');
check('six AND slots and a hard UI limit', '(()=>{let b=MB_Specs.blockForSpec(MicroBlocksSFC.specs[3],"Control");b.isTemplate=false;for(let i=0;i<8;i++)b.expand();return b.inputs().length===6&&!b.canExpand()})()');
check('six OR choices with six command slots', '(()=>{let b=MB_Specs.blockForSpec(MicroBlocksSFC.specs[5],"Control");b.isTemplate=false;for(let i=0;i<8;i++)b.expand();return b.inputs().length===12&&b.inputs().filter(s=>s instanceof CommandSlotMorph).length===6&&!b.canExpand()})()');
check('generated workers remain reachable to uploader','MB_editor.project.unusedFunctions().length===0');
check('preparing without edits reuses function objects','(()=>{let f=MB_editor.project.allFunctions()[0];MicroBlocksSFC.prepare(MB_editor.project);return f===MB_editor.project.allFunctions()[0]})()');
check('stable repeated bytes and source','(()=>{let m=MB_editor.codeManager,p=MB_editor.project;let a=JSON.stringify(p.allScripts().map(b=>m.compiledBytesFor(b))),s=p.codeString();return a===JSON.stringify(p.allScripts().map(b=>m.compiledBytesFor(b)))&&s===p.codeString()})()');
check('retained compiler follows rebuilt project after undo/locale','(()=>{let m=MB_editor.codeManager,s=MB_editor.project.codeString();MB_editor.project=new MB_Project();MB_editor.project.loadFromString(s);m.project=MB_editor.project;MicroBlocksSFC.preflight(m);return m.compiler.project===m.project&&m.project.codeString()===s})()');
check('edited worker action is marked for uploader source/CRC comparison','(()=>{let p=MB_editor.project,m=MB_editor.codeManager;let entry=m.chunkIDs.get("_sfc1_worker3");entry[4]=false;let step=p.allScripts()[0].allBlocks().find(b=>b.selector==="sfcStep"&&b.inputs()[0].evaluate()==="B2");step.inputs()[2].nestedBlock().inputs()[1].setContents(2);m.assignFunctionIDs();return entry[4]===true&&p.functionNamed("_sfc1_worker3").codeString().includes("B2Loop += 2")})()');
// Oversized real user action must fail before saveAllChunksNow can issue even
// variable-name writes. Exercise the actual asynchronous uploader entry point.
async function finish(){
    const huge=source.replace('B2Loop += 1',Array(400).fill('B2Loop += 1').join('\n'));
    const over=open(assets,huge);over.evaluate('globalThis.writes=0;MB_connection.connectedToBoard=()=>true;MB_connection.vmTooOld=()=>false;MB_connection.sendMsg=()=>{writes++};MB_connection.sendMsgSync=async()=>{writes++};');
    await assert.rejects(over.evaluate('MB_editor.codeManager.saveAllChunksNow()'),/1000-byte/);
    assert.equal(over.evaluate('writes'),0);checks++;
    assert.throws(()=>over.evaluate('MB_editor.codeManager.runChunk(0)'),/1000-byte/);
    assert.equal(over.evaluate('writes'),0);checks++;
    over.evaluate('globalThis.shownErrors=[];MB_editor.showError=(block,text)=>shownErrors.push(text)');
    await over.evaluate('MB_editor.codeManager.evalOnBoard(MB_editor.project.allScripts()[0])');
    assert.equal(over.evaluate('writes'),0);assert.match(over.evaluate('shownErrors[0]'),/1000-byte/);checks++;
    const collision=open(assets,source);collision.evaluate('MB_editor.project.libraries.get("_SFC workers").variableNames.push("UserData")');
    assert.throws(()=>collision.evaluate('MicroBlocksSFC.prepare(MB_editor.project)'),/unexpected user code/);checks++;
    assert.throws(()=>open(assets,source.replace("sfcStep 'B2' { B2Entry += 1 }", "sfcStep 'B2' 123")),/sections must contain commands/);checks++;
    const summary={status:'PASS',compiler:'genuine pinned JavaScript parser/Morphs/compiler',fixtures:records,additional_checks:checks,
        graphical:false,real_VM:false,physical_hardware:false,upstream_modified:false};
    fs.writeFileSync(path.join(output,'summary.json'),JSON.stringify(summary,null,2)+'\n');
    console.log(JSON.stringify({status:'PASS',fixtures:records.length,additional_checks:checks}));
}
finish().catch(e=>{console.error(e);process.exitCode=1;});
