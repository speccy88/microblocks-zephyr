/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 const core=typeof module==='object'&&module.exports?require('./device-files-core.js'):root.MicroBlocksFiles;
 const fail=code=>{throw new core.StorageError(code);};
 const validName=value=>typeof value==='string'&&/^[A-Z0-9_]{1,8}(\.[A-Z0-9_]{1,3})?$/.test(value);
 function name(value){if(!validName(value))fail('PATH');return value;}
 const delay=(signal)=>new Promise((resolve,reject)=>{
  if(signal.aborted){reject(new core.StorageError('CANCELLED'));return;}
  const finish=()=>{signal.removeEventListener('abort',abort);resolve();};
  const timer=setTimeout(finish,50),abort=()=>{clearTimeout(timer);signal.removeEventListener('abort',abort);reject(new core.StorageError('CANCELLED'));};
  signal.addEventListener('abort',abort,{once:true});
 });
 class Client {
  /* Shares the existing granted file controller, ID sequence and cancellation
   * owner. Does not open a socket, browser proxy or alternative permission path. */
  constructor(client,{now=()=>performance.now()}={}){this.client=client;this.now=now;this.caps=null;this.ownNames=new Set();}
  async available(){return this.client.run(async signal=>{
   try{const caps=await this.client.rpc('sdCaps',{},signal);this.caps=caps;return caps.available;}
   catch(e){if(['PROTOCOL','UNAVAILABLE'].includes(e.code)){this.caps=null;return false;}throw e;}
  });}
  async wait(job,signal){
   const began=this.now();
   while(this.now()-began<=40000){
    const status=await this.client.rpc('sdStatus',{job},signal);
    if(!status.busy){
     if(status.error){
      const error=new core.StorageError('STATE');error.native=status.error;error.flags=status.flags;
      error.message=status.flags&1?'SD write could not be verified; a partial file may remain. Open or inspect it before another write.':`SD operation failed (${status.error}). No automatic retry was made.`;throw error;
     }
     if(!(status.flags&4))fail('PROTOCOL');return status;
    }
    await delay(signal);
   }
   fail('TIMEOUT');
  }
  async bytes(job,length,signal){
   if(!Number.isSafeInteger(length)||length<0||length>8192)fail('PROTOCOL');
   const output=new Uint8Array(length);
   for(let offset=0;offset<length;offset+=512){
    const count=Math.min(512,length-offset),part=await this.client.rpc('sdChunk',{job,offset,count},signal);
    if(!(part.bytes instanceof Uint8Array)||part.bytes.length!==count)fail('PROTOCOL');output.set(part.bytes,offset);
   }
   return output;
  }
  async cancelJob(job){
   if(job===null)return;
   try{await this.client.rpc('sdCancel',{job},new AbortController().signal,500);}catch{}
  }
  async list(){return this.client.run(async signal=>{
   let job=null;
   try{
    ({job}=await this.client.rpc('sdList',{},signal));const status=await this.wait(job,signal);
    const data=await this.bytes(job,status.bytes,signal);
    if(!data.length||data[0]>8)fail('PROTOCOL');const files=[],view=new DataView(data.buffer,data.byteOffset,data.byteLength);let at=1;
    for(let i=0;i<data[0];i++){
     if(data.length-at<5)fail('PROTOCOL');const bytes=view.getUint32(at,true),size=data[at+4];at+=5;
     if(!size||size>12||size>data.length-at)fail('PROTOCOL');let value='';for(let k=0;k<size;k++)value+=String.fromCharCode(data[at++]);
     name(value);if(files.some(file=>file.name===value))fail('PROTOCOL');files.push(Object.freeze({name:value,bytes}));
    }
    if(at!==data.length)fail('PROTOCOL');return {files,truncated:!!(status.flags&16)};
   }catch(e){await this.cancelJob(job);throw e;}
  });}
  async read(value){name(value);return this.client.run(async signal=>{
   let job=null;
   try{({job}=await this.client.rpc('sdOpen',{name:value},signal));const status=await this.wait(job,signal);
    if(status.name!==value)fail('PROTOCOL');return {name:value,bytes:await this.bytes(job,status.bytes,signal)};
   }catch(e){await this.cancelJob(job);throw e;}
  });}
  async create(value,data){
   name(value);if(!(data instanceof Uint8Array)||data.length>8192)fail('SIZE');const owned=data.slice();
   return this.client.run(async signal=>{
    let job=null,commit=false;
    try{
     ({job}=await this.client.rpc('sdBegin',{name:value,bytes:owned.length},signal));
     for(let offset=0;offset<owned.length;offset+=512){
      const part=owned.slice(offset,Math.min(offset+512,owned.length));
      const reply=await this.client.rpc('sdAppend',{job,offset,bytes:part},signal);if(reply.received!==offset+part.length)fail('PROTOCOL');
     }
     commit=true;const started=await this.client.rpc('sdCreate',{job},signal);if(started.job!==job)fail('PROTOCOL');
     const status=await this.wait(job,signal);if(status.name!==value||status.bytes!==owned.length||(status.flags&7)!==7)fail('PROTOCOL');
     const reread=await this.bytes(job,status.bytes,signal);if(reread.some((v,i)=>v!==owned[i]))fail('PROTOCOL');
     this.ownNames.add(value);return {name:value,bytes:reread};
    }catch(e){
     if(commit&&(Number.isInteger(e.flags)?!!(e.flags&1):['TIMEOUT','CANCELLED','DISCONNECTED','PROTOCOL'].includes(e.code)))this.client.uncertain=true;
     await this.cancelJob(job);throw e;
    }
    finally{owned.fill(0);}
   },true).finally(()=>owned.fill(0));
  }
  async removeOwn(value){name(value);if(!this.ownNames.has(value))fail('STATE');
   return this.client.run(async signal=>{
    let job=null,started=false;
    try{started=true;({job}=await this.client.rpc('sdRemove',{name:value},signal));const status=await this.wait(job,signal);
     if(status.name!==value||!(status.flags&8))fail('PROTOCOL');this.ownNames.delete(value);return true;
    }catch(e){if(started)this.client.uncertain=true;await this.cancelJob(job);throw e;}
   },true);
  }
 }
 const api={Client,name,validName};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroBlocksSDFiles=api;
})(typeof window==='object'?window:globalThis);
