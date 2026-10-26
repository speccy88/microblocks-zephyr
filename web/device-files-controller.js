/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 const core=typeof module==='object'&&module.exports?require('./device-files-core.js'):root.MicroBlocksFiles;
 const wire=typeof module==='object'&&module.exports?require('./device-files-wire.js'):root.MicroBlocksFilesWire;
 class Controller {
  constructor({timeout=3000,nonce=()=>root.crypto.getRandomValues(new Uint32Array(1))[0]||1}={}){
   if(!Number.isSafeInteger(timeout)||timeout<10||timeout>10000)throw new core.StorageError('PROTOCOL');
   Object.assign(this,{timeout,nonce,send:null,epoch:0,state:'disconnected',error:null,transport:null,pending:null});
   this.listeners=new Set();this.frames=new Set();
  }
  snapshot(){return Object.freeze({state:this.state,error:this.error,transport:this.transport,epoch:this.epoch});}
  subscribe(fn){this.listeners.add(fn);fn(this.snapshot());return ()=>this.listeners.delete(fn);}
  notify(state,error=null){this.state=state;this.error=error;for(const fn of this.listeners)fn(this.snapshot());}
  drop(){
   if(this.pending)this.pending.done(new core.StorageError('DISCONNECTED'));
   this.transport?.close();this.transport=null;this.frames.clear();
  }
  link(send){
   if(send!==null&&typeof send!=='function')throw new core.StorageError('PROTOCOL');
   if(this.send===send)return;
   this.epoch++;this.drop();this.send=send;this.notify(send?'available':'disconnected');
  }
  receive(frame){
   const p=this.pending;
   if(p&&frame instanceof Uint8Array&&frame.length>=15&&frame[1]===217&&frame[10]===wire.encode(p.request,p.session)[10]&&new DataView(frame.buffer,frame.byteOffset,frame.length).getUint32(11,true)===p.request.id){
    try{const r=wire.decode(frame,p.request,p.session);p.done(r.ok?null:new core.StorageError(r.code),r.data);}catch(e){p.done(e);}
    return;
   }
   for(const fn of this.frames)fn(frame);
  }
  control(request,session){
   if(!this.send||this.pending)return Promise.reject(new core.StorageError(this.send?'BUSY':'DISCONNECTED'));
   const frame=wire.encode(request,session),send=this.send;
   return new Promise((resolve,reject)=>{
    const p={request,session,done:(error,value)=>{if(this.pending!==p)return;clearTimeout(p.timer);this.pending=null;error?reject(error):resolve(value);}};
    this.pending=p;p.timer=setTimeout(()=>p.done(new core.StorageError('TIMEOUT')),this.timeout);
    try{if(send(frame)!==frame.length)p.done(new core.StorageError('DISCONNECTED'));}catch{p.done(new core.StorageError('DISCONNECTED'));}
   });
  }
  async open(){
   if(!this.send)throw new core.StorageError('DISCONNECTED');
   if(this.pending||this.transport)throw new core.StorageError('BUSY');
   const epoch=this.epoch,nonce=this.nonce(),request={version:1,id:nonce,op:'open',args:{nonce}};
   this.notify('connecting');
   try{
    const grant=await this.control(request,0);
    if(epoch!==this.epoch)throw new core.StorageError('DISCONNECTED');
    if(grant.nonce!==nonce)throw new core.StorageError('PROTOCOL');
    const send=this.send;
    this.transport=new wire.Transport({session:grant.session,
     send:frame=>{if(epoch!==this.epoch||this.send!==send||send(frame)!==frame.length)throw new core.StorageError('DISCONNECTED');},
     subscribe:fn=>{this.frames.add(fn);return ()=>this.frames.delete(fn);}});
    this.notify('ready');return this.transport;
   }catch(e){if(epoch===this.epoch)this.notify('error',e.code||'PROTOCOL');throw e;}
  }
  async close(){
   const epoch=++this.epoch,session=this.transport?.session;
   this.drop();this.notify(this.send?'closing':'disconnected');
   try{if(session&&this.send)await this.control({version:1,id:this.nonce(),op:'close',args:{}},session);}
   finally{if(epoch===this.epoch)this.notify(this.send?'available':'disconnected');}
  }
 }
 const api={Controller};
 if(typeof module==='object'&&module.exports)module.exports=api;
 else {root.MicroBlocksFilesController=api;root.MicroBlocksFilesConnection=new Controller();}
})(typeof window==='object'?window:globalThis);
