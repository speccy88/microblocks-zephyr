/* SPDX-License-Identifier: MIT */
/* API44 in-memory console fixture, never a device transport.
 * Source: pollen-robotics/microduck 96b89d8613f06722c1d64ce75ab0d7124fed9d8f,
 * duck-ipc-proto/src/lib.rs + vetbook.rs; updater/src/ipc.rs dispatch.
 * All measurements, services, update histories and actions are fictional. */
((root)=>{
 'use strict';
 const commonJS=typeof module==='object'&&module.exports;
 const commands=commonJS?require('./commands.js'):root.MicroDuckCommands;
 const rpc=commonJS?require('./rpc.js'):root.MicroDuckRpc;
 const FIXTURE_PIN='000000',FIXTURE_SSID='SIMULATION-NET-OPEN',IP='192.0.2.44';
 const SKILLS=Object.freeze(['simulation_bow','simulation_nod']);
 const LIMITS=Object.freeze({requests:256,actions:32,audit:32});
 const NOTICE='SIMULATION ONLY: fictional data and recorded intentions; no robot, network, download, update or physical action.';
 const FAULTS=new Set(['timeout','disconnect','remote_error','malformed','wrong_id']);
 const LOG_UNITS=new Set('robotd configd btd updaterd padd netpadd mediad tofd nfcd bluetooth networkmanager'.split(' '));
 const clone=value=>JSON.parse(JSON.stringify(value));
 const marked=value=>({...value,simulation:true,notice:NOTICE});
 const fail=code=>{throw new commands.DuckError(code);};

 function createFixture(options={}){
  if(!commands||!rpc||commands.API_VERSION!==44)throw Error('Reviewed API44 RPC modules required.');
  if(!options||Object.getPrototypeOf(options)!==Object.prototype||Object.keys(options).some(k=>!['timeoutMs','fault','faultMethod'].includes(k)))fail('PARAMS');
  const timeoutMs=options.timeoutMs??10000,fault=options.fault??null,faultMethod=options.faultMethod??'system.info';
  if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>120000||fault!==null&&!FAULTS.has(fault))fail('PARAMS');
  if(typeof faultMethod!=='string'||!commands.methods.includes(faultMethod)||faultMethod==='update.subscribe')fail('PARAMS');
  let receive=null,drop=null,closed=false,authenticated=false,joined=false,enabled=false,homed=false,name='SIMULATION Duck',installed='0.0.0';
  let skills=[...SKILLS],sequence=0,inFlight=0;
  const requests=[],actions=[],audit=[],updateLog=[];
  const stats={requests:0,writeChunks:0,replyChunks:0,maxWriteBytes:0,maxAckInFlight:0};
  const lines=new rpc.Lines(rpc.MAX_REQUEST);
  function constraints(method,params,normalized){
   if(method==='update.subscribe')fail('METHOD_DENIED');
   if(method==='hello'&&normalized.api_version!==44)fail('API_VERSION');
   if(method==='system.authenticate'&&normalized.pin!==FIXTURE_PIN)fail('SIMULATION_INPUT');
   if(method==='net.connect'||method==='net.forget'){
    if(normalized.ssid!==FIXTURE_SSID||Object.hasOwn(params,'psk'))fail('SIMULATION_INPUT');
   }
   if(Object.hasOwn(normalized,'component')&&normalized.component!=='robotd')fail('SIMULATION_INPUT');
   if(method==='system.logs'&&!LOG_UNITS.has(normalized.unit.toLowerCase().replace(/\.service$/,'')))fail('SIMULATION_INPUT');
  }
  function record(method,outcome,code=''){
   const entry={sequence:++sequence,method,outcome,code,simulation:true};audit.push(entry);
   if(audit.length>LIMITS.audit)audit.shift();return entry;
  }
  function answer(q,policy){
   const p=q.params;
   if(q.method==='hello')return marked({api_version:44,daemon_version:'0.0.0-simulation',revision:null});
   if(q.method==='system.authenticate'){authenticated=true;return marked({authenticated:true,attempts_remaining:3});}
   if(!authenticated)fail('AUTH_REQUIRED');
   if(policy.mutation)actions.push({sequence:actions.length+1,method:q.method,simulation:true});
   switch(q.method){
    case 'system.info':return marked({name,serial:null,uptime_seconds:0,simulated:true});
    case 'system.setName':name='SIMULATION '+p.name;return marked({name});
    case 'system.services':return [marked({unit:'robotd.service',state:'inactive',identity:{service:'robotd',version:'0.0.0',pid:0}})];
    case 'system.logs':return marked({unit:p.unit.endsWith('.service')?p.unit:p.unit+'.service',lines:[NOTICE],truncated:false});
    case 'net.status':return marked({state:joined?'connected':'disconnected',ssid:joined?FIXTURE_SSID:null,signal:joined?88:null,ip4:joined?IP:null,ip6:null,mac:null,iface:joined?'simulation0':null});
    case 'net.scan':return marked({networks:[{ssid:FIXTURE_SSID,security:'open',signal:88,saved:joined}]});
    case 'net.connect':joined=true;return marked({outcome:'connected',ssid:FIXTURE_SSID,ip4:IP});
    case 'net.forget':{const removed=joined;joined=false;return marked({removed});}
    case 'robot.health':return marked({healthy:false,degraded:true,reason:NOTICE,battery:{volts:7.8,percent:73.25},cpu_temp_c:41.25,bus:{consecutive_errors:0,startup_failures:0},imu:{ready:false,stale_blocks:0,consecutive_stale_blocks:0}});
    case 'robot.policies':return marked({mode:'walk',enabled,slots:[],skills:[...skills],homed,sitting:false,change_error:NOTICE});
    case 'robot.skills':return marked({skills:skills.map(skill=>({name:skill,duration:1.0}))});
    case 'robot.model':return marked({asset:'SIMULATION',trunk_height_m:0,joint_names:[],head_joints:[],tof_beams:[],tof_fov_deg:0,frames_at_zero:{camera:{pos:[0,0,0],quat:[1,0,0,0]},tof:{pos:[0,0,0],quat:[1,0,0,0]}}});
    case 'robot.vetbook':return marked({schema:1,opened:0,life:{powered_s:0,skills:{}},motors:[],events:[],last_boot_id:'SIMULATION',last_version:'0.0.0',last_volts:0});
    case 'pad.status':return marked({pads:[],driver:'inactive'});
    case 'pad.bindings':return marked({bindings:[]});
    case 'robot.init':homed=true;return marked({accepted:true,reason:NOTICE});
    case 'robot.enable':enabled=p.toggle?!enabled:p.on;return marked({accepted:true,reason:NOTICE});
    case 'robot.do':return marked({accepted:skills.includes(p.skill)&&enabled&&homed,reason:NOTICE});
    case 'robot.sound':return marked({accepted:true,reason:NOTICE});
    case 'update.status':return [marked({component:'robotd',installed,phase:'idle',healthy:false,degraded:true,reason:NOTICE,pinned:null,last_attempt:updateLog.at(-1)||null,last_checked:null})];
    case 'update.check':return installed==='0.0.0'?marked({state:'available',installed,candidate:'0.0.1-simulation',mandatory:false,changelog:NOTICE}):marked({state:'up_to_date',installed});
    case 'update.listInstalled':return [marked({version:installed,active:true,golden:installed==='0.0.0',source_revision:null}),...(installed==='0.0.0'?[]:[marked({version:'0.0.0',active:false,golden:true,source_revision:null})])];
    case 'update.log':return updateLog.slice(-p.limit).map(clone);
    case 'update.show':return marked({run:p.run??updateLog.at(-1)?.run??1,component:'robotd',events:[{at:0,event:'note',text:NOTICE}],available:updateLog.length?updateLog.map(e=>e.run).reverse():[1]});
    case 'update.apply':case 'update.rollback':case 'update.select':{
     const from=installed,to=q.method==='update.rollback'?'0.0.0':q.method==='update.select'?p.version:p.target==='latest'?'0.0.1-simulation':p.target.exact;
     if(from===to)return marked({outcome:'already_current',version:installed});
     installed=to;updateLog.push(marked({at:0,component:'robotd',from,to,outcome:{kind:'success'},run:updateLog.length+1}));
     return marked({outcome:'applied',from,to});
    }
    default:fail('METHOD_DENIED');
   }
  }
  function emit(reply,malformed=false){
   const bytes=new TextEncoder().encode(malformed?'not-json\n':JSON.stringify(reply)+'\n');
   try{for(let at=0;at<bytes.length&&!closed;at+=7){stats.replyChunks++;receive?.(bytes.subarray(at,at+7));}}
   finally{bytes.fill(0);}
  }
  const transport=Object.freeze({confidential:true,
   subscribe(onBytes,onDrop){receive=onBytes;drop=onDrop;return ()=>{receive=null;drop=null;};},
   async write(chunk){
    if(closed)fail('DISCONNECTED');if(!(chunk instanceof Uint8Array)||chunk.length>20)fail('PROTOCOL');
    ++inFlight;stats.maxAckInFlight=Math.max(stats.maxAckInFlight,inFlight);stats.writeChunks++;stats.maxWriteBytes=Math.max(stats.maxWriteBytes,chunk.length);
    try{
     await Promise.resolve();if(closed)return;
     for(const line of lines.push(chunk)){
      const q=JSON.parse(line);
      if(q.jsonrpc!=='2.0'||!Number.isSafeInteger(q.id)||q.id<1)fail('PROTOCOL');
      // update.apply has reviewed normalized wire options:{}; never accept
      // arbitrary updater force/from_dir options through a raw transport write.
      let input=q.params;
      if(q.method==='update.apply'){
       if(!input||Object.keys(input).some(k=>!['component','target','options'].includes(k))||!input.options||Object.getPrototypeOf(input.options)!==Object.prototype||Object.keys(input.options).length)fail('PARAMS');
       input={component:input.component,target:input.target};
      }
      const checked=commands.validate(q.method,input);constraints(q.method,input,checked.params);
      if(stats.requests>=LIMITS.requests||checked.policy.mutation&&actions.length>=LIMITS.actions)fail('FIXTURE_LIMIT');
      if(!checked.policy.public&&!authenticated)fail('AUTH_REQUIRED');
      stats.requests++;requests.push({id:q.id,method:q.method});if(requests.length>LIMITS.audit)requests.shift();
      const auditEntry=record(q.method,'received');
      if(fault==='remote_error'&&q.method===faultMethod){auditEntry.outcome='rejected';auditEntry.code='REMOTE_-32003';emit({jsonrpc:'2.0',id:q.id,error:{code:-32003,message:'SIMULATION refusal',data:{simulation:true}}});continue;}
      const result=answer(q,checked.policy);
      if(q.method===faultMethod&&fault){
       auditEntry.outcome='unknown';auditEntry.code='FIXTURE_'+fault.toUpperCase();
       if(fault==='timeout')continue;
       if(fault==='disconnect'){drop?.();continue;}
       emit({jsonrpc:'2.0',id:fault==='wrong_id'?q.id+1:q.id,result},fault==='malformed');continue;
      }
      auditEntry.outcome='completed';emit({jsonrpc:'2.0',id:q.id,result});
     }
     // A final notification deliberately precedes its write acknowledgement.
     await Promise.resolve();
    }finally{--inFlight;}
   },
   close(){closed=true;authenticated=false;lines.clear();receive=null;drop=null;}
  });
  const client=new rpc.RpcClient(transport,{timeoutMs}),request=client.request.bind(client);
  Object.defineProperty(client,'transport',{value:transport,writable:false,configurable:false});
  Object.defineProperty(client,'request',{value:(method,params={},requestOptions={})=>{
   try{
    if(client.closed)return request(method,params,requestOptions);
    const checked=commands.validate(method,params);constraints(method,params,checked.params);
    if(stats.requests>=LIMITS.requests)fail('FIXTURE_LIMIT');
    if(checked.policy.mutation&&actions.length>=LIMITS.actions)fail('FIXTURE_ACTION_LIMIT');
    return request(method,params,requestOptions);
   }catch(error){return Promise.reject(error);}
  },writable:false,configurable:false});
  const snapshot=()=>clone({simulation:true,notice:NOTICE,apiVersion:44,closed,authenticated:client.authenticated,skills,requests,actions,audit,stats,limits:LIMITS});
  return Object.freeze({client,apiVersion:44,simulation:true,snapshot,close(){client.close();},setSkills(names){
   if(!Array.isArray(names)||names.length>SKILLS.length||names.some(n=>!SKILLS.includes(n))||new Set(names).size!==names.length)fail('PARAMS');
   skills=[...names];
  }});
 }
 const api=Object.freeze({createFixture,FIXTURE_PIN,FIXTURE_SSID,SKILLS,LIMITS});
 if(commonJS)module.exports=api;else root.MicroDuckConsoleFixture=api;
})(typeof globalThis==='object'?globalThis:this);
