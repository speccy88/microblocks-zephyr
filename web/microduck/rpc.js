/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 const commands=typeof module==='object'&&module.exports?require('./commands.js'):root.MicroDuckCommands;
 const {DuckError}=commands,MAX_REQUEST=8192,MAX_REPLY=65536;
 const UPDATE_PHASES=Object.freeze(['idle','preflight','checking','downloading','verifying','extracting','running_pre_hook','swapping','running_post_hook','applying','health_gate','committing','rolling_back']);
 const fail=code=>{throw new DuckError(code);};
 // Never retain arbitrary updater detail/log text in an observation record.
 function progress(params){
  if(!params||Object.getPrototypeOf(params)!==Object.prototype||Object.keys(params).some(key=>!['component','phase','percent','detail','simulation'].includes(key)))fail('PROTOCOL');
  let component;try{component=commands.validate('update.check',{component:params.component}).params.component;}catch{fail('PROTOCOL');}
  if(!UPDATE_PHASES.includes(params.phase)||params.percent!=null&&(!Number.isInteger(params.percent)||params.percent<0||params.percent>100)||params.detail!=null&&typeof params.detail!=='string'||params.simulation!==undefined&&typeof params.simulation!=='boolean')fail('PROTOCOL');
  return Object.freeze({component,phase:params.phase,percent:params.percent??null,detailOmitted:typeof params.detail==='string',origin:params.simulation===true?'simulation':'unmarked'});
 }
 class Lines{
  constructor(limit=MAX_REPLY){if(!Number.isInteger(limit)||limit<1||limit>MAX_REPLY)fail('LIMIT');this.limit=limit;this.buffer=new Uint8Array(limit);this.used=0;}
  clear(){this.buffer.fill(0,0,this.used);this.used=0;}
  push(chunk){
   if(!(chunk instanceof Uint8Array))fail('PROTOCOL');if(chunk.length>MAX_REPLY){this.clear();fail('LINE_TOO_LONG');}const lines=[];
   for(const byte of chunk){
    if(this.used===this.limit){this.clear();fail('LINE_TOO_LONG');}
    this.buffer[this.used++]=byte;
    if(byte!==10)continue;
    let end=this.used-1;if(end&&this.buffer[end-1]===13)end--;
    try{if(end)lines.push(new TextDecoder('utf-8',{fatal:true}).decode(this.buffer.subarray(0,end)));}
    catch{this.clear();fail('UTF8');}
    this.clear();
   }
   return lines;
  }
 }
 function encode(request){let line;try{line=new TextEncoder().encode(JSON.stringify(request)+'\n');}catch{fail('PARAMS');}if(line.length>MAX_REQUEST)fail('REQUEST_TOO_LONG');return line;}
 class RpcClient{
  constructor(transport,{timeoutMs=10000,onNotification=()=>{}}={}){
   if(!transport||typeof transport.write!=='function'||typeof transport.subscribe!=='function'||!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>120000||typeof onNotification!=='function')fail('PARAMS');
   this.transport=transport;this.timeoutMs=timeoutMs;this.onNotification=onNotification;this.lines=new Lines();this.nextId=1;this.pending=null;this.closed=false;this.authenticated=false;
   this.detach=transport.subscribe(bytes=>this.receive(bytes),()=>this.close('DISCONNECTED'));
  }
  request(method,params={},options={}){
   try{
    if(this.closed)fail('DISCONNECTED');if(this.pending)fail('BUSY');
    if(!options||typeof options!=='object'||(options.signal!==undefined&&(!root.AbortSignal||!(options.signal instanceof root.AbortSignal))))fail('PARAMS');
    const checked=commands.validate(method,params),policy=checked.policy;
    if(policy.stream)fail('STREAM_REQUIRED');
    if(policy.secret&&this.transport.confidential!==true)fail('CONFIDENTIALITY_REQUIRED');
    if(!policy.public&&!this.authenticated)fail('AUTH_REQUIRED');
    if(policy.mutation&&options.confirmed!==true)fail('CONFIRMATION_REQUIRED');
    if(options.signal?.aborted)fail('CANCELLED');if(this.nextId>Number.MAX_SAFE_INTEGER)fail('ID_EXHAUSTED');
    const id=this.nextId++,bytes=encode({jsonrpc:'2.0',id,method,params:checked.params});
    if(method==='system.authenticate')this.authenticated=false;
    const promise=new Promise((resolve,reject)=>{
     const p={id,method,resolve,reject,bytes,signal:options.signal,acknowledged:false,completion:null};this.pending=p;
     p.abort=()=>this.close('CANCELLED');p.timer=setTimeout(()=>this.close('TIMEOUT'),this.timeoutMs);
     p.signal?.addEventListener('abort',p.abort,{once:true});
    });
    // One request at a time; each ATT write must be acknowledged before the next.
    void this.send(bytes,id);return promise;
   }catch(error){return Promise.reject(error);}
  }
  watchUpdates(options={}){
   try{
    if(this.closed)fail('DISCONNECTED');if(this.pending)fail('BUSY');
    if(!options||Object.getPrototypeOf(options)!==Object.prototype||Object.keys(options).some(key=>!['onProgress','onEnd','signal','durationMs','maxEvents'].includes(key)))fail('PARAMS');
    const {onProgress=()=>{},onEnd=()=>{},signal,durationMs=60000,maxEvents=128}=options;
    if(typeof onProgress!=='function'||typeof onEnd!=='function'||!Number.isInteger(durationMs)||durationMs<1||durationMs>300000||!Number.isInteger(maxEvents)||maxEvents<1||maxEvents>256||signal!==undefined&&(!root.AbortSignal||!(signal instanceof root.AbortSignal)))fail('PARAMS');
    commands.validate('update.subscribe',{});
    if(!this.authenticated)fail('AUTH_REQUIRED');if(signal?.aborted)fail('CANCELLED');if(this.nextId>Number.MAX_SAFE_INTEGER)fail('ID_EXHAUSTED');
    const id=this.nextId++,bytes=encode({jsonrpc:'2.0',id,method:'update.subscribe',params:{}});
    const promise=new Promise((resolve,reject)=>{
     const p={id,method:'update.subscribe',kind:'watch',bytes,signal,resolve,reject,onProgress,onEnd,durationMs,maxEvents,notifications:0,accepted:0,early:[],acknowledged:false,started:false,ended:false,endCode:null,completion:null};
     p.handle=Object.freeze({stop:()=>{if(this.pending===p)this.close('WATCH_STOPPED');},snapshot:()=>Object.freeze({phase:p.ended?'closed':p.started?'observing':'starting',acknowledged:p.acknowledged,notifications:p.notifications,accepted:p.accepted,maxEvents,durationMs,endCode:p.endCode})});
     this.pending=p;p.abort=()=>this.close('CANCELLED');p.timer=setTimeout(()=>this.close('TIMEOUT'),this.timeoutMs);signal?.addEventListener('abort',p.abort,{once:true});
    });
    void this.send(bytes,id);return promise;
   }catch(error){return Promise.reject(error);}
  }
  async send(bytes,id){
   const p=this.pending;
   try{
    for(let at=0;at<bytes.length;at+=20){
     if(this.closed||this.pending!==p||p?.id!==id)return;
     const chunk=bytes.slice(at,at+20);
     try{await this.transport.write(chunk);}finally{chunk.fill(0);}
    }
    if(!this.closed&&this.pending===p){p.acknowledged=true;this.complete(p);}
   }catch{this.close('WRITE_FAILED');}finally{bytes.fill(0);}
  }
  receive(bytes){
   if(this.closed)return;
   try{for(const line of this.lines.push(bytes)){
    if(this.closed)break;
    let reply;try{reply=JSON.parse(line);}catch{fail('PROTOCOL');}
    if(!reply||typeof reply!=='object'||Array.isArray(reply)||reply.jsonrpc!=='2.0')fail('PROTOCOL');
    if(!Object.hasOwn(reply,'id')){
     if(typeof reply.method!=='string'||reply.method.length>128||Object.hasOwn(reply,'result')||Object.hasOwn(reply,'error'))fail('PROTOCOL');
     const watching=this.pending;
     if(watching?.kind==='watch'){
      if(++watching.notifications>watching.maxEvents){this.close('WATCH_EVENT_LIMIT');return;}
      if(reply.method==='update.progress'){
       const sample=progress(reply.params);
       if(watching.started)this.deliverProgress(watching,sample);else watching.early.push(sample);
      }
      if(watching.started&&watching.notifications>=watching.maxEvents)this.close('WATCH_EVENT_LIMIT');
      continue;
     }
     try{this.onNotification({method:reply.method,params:reply.params});}catch{}
     continue;
    }
    if(!Number.isSafeInteger(reply.id)||reply.id<1)fail('PROTOCOL');
    const p=this.pending;if(!p||p.id!==reply.id)continue;
    const good=Object.hasOwn(reply,'result'),bad=Object.hasOwn(reply,'error');if(good===bad||p.completion)fail('PROTOCOL');
    if(bad){if(!reply.error||!Number.isInteger(reply.error.code))fail('PROTOCOL');p.completion={error:new DuckError('REMOTE_'+reply.error.code)};this.complete(p);continue;}
    if(p.kind==='watch')fail('PROTOCOL');
    if(p.method==='system.authenticate'){
     if(!reply.result||typeof reply.result.authenticated!=='boolean')fail('PROTOCOL');
     if(reply.result.authenticated!==true){p.completion={error:new DuckError('AUTH_FAILED')};this.complete(p);continue;}
    }
    p.completion={result:reply.result};this.complete(p);
   }}catch(error){this.close(error instanceof DuckError?error.code:'PROTOCOL');}
  }
  // A notification can arrive before the final ATT write's promise settles.
  // Keep stream ownership, the deadline and abort listener until both finish.
  complete(p){
   if(this.pending!==p||!p.acknowledged)return;
   if(p.kind==='watch'){
    if(p.completion?.error){this.close(p.completion.error.code);return;}if(p.started)return;
    p.started=true;clearTimeout(p.timer);p.timer=setTimeout(()=>this.close('WATCH_TIME_LIMIT'),p.durationMs);p.resolve(p.handle);
    const early=p.early;p.early=[];for(const sample of early){if(this.pending!==p)break;this.deliverProgress(p,sample);}
    if(this.pending===p&&p.notifications>=p.maxEvents)this.close('WATCH_EVENT_LIMIT');return;
   }
   if(!p.completion)return;const {error,result}=p.completion;p.completion=null;if(p.method==='system.authenticate'&&!error)this.authenticated=true;this.finish(p,error,result);
  }
  deliverProgress(p,sample){if(this.pending!==p)return;++p.accepted;try{p.onProgress(sample);}catch{}}
  finish(p,error,result){
   if(this.pending!==p)return;this.pending=null;clearTimeout(p.timer);p.signal?.removeEventListener('abort',p.abort);p.bytes.fill(0);
   if(p.kind==='watch'){
    p.ended=true;p.endCode=error?.code||'DISCONNECTED';p.early=[];p.completion=null;
    if(!p.started)p.reject(error||new DuckError(p.endCode));
    try{p.onEnd(Object.freeze({code:p.endCode,acknowledged:p.acknowledged,notifications:p.notifications,accepted:p.accepted}));}catch{}return;
   }
   error?p.reject(error):p.resolve(result);
  }
  authenticate(pin,options={}){return this.request('system.authenticate',{pin},options);}
  close(code='DISCONNECTED'){
   if(this.closed)return;this.closed=true;this.authenticated=false;this.lines.clear();
   if(this.pending)this.finish(this.pending,new DuckError(code));
   try{this.detach?.();}catch{}this.detach=null;try{this.transport.close?.();}catch{}
  }
 }
 const api=Object.freeze({RpcClient,Lines,encode,MAX_REQUEST,MAX_REPLY,DuckError,UPDATE_PHASES});
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckRpc=api;
})(typeof globalThis==='object'?globalThis:this);
