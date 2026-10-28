/* SPDX-License-Identifier: MIT */
// Actual client and wire codec with synthetic native operations; no board I/O.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const core=require('../web/device-files-core.js'),SD=require('../web/device-sd-core.js'),wire=require('../web/device-files-wire.js');
const {fixture}=require('./device_sd_fakes.js');
test('SD names cannot select a volume, escape MBFILES or alias long filenames',()=>{
 for(const value of ['A','NOTE.TXT','12345678.123','_A.BIN'])assert.equal(SD.name(value),value);
 for(const value of ['','../A','/SD/A','SD:/A','a.txt','A.','123456789.TXT','A/B','A\\B','A%20B','A..TXT'])assert.throws(()=>SD.name(value),{code:'PATH'});
});
test('SD create/list/open/remove preserves existing files and exact empty, Unicode and full-size bytes',async()=>{
 const {native,client,sd}=fixture();assert.equal(await sd.available(),true);
 for(const [name,data] of [['EMPTY.TXT',new Uint8Array()],['UTF8.TXT',core.encodeText('Bonjour é 🌻')],['FULL.BIN',Uint8Array.from({length:8192},(_,i)=>i*19)]]){
  const owned=data.slice(),saved=await sd.create(name,data);assert.deepEqual(saved.bytes,owned);
  assert.equal((await sd.list()).files.some(f=>f.name===name),true);
  assert.deepEqual((await sd.read(name)).bytes,owned);assert.equal(await sd.removeOwn(name),true);assert.equal(native.files.has(name),false);
 }
 assert.equal(new TextDecoder().decode(native.files.get('SOURCE.TXT')),'Preserved source');
 await assert.rejects(sd.removeOwn('SOURCE.TXT'),{code:'STATE'});assert.equal(native.calls.filter(op=>op==='sdRemove').length,3);
 await client.keepAlive();assert.equal(native.calls.at(-1),'capabilities');assert.equal(client.uncertain,false);
});
test('confirmed existing-name refusal is not a successful write or an uncertain mutation',async()=>{
 const {native,client,sd}=fixture();await assert.rejects(sd.create('SOURCE.TXT',core.encodeText('replace')));
 assert.equal(new TextDecoder().decode(native.files.get('SOURCE.TXT')),'Preserved source');assert.equal(client.uncertain,false);
 assert.equal(native.calls.filter(op=>op==='sdCreate').length,1);
});
test('modified creation snapshot is preserved on removal failure and blocks further mutations',async()=>{
 const {native,client,sd}=fixture();await sd.create('OWN.TXT',core.encodeText('original'));
 native.files.set('OWN.TXT',core.encodeText('changed externally'));
 await assert.rejects(sd.removeOwn('OWN.TXT'));assert.equal(native.files.has('OWN.TXT'),true);assert.equal(client.uncertain,true);
 await assert.rejects(sd.create('NEXT.TXT',new Uint8Array()),{code:'UNCERTAIN'});
});
test('bad verification chunks are rejected without retrying the committed write',async()=>{
 const {native,client,sd}=fixture();native.corrupt=true;
 await assert.rejects(sd.create('OWN.TXT',core.encodeText('data')),{code:'PROTOCOL'});
 assert.equal(native.calls.filter(op=>op==='sdCreate').length,1);assert.equal(client.uncertain,true);
});
test('cancellation stops waiting, sends one bounded cancellation and preserves unknown outcomes',async()=>{
 const {native,client,sd}=fixture();native.delayOp='sdStatus';
 const operation=sd.create('OWN.TXT',core.encodeText('data'));
 while(!native.calls.includes('sdStatus'))await new Promise(resolve=>setImmediate(resolve));
 assert.equal(client.cancel(),true);await assert.rejects(operation,{code:'CANCELLED'});
 assert.equal(native.calls.filter(op=>op==='sdCancel').length,1);assert.equal(client.busy,false);assert.equal(client.uncertain,true);
});
test('SD wire status and chunk lengths are checked independently of transport success',()=>{
 const request={version:1,id:1,op:'sdStatus',args:{job:1}},frame=new Uint8Array(5+25),view=new DataView(frame.buffer,5);
 frame.set([251,217,0,25,0]);frame.set([77,66,70,82,1,16],5);view.setUint32(6,1,true);view.setUint32(10,7,true);view.setInt32(17,-140,true);
 const decoded=wire.decode(frame,request,7);assert.equal(decoded.data.error,-140);assert.equal(decoded.data.busy,false);
 frame[5+23]=32;assert.throws(()=>wire.decode(frame,request,7),{code:'PROTOCOL'});
});
module.exports={fixture};
