// SPDX-License-Identifier: MPL-2.0
// Existing identified VM connection only; upstream engine and GP stay intact.
(function(root){
 'use strict';
 const MAX_INPUT=131072,LIMITS=Object.freeze({206:[2,514],207:[4,4],208:[14,526],209:[12,12],216:[10,1010],217:[16,640]});
 const installed=new WeakMap();
 function install(Connection,connection,runtime,{files=null,frameEvent=()=>{},stateEvent=()=>{},error=()=>{}}={}){
  if(installed.has(connection))return installed.get(connection);
  for(const key of ['processNextMessage','disconnect'])if(typeof Connection.prototype[key]!=='function')throw Error('Upstream P4 hook changed: '+key);
  if(typeof runtime?.subscribe!=='function'||typeof runtime?.sendFrame!=='function')throw Error('Missing identified target transport');
  let current={epoch:-1,verified:false},closed=false;const frames=new Set(),states=new Set();
  const process=connection.processNextMessage;
  const available=()=>!closed&&current.verified&&runtime.verified(connection);
  function receive(frame){
   if(!available())return;
   for(const fn of [...frames]){try{fn(frame.slice());}catch(e){error('P4 service reply failed: '+e.message);}}
   try{frameEvent(frame.slice());}catch(e){error('P4 frame observer failed: '+e.message);}
  }
  connection.processNextMessage=function(){
   if(!this.isConnected())return false;
   const incoming=this.port.read();
   if(incoming?.length){
    if(!(incoming instanceof Uint8Array)||(this.recvBuf?.length||0)+incoming.length>MAX_INPUT){error('P4 receive buffer limit exceeded');this.disconnect();return false;}
    this.recvBuf=this.joinBytes(this.recvBuf||new Uint8Array(),incoming);
   }
   const bytes=this.recvBuf;
   if(bytes.length>=3&&bytes[0]===251&&Object.hasOwn(LIMITS,bytes[1])){
    if(bytes.length<5)return false;
    const size=bytes[3]+256*bytes[4],[min,max]=LIMITS[bytes[1]];
    if(bytes[2]!==0||size<min||size>max){error('Invalid P4 service response bounds');this.disconnect();return false;}
    if(bytes.length<5+size)return false;
    const frame=bytes.slice(0,5+size);this.recvBuf=bytes.slice(5+size);receive(frame);return true;
   }
   return process.call(this);
  };
  function send(frame){
   if(!(frame instanceof Uint8Array)||!Object.hasOwn(LIMITS,frame[1])||[207,209].includes(frame[1]))throw Error('Unsupported P4 request type');
   return available()?runtime.sendFrame(connection,frame):0;
  }
  const unsubscribe=runtime.subscribe(connection,update=>{
   if(update.epoch===current.epoch&&update.verified===current.verified)return;
   current=update;const epoch=current.epoch;
   // Capture this generation: retained controller send functions cannot write
   // to a later port, even when it has the same board/version string.
   const ownSend=frame=>available()&&current.epoch===epoch?send(frame):0;
   files?.link(current.verified?ownSend:null);
   try{stateEvent(Object.freeze({...current}));}catch(e){error(e.message);}
   for(const fn of [...states]){try{fn(Object.freeze({...current}));}catch(e){error(e.message);}}
  });
  if(files)frames.add(frame=>{if(frame[1]===217)files.receive(frame);});
  const api=Object.freeze({send,available,
   subscribe(fn){if(typeof fn!=='function')throw Error('P4 frame listener must be a function');frames.add(fn);return ()=>frames.delete(fn);},
   subscribeState(fn){if(typeof fn!=='function')throw Error('P4 state listener must be a function');states.add(fn);fn(Object.freeze({...current}));return ()=>states.delete(fn);},
   close(){if(closed)return;closed=true;unsubscribe();files?.link(null);frames.clear();states.clear();connection.processNextMessage=process;}});
  installed.set(connection,api);return api;
 }
 const api=Object.freeze({install,LIMITS,MAX_INPUT});root.MicroBlocksP4Services=api;
 if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
