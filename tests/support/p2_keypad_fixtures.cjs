// SPDX-License-Identifier: MIT
const assert=require('node:assert/strict');
const {fixture}=require('./gp_sensor_fixture.cjs');
module.exports=function(trees){
 let now=1000,mask=0,revision=8;
 const f=fixture(trees,{hooks:{millisOp:()=>now,millisSince:start=>now-start,
  '[p2:p2KeypadInit]':()=>true,'[p2:p2KeypadScan]':()=>mask,'[p2:p2RuntimeRevision]':()=>revision}});
 assert.equal(f.call('p2PeripheralFirmware'),false);revision=9;assert.equal(f.call('p2PeripheralFirmware'),true);
 assert.equal(f.call('p2KeypadInit',[8,9,10,11],[12,13,14,15]),true);
 mask=32;assert.equal(f.call('p2KeypadKey'),'');now+=29;assert.equal(f.call('p2KeypadKey'),'');
 now++;assert.equal(f.call('p2KeypadKey'),'5');
 mask=-1;assert.equal(f.call('p2KeypadKey'),'');now+=30;assert.equal(f.call('p2KeypadKey'),'?');
 mask=0;assert.equal(f.call('p2KeypadKey'),'');now+=30;assert.equal(f.call('p2KeypadKey'),'');
 return {debounce_30ms:true,key_labels:true,ghost_status:true};
};
