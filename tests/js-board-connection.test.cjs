// SPDX-License-Identifier: MPL-2.0
// Actual pinned connection classes; the USB device is a protocol fixture.
'use strict';
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {load}=require('./support/js_editor_headless.cjs');
const delay=()=>new Promise(resolve=>setTimeout(resolve,1));
async function until(check){const end=Date.now()+2500;while(!check()){if(Date.now()>end)throw Error('Fixture timed out');await delay();}}
function device(version){
 const queued=[],waiters=[],messages=[];let incoming=[],closed=0,opened=0;
 function deliver(bytes){if(waiters.length)waiters.shift()({value:new Uint8Array(bytes),done:false});else queued.push(bytes);}
 const reader={read(){if(queued.length)return Promise.resolve({value:new Uint8Array(queued.shift()),done:false});return new Promise(resolve=>waiters.push(resolve));},async cancel(){for(const resolve of waiters.splice(0))resolve({done:true});},releaseLock(){}};
 const writer={async write(bytes){
  incoming.push(...bytes);
  while(incoming.length>=3){
   const size=incoming[0]===250?3:incoming.length>=5?5+incoming[3]+256*incoming[4]:Infinity;
   if(incoming.length<size)break;const frame=incoming.splice(0,size);messages.push(frame);
   if(frame[1]===26)deliver([250,26,frame[2]]);
   if(frame[1]===12){const body=[2,...Buffer.from(version)],reply=[251,22,0,body.length&255,body.length>>8,...body];
    // Fragment both length and body, as on the native serial stream.
    deliver(reply.slice(0,4));deliver(reply.slice(4,9));deliver(reply.slice(9));}
  }
 },async abort(){},releaseLock(){}};
 const port={async open(){opened++;},async setSignals(){},async close(){closed++;},readable:{getReader:()=>reader},writable:{getWriter:()=>writer}};
 return {port,messages,get closed(){return closed;},get opened(){return opened;}};
}
async function main(){const root=process.argv[2],results=[];
 for(const id of process.argv.slice(3)){
  const assets=path.join(root,id),config=JSON.parse(fs.readFileSync(path.join(assets,'target-profile.json')));
  const version=`v${config.vm_versions[0]||417} ${config.board_type_prefix} Zephyr (fixture)`;
  const d=device(version);let requests=0;const h=load(assets,{serial:{async requestPort(){requests++;return d.port;}}});
  h.evaluate('globalThis.downloads=0;MB_editor.justConnected=async()=>{downloads++;};');
  if(config.placeholder){await assert.rejects(h.evaluate('MB_connection.connect("serial")'),/offline editing/);assert.equal(requests,0);results.push({id,provider_opened:false});continue;}
  await h.evaluate('MB_connection.connect("serial")');await until(()=>h.evaluate('MB_connection.isConnected()'));
  assert.equal(await h.evaluate('MB_connection.sendMsg("chunkCode16Msg",0,[2,3])'),false);
  assert.equal(d.messages.filter(msg=>msg[1]===32).length,0);
  await h.evaluate('MB_connection.justConnected()');await h.evaluate('MB_connection.sendQueue');
  assert.equal(h.evaluate('downloads'),1,id);assert.equal(h.evaluate('MB_connection.vmVersion'),config.vm_versions[0],id);
  assert.equal(h.evaluate('MB_connection.boardType'),version.split(' ').slice(1).join(' '));
  const identity=d.messages.findIndex(msg=>msg[1]===12),stop=d.messages.findIndex(msg=>msg[1]===6);
  assert(identity>=0&&stop>identity,id);assert.equal(requests,1);
  h.evaluate('MB_connection.disconnect()');await until(()=>d.closed===1);
  assert.equal(h.evaluate('MB_connection.recvBuf.length'),0);
  results.push({id,version:config.vm_versions[0],fragmented_identity:true,identity_before_stop:true,physical_hardware:false});
 }
 // A wrong target response must fail before the real editor's upload hook.
 const d=device('v417 Waveshare ESP32-P4 WIFI6 Zephyr'),h=load(path.join(root,'fruit-jam'),{serial:{async requestPort(){return d.port;}}});
 h.evaluate('globalThis.downloads=0;MB_editor.justConnected=async()=>{downloads++;};');await h.evaluate('MB_connection.connect("serial")');await until(()=>h.evaluate('MB_connection.isConnected()'));
 await h.evaluate('MB_connection.justConnected()');await until(()=>d.closed===1);
 assert.equal(h.evaluate('downloads'),0);assert(!d.messages.some(msg=>[6,32].includes(msg[1])));
 console.log(JSON.stringify({actual_pinned_connection:true,physical_hardware:false,profiles:results,wrong_identity_blocked:true}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
