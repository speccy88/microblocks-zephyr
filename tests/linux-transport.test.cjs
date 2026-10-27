// SPDX-License-Identifier: MPL-2.0
const {test}=require('node:test'),assert=require('node:assert/strict');
const {linuxVMWebSocket}=require('../web/portal/portal-core.js');
const local={runtime:'linux',local_bridge:true},published={runtime:'linux'};
test('Linux local bridge permits exactly the loopback editor origin and VM path',()=>{
 for(const host of ['127.0.0.1','localhost']){
  const origin='http://'+host+':8876';
  assert.equal(linuxVMWebSocket(local,origin,'ws://'+host+':8876/ws/vm').href,'ws://'+host+':8876/ws/vm');
  for(const url of ['ws://192.168.1.105:8876/ws/vm','ws://'+host+':8877/ws/vm','ws://'+host+':8876/other','ws://'+host+':8876/ws/vm?token=x','ws://'+host+':8876/ws/vm#x','wss://example.com/ws/vm'])assert.throws(()=>linuxVMWebSocket(local,origin,url));
 }
});
test('Published Linux editors require explicit WSS, never insecure LAN or loopback fallback',()=>{
 for(const origin of ['https://speccy88.github.io','http://192.168.1.105:8876','http://127.0.0.1:8876']){
  assert.equal(linuxVMWebSocket(published,origin,'wss://vm.example/ws/vm').href,'wss://vm.example/ws/vm');
  for(const url of ['ws://192.168.1.105/ws/vm','ws://127.0.0.1:8876/ws/vm','wss://u:p@vm.example/ws/vm','wss://vm.example/ws/vm?token=x','wss://vm.example/ws/vm#x'])assert.throws(()=>linuxVMWebSocket(published,origin,url));
 }
 assert.throws(()=>linuxVMWebSocket({},'http://127.0.0.1:8876','ws://127.0.0.1:8876/ws/vm'));
});
