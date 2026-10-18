/* SPDX-License-Identifier: MPL-2.0 */
/* Browser-only project data and bounded byte-stream transports. No telemetry. */
(function(root){
 'use strict';
 const MAX_PROJECT=4*1024*1024,MAX_QUEUE=65536;
 class ProjectStore{
  constructor(indexedDB=root.indexedDB){this.provider=indexedDB;this.opened=null;}
  open(){
   if(!this.provider)return Promise.reject(new Error('Browser storage is unavailable. Export a project file.'));
   if(!this.opened)this.opened=new Promise((resolve,reject)=>{
    const request=this.provider.open('microblocks-zephyr-projects',1);
    request.onupgradeneeded=()=>request.result.createObjectStore('projects',{keyPath:'id'});
    request.onsuccess=()=>resolve(request.result);
    request.onerror=()=>reject(new Error('Cannot open browser storage. Export a project file.'));
    request.onblocked=()=>reject(new Error('Close other portal tabs to open browser storage.'));
   });return this.opened;
  }
  async save(board,id,name,source){
   if(typeof source!=='string'||new TextEncoder().encode(source).length>MAX_PROJECT)throw Error('Project exceeds the 4 MiB browser-save limit.');
   const database=await this.open();
   const item={id:board+':'+id,board,name:String(name).slice(0,120),source,updated:new Date().toISOString()};
   await new Promise((resolve,reject)=>{
    const transaction=database.transaction('projects','readwrite');transaction.objectStore('projects').put(item);
    transaction.oncomplete=resolve;
    transaction.onerror=transaction.onabort=()=>reject(Error('Browser save failed. Storage may be full or disabled. Export a project file.'));
   });return item;
  }
  async list(board){
   const database=await this.open();return new Promise((resolve,reject)=>{
    const request=database.transaction('projects').objectStore('projects').getAll();
    request.onsuccess=()=>resolve(request.result.filter(item=>item.board===board).sort((a,b)=>b.updated.localeCompare(a.updated)));
    request.onerror=()=>reject(Error('Cannot read saved projects.'));
   });
  }
 }
 class ByteQueue{
  constructor(){this.parts=[];this.bytes=0;}
  clear(){for(const p of this.parts)p.fill(0);this.parts=[];this.bytes=0;}
  push(data){if(this.bytes+data.length>MAX_QUEUE)throw Error('Board input queue is full. Reconnect the board.');this.parts.push(data.slice());this.bytes+=data.length;}
  read(max){const out=new Uint8Array(Math.min(max,this.bytes));let pos=0;
   while(pos<out.length){const p=this.parts[0],n=Math.min(p.length,out.length-pos);out.set(p.subarray(0,n),pos);pos+=n;
    if(n===p.length)this.parts.shift();else this.parts[0]=p.subarray(n);}
   this.bytes-=out.length;return out;
  }
 }
 class SerialTransport{
  constructor(provider,filters,onData,onState){Object.assign(this,{provider,filters,onData,onState});this.port=null;this.reader=null;this.writer=null;this.pending=0;this.chain=Promise.resolve();this.closing=false;}
  async connect(){
   if(this.port||this.connecting)return;
   if(this.closing)throw Error('USB is still disconnecting. Connect again when it finishes.');
   if(!this.provider)throw Error('USB needs desktop Chrome or Edge with Web Serial.');
   this.connecting=true;
   try{
    const port=await this.provider.requestPort({filters:this.filters});this.port=port;
    await port.open({baudRate:115200,bufferSize:8192});
    await port.setSignals({dataTerminalReady:true,requestToSend:false});
    this.reader=port.readable.getReader();this.writer=port.writable.getWriter();this.closing=false;
    this.onState(true);this.loop=this.readLoop(port,this.reader);
   }catch(error){await this.disconnect();throw error;}finally{this.connecting=false;}
  }
  async readLoop(port,reader){
   try{while(!this.closing&&this.port===port){const {value,done}=await reader.read();if(done)break;if(value)this.onData(value);}}
   catch(error){if(!this.closing)this.onState(false,'USB connection closed.');}
   finally{if(!this.closing&&this.port===port)await this.disconnect();}
  }
  write(data){
   if(!this.writer||this.closing)return 0;
   if(this.pending+data.length>MAX_QUEUE){this.onState(false,'Board output queue is full.');void this.disconnect();return 0;}
   const copy=data.slice(),writer=this.writer;this.pending+=copy.length;
   this.chain=this.chain.then(()=>writer.write(copy)).catch(()=>{this.onState(false,'USB write failed.');void this.disconnect();})
    .finally(()=>{this.pending-=copy.length;copy.fill(0);});return data.length;
  }
  async disconnect(){
   if(this.closing)return;this.closing=true;
   const reader=this.reader,writer=this.writer,port=this.port;this.reader=null;this.writer=null;this.port=null;
   try{if(reader){await reader.cancel();reader.releaseLock();}}catch{}
   try{await this.chain;}catch{}
   try{if(writer)writer.releaseLock();}catch{}
   try{if(port){await port.setSignals({dataTerminalReady:false,requestToSend:false});await port.close();}}catch{}
   this.onState(false);this.closing=false;
  }
 }
 const api={ProjectStore,ByteQueue,SerialTransport,MAX_PROJECT,MAX_QUEUE};
 root.MicroBlocksPortal=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
