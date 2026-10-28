// SPDX-License-Identifier: MPL-2.0
const assert=require('node:assert/strict');
const policy=require('../web/js-editor/target-profile.js');
let tests=0;
function test(run){run();tests++;}
function port(){return class {connect(type){this.calls=(this.calls||[]).concat(type);return 42;}};}
test(()=>{assert.throws(()=>policy.get('__proto__'));assert.throws(()=>policy.get('other'));});
test(()=>{const C=port(),p=new C();policy.install(C,'microduck',{href:'http://127.0.0.1:18876/'});for(const type of ['linux-loopback','usb','wifi',null])assert.throws(()=>p.connect(type),/offline editing/);assert.equal(p.calls,undefined);});
test(()=>{const C=port(),p=new C();policy.install(C,'raspberry-pi5',{href:'https://example.com/js-preview/'});assert.throws(()=>p.connect('linux-loopback'),/WSS is not commissioned/);assert.equal(p.calls,undefined);});
test(()=>{const C=port(),p=new C();policy.install(C,'raspberry-pi5',{href:'http://127.0.0.1:18876/'});assert.equal(p.connect('linux-loopback'),42);assert.throws(()=>p.connect('usb'));assert.deepEqual(p.calls,['linux-loopback']);});
test(()=>{const C=port();policy.install(C,'microduck',{href:'https://example.com/'});policy.install(C,'microduck',{href:'https://example.com/'});assert.throws(()=>policy.install(C,'raspberry-pi5',{href:'http://127.0.0.1:18876/'}),/Cannot change/);});
test(()=>{for(const href of ['http://localhost:18876/','http://127.0.0.1:80/','http://user@127.0.0.1:18876/','https://127.0.0.1:18876/'])assert.equal(policy.canConnect(policy.get('raspberry-pi5'),{href}),false);});
test(()=>{const C=port(),p=new C();policy.install(C,'development',{href:'https://example.com/'});assert.equal(p.connect('usb'),42);});
test(()=>{for(const href of ['https://example.com/js-preview/fruit-jam/','http://127.0.0.1:18899/']){const C=port(),p=new C();policy.install(C,'fruit-jam',{href});assert.equal(p.connect('serial'),42);for(const type of ['BLE','boardie','linux-loopback'])assert.throws(()=>p.connect(type),/selected target USB/);assert.deepEqual(p.calls,['serial']);}});
test(()=>{for(const href of ['http://example.com/','http://192.168.1.105/','https://user@example.com/']){const C=port(),p=new C();policy.install(C,'esp32p4',{href});assert.throws(()=>p.connect('serial'),/selected target USB/);assert.equal(p.calls,undefined);}});
test(()=>{let installs=0;const firmware={installVM(){installs++;}};policy.protectFirmware(firmware,'esp32p4');assert.throws(()=>firmware.installVM(),/project firmware installation procedure/);policy.protectFirmware(firmware,'esp32p4');assert.equal(installs,0);const development={installVM(){installs++;}};policy.protectFirmware(development,'development');development.installVM();assert.equal(installs,1);});
console.log(JSON.stringify({tests,passed:tests,hardware:false}));
