// SPDX-License-Identifier: MPL-2.0
// Synthetic USB bytes only. Actual pinned connection/transport classes consume them.
'use strict';
const {load}=require('./js_editor_headless.cjs');
const tick=()=>new Promise(resolve=>setTimeout(resolve,0));
async function until(check){for(let n=0;n<2500;n++){if(check())return;await tick();}throw Error('Synthetic USB deadline');}
const long=(type,body,chunk=0)=>new Uint8Array([251,type,chunk,body.length&255,body.length>>8,...body]);
function device(){
 const queued=[],waiting=[],messages=[];let incoming=[],closed=false;
 const d={messages,onMessage:null,feed(bytes){const value=new Uint8Array(bytes);if(waiting.length)waiting.shift()({value,done:false});else queued.push(value);},get closed(){return closed;}};
 const reader={read(){return queued.length?Promise.resolve({value:queued.shift(),done:false}):new Promise(resolve=>waiting.push(resolve));},async cancel(){for(const fn of waiting.splice(0))fn({done:true});},releaseLock(){}};
 const writer={async write(bytes){incoming.push(...bytes);while(incoming.length>=3){const size=incoming[0]===250?3:incoming.length>=5?5+incoming[3]+256*incoming[4]:Infinity;if(incoming.length<size)break;const frame=new Uint8Array(incoming.splice(0,size));messages.push(frame);d.onMessage?.(frame);}},async abort(){},releaseLock(){}};
 d.port={async open(){},async setSignals(){},async close(){closed=true;},readable:{getReader:()=>reader},writable:{getWriter:()=>writer}};return d;
}
async function connect(assets){
 const devices=[],h=load(assets,{serial:{async requestPort(){const d=device();devices.push(d);return d.port;}}}),c=h.evaluate('MB_connection');
 h.evaluate('MB_editor.updateRunning=()=>{};');
 async function inject(frame){devices.at(-1).feed(frame);await tick();c.processMessages();}
 async function open(){await c.connect('serial');await until(()=>c.isConnected());await inject(long(22,[2,...Buffer.from('v417 Waveshare ESP32-P4 WIFI6 Zephyr')]));await c.sendQueue;}
 await open();return {h,c,devices,inject,open,async close(){c.disconnect();await until(()=>devices.at(-1).closed);}};
}
module.exports={connect,device,long,tick,until};
