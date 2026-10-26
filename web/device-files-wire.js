/* SPDX-License-Identifier: MIT */
// Injected existing-controller frames only. This module never opens a connection.
((root)=>{
 'use strict';
 const core=typeof module==='object'&&module.exports?require('./device-files-core.js'):root.MicroBlocksFiles;
 const TYPE=217,MAX=0x3fffffff,CHUNK=512,RESPONSE_MAX=640;
 const OPS=Object.freeze({capabilities:1,list:2,stat:3,read:4,begin:5,append:6,finish:7,cancel:8,open:9,close:10});
 const STATUS=['','PROTOCOL','DISCONNECTED','PATH','UNAVAILABLE','SIZE','BUSY','CONFLICT','EXISTS','NOT_FOUND','FULL','CANCELLED','TIMEOUT','STATE'];
 const fail=code=>{throw new core.StorageError(code);};
 const bounded=(n,min,max)=>Number.isSafeInteger(n)&&n>=min&&n<=max;
 const need=(n,min,max)=>{if(!bounded(n,min,max))fail('PROTOCOL');return n;};
 const ref=value=>{if(typeof value!=='string'||!/^r[1-9][0-9]{0,9}$/.test(value))fail('PROTOCOL');return need(Number(value.slice(1)),1,MAX);};
 function encode(request,session){
  need(session,request?.op==='open'?0:1,MAX);if(request?.op==='open'&&session!==0)fail('PROTOCOL');
  if(!request||request.version!==1||!OPS[request.op]||!request.args)fail('PROTOCOL');
  const id=need(request.id,1,0xffffffff),a=request.args,op=OPS[request.op];
  let path='',token=0,arg=0,count=0,data=new Uint8Array();
  if(['stat','read','begin'].includes(request.op))path=core.path(a.path);
  switch(request.op){
   case 'list':if(a.backend!=='RAM')fail('UNAVAILABLE');break;
   case 'read':token=ref(a.revision);arg=need(a.offset,0,8192);count=need(a.count,0,CHUNK);if(arg+count>8192)fail('SIZE');break;
   case 'begin':token=a.expectedRevision===null?0:ref(a.expectedRevision);arg=need(a.bytes,0,8192);break;
   case 'append':
    token=need(a.job,1,MAX);arg=need(a.offset,0,8192);
    if(!(a.bytes instanceof Uint8Array))fail('PROTOCOL');count=need(a.bytes.length,1,CHUNK);
    if(arg+count>8192)fail('SIZE');data=a.bytes;break;
   case 'finish':case 'cancel':token=need(a.job,1,MAX);break;
   case 'open':token=need(a.nonce,1,0xffffffff);break;
  }
  const bodyLength=26+path.length+data.length,frame=new Uint8Array(bodyLength+6),v=new DataView(frame.buffer,5,bodyLength);
  frame.set([251,TYPE,0,(bodyLength+1)&255,(bodyLength+1)>>8]);frame.set([77,66,70,83,1,op],5);
  v.setUint32(6,id,true);v.setUint32(10,session,true);v.setUint32(14,token,true);v.setUint32(18,arg,true);
  v.setUint16(22,count,true);v.setUint8(24,path.length);
  for(let i=0;i<path.length;i++)v.setUint8(26+i,path.charCodeAt(i));
  frame.set(data,31+path.length);frame[frame.length-1]=254;return frame;
 }
 function decode(frame,request,session){
  if(!(frame instanceof Uint8Array)||frame.length<21||frame.length>RESPONSE_MAX+5||
    frame[0]!==251||frame[1]!==TYPE||frame[2]!==0||frame[3]+256*frame[4]!==frame.length-5)fail('PROTOCOL');
  // Pinned SmallVM sendMessage() emits body bytes without the request terminator.
  const b=frame.subarray(5),v=new DataView(b.buffer,b.byteOffset,b.length);let at=16;
  if(b[0]!==77||b[1]!==66||b[2]!==70||b[3]!==82||b[4]!==1||b[5]!==OPS[request.op]||
    v.getUint32(6,true)!==request.id||v.getUint32(10,true)!==session||b[15]||b[14]>=STATUS.length)fail('PROTOCOL');
  const take=n=>{if(n>b.length-at)fail('PROTOCOL');const pos=at;at+=n;return pos;};
  const u8=()=>v.getUint8(take(1)),u16=()=>v.getUint16(take(2),true),u32=()=>v.getUint32(take(4),true);
  const revision=()=> 'r'+need(u32(),1,MAX);
  const meta=()=>{
   const r=revision(),bytes=u16(),n=need(u8(),1,63),start=take(n);let path='';
   for(let i=0;i<n;i++)path+=String.fromCharCode(b[start+i]);
   return core.metadata({path,bytes,revision:r});
  };
  let result;
  if(b[14]){if(at!==b.length)fail('PROTOCOL');return {version:1,id:request.id,ok:false,code:STATUS[b[14]]};}
  switch(request.op){
   case 'capabilities':{
    const maxFiles=u8(),maxFileBytes=u16(),chunkBytes=u16();if(u8()!==3||u8()!==1||chunkBytes>CHUNK)fail('PROTOCOL');
    result={version:1,backends:[{name:'RAM',available:true,volatile:true,conditionalWrites:true,maxFiles,maxFileBytes,chunkBytes},{name:'Flash',available:false},{name:'SD',available:false}]};
    core.capabilities(result);break;
   }
   case 'list':{
    const count=need(u8(),0,8),freeSlots=need(u8(),0,8),used=u32(),files=[];
    for(let i=0;i<count;i++)files.push(meta());
    result={files,freeSlots,used};core.fileList(result,{maxFiles:8,maxFileBytes:8192});break;
   }
   case 'stat':case 'finish':result=meta();break;
   case 'read':{
    const r=revision(),count=need(u16(),0,CHUNK),start=take(count);result={revision:r,bytes:b.slice(start,start+count)};break;
   }
   case 'begin':result={job:need(u32(),1,MAX)};break;
   case 'append':result={received:need(u16(),0,8192)};break;
   case 'cancel':if(u8()!==1)fail('PROTOCOL');result={cancelled:true};break;
   case 'open':result={session:need(u32(),1,MAX),nonce:need(u32(),1,0xffffffff)};break;
   case 'close':if(u8()!==1)fail('PROTOCOL');result={closed:true};break;
   default:fail('PROTOCOL');
  }
  if(at!==b.length)fail('PROTOCOL');return {version:1,id:request.id,ok:true,data:result};
 }
 class Transport {
  // session comes from a trusted controller grant, never from a project/block.
  // subscribe accepts COMPLETE existing VM frames, not arbitrary stream chunks.
  constructor({session,send,subscribe}){
   need(session,1,MAX);if(typeof send!=='function'||typeof subscribe!=='function')fail('PROTOCOL');
   this.session=session;this.send=send;this.pending=null;this.lastId=0;this.closed=false;
   this.unsubscribe=subscribe(frame=>this.receive(frame));
   if(typeof this.unsubscribe!=='function'){this.closed=true;fail('PROTOCOL');}
  }
  settle(error,reply){
   const p=this.pending;if(!p)return;this.pending=null;p.signal?.removeEventListener('abort',p.abort);
   if(error)p.reject(error);else p.resolve(reply);
  }
  receive(frame){
   if(this.closed||!this.pending||!(frame instanceof Uint8Array)||frame[1]!==TYPE)return;
   // Drop late responses without allowing them to resolve a newer request.
   if(frame.length>=19){const v=new DataView(frame.buffer,frame.byteOffset,frame.length);if(v.getUint32(11,true)!==this.pending.request.id||v.getUint32(15,true)!==this.session)return;}
   try{this.settle(null,decode(frame,this.pending.request,this.session));}
   catch(e){this.settle(e instanceof core.StorageError?e:new core.StorageError('PROTOCOL'));}
  }
  request(request,{signal}={}){
   if(this.closed)return Promise.reject(new core.StorageError('DISCONNECTED'));
   if(this.pending)return Promise.reject(new core.StorageError('BUSY'));
   if(signal?.aborted)return Promise.reject(new core.StorageError('CANCELLED'));
   let frame;try{if(request.id<=this.lastId)fail('PROTOCOL');frame=encode(request,this.session);}catch(e){return Promise.reject(e);}
   this.lastId=request.id;
   return new Promise((resolve,reject)=>{
    const pending={request:{id:request.id,op:request.op},signal,resolve,reject,abort:()=>this.settle(new core.StorageError('CANCELLED'))};
    this.pending=pending;signal?.addEventListener('abort',pending.abort,{once:true});
    // send completion alone is never a successful file reply.
    try{Promise.resolve(this.send(frame)).catch(()=>{if(this.pending===pending)this.settle(new core.StorageError('DISCONNECTED'));});}
    catch{if(this.pending===pending)this.settle(new core.StorageError('DISCONNECTED'));}
   });
  }
  close(){if(this.closed)return;this.closed=true;this.settle(new core.StorageError('DISCONNECTED'));this.unsubscribe();}
 }
 const api={TYPE,CHUNK,encode,decode,Transport};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroBlocksFilesWire=api;
})(typeof window==='object'?window:globalThis);
