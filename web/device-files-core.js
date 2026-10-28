/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 const LIMITS=Object.freeze({files:8,bytes:8192,path:63,chunk:1024});
 const MESSAGES=Object.freeze({DISCONNECTED:'File transfer is disconnected. Connect the board and select Connect files.',
  PATH:'Use a /RAM/ path with simple names, without .. or URL escapes.',UNAVAILABLE:'This storage backend is unavailable.',
  SIZE:'The file or transfer exceeds the storage limit.',PROTOCOL:'The storage reply was invalid. Refresh or reconnect.',
  BUSY:'Wait for the current file operation.',CONFLICT:'The file changed. Keep your draft and reopen the current file.',
  EXISTS:'That file already exists. Open it before replacing its contents.',NOT_FOUND:'File not found.',
  FULL:'No free file slots remain.',CANCELLED:'File operation cancelled.',
  TIMEOUT:'The storage reply timed out. The result may be uncertain.',
  UNCERTAIN:'A write result is uncertain. Reconnect before making another change.',
  TEXT:'This is binary data or invalid UTF-8. Download it to inspect its bytes.',STATE:'The file operation is no longer valid.'});
 class StorageError extends Error {constructor(code){super(MESSAGES[code]||MESSAGES.PROTOCOL);this.code=MESSAGES[code]?code:'PROTOCOL';}}
 const fail=code=>{throw new StorageError(code);};
 const integer=(v,min,max)=>Number.isSafeInteger(v)&&v>=min&&v<=max;
 const object=v=>v&&typeof v==='object'&&!Array.isArray(v);
 function path(value){
  if(typeof value!=='string'||value.length>LIMITS.path||!/^\/(RAM|Flash|SD)\/[A-Za-z0-9_][A-Za-z0-9_.-]*(\/[A-Za-z0-9_][A-Za-z0-9_.-]*){0,3}$/.test(value))fail('PATH');
  if(!value.startsWith('/RAM/'))fail('UNAVAILABLE');
  return value;
 }
 function revision(value){if(typeof value!=='string'||!/^[A-Za-z0-9_-]{1,32}$/.test(value))fail('PROTOCOL');return value;}
 function metadata(value){
  if(!object(value)||!integer(value.bytes,0,LIMITS.bytes))fail('PROTOCOL');
  return Object.freeze({path:path(value.path),bytes:value.bytes,revision:revision(value.revision)});
 }
 function capabilities(value){
  if(!object(value)||value.version!==1||!Array.isArray(value.backends)||value.backends.length!==3)fail('PROTOCOL');
  const seen=new Set();let ram;
  for(const b of value.backends){
   if(!object(b)||!['RAM','Flash','SD'].includes(b.name)||seen.has(b.name)||typeof b.available!=='boolean')fail('PROTOCOL');
   seen.add(b.name);
   if(b.name!=='RAM'){if(b.available)fail('UNAVAILABLE');continue;}
   if(!b.available||b.volatile!==true||b.conditionalWrites!==true||!integer(b.maxFiles,1,LIMITS.files)||!integer(b.maxFileBytes,1,LIMITS.bytes)||!integer(b.chunkBytes,1,LIMITS.chunk))fail('PROTOCOL');
   ram=Object.freeze({name:'RAM',maxFiles:b.maxFiles,maxFileBytes:b.maxFileBytes,chunkBytes:b.chunkBytes,volatile:true});
  }
  if(!ram)fail('PROTOCOL');return ram;
 }
 function fileList(value,caps){
  if(!object(value)||!Array.isArray(value.files)||value.files.length>caps.maxFiles)fail('PROTOCOL');
  const files=value.files.map(metadata),seen=new Set();let used=0;
  for(const f of files){if(seen.has(f.path)||f.bytes>caps.maxFileBytes)fail('PROTOCOL');seen.add(f.path);used+=f.bytes;}
  if(value.used!==used||value.freeSlots!==caps.maxFiles-files.length)fail('PROTOCOL');
  return Object.freeze({files:Object.freeze(files.sort((a,b)=>a.path.localeCompare(b.path))),used,freeSlots:value.freeSlots,capacity:caps.maxFiles*caps.maxFileBytes});
 }
 function encodeText(value,max=LIMITS.bytes){
  if(typeof value!=='string'||value.includes('\0'))fail('TEXT');if(value.length>max)fail('SIZE');
  // Reject unpaired UTF-16 rather than silently replacing it during UTF-8 encoding.
  for(let i=0;i<value.length;i++){const c=value.charCodeAt(i);if(c>=0xd800&&c<=0xdbff){const d=value.charCodeAt(++i);if(!(d>=0xdc00&&d<=0xdfff))fail('TEXT');}else if(c>=0xdc00&&c<=0xdfff)fail('TEXT');}
  const data=new TextEncoder().encode(value);if(data.length>max)fail('SIZE');return data;
 }
 function decodeText(data){
  if(!(data instanceof Uint8Array)||data.length>LIMITS.bytes)fail('SIZE');
  try{const text=new TextDecoder('utf-8',{fatal:true}).decode(data);if(text.includes('\0'))fail('TEXT');return text;}
  catch{fail('TEXT');}
 }
 function download(value,data){
  path(value);if(!(data instanceof Uint8Array)||data.length>LIMITS.bytes)fail('SIZE');
  return {name:value.slice(value.lastIndexOf('/')+1),type:'application/octet-stream',bytes:data.slice()};
 }
 class Client {
  constructor(transport=null,{timeout=3000}={}){
   this.transport=transport;this.timeout=timeout;this.next=0;this.active=null;this.caps=null;this.uncertain=false;
   if(!integer(timeout,10,10000))fail('PROTOCOL');
  }
  get busy(){return !!this.active;}
  cancel(){if(this.active){this.active.abort();return true;}return false;}
  async rpc(op,args,signal,timeout=this.timeout){
   if(!this.transport||typeof this.transport.request!=='function')fail('DISCONNECTED');
   if(signal.aborted)fail('CANCELLED');if(this.next>=0xffffffff)fail('STATE');
   const id=++this.next,request={version:1,id,op,args},requestAbort=new AbortController();let timer,onAbort;
   const interrupted=new Promise((resolve,reject)=>{
    timer=setTimeout(()=>{reject(new StorageError('TIMEOUT'));requestAbort.abort();},timeout);
    onAbort=()=>{requestAbort.abort();reject(new StorageError('CANCELLED'));};signal.addEventListener('abort',onAbort,{once:true});
   });
   try{
    const reply=await Promise.race([Promise.resolve().then(()=>this.transport.request(request,{signal:requestAbort.signal})),interrupted]);
    if(signal.aborted)fail('CANCELLED');
    if(!object(reply)||reply.version!==1||reply.id!==id||typeof reply.ok!=='boolean')fail('PROTOCOL');
    if(!reply.ok)fail(reply.code);
    return reply.data;
   }catch(e){throw e instanceof StorageError?e:new StorageError('PROTOCOL');}
   finally{clearTimeout(timer);signal.removeEventListener('abort',onAbort);requestAbort.abort();}
  }
  async run(task,mutation=false){
   if(this.active)fail('BUSY');if(mutation&&this.uncertain)fail('UNCERTAIN');
   const controller=new AbortController();this.active=controller;
   try{return await task(controller.signal);}finally{if(this.active===controller)this.active=null;}
  }
  async limits(signal){if(!this.caps)this.caps=capabilities(await this.rpc('capabilities',{},signal));return this.caps;}
  async refresh(){return this.run(async signal=>{
   const caps=await this.limits(signal);return {caps,list:fileList(await this.rpc('list',{backend:'RAM'},signal),caps)};
  });}
  // Read-only lease renewal shares the ordinary request-ID and busy guards.
  // Never replay a save to recover an expired session.
  async keepAlive(){return this.run(async signal=>capabilities(await this.rpc('capabilities',{},signal)));}
  async read(value){path(value);return this.run(async signal=>{
   const caps=await this.limits(signal),meta=metadata(await this.rpc('stat',{path:value},signal));
   if(meta.path!==value||meta.bytes>caps.maxFileBytes)fail('PROTOCOL');
   const bytes=new Uint8Array(meta.bytes);
   for(let offset=0;offset<bytes.length;offset+=caps.chunkBytes){
    const count=Math.min(caps.chunkBytes,bytes.length-offset),part=await this.rpc('read',{path:value,revision:meta.revision,offset,count},signal);
    if(!object(part)||part.revision!==meta.revision||!(part.bytes instanceof Uint8Array)||part.bytes.length!==count)fail('PROTOCOL');
    bytes.set(part.bytes,offset);
   }
   return {meta,bytes};
  });}
  async save(value,bytes,expected=null){
   path(value);if(!(bytes instanceof Uint8Array)||bytes.length>LIMITS.bytes)fail('SIZE');if(expected!==null)revision(expected);
   const owned=bytes.slice();
   return this.run(async signal=>{
    let job=null,commitAttempted=false,beginAttempted=false;
    try{
     const caps=await this.limits(signal);if(owned.length>caps.maxFileBytes)fail('SIZE');
     beginAttempted=true;
     const begun=await this.rpc('begin',{path:value,bytes:owned.length,expectedRevision:expected},signal);
     if(!object(begun)||!integer(begun.job,1,0x3fffffff))fail('PROTOCOL');job=begun.job;
     for(let offset=0;offset<owned.length;offset+=caps.chunkBytes){
      const data=owned.slice(offset,Math.min(offset+caps.chunkBytes,owned.length));
      const part=await this.rpc('append',{job,offset,bytes:data},signal);
      if(!object(part)||part.received!==offset+data.length)fail('PROTOCOL');
     }
     if(signal.aborted)fail('CANCELLED');commitAttempted=true;
     const meta=metadata(await this.rpc('finish',{job},signal));
     if(meta.path!==value||meta.bytes!==owned.length||meta.revision===expected)fail('PROTOCOL');
     return meta;
    }catch(error){
     if(commitAttempted)this.uncertain=true;
     else if(job!==null){
      try{const cancelled=await this.rpc('cancel',{job},new AbortController().signal,250);if(cancelled?.cancelled!==true)this.uncertain=true;}
      catch{this.uncertain=true;}
     }else if(beginAttempted&&['TIMEOUT','CANCELLED','PROTOCOL'].includes(error.code))this.uncertain=true;
     throw error;
    }finally{owned.fill(0);}
   },true);
  }
 }
 const api={LIMITS,StorageError,path,metadata,capabilities,fileList,encodeText,decodeText,download,Client};
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroBlocksFiles=api;
})(typeof window==='object'?window:globalThis);
