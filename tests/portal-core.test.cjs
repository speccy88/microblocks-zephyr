// SPDX-License-Identifier: MPL-2.0
const {test}=require('node:test');
const assert=require('node:assert/strict');
const {ByteQueue,SerialTransport,ProjectStore,MAX_QUEUE,MAX_PROJECT}=require('../web/portal/portal-core.js');

function fakeSerial(){
 const sent=[],events=[];let controller;
 const port={readable:new ReadableStream({start(c){controller=c;},cancel(){events.push('cancel');}}),
  writable:{getWriter(){return {async write(data){sent.push([...data]);},releaseLock(){events.push('writer-release');}};}},
  async open(options){assert.equal(options.baudRate,115200);events.push('open');},
  async setSignals(s){events.push(s.dataTerminalReady?'dtr-on':'dtr-off');},async close(){events.push('close');}};
 const provider={async requestPort(options){assert.deepEqual(options.filters,[{usbVendorId:0x2fe3,usbProductId:4}]);return port;}};
 return {provider,port,sent,events,get controller(){return controller;}};
}

test('input queue preserves stream order, copies input, and enforces its bound',()=>{
 const q=new ByteQueue(),first=new Uint8Array([1,2,3]);q.push(first);first.fill(9);q.push(new Uint8Array([4,5]));
 assert.deepEqual([...q.read(4)],[1,2,3,4]);assert.deepEqual([...q.read(4)],[5]);assert.equal(q.bytes,0);
 q.push(new Uint8Array(MAX_QUEUE));assert.throws(()=>q.push(new Uint8Array(1)),/full/);q.clear();assert.equal(q.bytes,0);
});

test('USB writes retain exact bytes after caller wipes the submitted packet',async()=>{
 const f=fakeSerial(),received=[],states=[];
 const transport=new SerialTransport(f.provider,[{usbVendorId:0x2fe3,usbProductId:4}],d=>received.push([...d]),c=>states.push(c));
 await transport.connect();const packet=new Uint8Array([251,205,0,1,0,254]);assert.equal(transport.write(packet),packet.length);packet.fill(0);
 await transport.chain;assert.deepEqual(f.sent,[[251,205,0,1,0,254]]);
 f.controller.enqueue(new Uint8Array([250,26,1]));await new Promise(r=>setImmediate(r));assert.deepEqual(received,[[250,26,1]]);
 await transport.disconnect();assert.deepEqual(f.events,['open','dtr-on','cancel','writer-release','dtr-off','close']);assert.equal(states.at(-1),false);
});

test('disconnect drains queued writes before releasing the port',async()=>{
 const f=fakeSerial(),transport=new SerialTransport(f.provider,[{usbVendorId:0x2fe3,usbProductId:4}],()=>{},()=>{});
 await transport.connect();transport.write(new Uint8Array([1]));transport.write(new Uint8Array([2]));
 await transport.disconnect();assert.deepEqual(f.sent,[[1],[2]]);assert.equal(transport.pending,0);assert.equal(f.events.at(-1),'close');
});

test('P2 Prop Plug never asserts reset DTR on connect or disconnect',async()=>{
 const f=fakeSerial();
 const transport=new SerialTransport(f.provider,[{usbVendorId:0x2fe3,usbProductId:4}],()=>{},()=>{},
  {dataTerminalReady:false,requestToSend:false});
 await transport.connect();await transport.disconnect();
 assert.equal(f.events.includes('dtr-on'),false);
 assert.equal(f.events.filter(x=>x==='dtr-off').length,2);
});

test('no duplicate chooser while an explicit Connect request is pending',async()=>{
 const f=fakeSerial();let release,calls=0;
 const provider={requestPort(){calls++;return new Promise(r=>release=()=>r(f.port));}};
 const transport=new SerialTransport(provider,[],()=>{},()=>{});const first=transport.connect();await transport.connect();assert.equal(calls,1);
 release();await first;await transport.disconnect();
});

test('unsupported browsers and failed storage do not claim a connection or save',async()=>{
 const transport=new SerialTransport(null,[],()=>{},()=>{});await assert.rejects(transport.connect(),/desktop Chrome or Edge/);
 assert.equal(transport.port,null);const store=new ProjectStore(null);await assert.rejects(store.save('fruit-jam','workspace','Workspace','module main'),/unavailable/);
 await assert.rejects(store.save('fruit-jam','workspace','Workspace','x'.repeat(MAX_PROJECT+1)),/4 MiB/);
});

test('a new chooser cannot race a USB disconnect that is draining a write',async()=>{
 const f=fakeSerial();let release;
 f.port.writable.getWriter=()=>({write(){return new Promise(r=>release=r);},releaseLock(){}});
 const transport=new SerialTransport(f.provider,[{usbVendorId:0x2fe3,usbProductId:4}],()=>{},()=>{});
 await transport.connect();transport.write(new Uint8Array([1]));await Promise.resolve();
 const closing=transport.disconnect();await assert.rejects(transport.connect(),/still disconnecting/);
 release();await closing;assert.equal(transport.port,null);
});
