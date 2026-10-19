// SPDX-License-Identifier: MPL-2.0
// Executes the actual adapter entry points with synthetic providers, no DOM,
// physical serial ports, network connection, project load or credentials.
const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const core=require('../web/portal/portal-core.js');

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
