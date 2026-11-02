// SPDX-License-Identifier: MIT
// Browser API fixtures, never a board/device acceptance claim.
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const api=require('../web/mobile/mobile-browser.js'),layout=require('../web/mobile/mobile-entry.js');
function fixture(runtime='board',hostname='192.168.1.42'){
 const sockets=[],received=[],timers=[];
 class Socket{
  constructor(...args){this.args=args;this.readyState=1;this.bufferedAmount=0;this.sent=[];sockets.push(this);}
  send(bytes){this.sent.push(Array.from(bytes));}
  close(){this.readyState=3;this.closed=true;}
 }
 const location={href:`http://${hostname}/mobile/index.html`,protocol:'http:',hostname,origin:`http://${hostname}`};
 const client=api.create({profile:{runtime,board:'rlcd'},location,Socket,receive:e=>received.push(e),schedule:fn=>{timers.push(fn);return timers.length;},cancel:()=>{}});
 return {client,sockets,received,timers,connect:id=>client.bridge.postMessage({type:'connect',id,address:hostname})};
}
test('mobile detection uses touch capability and explicit choices win',()=>{
 assert(layout.isTouch({navigator:{maxTouchPoints:5},matchMedia:()=>({matches:true}),innerWidth:932,innerHeight:430}));
 assert(!layout.isTouch({navigator:{maxTouchPoints:0},matchMedia:()=>({matches:false}),innerWidth:390,innerHeight:844}));
 assert(layout.isTouch({navigator:{maxTouchPoints:0},ontouchstart:null,matchMedia:()=>({matches:false}),innerWidth:390,innerHeight:844}));
 assert.equal(layout.mode(null,null,true),'offer');assert.equal(layout.mode(null,null,false),'desktop');
 assert.equal(layout.mode('desktop','mobile',true),'desktop');assert.equal(layout.mode(null,'desktop',true),'desktop');
 assert.throws(()=>layout.safeURL('https://other.invalid/',{href:'https://site.invalid/app/',origin:'https://site.invalid'}),/stay/);
});
test('Pages and public HTTP cannot allocate a socket',()=>{
 for(const f of [fixture('pages'),fixture('board','example.com')]){
  assert(!f.client.available);assert.throws(()=>f.connect('1'));assert.equal(f.sockets.length,0);
 }
});
test('shared non-Pi board profiles do not gain tailnet access',()=>{
 for(const runtime of ['board','pages']){
  const f=fixture(runtime,'100.100.10.20');assert(!f.client.available);assert.throws(()=>f.connect('1'));
  assert.equal(f.sockets.length,0);assert.throws(()=>api.boardURL('100.100.10.20'));
 }
});
test('real socket API receives only a fixed same-origin URL and explicit ready marker',()=>{
 const f=fixture();f.connect('a');const s=f.sockets[0];
 assert.deepEqual(s.args,['ws://192.168.1.42/ws/vm']);assert.equal(s.binaryType,'arraybuffer');
 assert.equal(f.received.length,0);s.onmessage({data:'ready'});assert.equal(f.received[0].type,'ready');
 s.onmessage({data:Uint8Array.of(1,2,255).buffer});assert.deepEqual(f.received[1].bytes,[1,2,255]);
 assert.throws(()=>f.client.bridge.postMessage({type:'connect',id:'b',address:'192.168.1.43'}));
});
test('output acknowledgements wait for the browser queue and old callbacks are ignored',()=>{
 const f=fixture();f.connect('a');const s=f.sockets[0];s.onmessage({data:'ready'});
 f.client.bridge.postMessage({type:'write',id:'a',bytes:[3,4]});assert.deepEqual(s.sent,[[3,4]]);
 assert.equal(f.received.length,1);s.bufferedAmount=2;f.timers.shift()();assert.equal(f.received.length,1);
 s.bufferedAmount=0;f.timers.shift()();assert.equal(f.received.at(-1).count,2);
 const old=s.onmessage;f.connect('b');old({data:Uint8Array.of(9).buffer});assert.equal(f.received.length,2);assert(s.closed);
});
test('malformed/oversized frames and socket errors close the session',()=>{
 for(const value of ['wrong',Uint8Array.of(1).buffer]){const f=fixture();f.connect('1');f.sockets[0].onmessage({data:value});assert.equal(f.received.at(-1).type,'error');assert(f.sockets[0].closed);}
 const f=fixture();f.connect('1');f.sockets[0].onmessage({data:'ready'});f.sockets[0].onmessage({data:new ArrayBuffer(4097)});assert(f.sockets[0].closed);
 const g=fixture();g.connect('1');g.sockets[0].onerror();assert(g.sockets[0].closed);
});
test('private board navigation has no hostname, credential, protocol or public-IP escape',()=>{
 assert.equal(api.boardURL(' 172.16.0.2 '),'http://172.16.0.2/?layout=mobile');
 for(const x of ['8.8.8.8','127.0.0.1','192.168.1.02','192.168.1.2:80','http://192.168.1.2','192.168.1.2@other.invalid','192.168.1.2/path','10.0.0.256'])assert.throws(()=>api.boardURL(x));
});
