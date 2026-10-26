/* SPDX-License-Identifier: MIT */
/* Development-only browser memory adapter. Never packaged for Pages or a board. */
((root)=>{
 'use strict';
 const core=typeof module==='object'&&module.exports?require('./device-files-core.js'):root.MicroBlocksFiles;
 function create({latency=35,empty=false}={}){
  if(!Number.isInteger(latency)||latency<0||latency>1000)throw Error('Invalid fixture delay');
  const files=new Map();let serial=0,jobSerial=0,stage=null,closed=false;
  const raise=code=>{throw new core.StorageError(code);};
  const meta=(path,file)=>({path,bytes:file.bytes.length,revision:file.revision});
  const put=(path,bytes)=>files.set(path,{bytes:bytes.slice(),revision:'r'+(++serial)});
  if(!empty){
   put('/RAM/readme.txt',core.encodeText('Local sample files\n\nThese files exist only in this browser fixture.\nNo board, microphone, camera or host file was accessed.\n\nMarkup stays literal:\n<script>alert("not executed")</script>\n'));
   put('/RAM/sensor.json',core.encodeText('{\n  "source": "synthetic fixture",\n  "temperature": 21.5,\n  "unit": "C"\n}\n'));
   put('/RAM/sample.bin',Uint8Array.from([0,1,2,3,127,128,254,255]));
  }
  const number=(n,max)=>Number.isSafeInteger(n)&&n>=0&&n<=max;
  function file(path){core.path(path);const f=files.get(path);if(!f)raise('NOT_FOUND');return f;}
  function current(job){if(!stage||stage.job!==job)raise('STATE');return stage;}
  function action(op,a){
   switch(op){
    case 'capabilities':return {version:1,backends:[{name:'RAM',available:true,volatile:true,conditionalWrites:true,maxFiles:8,maxFileBytes:8192,chunkBytes:1024},{name:'Flash',available:false},{name:'SD',available:false}]};
    case 'list':if(a.backend!=='RAM')raise('UNAVAILABLE');return {files:[...files].map(([p,f])=>meta(p,f)),used:[...files.values()].reduce((n,f)=>n+f.bytes.length,0),freeSlots:8-files.size};
    case 'stat':return meta(a.path,file(a.path));
    case 'read':{
     const f=file(a.path);if(a.revision!==f.revision)raise('CONFLICT');
     if(!number(a.offset,f.bytes.length)||!number(a.count,1024)||a.count>f.bytes.length-a.offset)raise('SIZE');
     return {revision:f.revision,bytes:f.bytes.slice(a.offset,a.offset+a.count)};
    }
    case 'begin':{
     core.path(a.path);if(!number(a.bytes,8192))raise('SIZE');if(stage)raise('BUSY');
     const f=files.get(a.path);
     if(a.expectedRevision===null){if(f)raise('EXISTS');}else if(!f||a.expectedRevision!==f.revision)raise('CONFLICT');
     if(!f&&files.size===8)raise('FULL');if(jobSerial===0x3fffffff)raise('FULL');
     stage={job:++jobSerial,path:a.path,expected:a.expectedRevision,bytes:new Uint8Array(a.bytes),received:0};
     return {job:stage.job};
    }
    case 'append':{
     const s=current(a.job);
     if(!(a.bytes instanceof Uint8Array)||a.bytes.length>1024||a.offset!==s.received||a.bytes.length>s.bytes.length-s.received)raise('SIZE');
     s.bytes.set(a.bytes,s.received);s.received+=a.bytes.length;return {received:s.received};
    }
    case 'finish':{
     const s=current(a.job),f=files.get(s.path);
     if(s.received!==s.bytes.length)raise('SIZE');
     if(s.expected===null?!!f:!f||f.revision!==s.expected)raise('CONFLICT');
     put(s.path,s.bytes);s.bytes.fill(0);stage=null;return meta(s.path,files.get(s.path));
    }
    case 'cancel':{const s=current(a.job);s.bytes.fill(0);stage=null;return {cancelled:true};}
    default:raise('PROTOCOL');
   }
  }
  async function request(message,{signal}={}){
   if(closed)raise('DISCONNECTED');if(signal?.aborted)raise('CANCELLED');
   if(latency)await new Promise((resolve,reject)=>{
    const onAbort=()=>{clearTimeout(timer);signal.removeEventListener('abort',onAbort);reject(new core.StorageError('CANCELLED'));};
    const timer=setTimeout(()=>{signal?.removeEventListener('abort',onAbort);resolve();},latency);signal?.addEventListener('abort',onAbort,{once:true});
   });
   if(closed)raise('DISCONNECTED');if(signal?.aborted)raise('CANCELLED');
   if(!message||message.version!==1||!Number.isInteger(message.id)||message.id<1||!message.args||typeof message.args!=='object')raise('PROTOCOL');
   try{return {version:1,id:message.id,ok:true,data:action(message.op,message.args)};}
   catch(e){return {version:1,id:message.id,ok:false,code:e instanceof core.StorageError?e.code:'PROTOCOL'};}
  }
  return {kind:'fixture',request,close(){closed=true;if(stage)stage.bytes.fill(0);stage=null;for(const f of files.values())f.bytes.fill(0);files.clear();}};
 }
 if(typeof module==='object'&&module.exports)module.exports={create};
 else if(root.location.protocol==='http:'&&root.location.hostname==='127.0.0.1')root.MicroBlocksFilesFixture={create};
})(typeof window==='object'?window:globalThis);
