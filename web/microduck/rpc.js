/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 const commands=typeof module==='object'&&module.exports?require('./commands.js'):root.MicroDuckCommands;
 const {DuckError}=commands,MAX_REQUEST=8192,MAX_REPLY=65536;
 const fail=code=>{throw new DuckError(code);};
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
    let reply;try{reply=JSON.parse(line);}catch{fail('PROTOCOL');}
    if(!reply||typeof reply!=='object'||Array.isArray(reply)||reply.jsonrpc!=='2.0')fail('PROTOCOL');
    if(!Object.hasOwn(reply,'id')){
     if(typeof reply.method!=='string'||reply.method.length>128||Object.hasOwn(reply,'result')||Object.hasOwn(reply,'error'))fail('PROTOCOL');
     try{this.onNotification({method:reply.method,params:reply.params});}catch{}
     continue;
    }
    if(!Number.isSafeInteger(reply.id)||reply.id<1)fail('PROTOCOL');
    const p=this.pending;if(!p||p.id!==reply.id)continue;
    const good=Object.hasOwn(reply,'result'),bad=Object.hasOwn(reply,'error');if(good===bad||p.completion)fail('PROTOCOL');
    if(bad){if(!reply.error||!Number.isInteger(reply.error.code))fail('PROTOCOL');p.completion={error:new DuckError('REMOTE_'+reply.error.code)};this.complete(p);continue;}
    if(p.method==='system.authenticate'){
     if(!reply.result||typeof reply.result.authenticated!=='boolean')fail('PROTOCOL');
     if(reply.result.authenticated!==true){p.completion={error:new DuckError('AUTH_FAILED')};this.complete(p);continue;}
    }
    p.completion={result:reply.result};this.complete(p);
   }}catch(error){this.close(error instanceof DuckError?error.code:'PROTOCOL');}
  }
  // A notification can arrive before the final ATT write's promise settles.
  // Keep stream ownership, the deadline and abort listener until both finish.
  complete(p){if(this.pending!==p||!p.acknowledged||!p.completion)return;const {error,result}=p.completion;p.completion=null;if(p.method==='system.authenticate'&&!error)this.authenticated=true;this.finish(p,error,result);}
  finish(p,error,result){if(this.pending!==p)return;this.pending=null;clearTimeout(p.timer);p.signal?.removeEventListener('abort',p.abort);p.bytes.fill(0);error?p.reject(error):p.resolve(result);}
  authenticate(pin,options={}){return this.request('system.authenticate',{pin},options);}
  close(code='DISCONNECTED'){
   if(this.closed)return;this.closed=true;this.authenticated=false;this.lines.clear();
   if(this.pending)this.finish(this.pending,new DuckError(code));
   try{this.detach?.();}catch{}this.detach=null;try{this.transport.close?.();}catch{}
  }
 }
 const api=Object.freeze({RpcClient,Lines,encode,MAX_REQUEST,MAX_REPLY,DuckError});
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckRpc=api;
})(typeof globalThis==='object'?globalThis:this);
