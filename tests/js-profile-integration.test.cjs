// SPDX-License-Identifier: MPL-2.0
const assert=require('node:assert/strict');
const {load}=require('./support/js_editor_headless.cjs');
const [pi,duck]=process.argv.slice(2);
let sockets=0;
class Socket {constructor(){sockets++;this.readyState=0;}close(){this.readyState=3;if(this.onclose)this.onclose();}}
const h=load(pi,{Socket});
const bytes=h.evaluate(`(()=>{const p=new MB_Project();const m=new MB_CodeManager(p);MB_editor.project=p;MB_editor.codeManager=m;return new MB_Compiler(p,m).compiledBytesFor(MB_Parser.blockFor(MB_Parser.parse('20 + 22')[0],true));})()`);
assert(bytes.length>4);
h.evaluate(`(()=>{const p=new MB_CommPort();p.connect('linux-loopback');p.disconnect();})()`);assert.equal(sockets,1);
const hosted=load(pi,{Socket,location:{href:'https://example.com/js-preview/raspberry-pi5/'}});
assert.throws(()=>hosted.evaluate(`new MB_CommPort().connect('linux-loopback')`),/WSS is not commissioned/);assert.equal(sockets,1);
const placeholder=load(duck,{Socket});
for(const type of ['serial','BLE','boardie','linux-loopback'])assert.throws(()=>placeholder.evaluate(`new MB_CommPort().connect(${JSON.stringify(type)})`),/offline editing only/);
assert.equal(sockets,1);
console.log(JSON.stringify({passed:3,actual_pinned_comm_port:true,actual_compiler:true,compiled_arithmetic_bytes:bytes.length,physical_hardware:false}));
