// SPDX-License-Identifier: MIT
// RPC216 only; each action owns a connection generation, never an actuator.
(function(root){
 'use strict';
 const messages={1:'Invalid neural request or model metadata.',2:'Neural backend busy; unload the existing model first.',3:'Native neural backend unavailable.',4:'Model or tensor exceeds its limits.',5:'Unsupported model.',6:'Insufficient model memory.',7:'Model reference expired.',8:'Model hash mismatch.',9:'Model or input upload is incomplete.'};
 class Client{
  constructor(broker,core,{timeout=8000}={}){
   if(!Number.isInteger(timeout)||timeout<10||timeout>10000)throw Error('Invalid neural timeout');
   Object.assign(this,{broker,core,timeout,next:0,pending:null,current:{epoch:-1,verified:false},closed:false});
   this.offState=broker.subscribeState(state=>{if(state.epoch!==this.current.epoch||!state.verified)this.settle(Error('Neural session changed. Check the current backend before continuing.'));this.current=state;});
   this.offFrame=broker.subscribe(frame=>this.receive(frame));
  }
  settle(error,value){const p=this.pending;if(!p)return;this.pending=null;clearTimeout(p.timer);error?p.reject(error):p.resolve(value);}
  bind(){
   if(this.closed||!this.current.verified||!this.broker.available())throw Error('Connect and identify the P4 first.');
   const epoch=this.current.epoch;
   return Object.freeze({request:(...args)=>this.request(epoch,...args),valid:()=>!this.closed&&this.current.epoch===epoch&&this.current.verified});
  }
  request(epoch,op,token=0,offset=0,arg=0,data=new Uint8Array(),readCount=0){
   if(this.closed||this.current.epoch!==epoch||!this.current.verified)return Promise.reject(Error('Neural action belongs to a previous connection.'));
   if(this.pending)return Promise.reject(Error('Wait for the current neural request.'));
   if(!Number.isInteger(op)||op<0||op>10||!Number.isInteger(token)||token<0||token>0x1fffffff||!(data instanceof Uint8Array)||this.next===0xffffffff)return Promise.reject(Error('Invalid or exhausted neural request.'));
   let frame;const id=++this.next;
   try{frame=this.core.packet(op,id,token,offset,arg,data,readCount);}catch(e){return Promise.reject(e);}
   return new Promise((resolve,reject)=>{
    const p={id,op,epoch,token,resolve,reject};this.pending=p;
    p.timer=setTimeout(()=>{if(this.pending===p)this.settle(Error('Neural reply timed out; the outcome may be uncertain. Check the backend or reconnect.'));},this.timeout);
    try{if(this.broker.send(frame)!==frame.length)this.settle(Error('Neural request was not queued.'));}catch(e){this.settle(e);}
   });
  }
  receive(frame){
   const p=this.pending;if(!p||frame[1]!==216||p.epoch!==this.current.epoch)return;
   if(frame.length<15||frame.length>1015||frame[0]!==251||frame[2]!==0||frame[3]+256*frame[4]!==frame.length-5){this.settle(Error('Invalid neural response framing.'));return;}
   const b=frame.subarray(5),v=new DataView(b.buffer,b.byteOffset,b.length);
   if(v.getUint32(0,true)!==p.id)return;
   const token=v.getUint32(6,true);
   if(b[5]!==p.op||b[4]>9||token>0x1fffffff||(![1,8].includes(p.op)&&token!==p.token)){this.settle(Error('Neural response does not match the request.'));return;}
   if(b[4])this.settle(Error(messages[b[4]]));else this.settle(null,{token,data:b.slice(10)});
  }
  close(){if(this.closed)return;this.closed=true;this.settle(Error('Neural editor closed.'));this.offState();this.offFrame();}
 }
 const api=Object.freeze({Client});root.MicroBlocksP4Neural=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
