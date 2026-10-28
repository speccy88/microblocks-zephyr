// SPDX-License-Identifier: MPL-2.0
// Exercise the packaged adapter with a minimal editor DOM and fake transports.
// No real network, USB port, credentials or project is used.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const path=require('node:path');
const vm=require('node:vm');
const {execFileSync}=require('node:child_process');
const core=require('../web/portal/portal-core.js');
const repo=path.resolve(__dirname,'..');
const source=execFileSync(process.env.PYTHON||'python',['-c',
 "import sys;from pathlib import Path;sys.path.insert(0,'tools');from package_p4_ide import adapter;sys.stdout.buffer.write(adapter(Path('.')))"],
 {cwd:repo,encoding:'utf8'});

async function editor(origin,profile){
 const fields=new Map(),listeners={},sockets=[];let serialRequests=0;
 function node(tag){return {tag,value:'',children:[],dataset:{},
  append(...items){this.children.push(...items);if(tag==='select'&&!this.value&&items[0]?.value)this.value=items[0].value;},
  prepend(){},insertBefore(){},replaceChildren(){this.children=[];},
  setAttribute(name,value){if(name==='aria-label')fields.set(value,this);}};}
 const document={documentElement:node('html'),hidden:false,
  createElement:node,createTextNode:()=>node('text'),querySelector:()=>node('div'),
  addEventListener(name,fn){listeners[name]=fn;}};
 const window={addEventListener(){}};
 class Socket{static OPEN=1;constructor(url){this.url=url;this.readyState=1;this.sent=[];this.closeCount=0;sockets.push(this);}close(){this.closeCount++;this.readyState=3;}send(data){this.sent.push([...data]);}}
 const context={window,document,location:new URL(origin),MicroBlocksPortal:core,
  PORTAL_BOARD:{board:'esp32p4',name:'P4',...profile},
  navigator:{serial:{async requestPort(){serialRequests++;throw Error('Fake USB');}}},
  GP_writeFile(){},GP:{apiCall(){}},Menus:{connection:{},settings:{items:[]}},
  IDE:{board:{connected:false}},WebSocket:Socket,URL,Map,TextEncoder,TextDecoder,
  Uint8Array,Uint32Array,ArrayBuffer,setTimeout,clearTimeout,setInterval(){}};
 vm.runInNewContext(source,context);
 await listeners['board-ide-ready']();
 return {window,fields,sockets,get serialRequests(){return serialRequests;}};
}

test('real hosted adapter uses station address and ignores an injected endpoint field',async()=>{
 for(const [origin,expected] of [['http://192.168.20.41','ws://192.168.20.41/ws/vm'],
  ['http://10.0.0.7:8080','ws://10.0.0.7:8080/ws/vm'],
  ['https://board.local:8443','wss://board.local:8443/ws/vm']]){
  const app=await editor(origin,{hosted:true,bridge:false});
  app.fields.get('Secure WebSocket address').value='ws://other.invalid/ws/vm';
  await app.window.webSerialConnect();assert.equal(app.sockets.length,1);
  assert.equal(app.sockets[0].url,expected);assert.equal(app.serialRequests,0);
  assert.equal(app.window.webSerialIsConnected(),false);
  app.sockets[0].onmessage({data:'ready'});
  assert.equal(app.window.webSerialIsConnected(),true);
 }
});

test('hosted USB selection stays USB and loopback bridge cannot become a remote exception',async()=>{
 const usb=await editor('http://10.0.0.7',{hosted:true});
 usb.fields.get('Connection mode').value='usb';await usb.window.webSerialConnect();
 assert.equal(usb.serialRequests,1);assert.equal(usb.sockets.length,0);
 const bridge=await editor('http://127.0.0.1:8875',{bridge:true});
 await bridge.window.webSerialConnect();assert.equal(bridge.sockets[0].url,'ws://127.0.0.1:8875/ws/vm');
 const invalid=await editor('http://10.0.0.7',{bridge:true});
 await invalid.window.webSerialConnect();assert.equal(invalid.sockets.length,0);
});

test('public portal retains its secure remote endpoint guard',async()=>{
 const app=await editor('https://speccy88.github.io',{});
 app.fields.get('Connection mode').value='wifi';
 for(const url of ['ws://10.0.0.7/ws/vm','wss://user:secret@board.local/ws/vm','wss://board.local/ws/vm#x']){
  app.fields.get('Secure WebSocket address').value=url;await app.window.webSerialConnect();
  assert.equal(app.sockets.length,0);
 }
 app.fields.get('Secure WebSocket address').value='wss://board.local/ws/vm';
 await app.window.webSerialConnect();assert.equal(app.sockets[0].url,'wss://board.local/ws/vm');
});

test('old socket callbacks cannot disconnect or feed a replacement controller',async()=>{
 const app=await editor('http://10.0.0.7',{hosted:true});
 await app.window.webSerialConnect();const old=app.sockets[0];old.onmessage({data:'ready'});
 app.window.webSerialDisconnect();await new Promise(resolve=>setImmediate(resolve));
 await app.window.webSerialConnect();const current=app.sockets[1];current.onmessage({data:'ready'});
 old.onclose();old.onmessage({data:'not binary'});old.onerror();
 assert.equal(app.window.webSerialIsConnected(),true);assert.equal(app.window.GP_readSerialPort(100).length,0);
 current.onclose();assert.equal(app.window.webSerialIsConnected(),false);
});

const waits=JSON.parse(execFileSync(process.env.PYTHON||'python',['-c',
 "import sys,json;sys.path.insert(0,'tools');from package_p4_ide import serial_open_wait;print(json.dumps({'usb':serial_open_wait().decode(),'hosted':serial_open_wait(True).decode()}))"],{cwd:repo,encoding:'utf8'}));
const budget=kind=>Number(waits[kind].match(/< (\d+)\)\)/)[1]);
async function gpOpen(app,deadline,readyAt){
 app.window.GP_openSerialPort();const socket=app.sockets[0];socket.readyState=0;let elapsed=0;
 while(!app.window.GP_isOpenSerialPort(1)&&elapsed<deadline){
  elapsed+=10;
  if(elapsed>=readyAt){socket.readyState=1;socket.onmessage({data:'ready'});}
 }
 if(!app.window.GP_isOpenSerialPort(1))app.window.GP_closeSerialPort(1);
 return {elapsed,socket,connected:app.window.GP_isOpenSerialPort(1)};
}
test('measured 8.9s handshake fails at legacy deadline but completes in actual hosted budget',async()=>{
 const old=await editor('http://10.0.0.7',{hosted:true});
 const expired=await gpOpen(old,budget('usb'),8907);
 assert.equal(expired.connected,false);assert.equal(expired.elapsed,5000);assert.equal(expired.socket.closeCount,1);assert.deepEqual(expired.socket.sent,[]);
 const hosted=await editor('http://10.0.0.7',{hosted:true});
 const opened=await gpOpen(hosted,budget('hosted'),8907);
 assert.equal(opened.connected,true);assert.equal(opened.elapsed,8910);assert.equal(opened.socket.closeCount,0);
 assert.equal(hosted.sockets.length,1);assert.equal(hosted.serialRequests,0);assert.deepEqual(opened.socket.sent,[]);
 assert.equal(hosted.window.GP_writeSerialPort(new Uint8Array([250,12,0])),3);assert.deepEqual(opened.socket.sent,[[250,12,0]]);
});
test('hosted opening still expires once without replaying commands or opening another socket',async()=>{
 const app=await editor('http://10.0.0.7',{hosted:true});const expired=await gpOpen(app,budget('hosted'),Infinity);
 assert.equal(expired.connected,false);assert.equal(expired.elapsed,30000);assert.equal(expired.socket.closeCount,1);
 assert.equal(app.sockets.length,1);assert.deepEqual(expired.socket.sent,[]);assert.equal(app.serialRequests,0);
 expired.socket.readyState=1;expired.socket.onmessage({data:'ready'});assert.equal(app.window.GP_isOpenSerialPort(1),false);
});
