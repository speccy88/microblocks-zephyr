/* SPDX-License-Identifier: MIT */
/* Reviewed API44 console policy. Attaches existing RpcClient only; no transport. */
((root)=>{
 'use strict';
 const common=typeof module==='object'&&module.exports;
 const commands=common?require('./commands.js'):root.MicroDuckCommands;
 const rpc=common?require('./rpc.js'):root.MicroDuckRpc;
 const FIXTURE_PIN='000000',FIXTURE_SSID='SIMULATION-NET-OPEN';
 const DENIED=new Set(['system.authenticate','net.connect','update.subscribe']);
 const METHODS=Object.freeze(commands.methods.filter(name=>!DENIED.has(name)));
 const defaults={hello:{api_version:44},'system.logs':{unit:'robotd',lines:50,boot:0},
  'system.setName':{name:'MicroDuck'},'net.forget':{ssid:FIXTURE_SSID},
  'robot.enable':{on:false,toggle:false},'robot.do':{skill:'simulation_bow'},'robot.sound':{tag:'chirp'},
  'update.check':{component:'robotd'},'update.listInstalled':{component:'robotd'},
  'update.rollback':{component:'robotd'},'update.select':{component:'robotd',version:'0.0.0'},
  'update.apply':{component:'robotd',target:'latest'},'update.log':{limit:20},'update.show':{run:null}};
 const EXAMPLES=Object.freeze(Object.fromEntries(METHODS.map(name=>[name,JSON.stringify(defaults[name]||{},null,2)])));
 const POLICIES=Object.freeze(Object.fromEntries(METHODS.map(name=>{
  const p=commands.validate(name,defaults[name]||{}).policy;
  return [name,Object.freeze({public:p.public===true,mutation:p.mutation===true,motion:p.motion===true,secret:p.secret===true})];
 })));
 const PREFLIGHT=new Set(['PARAMS','AUTH_REQUIRED','CONFIDENTIALITY_REQUIRED','CONFIRMATION_REQUIRED','BUSY','ID_EXHAUSTED',
  'METHOD_DENIED','SECRET_FORM_REQUIRED','SECRET_INPUT_DENIED','API_VERSION','STALE_PREVIEW','SIMULATION_INPUT',
  'UNDISCOVERED_SKILL','REQUEST_TOO_LONG']);
 const CODES=new Set([...PREFLIGHT,'CAPABILITIES_INVALID','DISCONNECTED','CANCELLED','TIMEOUT','WRITE_FAILED','PROTOCOL','UTF8','LINE_TOO_LONG',
  'AUTH_FAILED','STALE_SESSION','JSON_PARAMS','JSON_LIMIT','JSON_DUPLICATE','INTERNAL']);
 function safeCode(error){const code=error?.code;return typeof code==='string'&&(CODES.has(code)||/^REMOTE_-?\d{1,10}$/.test(code))?code:'INTERNAL';}
 class ConsoleError extends commands.DuckError{constructor(code,outcome='not_sent'){super(code);this.outcome=outcome;}}
 const fail=(code,outcome)=>{throw new ConsoleError(code,outcome);};
 function check(method,params){try{return commands.validate(method,params);}catch(error){throw new ConsoleError(safeCode(error));}}
 const plain=value=>value&&Object.getPrototypeOf(value)===Object.prototype;
 function describe(method){if(!Object.hasOwn(POLICIES,method))fail('METHOD_DENIED');return POLICIES[method];}
 function unicode(text){for(let i=0;i<text.length;i++){const c=text.charCodeAt(i);if(c>=0xd800&&c<=0xdbff){const n=text.charCodeAt(++i);if(!(n>=0xdc00&&n<=0xdfff))fail('JSON_PARAMS');}else if(c>=0xdc00&&c<=0xdfff)fail('JSON_PARAMS');}return text;}
 function parseParams(text){
  if(typeof text!=='string')fail('JSON_PARAMS');
  if(new TextEncoder().encode(text).length>4096)fail('JSON_LIMIT');
  let at=0,nodes=0;
  const ws=()=>{while(/[\x20\t\r\n]/.test(text[at]||'!'))at++;};
  function string(){
   const begin=at++;let escaped=false;
   while(at<text.length){const c=text[at++];if(!escaped&&c==='"'){try{return unicode(JSON.parse(text.slice(begin,at)));}catch(error){if(error instanceof ConsoleError)throw error;fail('JSON_PARAMS');}}if(!escaped&&c==='\\')escaped=true;else escaped=false;}
   fail('JSON_PARAMS');
  }
  function value(depth){
   ws();if(depth>16||++nodes>1024)fail('JSON_LIMIT');
   const c=text[at];
   if(c==='"')return string();
   if(c==='{'){
    at++;ws();const object={},keys=new Set();if(text[at]==='}'){at++;return object;}
    do{ws();if(text[at]!=='"')fail('JSON_PARAMS');const key=string();if(keys.has(key))fail('JSON_DUPLICATE');if(keys.size>=128)fail('JSON_LIMIT');keys.add(key);
     if(['__proto__','prototype','constructor'].includes(key))fail('JSON_PARAMS');ws();if(text[at++]!==':')fail('JSON_PARAMS');
     Object.defineProperty(object,key,{value:value(depth+1),enumerable:true,writable:true,configurable:true});ws();if(text[at]==='}'){at++;return object;}if(text[at++]!==',')fail('JSON_PARAMS');
    }while(at<text.length);fail('JSON_PARAMS');
   }
   if(c==='['){at++;ws();const array=[];if(text[at]===']'){at++;return array;}do{if(array.length>=256)fail('JSON_LIMIT');array.push(value(depth+1));ws();if(text[at]===']'){at++;return array;}if(text[at++]!==',')fail('JSON_PARAMS');}while(at<text.length);fail('JSON_PARAMS');}
   for(const [token,result]of [['true',true],['false',false],['null',null]])if(text.startsWith(token,at)){at+=token.length;return result;}
   const match=/^-?(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+-]?\d+)?/.exec(text.slice(at));
   if(!match)fail('JSON_PARAMS');at+=match[0].length;const number=Number(match[0]);if(!Number.isFinite(number))fail('JSON_PARAMS');return number;
  }
  const parsed=value(0);ws();if(at!==text.length||!parsed||Array.isArray(parsed)||typeof parsed!=='object')fail('JSON_PARAMS');return parsed;
 }
 function noSecrets(value){if(value&&typeof value==='object')for(const [key,item]of Object.entries(value)){if(/^(?:pin|psk|password|passphrase|token|secret|authorization|private_key|access_token|refresh_token)$/i.test(key))fail('SECRET_INPUT_DENIED');noSecrets(item);}}
 function frozenCopy(value){if(!value||typeof value!=='object')return value;const copy=Array.isArray(value)?value.map(frozenCopy):Object.fromEntries(Object.entries(value).map(([k,v])=>[k,frozenCopy(v)]));return Object.freeze(copy);}
 function safeResult(value,secret=''){
  let nodes=0,budget=32768;const seen=new Set();
  function visit(item,depth){
   if(depth>16||++nodes>4096||budget<=0)return '[truncated]';
   if(typeof item==='string'){let s=secret?item.split(secret).join('[redacted]'):item;s=s.slice(0,Math.min(4096,budget));budget-=s.length;return s;}
   if(item===null||typeof item==='boolean')return item;
   if(typeof item==='number')return Number.isFinite(item)?item:'[invalid number]';
   if(!item||typeof item!=='object'||seen.has(item))return '[invalid value]';seen.add(item);
   if(Array.isArray(item))return item.slice(0,256).map(v=>visit(v,depth+1));
   return Object.fromEntries(Object.entries(item).slice(0,128).map(([key,v])=>[(secret?key.split(secret).join('[redacted]'):key).slice(0,128),/pin|psk|password|passphrase|token|secret|authorization|private.?key/i.test(key)?'[redacted]':visit(v,depth+1)]));
  }
  return visit(value,0);
 }
 const states=new WeakMap();
 function stateFor(owner){const s=states.get(owner);if(!s)fail('INTERNAL');if(s.client?.closed){s.stage=null;s.skills.clear();}return s;}
 function ready(s){if(!s.client||s.client.closed)fail('DISCONNECTED');if(s.apiVersion!==44)fail('API_VERSION');if(s.busy)fail('BUSY');}
 function authorized(s,policy){ready(s);if(policy.secret&&s.client.transport.confidential!==true)fail('CONFIDENTIALITY_REQUIRED');if(!policy.public&&!s.client.authenticated)fail('AUTH_REQUIRED');}
 function audit(s,method,outcome,code=''){s.history.push(Object.freeze({sequence:++s.sequence,method,outcome,code,simulation:s.simulation}));if(s.history.length>32)s.history.shift();}
 function skillNames(result){if(!result||!Array.isArray(result.skills)||result.skills.length>256)fail('CAPABILITIES_INVALID');const set=new Set();for(const name of result.skills){if(typeof name!=='string'||!name||name.length>128||/[\x00-\x1f\x7f]/.test(name))fail('CAPABILITIES_INVALID');set.add(name);}return set;}
 class Controller{
  constructor(){states.set(this,{client:null,apiVersion:null,simulation:false,generation:0,busy:false,stage:null,skills:new Set(),history:[],sequence:0,nextPreview:1,abort:null});}
  attach(client,metadata={}){
   if(!plain(metadata)||Object.keys(metadata).some(k=>!['apiVersion','simulation'].includes(k)))fail('PARAMS');
   const {apiVersion,simulation=false}=metadata;
   if(!(client instanceof rpc.RpcClient)||client.closed||typeof simulation!=='boolean')fail('PARAMS');if(apiVersion!==44)fail('API_VERSION');
   if(stateFor(this).client===client)fail('PARAMS');this.detach();const s=stateFor(this);s.client=client;s.apiVersion=apiVersion;s.simulation=simulation;return this.snapshot();
  }
  detach(){const s=stateFor(this);++s.generation;s.stage=null;s.skills.clear();s.abort?.abort();s.abort=null;s.client?.close('DISCONNECTED');s.client=null;s.apiVersion=null;s.simulation=false;s.busy=false;s.history=[];s.sequence=0;}
  invalidate(){stateFor(this).stage=null;}
  cancel(){const s=stateFor(this);s.stage=null;if(s.busy)s.abort?.abort();else s.client?.close('CANCELLED');}
  snapshot(){const s=stateFor(this);return Object.freeze({phase:!s.client?'disconnected':s.client.closed?'closed':s.busy?'busy':'ready',busy:s.busy,
   apiVersion:s.apiVersion,confidential:s.client?.transport.confidential===true,authenticated:s.client?.authenticated===true&&!s.client.closed,
   simulation:s.simulation,skills:Object.freeze([...s.skills]),prepared:s.stage?.preview||null,history:Object.freeze([...s.history])});}
  preview(method,paramsText='{}'){
   const s=stateFor(this);s.stage=null;if(DENIED.has(method))fail(method==='update.subscribe'?'METHOD_DENIED':'SECRET_FORM_REQUIRED');const policy=describe(method);
   const params=parseParams(paramsText);noSecrets(params);const checked=check(method,params);authorized(s,policy);
   if(method==='hello'&&checked.params.api_version!==44)fail('API_VERSION');
   if(method==='robot.do'&&!s.skills.has(checked.params.skill))fail('UNDISCOVERED_SKILL');
   return this.#makeStage(method,checked.params,policy,false);
  }
  previewProvisioning(input={}){
   if(!plain(input)||Object.keys(input).some(k=>!['ssid','psk'].includes(k)))fail('PARAMS');const {ssid,psk}=input;
   const s=stateFor(this);s.stage=null;authorized(s,{secret:true,public:false});
   if(s.simulation&&(ssid!==FIXTURE_SSID||psk!==undefined&&psk!==null))fail('SIMULATION_INPUT');
   const checked=check('net.connect',{ssid,...(psk===undefined?{}:{psk})});return this.#makeStage('net.connect',checked.params,checked.policy,true);
  }
  #makeStage(method,params,policy,secret){
   const s=stateFor(this);if(s.nextPreview>Number.MAX_SAFE_INTEGER)fail('ID_EXHAUSTED');const preview=Object.freeze({id:s.nextPreview++,method,
    paramsPreview:JSON.stringify(secret?{ssid:params.ssid,...(Object.hasOwn(params,'psk')?{psk:'[redacted]'}:{})}:params,null,2).replace(/[\u202a-\u202e\u2066-\u2069]/g,c=>'\\u'+c.charCodeAt(0).toString(16).padStart(4,'0')),
    mutation:policy.mutation===true,motion:policy.motion===true,simulation:s.simulation});
   s.stage={preview,method,params:frozenCopy(params),policy,generation:s.generation,secret};return preview;
  }
  async authenticate(pin){
   const s=stateFor(this);s.stage=null;authorized(s,{secret:true,public:true});
   if(s.simulation&&pin!==FIXTURE_PIN)fail('SIMULATION_INPUT');check('system.authenticate',{pin});
   const result=await this.#perform('system.authenticate',{pin},{public:true,secret:true},false,false);pin='';
   return {authenticated:result.authenticated===true,...(Number.isInteger(result.attempts_remaining)&&result.attempts_remaining>=0&&result.attempts_remaining<=100?{attempts_remaining:result.attempts_remaining}:{})};
  }
  async execute(preview,options={}){
   const s=stateFor(this),stage=s.stage;
   if(!stage||stage.preview!==preview||stage.generation!==s.generation)fail('STALE_PREVIEW');s.stage=null;
   try{if(!plain(options)||Object.keys(options).some(k=>k!=='confirmed')||options.confirmed!==undefined&&typeof options.confirmed!=='boolean')fail('PARAMS');
    const confirmed=options.confirmed===true;authorized(s,stage.policy);if(stage.policy.mutation&&!confirmed)fail('CONFIRMATION_REQUIRED');
    const result=await this.#perform(stage.method,stage.params,stage.policy,confirmed,stage.secret);
    return {method:stage.method,result,simulation:s.simulation,outcome:'completed'};
   }finally{stage.params=null;}
  }
  async #perform(method,params,policy,confirmed,secret){
   const s=stateFor(this);authorized(s,policy);const generation=s.generation,client=s.client,abort=new AbortController();s.busy=true;s.abort=abort;
   let sent=false;
   try{
    if(method==='robot.do'){
     const latest=await client.request('robot.policies',{}, {signal:abort.signal});
     if(s.generation!==generation)fail('STALE_SESSION','unknown');s.skills=skillNames(latest);if(!s.skills.has(params.skill))fail('UNDISCOVERED_SKILL');
    }
    // The existing update.apply validator adds the mandatory empty options
    // object. Supply its accepted inputs so the RpcClient can validate again;
    // never accept user options which weaken an updater preflight.
    const outbound=method==='update.apply'?{component:params.component,target:params.target}:params;
    sent=true;const raw=await client.request(method,outbound,{confirmed,signal:abort.signal});
    if(s.generation!==generation)fail('STALE_SESSION','unknown');
    if(method==='robot.policies')s.skills=skillNames(raw);
    const result=safeResult(raw,secret&&typeof params.psk==='string'?params.psk:'');audit(s,method,'completed');return result;
   }catch(error){
    const code=safeCode(error),outcome=/^REMOTE_/.test(code)||code==='AUTH_FAILED'?'rejected':!sent||PREFLIGHT.has(code)?'not_sent':'unknown';
    if(s.generation===generation){s.stage=null;if(client.closed)s.skills.clear();audit(s,method,outcome,code);}
    throw new ConsoleError(code,outcome);
   }finally{if(s.generation===generation){s.busy=false;s.abort=null;}}
  }
 }
 const api=Object.freeze({Controller,ConsoleError,parseParams,METHODS,EXAMPLES,describe,safeCode,FIXTURE_PIN,FIXTURE_SSID});
 if(common)module.exports=api;else root.MicroDuckConsole=api;
})(typeof globalThis==='object'?globalThis:this);
