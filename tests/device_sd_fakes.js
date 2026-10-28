/* SPDX-License-Identifier: MIT */
'use strict';
const assert=require('node:assert/strict'),core=require('../web/device-files-core.js'),SD=require('../web/device-sd-core.js'),wire=require('../web/device-files-wire.js');
function fixture(){
 const files=new Map([['SOURCE.TXT',new TextEncoder().encode('Preserved source')]]),owned=new Map(),calls=[];
 let nextJob=0,lastId=0,stage=null,result=null,corrupt=false,delayOp=null;
 const set=(name,bytes,flags,error=0)=>{result={name,bytes:bytes.slice(),flags,error,job:++nextJob};return {job:nextJob};};
 const native={files,owned,calls,get corrupt(){return corrupt;},set corrupt(v){corrupt=v;},set delayOp(v){delayOp=v;},
  async request(r,{signal}={}){
   assert.ok(r.id>lastId);lastId=r.id;calls.push(r.op);
   // Every request must also pass the actual outgoing wire codec.
   wire.encode(r,1);
   if(delayOp===r.op)await new Promise((resolve,reject)=>{signal?.addEventListener('abort',()=>reject(new core.StorageError('CANCELLED')),{once:true});});
   const a=r.args;let data;
   switch(r.op){
   case 'sdCaps':data={available:true,maxBytes:8192,chunkBytes:512,listLimit:8,flags:3};break;
   case 'sdBegin':stage={name:a.name,bytes:new Uint8Array(a.bytes),received:0,job:++nextJob};data={job:stage.job};break;
   case 'sdAppend':assert.equal(a.job,stage.job);assert.equal(a.offset,stage.received);stage.bytes.set(a.bytes,a.offset);stage.received+=a.bytes.length;data={received:stage.received};break;
   case 'sdCreate':{
    assert.equal(a.job,stage.job);const job=stage.job;
    if(files.has(stage.name))result={name:stage.name,bytes:new Uint8Array(),flags:0,error:-17,job};
    else{files.set(stage.name,stage.bytes.slice());owned.set(stage.name,stage.bytes.slice());result={name:stage.name,bytes:stage.bytes.slice(),flags:7,error:0,job};}
    stage=null;data={job};break;
   }
   case 'sdOpen':data=set(a.name,files.get(a.name)||new Uint8Array(),4,files.has(a.name)?0:-2);break;
   case 'sdList':{
    const list=[...files].slice(0,8),bytes=new Uint8Array(1+list.reduce((n,[name])=>n+5+name.length,0));bytes[0]=list.length;let at=1;
    for(const [name,file] of list){new DataView(bytes.buffer).setUint32(at,file.length,true);at+=4;bytes[at++]=name.length;for(const c of name)bytes[at++]=c.charCodeAt(0);}
    data=set('',bytes,4);break;
   }
   case 'sdStatus':assert.equal(a.job,result.job);data={busy:false,error:result.error,bytes:result.bytes.length,flags:result.flags,name:result.name};break;
   case 'sdChunk':assert.equal(a.job,result.job);data={bytes:result.bytes.slice(a.offset,a.offset+a.count)};if(corrupt)data.bytes=new Uint8Array();break;
   case 'sdRemove':{
    assert.ok(owned.has(a.name));const matches=Buffer.from(files.get(a.name)).equals(Buffer.from(owned.get(a.name)));
    if(matches){files.delete(a.name);owned.delete(a.name);}data=set(a.name,new Uint8Array(),matches?12:0,matches?0:-116);break;
   }
   case 'sdCancel':stage=null;data={requested:true};break;
   case 'capabilities':data={version:1,backends:[{name:'RAM',available:true,volatile:true,conditionalWrites:true,maxFiles:8,maxFileBytes:8192,chunkBytes:512},{name:'Flash',available:false},{name:'SD',available:false}]};break;
   default:throw new Error(r.op);
   }
   return {version:1,id:r.id,ok:true,data};
  }};
 const client=new core.Client(native),sd=new SD.Client(client);return {native,client,sd};
}

module.exports={fixture};
