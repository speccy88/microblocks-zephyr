// SPDX-License-Identifier: MIT
const assert=require('node:assert/strict');
const {fixture}=require('./gp_sensor_fixture.cjs');
module.exports=function(trees){
 let busy=0,polls=0,waits=0;const transfers=[];
 const f=fixture(trees,{hooks:{
  '[display:p2EPDSetup]':()=>true,'[display:p2EPDReset]':()=>true,
  '[display:p2EPDBusy]':()=>{polls++;return busy;},
  '[display:p2EPDTransfer]':(data,value)=>{transfers.push({data,value:typeof value==='number'?value:Array.from(value)});return true;},
  waitMillis:ms=>{waits+=ms;},
  '[misc:shapeforChar]':()=>new Uint8Array([1,1,1,1,1]),
  '[data:unicodeAt]':(index,text)=>Array.from(text)[index-1].codePointAt(0)
 }});
 assert.equal(f.call('p2EPDInit',8,9,10,11,12,13),true);
 assert.equal(f.globals._p2EPDFrame.length,4736);assert(f.globals._p2EPDFrame.every(x=>x===255));
 const lut=transfers.findIndex(t=>!t.data&&t.value===50);
 assert.equal(transfers[lut+1].value.length,30);assert.deepEqual(transfers[lut+1].value.slice(0,4),[2,2,1,17]);
 assert.equal(f.call('p2EPDPixel',0,0,true),true);assert.equal(f.globals._p2EPDFrame[0],127);
 assert.equal(f.call('p2EPDPixel',127,295,true),true);assert.equal(f.globals._p2EPDFrame.at(-1),254);
 assert.equal(f.call('p2EPDPixel',128,0,true),false);
 f.call('p2EPDClear',false);assert.equal(f.call('p2EPDLine',0,0,127,295,true),true);
 let black=0;for(const byte of f.globals._p2EPDFrame)for(let mask=1;mask<256;mask<<=1)if(!(byte&mask))black++;
 assert.equal(black,296);
 f.call('p2EPDClear',false);f.call('p2EPDText','A',0,0);
 assert.equal(f.globals._p2EPDFrame[0],7);assert.equal(f.globals._p2EPDFrame[16],255);
 transfers.length=0;assert.equal(f.call('p2EPDUpdate'),true);
 const pages=transfers.filter(t=>t.data&&Array.isArray(t.value)&&t.value.length===128);
 assert.equal(pages.length,37);assert.deepEqual(pages.flatMap(p=>p.value),Array.from(f.globals._p2EPDFrame));
 assert(transfers.some(t=>!t.data&&t.value===36));assert(transfers.some(t=>!t.data&&t.value===32));
 busy=1;polls=0;waits=0;assert.equal(f.call('_p2EPDWait'),false);assert.equal(polls,500);assert.equal(waits,5000);
 busy=-1;polls=0;assert.equal(f.call('_p2EPDWait'),false);assert.equal(polls,1);
 return {framebuffer:true,graphics:true,pages_128_bytes:37,busy_timeout:true,physical:false};
};
