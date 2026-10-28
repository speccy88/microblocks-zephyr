/* SPDX-License-Identifier: MIT */
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const core=require('../web/device-files-core.js');
const wire=require('../web/device-files-wire.js');

test('measured late session grant cannot revive the expired request or replay operations',async()=>{
 let now=0,next=0;const timers=new Map(),sent=[],module={exports:{}};
 const context={module,require:id=>id==='./device-files-core.js'?core:wire,
  Uint8Array,DataView,Set,Promise,
  setTimeout(fn,ms){const id=++next;timers.set(id,{fn,due:now+ms});return id;},
  clearTimeout(id){timers.delete(id);}};
 vm.runInNewContext(fs.readFileSync(require.resolve('../web/device-files-controller.js'),'utf8'),context);
 const controller=new module.exports.Controller({nonce:()=>123});
 controller.link(frame=>{sent.push(frame.slice());return frame.length;});
 const opening=controller.open();assert.equal(sent.length,1);assert.equal(sent[0][10],9);
 now=3000;for(const [id,timer] of timers){if(timer.due<=now){timers.delete(id);timer.fn();}}
 await assert.rejects(opening,e=>e.code==='TIMEOUT');
 assert.equal(controller.state,'error');assert.equal(controller.transport,null);
 now=20109;
 const reply=new Uint8Array(29),v=new DataView(reply.buffer);
 reply.set([251,217,0,24,0,77,66,70,82,1,9]);v.setUint32(11,123,true);
 v.setUint32(15,0,true);v.setUint32(21,1,true);v.setUint32(25,123,true);
 controller.receive(reply);await Promise.resolve();
 assert.equal(controller.state,'error');assert.equal(controller.transport,null);
 assert.equal(controller.pending,null);assert.equal(sent.length,1);assert.equal(timers.size,0);
 await controller.close();assert.equal(sent.length,1); // no known grant: no guessed close or write
});
