// SPDX-License-Identifier: MPL-2.0
// Receive-only result snapshots on the existing identified P4 connection.
(function(root){
 'use strict';const MAX_ID=0x1fffffff;
 class Client{
  constructor(broker,core,{known=()=>false,result=()=>{},expired=()=>{},session=()=>{},status=()=>{},crypto=root.crypto,timeout=4000}={}){
   if(!Number.isInteger(timeout)||timeout<10||timeout>10000)throw Error('Invalid media timeout');
   Object.assign(this,{broker,core,known,result,expired,onSession:session,status,crypto,timeout,next:0,pending:null,session:0,generation:0,viewEpoch:0,current:{epoch:-1,verified:false},closed:false,fetching:false});
   this.latest=new Map();this.queued=new Set();this.accept=false;this.seed=null;this.sessions=0;this.ready=Promise.resolve();
   this.offFrames=broker.subscribe(frame=>this.receive(frame));
   this.offState=broker.subscribeState(state=>{if(state.epoch===this.current.epoch&&state.verified===this.current.verified)return;this.current=state;this.reset();if(state.verified)this.ready=this.start().catch(e=>{if(!this.closed&&this.current.verified)this.notify(this.status,e.message);});});
  }
  settle(error,value){const p=this.pending;if(!p)return;this.pending=null;clearTimeout(p.timer);error?p.reject(error):p.resolve(value);}
  notify(fn,...args){try{fn(...args);}catch{/* A view failure must not break the VM connection. */}}
  discard(){this.accept=false;this.viewEpoch++;this.queued.clear();for(const uid of this.latest.keys())this.notify(this.expired,uid);this.latest.clear();this.settle(Error('Media view changed.'));}
  reset(){this.generation++;this.session=0;this.notify(this.onSession,0);this.discard();}
  request(op,token=0,uid=0,offset=0,count=0,session=this.session){
   if(this.closed||!this.broker.available())return Promise.reject(Error('Media is disconnected.'));
   if(this.pending)return Promise.reject(Error('Media request already active.'));
   if(this.next===0xffffffff)return Promise.reject(Error('Media request IDs exhausted.'));
   for(const n of [session,token,uid,offset,count])if(!Number.isInteger(n)||n<0||n>0xffffffff)return Promise.reject(Error('Invalid media request.'));
   if(!Number.isInteger(op)||op<0||op>5||count>512||uid>MAX_ID||session>MAX_ID)return Promise.reject(Error('Media request bounds exceeded.'));
   const id=++this.next,frame=this.core.packet(id,op,session,token,offset,count,uid);
   return new Promise((resolve,reject)=>{const p={id,op,session,token,resolve,reject};this.pending=p;p.timer=setTimeout(()=>{if(this.pending===p)this.settle(Error('Media response timed out.'));},this.timeout);
    try{if(this.broker.send(frame)!==frame.length)this.settle(Error('Media request was not queued.'));}catch(e){this.settle(e);}
   });
  }
  async start(){
   const generation=this.generation,caps=JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await this.request(0,0,0,0,0,0)));
   if(generation!==this.generation)return;
   if(!caps||Array.isArray(caps)||caps.protocol!==1||caps.chunk_bytes!==512||!Number.isInteger(caps.slots)||caps.slots<1||caps.slots>4||!Number.isInteger(caps.budget)||caps.budget<1||caps.budget>524288||caps.image_width!==160||caps.image_height!==90||caps.audio_frames!==128000)throw Error('Native inline media capabilities require review.');
   await this.negotiate(generation);
  }
  async negotiate(generation){
   if(this.sessions>=MAX_ID)throw Error('Media session IDs exhausted; reopen the editor.');
   if(this.seed===null){const random=new Uint32Array(1);this.crypto.getRandomValues(random);this.seed=random[0]&MAX_ID;}
   const nonce=((this.seed+this.sessions++)%MAX_ID)+1;
   await this.request(1,0,0,0,0,nonce);if(generation!==this.generation)return;
   this.session=nonce;this.accept=true;this.notify(this.onSession,nonce);this.notify(this.status,'Inline image/audio results ready.');
  }
  async renew(){
   await this.ready;if(!this.session)return false;
   this.reset();await this.negotiate(this.generation);return !!this.session;
  }
  receive(frame){
   if(this.closed||!(frame instanceof Uint8Array)||frame[0]!==251)return;
   const body=frame.subarray(5);if(frame[3]+256*frame[4]!==body.length)return;
   if(frame[1]===208){
    const p=this.pending;if(!p||body.length<14)return;const v=new DataView(body.buffer,body.byteOffset,body.length);
    if(v.getUint32(0,true)!==p.id)return;
    if(body[5]!==p.op||v.getUint32(6,true)!==p.session||v.getUint32(10,true)!==p.token||body[4]>1){this.settle(Error('Media reply does not match the request.'));return;}
    this.settle(body[4]?Error('Media result expired or unavailable.'):null,body.slice(14));
   }else if(frame[1]===209&&body.length===12&&this.session&&this.accept){
    const v=new DataView(body.buffer,body.byteOffset,body.length),uid=v.getUint32(4,true),token=v.getUint32(8,true);
    if(v.getUint32(0,true)!==this.session||uid<1||uid>MAX_ID||!this.known(uid))return;
    if(this.latest.size>=128&&!this.latest.has(uid))return;
    this.latest.set(uid,token);
    if(!token){this.queued.delete(uid);this.notify(this.expired,uid);return;}
    if(this.queued.size>=16&&!this.queued.has(uid)){const old=this.queued.values().next().value;this.queued.delete(old);this.notify(this.expired,old);}
    this.queued.add(uid);void this.fetchQueue();
   }
  }
  async fetchQueue(){
   if(this.fetching)return;this.fetching=true;
   try{while(this.queued.size){
    const uid=this.queued.values().next().value;this.queued.delete(uid);const token=this.latest.get(uid),session=this.session,generation=this.generation,viewEpoch=this.viewEpoch;
    const current=()=>generation===this.generation&&viewEpoch===this.viewEpoch&&this.latest.get(uid)===token&&this.known(uid);let raw;
    try{
     if(!session||!token||!current())continue;
     const meta=this.core.metadata(JSON.parse(new TextDecoder('utf-8',{fatal:true}).decode(await this.request(2,token,uid,0,0,session))));if(!current())throw Error('Media site changed.');raw=new Uint8Array(meta.bytes);
     for(let offset=0;offset<raw.length;offset+=512){if(!current())throw Error('Media result replaced.');const count=Math.min(512,raw.length-offset),part=await this.request(3,token,uid,offset,count,session);try{if(!current()||part.length!==count)throw Error('Short or replaced media result.');raw.set(part,offset);}finally{part.fill(0);}}
     if(current())await this.result(uid,meta,raw);
    }catch{if(current())this.notify(this.expired,uid);}
    finally{if(raw)raw.fill(0);if(session&&session===this.session&&generation===this.generation){try{await this.request(4,token,uid,0,0,session);}catch{}}}
   }}finally{this.fetching=false;}
  }
  close(){if(this.closed)return;this.closed=true;this.offState();this.offFrames();this.reset();}
 }
 const api=Object.freeze({Client,MAX_ID});root.MicroBlocksP4MediaClient=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
