// SPDX-License-Identifier: MPL-2.0
'use strict';const assert=require('node:assert/strict');
const {WSSPort,secureEndpoint,MAX_OUTPUT}=require('../web/js-editor/board-transport.js'),{load}=require('./support/js_editor_headless.cjs');
class Socket{
 static all=[];
 constructor(url){this.url=url;this.readyState=0;this.bufferedAmount=0;this.sent=[];Socket.all.push(this);}
 open(){this.readyState=1;}receive(data){this.onmessage({data});}send(data){this.sent.push(data.slice());}close(){this.readyState=3;if(this.onclose)this.onclose();}
}
const tick=()=>new Promise(resolve=>setImmediate(resolve));
async function main(){let passed=0;async function test(fn){await fn();passed++;}
 await test(()=>{for(const value of ['ws://board.invalid/ws/vm','https://board.invalid/ws/vm','wss://user:password@board.invalid/ws/vm','wss://board.invalid/ws/vm?token=x','wss://board.invalid/ws/vm#x','wss://board.invalid/other',' wss://board.invalid/ws/vm','wss://board.invalid/\nws/vm'])assert.throws(()=>secureEndpoint(value));assert.equal(Socket.all.length,0);assert.equal(secureEndpoint('wss://board.invalid:8443/ws/vm'),'wss://board.invalid:8443/ws/vm');});
 await test(async()=>{const p=new WSSPort(Socket,'wss://board.invalid/ws/vm'),opening=p.connect(),s=Socket.all.at(-1);s.open();s.receive(new Uint8Array([250,26,0]));await assert.rejects(opening,/readiness/);assert(!p.isConnected());s.receive('ready');assert.equal(p.read().length,0);});
 await test(async()=>{const p=new WSSPort(Socket,'wss://board.invalid/ws/vm'),opening=p.connect(),s=Socket.all.at(-1);s.open();assert(!p.isConnected());s.receive('ready');await opening;
  const bytes=new Uint8Array([1,2]);assert.equal(p.write(bytes),2);bytes.fill(9);assert.deepEqual([...s.sent[0]],[1,2]);s.bufferedAmount=MAX_OUTPUT;assert.equal(p.write(new Uint8Array([1])),0);
  for(let i=0;i<33;i++)s.receive(new Uint8Array(4096));assert(!p.isConnected());assert.equal(p.read().length,0);
 });
 await test(async()=>{const p=new WSSPort(Socket,'wss://board.invalid/ws/vm'),opening=p.connect(),s=Socket.all.at(-1);s.open();s.receive('ready');await opening;s.receive('unexpected');assert(!p.isConnected());assert.equal(s.readyState,3);});
 await test(async()=>{
  const h=load(process.argv[2],{Socket,location:{href:'https://editor.invalid/js-preview/esp32p4/'}}),c=h.evaluate('MB_connection');
  await h.evaluate('MB_connection.connect("board-wss","wss://board.invalid/ws/vm")');const first=Socket.all.at(-1);first.open();first.receive('ready');await tick();assert(c.isConnected());assert.equal(await c.sendMsg('chunkCode16Msg',1,[2,3]),false);
  const body=[2,...Buffer.from('v417 Waveshare ESP32-P4 WIFI6 Zephyr')];first.receive(new Uint8Array([251,22,0,body.length,0,...body]));c.processMessages();assert(h.evaluate('MB_p4Services.available()'));
  const frame=require('../web/p4-neural-core.js').packet(0,19);assert.equal(h.evaluate('MB_p4Services').send(frame),frame.length);await c.sendQueue;assert(first.sent.some(x=>x[1]===216));
  const stale=h.evaluate('MicroBlocksFilesConnection.send');c.disconnect();await h.evaluate('MB_connection.connect("board-wss","wss://replacement.invalid/ws/vm")');const second=Socket.all.at(-1);second.open();second.receive('ready');await tick();second.receive(new Uint8Array([251,22,0,body.length,0,...body]));c.processMessages();
  first.receive(new Uint8Array([251,208,0,14,0,...new Uint8Array(14)]));first.onclose();assert(c.isConnected());assert.equal(stale(frame),0);assert.equal(second.url,'wss://replacement.invalid/ws/vm');c.disconnect();assert.equal(second.readyState,3);
 });
 console.log(JSON.stringify({passed,network:'synthetic WebSocket only',actual_pinned_connection:true,browser_tls_bypassed:false,physical_hardware:false}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
