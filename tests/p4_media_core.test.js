/* SPDX-License-Identifier: MIT */
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const core=require('../web/p4-media-core.js');
test('media protocol uses bounded native fields and exact terminator',()=>{
 const p=core.packet(123,3,456,789,1024,512,19),v=new DataView(p.buffer);
 assert.equal(p.length,34);assert.deepEqual([...p.slice(0,11)],[251,208,0,29,0,80,52,77,82,3,0]);
 assert.deepEqual([v.getUint32(11,true),v.getUint32(15,true),v.getUint32(19,true),v.getUint32(23,true),v.getUint16(27,true),v.getUint32(29,true)],[123,456,789,1024,512,19]);assert.equal(p[33],254);
});
const image=format=>({kind:1,width:1,height:1,source_width:1280,source_height:720,format,bytes:format});
test('known pixels preserve grayscale, RGB565 little endian and RGB888',()=>{
 assert.deepEqual([...core.rgba(image(1),[17])],[17,17,17,255]);
 assert.deepEqual([...core.rgba(image(2),[0,248])],[255,0,0,255]);
 assert.deepEqual([...core.rgba(image(3),[3,97,201])],[3,97,201,255]);
 assert.throws(()=>core.rgba(image(3),[1,2]));assert.throws(()=>core.metadata({...image(1),width:161}));
});
test('PCM export has exact sample rate, signed byte payload and WAV length',()=>{
 const m={kind:2,frames:3,rate:16000,channels:1,bytes:6},p=core.wav(m,Uint8Array.from([0,128,0,0,255,127])),v=new DataView(p.buffer);
 assert.equal(new TextDecoder().decode(p.slice(0,4)),'RIFF');assert.equal(v.getUint32(4,true),42);assert.equal(v.getUint32(24,true),16000);assert.equal(v.getUint16(34,true),16);assert.equal(v.getUint32(40,true),6);
 assert.deepEqual([...p.slice(44)],[0,128,0,0,255,127]);assert.throws(()=>core.wav({...m,frames:128001},[]));
});
test('cache limits independent outputs and disposes replaced, evicted and cleared blobs',()=>{
 const disposed=[],c=new core.Cache((uid,item)=>disposed.push([uid,item.url]),{bytes:100,entries:3,audio:2});
 c.put(1,{cost:30,kind:1});c.put(2,{cost:30,kind:2,url:'a'});c.get(1);c.put(3,{cost:30,kind:2,url:'b'});c.put(4,{cost:30,kind:2,url:'c'});
 assert.equal(c.items.has(2),false);assert.equal(c.bytes,90);c.put(4,{cost:10,kind:2,url:'d'});assert.deepEqual(disposed.slice(0,2),[[2,'a'],[4,'c']]);
 c.clear();assert.equal(c.bytes,0);assert.equal(c.items.size,0);assert.ok(disposed.some(x=>x[1]==='b'));assert.ok(disposed.some(x=>x[1]==='d'));
 assert.throws(()=>c.put(9,{cost:101,kind:1}));
});
test('replacement reaches ready after older expiry even with a last-request-first GP host',async()=>{
 const requests=[],order=[];let view='old';
 const raw=(action)=>new Promise(resolve=>requests.push(()=>{order.push(action);view=action==='result'?'ready':'expired';resolve();}));
 const call=core.serialCalls(raw),a=call('expire'),b=call('result');
 await Promise.resolve();assert.equal(requests.length,1);requests.pop()();await a;
 await Promise.resolve();assert.equal(requests.length,1);requests.pop()();await b;
 assert.deepEqual(order,['expire','result']);assert.equal(view,'ready');
});
