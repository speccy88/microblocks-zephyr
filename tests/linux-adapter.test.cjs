// SPDX-License-Identifier: MPL-2.0
// Execute the real shared core + adapter with synthetic browser providers.
// This is transport contract evidence, not GP interpreter or physical VM proof.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const vm=require('node:vm');
const {webcrypto}=require('node:crypto');
const tick=()=>new Promise(resolve=>setImmediate(resolve));

class Element{
 constructor(tag,document){this.tagName=tag.toUpperCase();this.ownerDocument=document;this.children=[];this.attributes={};this.dataset={};this.value='';this._text='';this.hidden=false;}
 set textContent(value){this._text=String(value);this.children=[];}
 get textContent(){return this._text+this.children.map(child=>child.textContent).join('');}
 append(...nodes){for(const node of nodes){node.parentNode=this;this.children.push(node);if(this.tagName==='SELECT'&&this.children.length===1)this.value=node.value;}}
 prepend(...nodes){for(const node of nodes.reverse()){node.parentNode=this;this.children.unshift(node);}}
 insertBefore(node,reference){const at=this.children.indexOf(reference);if(at<0)throw Error('Missing DOM insertion reference');node.parentNode=this;this.children.splice(at,0,node);}
 replaceChildren(...nodes){this.children=[];this._text='';this.append(...nodes);}
 remove(){if(this.parentNode)this.parentNode.children=this.parentNode.children.filter(child=>child!==this);}
 setAttribute(name,value){this.attributes[name]=String(value);}
 find(predicate){if(predicate(this))return this;for(const child of this.children){const found=child.find(predicate);if(found)return found;}}
}
function harness({origin='http://127.0.0.1:8876',localBridge=true,board='raspberry-pi5'}={}){
 let clock=0,nextTimer=0,chooserCalls=0;
 const timers=new Map(),intervals=new Map(),documentListeners=new Map(),windowListeners=new Map(),sockets=[],gpCalls=[],windowOpens=[];
 const document={hidden:false,documentElement:{dataset:{}},
  createElement(tag){return new Element(tag,this);},createTextNode(text){const node=new Element('#text',this);node.textContent=text;return node;},
  querySelector(selector){assert.equal(selector,'[data-ide="controls"]');return controls;},
  addEventListener(name,callback){if(!documentListeners.has(name))documentListeners.set(name,[]);documentListeners.get(name).push(callback);},
  removeEventListener(name,callback){const entries=documentListeners.get(name)||[];documentListeners.set(name,entries.filter(item=>item!==callback));},
  async emit(name,event={}){for(const callback of documentListeners.get(name)||[])await callback({type:name,...event});}
 };
 const controls=new Element('div',document);
 class Socket{
  static CONNECTING=0;static OPEN=1;static CLOSING=2;static CLOSED=3;
  constructor(url){this.url=url;this.readyState=Socket.CONNECTING;this.bufferedAmount=0;this.sent=[];this.closeCalls=[];sockets.push(this);}
  send(bytes){assert.equal(this.readyState,Socket.OPEN);this.sent.push(bytes.slice());}
  close(code,reason){this.closeCalls.push({code,reason});this.readyState=Socket.CLOSED;}
  opened(){this.readyState=Socket.OPEN;this.onopen?.({target:this});}
  message(data){this.onmessage?.({data,target:this});}
  closed(){this.readyState=Socket.CLOSED;this.onclose?.({code:1000,target:this});}
  error(){this.onerror?.({target:this});}
 }
 const context={document,location:new URL(origin),navigator:{serial:{async requestPort(){chooserCalls++;throw Error('Linux must not request USB');}}},
  PORTAL_BOARD:{board,name:board==='microduck'?'MicroDuck Linux':'Raspberry Pi 5',runtime:'linux',connection_enabled:true,...(localBridge?{local_bridge:true}:{})},
  WebSocket:Socket,URL,ArrayBuffer,Uint8Array,Uint32Array,TextEncoder,TextDecoder,Blob,crypto:webcrypto,performance:{now:()=>clock},
  GP:{callQueue:[],apiCall(name,params,callback){gpCalls.push({name,params,callback});}},GP_writeFile(){},GP_serialPortNames:[],
  IDE:{board:{connected:false}},Menus:{connection:{items:[]},settings:{items:[{label:'Install firmware'},{label:'About'}]}},
  toUTF8Array:text=>new TextEncoder().encode(text),confirm:()=>true,
  setTimeout(callback,delay){const id=++nextTimer;timers.set(id,{callback,due:clock+delay});return id;},
  clearTimeout(id){timers.delete(id);},setInterval(callback,delay){const id=++nextTimer;intervals.set(id,{callback,delay});return id;},clearInterval(id){intervals.delete(id);},
  addEventListener(name,callback){if(!windowListeners.has(name))windowListeners.set(name,[]);windowListeners.get(name).push(callback);},
  open(...args){windowOpens.push(args);}
 };
 context.window=context;
 vm.createContext(context);
 for(const file of ['portal-core.js','portal-adapter.js'])vm.runInContext(fs.readFileSync(require.resolve('../web/portal/'+file),'utf8'),context,{filename:file});
 return {context,document,controls,sockets,gpCalls,timers,intervals,windowOpens,get chooserCalls(){return chooserCalls;},
  ready:()=>document.emit('board-ide-ready'),
  find:predicate=>controls.find(predicate),status:()=>controls.find(node=>node.attributes.role==='status'),
  advance(milliseconds){clock+=milliseconds;for(const [id,item] of [...timers])if(item.due<=clock&&timers.delete(id))item.callback();},
  pagehide(){for(const callback of windowListeners.get('pagehide')||[])callback({type:'pagehide'});}
 };
}
function ping(id=7){return new Uint8Array([250,26,id]);}

test('real Linux toolbar starts in WebSocket mode without USB chooser or network activity',async()=>{
 const h=harness();assert.equal(h.sockets.length,0);assert.equal(h.chooserCalls,0);
 await h.ready();
 const mode=h.find(node=>node.attributes['aria-label']==='Connection mode');
 assert.equal(mode.value,'wifi');assert.deepEqual(mode.children.map(child=>child.value),['wifi']);
 const endpoint=h.find(node=>node.attributes['aria-label']==='Secure WebSocket address');
 assert.equal(endpoint.value,'ws://127.0.0.1:8876/ws/vm');assert.equal(endpoint.hidden,false);
 const wifi=h.find(node=>node.tagName==='DETAILS'&&node.children[0]?.textContent==='Wi-Fi setup over USB');assert.equal(wifi.hidden,true);
 assert.equal(h.find(node=>node.tagName==='BUTTON'&&node.textContent==='Open board-hosted IDE'),undefined);
 assert.ok(h.gpCalls.some(call=>call.name==='linux.loadLibrary'));
 assert.equal(h.sockets.length,0);assert.equal(h.chooserCalls,0);assert.equal(h.context.GP_isOpenSerialPort(),false);
});

test('opening before IDE readiness cannot fall through to a USB chooser',async()=>{
 const h=harness();assert.equal(h.context.GP_openSerialPort(),1);await tick();
 assert.equal(h.sockets.length,0);assert.equal(h.chooserCalls,0);assert.equal(h.context.GP_isOpenSerialPort(),false);
 await h.ready();assert.equal(h.sockets.length,0);assert.equal(h.chooserCalls,0);
});

test('GP logical port stays open while one bounded WebSocket handshake owns it',async()=>{
 const h=harness();await h.ready();
 assert.equal(h.context.GP_openSerialPort(),1);assert.equal(h.context.GP_openSerialPort(),1);
 assert.equal(h.sockets.length,1);assert.equal(h.chooserCalls,0);
 const socket=h.sockets[0];assert.equal(socket.binaryType,'arraybuffer');
 assert.equal(h.context.GP_isOpenSerialPort(),true);assert.equal(h.context.webSerialIsConnected(),true);
 assert.equal(h.context.GP_writeSerialPort(ping()),0);assert.equal(socket.sent.length,0);
 assert.equal(h.context.IDE.board.connected,false);assert.doesNotMatch(h.status().textContent,/connected$/i);
 socket.opened();assert.equal(h.context.GP_isOpenSerialPort(),true);
 assert.equal(h.context.GP_writeSerialPort(ping()),0);assert.equal(socket.sent.length,0);
 assert.deepEqual([...h.context.GP_readSerialPort(10)],[]); // no invented VM ping
 socket.message('ready');assert.equal(h.context.GP_writeSerialPort(ping()),3);
 assert.equal(h.context.GP_openSerialPort(),1);assert.equal(h.sockets.length,1); // already-ready controller still owns the stream
 assert.deepEqual([...socket.sent[0]],[250,26,7]);assert.equal(h.context.IDE.board.connected,false);
 assert.deepEqual([...h.context.GP_readSerialPort(10)],[]); // GP has not received a VM reply yet
 socket.message(ping(7).buffer);assert.deepEqual([...h.context.GP_readSerialPort(10)],[250,26,7]);
 h.advance(10000);assert.equal(socket.closeCalls.length,0);assert.equal(h.context.GP_isOpenSerialPort(),true);
 h.context.GP_closeSerialPort();await tick();assert.equal(h.context.GP_isOpenSerialPort(),false);
});

test('ready stream retains fragmented VM frames and copies accepted outgoing bytes',async()=>{
 const h=harness();await h.ready();h.context.GP_openSerialPort();const socket=h.sockets[0];socket.opened();socket.message('ready');
 socket.message(new Uint8Array([251,18,0,5]).buffer);assert.deepEqual([...h.context.GP_readSerialPort(20)],[]);
 socket.message(new Uint8Array([0,1,12,0,0,0]).buffer);
 assert.deepEqual([...h.context.GP_readSerialPort(20)],[251,18,0,5,0,1,12,0,0,0]);
 const original=new Uint8Array([1,2,3,4]);assert.equal(h.context.GP_writeSerialPort(original),4);original.fill(0);
 assert.deepEqual([...socket.sent[0]],[1,2,3,4]);h.context.GP_closeSerialPort();await tick();
});

test('old WebSocket close, message and error callbacks cannot corrupt a replacement',async()=>{
 const h=harness();await h.ready();h.context.GP_openSerialPort();const first=h.sockets[0];first.opened();first.message('ready');
 const staleMessage=first.onmessage,staleClose=first.onclose,staleError=first.onerror;
 h.context.GP_closeSerialPort();await tick();h.context.GP_openSerialPort();const second=h.sockets[1];second.opened();
 staleMessage({data:'ready'});assert.equal(h.context.GP_writeSerialPort(ping()),0); // stale readiness cannot open new stream
 second.message('ready');second.message(ping(12).buffer);const status=h.status().textContent;
 staleClose({code:1000});staleError({});staleMessage({data:ping(99).buffer});
 assert.equal(h.context.GP_isOpenSerialPort(),true);assert.equal(h.status().textContent,status);
 assert.deepEqual([...h.context.GP_readSerialPort(100)],[250,26,12]);
 assert.equal(h.context.GP_writeSerialPort(ping(14)),3);assert.deepEqual([...second.sent[0]],[250,26,14]);
 h.context.GP_closeSerialPort();await tick();
});

test('handshake deadline closes a silent endpoint without fabricating VM connection',async()=>{
 const h=harness();await h.ready();h.context.GP_openSerialPort();const socket=h.sockets[0];socket.opened();
 h.advance(9999);assert.equal(h.context.GP_isOpenSerialPort(),true);assert.equal(h.context.GP_writeSerialPort(ping()),0);
 h.advance(1);await tick();
 assert.equal(socket.closeCalls.length,1);assert.equal(socket.readyState,socket.constructor.CLOSED);
 assert.equal(h.context.GP_isOpenSerialPort(),false);assert.equal(h.context.webSerialIsConnected(),false);
 assert.equal(h.context.IDE.board.connected,false);assert.equal(h.context.GP_writeSerialPort(ping()),0);
 assert.equal(socket.sent.length,0);assert.deepEqual([...h.context.GP_readSerialPort(100)],[]);
 socket.message('ready');assert.equal(h.context.GP_isOpenSerialPort(),false);assert.doesNotMatch(h.status().textContent,/Linux SmallVM connected/);
 assert.equal(h.chooserCalls,0);
});

test('an abandoned connecting socket deadline cannot close its ready replacement',async()=>{
 const h=harness();await h.ready();h.context.GP_openSerialPort();const first=h.sockets[0];
 h.context.GP_closeSerialPort();await tick();
 h.context.GP_openSerialPort();const second=h.sockets[1];second.opened();second.message('ready');
 h.advance(10000);await tick();
 assert.equal(first.closeCalls.length,1);assert.equal(second.closeCalls.length,0);
 assert.equal(h.context.GP_isOpenSerialPort(),true);assert.equal(h.context.GP_writeSerialPort(ping()),3);
 h.context.GP_closeSerialPort();await tick();
});

test('binary data before the ready handshake is rejected without accepting the first ping',async()=>{
 const h=harness();await h.ready();h.context.GP_openSerialPort();const socket=h.sockets[0];socket.opened();
 socket.message(ping().buffer);await tick();
 assert.equal(socket.closeCalls.length,1);assert.equal(h.context.GP_isOpenSerialPort(),false);
 assert.equal(h.context.GP_writeSerialPort(ping()),0);assert.equal(socket.sent.length,0);
 assert.deepEqual([...h.context.GP_readSerialPort(20)],[]);assert.equal(h.context.IDE.board.connected,false);
});

test('HTTPS Linux editor waits for an explicit trusted WSS endpoint and never downgrades',async()=>{
 const h=harness({origin:'https://speccy88.github.io',localBridge:false});
 h.context.microblocksLinuxSetEndpoint('wss://board.example/ws/vm');assert.equal(h.sockets.length,0);
 await h.ready();assert.equal(h.sockets.length,0);assert.equal(h.chooserCalls,0);
 for(const url of ['ws://127.0.0.1:8876/ws/vm','wss://user:secret@board.example/ws/vm','wss://board.example/ws/vm?token=x'])assert.throws(()=>h.context.microblocksLinuxSetEndpoint(url));
 h.context.GP_openSerialPort();assert.equal(h.sockets.length,1);assert.equal(h.sockets[0].url,'wss://board.example/ws/vm');
 assert.equal(h.chooserCalls,0);h.context.GP_closeSerialPort();await tick();
});

test('local bridge endpoint is exact same-origin and explicit endpoint handoff never opens it',async()=>{
 const h=harness({origin:'http://localhost:8876'});await h.ready();
 h.context.microblocksLinuxSetEndpoint('ws://localhost:8876/ws/vm');assert.equal(h.sockets.length,0);
 for(const url of ['ws://127.0.0.1:8876/ws/vm','ws://localhost:8877/ws/vm','ws://localhost:8876/other','wss://localhost:8876/ws/vm'])assert.throws(()=>h.context.microblocksLinuxSetEndpoint(url));
 h.context.GP_openSerialPort();assert.equal(h.sockets[0].url,'ws://localhost:8876/ws/vm');h.context.GP_closeSerialPort();await tick();
});

test('pagehide closes Linux transport and board mismatch rejects only a real incompatible identity',async()=>{
 const h=harness({board:'microduck'});await h.ready();h.context.GP_openSerialPort();const socket=h.sockets[0];socket.opened();socket.message('ready');
 await h.document.emit('board.type',{detail:{value:'Connect'}});assert.equal(h.context.GP_isOpenSerialPort(),true);
 await h.document.emit('board.type',{detail:{value:'Linux ARM64'}});assert.equal(h.context.GP_isOpenSerialPort(),true);
 await h.document.emit('board.type',{detail:{value:'Parallax P2'}});await tick();assert.equal(h.context.GP_isOpenSerialPort(),false);
 h.context.GP_openSerialPort();const replacement=h.sockets[1];replacement.opened();replacement.message('ready');h.pagehide();await tick();
 assert.equal(replacement.closeCalls.length,1);assert.equal(h.context.GP_isOpenSerialPort(),false);assert.equal(h.chooserCalls,0);
});
