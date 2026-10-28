// SPDX-License-Identifier: MIT
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const api=require('../web/microduck/camera-rgb.js');
const geo=(width=8,height=4,rotate=0)=>({width,height,rotate,format:'UYVY',bytes:width*height*2});
function card(w=8,h=4){const data=new Uint8Array(w*h*2);for(let i=0;i<data.length;i+=4)data.set([128,16,128,16],i);data[1]=235;return data;}
function canvas(){const c={width:0,height:0,puts:[],buffers:[]};c.getContext=()=>({createImageData(w,h){const p={data:new Uint8ClampedArray(w*h*4)};c.buffers.push(p.data);return p;},putImageData(p){c.puts.push([...p.data]);}});return c;}
test('known BT601 colors and clipping are exact',()=>{
 for(const [v,want] of [[[16,128,128],[0,0,0]],[[235,128,128],[255,255,255]],[[81,90,240],[255,0,0]],[[41,240,110],[0,0,255]],[[0,10,20],[0,115,0]]])assert.deepEqual(api.rgb(...v),want);
 for(const n of [-1,256,NaN,Infinity,1.5,true])assert.throws(()=>api.rgb(n,128,128));
});
test('all quarter turns map the marked corner without inventing calibration',()=>{
 for(const [rotate,width,height,x,y] of [[0,8,4,0,0],[90,4,8,3,0],[180,8,4,7,3],[270,4,8,0,7]]){
  const p=api.convert(geo(8,4,rotate),card(),{applyRotation:true});assert.equal(p.width,width);assert.equal(p.height,height);
  assert.deepEqual([...p.rgba.slice((y*width+x)*4,(y*width+x)*4+4)],[255,255,255,255]);
  assert.equal(p.calibrationVerified,false);assert.equal(p.appliedRotation,rotate);
 }
 const stored=api.convert(geo(8,4,90),card());assert.equal(stored.width,8);assert.equal(stored.appliedRotation,0);
});
test('nearest sample sizing is bounded, downscale-only and aspect-preserving',()=>{
 assert.deepEqual(Object.values(api.convert(geo(),card(),{longest:4})).slice(0,2),[4,2]);
 const tiny=api.convert(geo(2,1),card(2,1),{longest:160});assert.equal(tiny.rgba.length,8);
 const tall=api.convert(geo(2,101),card(2,101),{longest:1});assert.equal(tall.width,1);assert.equal(tall.height,1);
 const full=api.convert(geo(2048,2048),card(2048,2048));assert.equal(full.rgba.byteLength,api.MAX_RGBA);assert.equal(full.width,160);assert.equal(full.height,160);
});
test('malformed, oversized, detached and shared input fails before output',()=>{
 const g=geo(),raw=card();
 for(const patch of [{width:3},{width:true},{height:0},{height:1e9},{bytes:63},{bytes:api.MAX_RAW+4},{rotate:45},{rotate:true},{format:'RGB'},{stride:16}])assert.throws(()=>api.convert({...g,...patch},raw));
 for(const bytes of [raw.subarray(0,63),new Uint8Array(65),[],new Uint8Array(new SharedArrayBuffer(64))])assert.throws(()=>api.convert(g,bytes));
 const detached=card();structuredClone(detached,{transfer:[detached.buffer]});assert.throws(()=>api.convert(g,detached));
 for(const options of [{longest:0},{longest:161},{longest:true},{longest:NaN},{applyRotation:1}])assert.throws(()=>api.convert(g,raw,options));
});
test('renderer clears on replacement/error and zeros temporary pixel arrays',()=>{
 const c=canvas(),v=new api.Preview(c);v.show(geo(),card());assert.equal(c.width,8);assert.equal(c.puts.length,1);assert(c.buffers[0].every(x=>x===0));
 assert.throws(()=>v.show(geo(),new Uint8Array(3)));assert.equal(c.width,0);assert.equal(c.height,0);
 v.show(geo(8,4,90),card(),{applyRotation:true});assert.equal(c.width,4);v.clear();assert.equal(c.width,0);
 v.close();v.close();assert.throws(()=>v.show(geo(),card()),/CLOSED/);
});
test('busy canvas and graphics failures preserve ownership and clear partial output',()=>{
 const occupied=canvas();occupied.width=12;assert.throws(()=>new api.Preview(occupied));assert.equal(occupied.width,12);
 const c=canvas(),v=new api.Preview(c);c.getContext=()=>null;assert.throws(()=>v.show(geo(),card()));assert.equal(c.width,0);
});
