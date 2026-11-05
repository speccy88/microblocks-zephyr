// SPDX-License-Identifier: MIT
const assert=require('node:assert/strict');
const {fixture}=require('./gp_sensor_fixture.cjs');
module.exports=function(trees){
 const writes=[],pointers={},ids={'24:15':51,'107:15':104,'30:15':61,'24:39':8,'107:23':3,'30:39':8};
 const frames={'24:40':[0x00,0x40,0x00,0xc0,0xf0,0x7f],
               '107:40':[0x00,0x40,0x00,0xc0,0xff,0x7f],
               '107:24':[100,0,156,255,0,0],
               '30:40':[100,0,156,255,0,0]};
 let shortRead=false;
 const f=fixture(trees,{hooks:{
  i2cGet:(address,reg)=>ids[address+':'+reg]??0,
  i2cSet:(address,reg,value)=>{writes.push([address,reg,value]);},
  '[sensors:i2cWrite]':(address,reg)=>{pointers[address]=reg&127;return 1;},
  '[sensors:i2cRead]':(address,bytes)=>{bytes.set(frames[address+':'+pointers[address]]??[]);return shortRead?0:bytes.length;}
 }});
 assert.equal(f.call('lis3dhBegin',24,2),true);
 assert.deepEqual(writes.slice(0,3),[[24,32,0],[24,35,136],[24,32,71]]);
 assert.deepEqual(f.call('lis3dhAcceleration'),[1024,-1024,2047]);
 assert.equal(f.call('lis3dhBegin',24,16),true);
 assert.deepEqual(f.call('lis3dhAcceleration'),[12288,-12288,24564]);
 let count=writes.length;assert.equal(f.call('lis3dhBegin',24,3),false);assert.equal(writes.length,count);
 assert.equal(f.call('lis3dhAcceleration'),false);
 assert.equal(f.call('lsm9ds1Begin',107,30),true);
 assert.deepEqual(f.call('lsm9ds1Acceleration'),[999,-999,1998]);
 assert.deepEqual(f.call('lsm9ds1Gyroscope'),[875,-875,0]);
 assert.deepEqual(f.call('lsm9ds1Magnetic'),[1400,-1400,0]);
 shortRead=true;assert.equal(f.call('lsm9ds1Acceleration'),false);shortRead=false;
 ids['107:23']=0;assert.equal(f.call('lsm9ds1Gyroscope'),false);
 ids['30:15']=0;count=writes.length;assert.equal(f.call('lsm9ds1Begin',107,30),false);assert.equal(writes.length,count);
 assert.equal(f.call('lsm9ds1Magnetic'),false);
 return {register_fixtures:true,negative_axes:true,range_scaling:true,wrong_id:true,short_read:true,not_ready:true};
};
