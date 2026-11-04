// SPDX-License-Identifier: MIT
// Protocol and failure tests with synthetic bytes; never opens hardware.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const L=require('../web/p2-installer/loader.js');
const encoder=new TextEncoder(),decoder=new TextDecoder();
const identity=version=>{const data=encoder.encode(version),p=new Uint8Array(6+data.length);p.set([251,22,0,data.length+1,0,2]);p.set(data,6);return p;};
class Link{
 constructor(config={}){this.config=config;this.queue=[];this.running=config.running||null;this.opens=[];this.closes=0;this.signals=[];this.sent=[];this.clock=0;this.hex='';this.flash=false;}
 async open(baud){this.opens.push(baud);}
 async close(){this.closes++;}
 async clear(){this.queue=[];}
 async setSignals(value){this.signals.push(value);if(value.dataTerminalReady)this.running=this.flash&&!this.config.bootFails?'v405 Parallax P2 Edge 32MB':null;}
 async read(ms){if(this.queue.length)return this.queue.shift();this.clock+=ms;return new Uint8Array();}
 async write(bytes){
  this.sent.push(bytes);const s=decoder.decode(bytes);
  if(bytes[0]===250&&bytes[1]===12){if(this.running)this.queue.push(identity(this.running));return;}
  if(s.startsWith('> Prop_Chk')){if(!this.config.noROM)this.queue.push(encoder.encode('\r\nProp_Ver '+(this.config.rom||'G')+'\r\n'));return;}
  if(s.startsWith('> Prop_Hex')||s.startsWith('> Prop_Txt')){this.hex='';return;}
  this.hex+=s;
  if(s.endsWith('?')){this.queue.push(encoder.encode(this.config.badCRC?'!':'.'));if(!this.config.badCRC)this.running='v405 Parallax P2 Edge 32MB';}
  if(s==='~'){this.flash=true;this.running='v405 Parallax P2 Edge 32MB';}
 }
 options(extra={}){return {now:()=>this.clock,sleep:async ms=>{this.clock+=ms;},...extra};}
}
async function fixture(config={}){
 const image=Uint8Array.from({length:512},(_,i)=>i&255),stub=new Uint8Array(496),link=new Link(config);
 const manifest={vm_version:405,extension_revision:8,images:{edge32:{bytes:image.length,sha256:await L.sha256(image),board_type:L.boards.edge32}},flasher:{bytes:stub.length,sha256:await L.sha256(stub)}};
 return {image,stub,link,manifest,run:(mode,options={})=>L.install(link,image,stub,manifest,'edge32',mode,link.options(options))};
}
test('RAM: positive ROM, verified checksum and VM identity, no flash commit',async()=>{
 const f=await fixture(),r=await f.run('ram');assert.equal(r.rom_checksum_verified,true);assert.equal(r.flash_boot_verified,false);
 assert.deepEqual(f.link.opens,[115200]);assert.equal(f.link.closes,1);assert(!f.link.flash);
 const bytes=new Uint8Array(Buffer.from(f.link.hex.replace(/[>\s?]/g,''),'base64'));
 assert.equal(L.sumWords(bytes),0x706f7250);assert.equal(bytes.length,f.image.length+4);
});
test('flash uses a checksummed separate programmer, no ROM checksum word, then verifies boot',async()=>{
 const f=await fixture(),phases=[],r=await f.run('flash',{progress:e=>phases.push(e.phase)});
 assert(r.flash_boot_verified);assert.equal(f.link.closes,3);assert.deepEqual(f.link.opens,[115200,460800,115200]);
 const bytes=Uint8Array.from(f.link.hex.match(/\b[0-9a-f]{2}\b/g).map(x=>parseInt(x,16)));
 assert.equal(bytes.length,f.stub.length+f.image.length);assert.equal(L.sumWords(bytes),0);
 assert.equal(new DataView(bytes.buffer).getUint32(8,true),0);assert(phases.indexOf('programming')<phases.indexOf('boot'));
});
test('an already running P2 is retained without reset or image transfer',async()=>{
 const f=await fixture({running:'v405 Parallax P2 Edge 32MB'}),r=await f.run('flash');
 assert(r.already_running);assert.equal(f.link.signals.length,0);assert.equal(f.link.hex,'');assert.equal(f.link.closes,1);
});
test('other MicroBlocks hardware is refused before reset',async()=>{
 const f=await fixture({running:'v417 Other Board'});await assert.rejects(f.run('flash'),/different MicroBlocks/);
 assert.equal(f.link.signals.length,0);assert.equal(f.link.closes,1);
});
test('missing or unsupported ROM never receives image data',async()=>{
 for(const config of [{noROM:true},{rom:'B'}]){const f=await fixture(config);await assert.rejects(f.run('flash'),/P2 ROM/);assert.equal(f.link.hex,'');assert(!f.link.flash);assert.equal(f.link.closes,2);}
});
test('changed firmware and programmer hashes fail before opening hardware',async()=>{
 const f=await fixture();f.image[0]^=1;await assert.rejects(f.run('ram'),/hash or size/);assert.equal(f.link.opens.length,0);
 const g=await fixture();g.stub[0]^=1;await assert.rejects(g.run('flash'),/programmer hash/);assert.equal(g.link.opens.length,0);
});
test('RAM ROM checksum failure is not called success',async()=>{
 const f=await fixture({badCRC:true});await assert.rejects(f.run('ram'),/checksum/);assert.equal(f.link.closes,1);assert(!f.link.flash);
});
test('cancellation before execution closes the link and does not program flash',async()=>{
 const f=await fixture(),cancel=new AbortController();
 await assert.rejects(f.run('flash',{signal:cancel.signal,progress:e=>{if(e.phase==='transfer')cancel.abort();}}),/cancelled/);
 assert(!f.link.flash);assert.equal(f.link.closes,2);
});
test('a failed flash boot remains a failure after successful transfer',async()=>{
 const f=await fixture({bootFails:true});
 await assert.rejects(f.run('flash'),e=>/boot verification failed/.test(e.message)&&e.flash_programming_started===true);
 assert(f.link.flash);assert.equal(f.link.closes,3);
});
test('bad selection and unaligned image fail without a port open',async()=>{
 const f=await fixture();await assert.rejects(L.install(f.link,f.image,f.stub,f.manifest,'automatic','flash'),/exact P2 module/);
 assert.equal(f.link.opens.length,0);assert.throws(()=>L.sumWords(new Uint8Array(3)),/complete 32-bit/);
});
test('ROM identification waits for its complete fragmented reply',async()=>{
 const f=await fixture();const write=f.link.write.bind(f.link);let replyReads=0;
 f.link.write=async bytes=>{await write(bytes);if(decoder.decode(bytes).startsWith('> Prop_Chk'))f.link.queue=[encoder.encode('\r\nProp_Ver G'),encoder.encode('\r\n')];};
 const read=f.link.read.bind(f.link);f.link.read=async ms=>{replyReads++;return read(ms);};
 assert.equal(await L.identifyROM(f.link,f.link.options()),'G');assert.equal(replyReads,2);
});
test('all reviewed RAM images fit inside the ROM window without a baud reopen',()=>{
 const pin=require('../dependencies/p2-web-installer.json');
 for(const entry of Object.values(pin.expected_images)){
  const encoded=4*Math.ceil((entry.bytes+4)/3),wire=(encoded+Math.ceil(encoded/2048)*3)*10/115200;
  assert(wire<55,entry.board_type+' exceeds the reviewed transfer time budget');
 }
});
