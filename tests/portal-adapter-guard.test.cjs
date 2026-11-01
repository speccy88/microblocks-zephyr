// SPDX-License-Identifier: MPL-2.0
// Executes the actual adapter entry points with synthetic providers, no DOM,
// physical serial ports, network connection, project load or credentials.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const core=require('../web/portal/portal-core.js');

test('MicroDuck RK3566 placeholder cannot open USB or WebSocket through GP entry points',async()=>{
 let serialRequests=0,networkRequests=0;
 const window={addEventListener(){}};
 const context={window,MicroBlocksPortal:core,
  PORTAL_BOARD:{board:'microduck',name:'MicroDuck Rockchip RK3566',runtime:'linux',placeholder:true,connection_enabled:false,
   connection_message:'Experimental placeholder; offline editing only.'},
  navigator:{serial:{async requestPort(){serialRequests++;throw Error('Unexpected USB');}}},
  document:{addEventListener(){}},GP_writeFile(){},GP:{apiCall(){}},
  WebSocket:class{constructor(){networkRequests++;throw Error('Unexpected connection');}},
  TextEncoder,TextDecoder,setTimeout,clearTimeout,Uint8Array,Uint32Array,Map,URL};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/portal/portal-adapter.js'),'utf8'),context);
 await window.webSerialConnect();assert.equal(window.GP_openSerialPort(),1);await Promise.resolve();
 assert.equal(serialRequests,0);assert.equal(networkRequests,0);assert.equal(window.webSerialIsConnected(),false);
 assert.equal(window.GP_writeSerialPort(new Uint8Array([250,26,0])),0);
});

test('the XRP editing preview cannot open USB or WebSocket through either GP entry point',async()=>{
 let serialRequests=0,networkRequests=0;
 const window={addEventListener(){}};
 const context={window,MicroBlocksPortal:core,
  PORTAL_BOARD:{board:'xrp-rp2350',name:'SparkFun XRP RP2350 (development)',connection_enabled:false},
  navigator:{serial:{async requestPort(){serialRequests++;throw Error('Unexpected device access');}}},
  document:{addEventListener(){}},GP_writeFile(){},GP:{apiCall(){}},
  WebSocket:class{constructor(){networkRequests++;throw Error('Unexpected network access');}},
  TextEncoder,TextDecoder,setTimeout,clearTimeout,Uint8Array,Uint32Array,Map,URL};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/portal/portal-adapter.js'),'utf8'),context);
 await window.webSerialConnect();
 assert.equal(window.GP_openSerialPort(),1);await Promise.resolve();
 assert.equal(serialRequests,0);assert.equal(networkRequests,0);
 assert.equal(window.webSerialIsConnected(),false);
 assert.equal(window.GP_writeSerialPort(new Uint8Array([250,26,0])),0);
});

test('actual P2 adapter uses FTDI selection, releases reset, and rejects another VM identity',async()=>{
 const signals=[],listeners={},calls=[];let closed=false;
 const port={readable:new ReadableStream({cancel(){}}),
  writable:{getWriter(){return {async write(){},releaseLock(){}};}},
  async open(options){calls.push(options.baudRate);},
  async setSignals(value){signals.push(JSON.parse(JSON.stringify(value)));},
  async close(){closed=true;}};
 const window={addEventListener(){}};
 const context={window,MicroBlocksPortal:core,PORTAL_BOARD:{board:'propeller2',name:'Parallax Propeller 2'},
  navigator:{serial:{async requestPort(options){calls.push(JSON.parse(JSON.stringify(options.filters)));return port;}}},
  document:{addEventListener(name,handler){listeners[name]=handler;}},
  GP_writeFile(){},GP:{apiCall(){}},TextEncoder,TextDecoder,setTimeout,clearTimeout,Uint8Array,Uint32Array,Map,URL};
 vm.runInNewContext(fs.readFileSync(path.join(__dirname,'../web/portal/portal-adapter.js'),'utf8'),context);
 assert.equal(calls.length,0);await window.webSerialConnect();
 assert.deepEqual(calls,[[{usbVendorId:0x0403}],115200]);
 assert.deepEqual(signals,[{dataTerminalReady:false,requestToSend:false}]);
 listeners['board.type']({detail:{value:'Parallax P2 Edge 32MB'}});
 assert.equal(window.webSerialIsConnected(),true);
 listeners['board.type']({detail:{value:'Fruit Jam'}});
 await new Promise(resolve=>setImmediate(resolve));
 assert.equal(window.webSerialIsConnected(),false);assert.equal(closed,true);
 assert.deepEqual(signals.at(-1),{dataTerminalReady:false,requestToSend:false});
});
