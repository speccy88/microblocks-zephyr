// SPDX-License-Identifier: MPL-2.0
const assert=require('node:assert/strict');
const {USBPort,install,MAX_INPUT,MAX_OUTPUT}=require('../web/js-editor/board-transport.js');
const catalog=require('../dependencies/editor-targets.json').targets;
const tick=()=>new Promise(resolve=>setImmediate(resolve));
const deferred=()=>{let resolve,reject;const promise=new Promise((a,b)=>{resolve=a;reject=b;});return {promise,resolve,reject};};
function device(){
 const pending=[],writes=[],signals=[];let readerMade=0,closed=0,opened=0;
 const reader={read(){const d=deferred();pending.push(d);return d.promise;},async cancel(){for(const d of pending.splice(0))d.resolve({done:true});},releaseLock(){}};
 const writer={async write(bytes){writes.push(bytes.slice());},async abort(){},releaseLock(){}};
 const port={async open(options){opened++;assert.equal(options.baudRate,115200);},async close(){closed++;},async setSignals(value){signals.push(value);},
  readable:{getReader(){readerMade++;return reader;}},writable:{getWriter(){return writer;}}};
 return {port,reader,writer,writes,signals,feed(value){assert(pending.length);pending.shift().resolve({value,done:false});},get opened(){return opened;},get closed(){return closed;},get readerMade(){return readerMade;}};
}
function connectionClasses(){
 class Port {isConnected(){return this.ready!==false;}read(){return new Uint8Array();}write(bytes){this.sent.push(bytes.slice());return bytes.length;}disconnect(){this.ready=false;}connect(){}}
 class Connection {
  constructor(){this.port=new Port();this.port.sent=[];this.sendQueue=Promise.resolve();this.recvBuf=new Uint8Array([251,17,0]);this.serialDelay=0;}
  connect(){this.port=new Port();this.port.sent=[];}
  disconnect(){if(this.port)this.port.disconnect();this.port=null;}
  isConnected(){return !!this.port&&this.port.isConnected();}
  sendMsg(){throw Error('Original writer must not be used');}
  msgNameToID(name){return Number.isInteger(name)?name:{getVersionMsg:12,pingMsg:26,stopAllMsg:6,chunkCode16Msg:32,extendedMsg:30}[name];}
  extractBoardType(text){return text.split(' ').slice(1).join(' ');}
  extractVersionNumber(text){return Number(text.split(' ')[0].slice(1));}
  versionReceived(text){this.vmVersion=this.extractVersionNumber(text);this.boardType=this.extractBoardType(text);}
  async sendMsgSync(name){await this.sendMsg(name);if(this.reply)this.versionReceived(this.reply);}
  processMessages(){}async waitForVersion(){}pushToIDE(){}setSerialDelay(){this.serialDelay++;}
  async justConnected(){throw Error('Original handshake must not upload');}
 }
 return {Port,Connection};
}
async function main(){let passed=0;
 async function test(run){await run();passed++;}
 await test(async()=>{
  const d=device(),seen=[];const p=new USBPort({async requestPort(options){seen.push(options);return d.port;}},catalog.propeller2);
  await p.connect();assert(p.isConnected());assert.deepEqual(seen,[{filters:[{usbVendorId:0x0403}]}]);assert.deepEqual(d.signals[0],{dataTerminalReady:false,requestToSend:false});
  const original=new Uint8Array([1,2,3,4]);assert.equal(p.write(original.subarray(1,3)),2);original.fill(9);await p.chain;assert.deepEqual([...d.writes[0]],[2,3]);
  d.feed(new Uint8Array([4,5]));await tick();assert.deepEqual([...p.read()],[4,5]);assert.equal(p.read().length,0);await p.disconnect();assert.equal(d.closed,1);
 });
 await test(async()=>{
  const choose=deferred(),d=device();let calls=0;const p=new USBPort({requestPort(){calls++;return choose.promise;}},catalog['fruit-jam']);
  const opening=p.connect();await p.disconnect();choose.resolve(d.port);await opening;assert.equal(calls,1);assert.equal(d.opened,0);assert.equal(d.closed,0);assert(!p.isConnected());
 });
 await test(async()=>{
  const opening=deferred(),d=device();d.port.open=()=>opening.promise;const p=new USBPort({async requestPort(){return d.port;}},catalog['fruit-jam']);
  const attempt=p.connect();await tick();await p.disconnect();opening.resolve();await attempt;assert.equal(d.readerMade,0);assert.equal(d.closed,1);assert(d.signals.every(x=>x.dataTerminalReady===false));
 });
 await test(async()=>{
  const d=device(),errors=[];const p=new USBPort({async requestPort(){return d.port;}},catalog.esp32p4,error=>errors.push(error));await p.connect();d.feed(new Uint8Array(MAX_INPUT+1));await tick();await p.disconnect();assert(errors.includes('USB input limit exceeded'));assert.equal(p.read().length,0);assert.equal(d.closed,1);
 });
 await test(async()=>{
  const d=device(),write=deferred();d.writer.write=()=>write.promise;d.writer.abort=async()=>write.reject(Error('Aborted'));
  const p=new USBPort({async requestPort(){return d.port;}},catalog.esp32p4);await p.connect();for(let n=0;n<MAX_OUTPUT/4096;n++)assert.equal(p.write(new Uint8Array(4096)),4096);assert.equal(p.write(new Uint8Array([1])),0);await tick();await p.disconnect();await p.chain;assert.equal(p.pending,0);assert.equal(d.closed,1);
 });
 await test(async()=>{
  const d=device(),p=new USBPort({async requestPort(){return d.port;}},catalog.esp32p4);await p.connect();d.port.setSignals=async()=>{throw Error('Signals unavailable');};await p.disconnect();assert.equal(d.closed,1);
 });
 await test(async()=>{
  const p=new USBPort(null,catalog.esp32p4);await assert.rejects(p.connect(),/Web Serial/);assert(!p.isConnected());assert.throws(()=>p.write(new Uint8Array(4097)),/1..4096/);
 });
 await test(async()=>{
  const {Port,Connection}=connectionClasses(),errors=[];let downloads=0;const api=install(Port,Connection,{...catalog['fruit-jam'],id:'fruit-jam'},null,()=>({clearRunningHighlights(){},async justConnected(){downloads++;}}),e=>errors.push(e));
  const c=new Connection(),wire=c.port;assert.equal(await c.sendMsg('chunkCode16Msg',1,[2,3]),false);assert.equal(wire.sent.length,0);
  c.reply='v417 Fruit Jam RP2350B Zephyr (experimental)';await c.justConnected();assert(api.verified(c));assert.equal(downloads,1);assert.equal(c.serialDelay,1);assert.deepEqual(wire.sent.slice(0,2).map(x=>x[1]),[12,6]);assert.equal(await c.sendMsg('chunkCode16Msg',1,[2,3]),true);
  c.disconnect();assert(!api.verified(c));assert.equal(c.recvBuf.length,0);
 });
 await test(async()=>{
  const {Port,Connection}=connectionClasses();let downloads=0;install(Port,Connection,{...catalog['fruit-jam'],id:'fruit-jam'},null,()=>({clearRunningHighlights(){},async justConnected(){downloads++;}}));
  const c=new Connection(),wire=c.port;c.reply='v417 Waveshare ESP32-P4 WIFI6 Zephyr';await c.justConnected();assert.equal(downloads,0);assert.equal(c.port,null);assert.deepEqual(wire.sent.map(x=>x[1]),[12]);
 });
 await test(async()=>{
  const {Port,Connection}=connectionClasses();install(Port,Connection,{...catalog.propeller2,id:'propeller2'},null,()=>({clearRunningHighlights(){},async justConnected(){}}));
  const c=new Connection();c.versionReceived('v417 Parallax P2 Edge');assert.equal(c.port,null);
 });
 await test(async()=>{
  const {Port,Connection}=connectionClasses();install(Port,Connection,{...catalog.esp32p4,id:'esp32p4'},null,()=>({clearRunningHighlights(){},async justConnected(){}}));
  const c=new Connection();c.versionReceived('v417 Waveshare ESP32-P4 WIFI6 Zephyr');const blocker=deferred();c.sendQueue=blocker.promise;const pending=c.sendMsg('chunkCode16Msg',1,[2,3]);c.disconnect();const replacement=new Port();replacement.sent=[];c.port=replacement;c.versionReceived('v417 Waveshare ESP32-P4 WIFI6 Zephyr');blocker.resolve();assert.equal(await pending,false);assert.equal(replacement.sent.length,0);
 });
 await test(async()=>{
  const {Port,Connection}=connectionClasses();install(Port,Connection,{...catalog.esp32p4,id:'esp32p4'},null,()=>({clearRunningHighlights(){},async justConnected(){}}));
  const c=new Connection(),wire=c.port;c.versionReceived('v417 Waveshare ESP32-P4 WIFI6 Zephyr');const body=Array.from({length:200},(_,i)=>i);const first=c.sendMsg('chunkCode16Msg',3,body),second=c.sendMsg('pingMsg',4);await Promise.all([first,second]);const bytes=wire.sent.flatMap(x=>[...x]);assert.deepEqual(bytes,[251,32,3,201,0,...body,254,250,26,4]);assert(wire.sent.every(x=>x.length<=63));
 });
 await test(async()=>{
  const {Port,Connection}=connectionClasses();const d=device(),closing=deferred();let requests=0;
  d.port.close=()=>closing.promise;install(Port,Connection,{...catalog.esp32p4,id:'esp32p4'},{async requestPort(){requests++;return d.port;}},()=>({}));
  const first=new Port();first.connect('serial');await tick();await tick();assert(first.isConnected());
  // A read-side failure begins cleanup outside the connection controller.
  d.feed(new Uint8Array(MAX_INPUT+1));await tick();
  const second=new Port();assert.throws(()=>second.connect('serial'),/cleanup is still pending/);assert.equal(requests,1);
  closing.resolve();await tick();await tick();second.connect('serial');await tick();await tick();assert.equal(requests,2);second.disconnect();await tick();
 });
 await test(async()=>{
  const {Port,Connection}=connectionClasses();install(Port,Connection,{...catalog.propeller2,id:'propeller2'},null,()=>({}));
  for(const text of ['x405 Parallax P2 Edge','v405 Parallax P2evil','v405 Parallax P2 Edge\n']){const c=new Connection();c.versionReceived(text);assert.equal(c.port,null);}
 });
 console.log(JSON.stringify({passed,physical_hardware:false,usb_provider:'faithful ownership fixture'}));
}
main().catch(error=>{console.error(error);process.exitCode=1;});
