/* SPDX-License-Identifier: MIT */
/* In-memory API44 fixtures, never a robot transport. No user secrets accepted. */
((root)=>{
 'use strict';
 const commonJS=typeof module==='object'&&module.exports;
 const commands=commonJS?require('./commands.js'):root.MicroDuckCommands;
 const rpc=commonJS?require('./rpc.js'):root.MicroDuckRpc;
 const NOTICE='SIMULATION ONLY. No robot is connected. Identity, network, battery and actions are fictional.';
 const SSID='SIMULATION-NET-OPEN',IP='192.0.2.44';
 const SKILLS=Object.freeze(['simulation_bow','simulation_nod']);
 const SOUNDS=Object.freeze(['alarm','greet','inquire','peck','chirp','coo']);
 const MAX_ACTIONS=32,MAX_REQUESTS=256,TRACE_LIMIT=64;
 const ALLOWED=new Set(['hello','system.info','net.status','net.scan','net.connect','robot.health','robot.policies','robot.skills','robot.sound','robot.do']);
 const copy=value=>JSON.parse(JSON.stringify(value));
 const fail=code=>{throw new commands.DuckError(code);};

 function createSession(){
  if(!commands||!rpc||commands.API_VERSION!==44)throw Error('Reviewed API44 commands and RPC modules are required.');
  let phase='new',receive=null,joined=false,authenticated=false;
  const discovered=new Set(),actions=[],trace=[];
  const stats={requests:0,writeChunks:0,replyChunks:0,maxWriteBytes:0};
  const lines=new rpc.Lines(rpc.MAX_REQUEST);
  function answer(q){
   if(q.method==='hello')return {api_version:44,daemon_version:'0.0.0-simulation',revision:null};
   // This fixed, fictional fixture PIN is never supplied by a user or a device.
   if(q.method==='system.authenticate'){
    authenticated=q.params.pin==='000000';return {authenticated,attempts_remaining:3};
   }
   if(!authenticated)fail('AUTH_REQUIRED');
   switch(q.method){
    case 'system.info':return {name:'SIMULATION Duck',serial:null,uptime_seconds:0,simulated:true};
    case 'net.scan':return {networks:[{ssid:SSID,signal:88,security:'open',saved:joined}]};
    case 'net.status':return {state:joined?'connected':'disconnected',ssid:joined?SSID:null,signal:joined?88:null,ip4:joined?IP:null,ip6:null,mac:null,iface:joined?'simulation0':null};
    case 'robot.health':return {healthy:false,degraded:true,reason:NOTICE+' Battery values are fictional.',battery:{volts:7.8,percent:73.25},bus:{consecutive_errors:0,startup_failures:0}};
    case 'robot.policies':return {mode:'walk',enabled:false,slots:[],skills:[...SKILLS],homed:false,sitting:false,change_error:NOTICE};
    case 'robot.skills':return {skills:SKILLS.map(name=>({name,duration:1.0}))};
    default:{
     if(actions.length>=MAX_ACTIONS)fail('ACTION_LIMIT');
     actions.push({sequence:actions.length+1,method:q.method,params:copy(q.params),simulation:true});
     if(q.method==='net.connect'){joined=true;return {outcome:'connected',ssid:SSID,ip4:IP};}
     return {accepted:true,reason:'SIMULATION ONLY: recorded; no physical action occurred.',simulated:true};
    }
   }
  }
  // The only transport is allocated inside this closure. There is no provider,
  // URL, GATT characteristic or caller-supplied transport that could be forwarded.
  const transport=Object.freeze({confidential:true,
   subscribe(onBytes){receive=onBytes;return ()=>{receive=null;};},
   async write(chunk){
    if(phase==='closed')fail('DISCONNECTED');
    stats.writeChunks++;stats.maxWriteBytes=Math.max(stats.maxWriteBytes,chunk.length);
    for(const line of lines.push(chunk)){
     const q=JSON.parse(line);
     if(++stats.requests>MAX_REQUESTS)fail('SIMULATION_LIMIT');
     trace.push({id:q.id,method:q.method});if(trace.length>TRACE_LIMIT)trace.shift();
     const reply={jsonrpc:'2.0',id:q.id,result:answer(q)};
     const bytes=new TextEncoder().encode(JSON.stringify(reply)+'\n');
     // Deliberately fragment replies across UTF-8/JSON boundaries and deliver
     // before this final write acknowledgement; the real RpcClient owns ordering.
     for(let at=0;at<bytes.length;at+=7){stats.replyChunks++;receive?.(bytes.subarray(at,at+7));}
     bytes.fill(0);
    }
   },
   close(){phase='closed';authenticated=false;lines.clear();receive=null;}
  });
  const client=new rpc.RpcClient(transport);
  const snapshot=()=>copy({simulation:true,notice:NOTICE,phase,joined,actions,trace,stats});
  async function start(){
   if(phase!=='new')fail(phase==='closed'?'DISCONNECTED':'BUSY');
   phase='starting';
   try{const hello=await client.request('hello');await client.authenticate('000000');phase='ready';return hello;}
   catch(error){client.close();throw error;}
  }
  async function request(method,params={},options={}){
   if(phase!=='ready')fail(phase==='closed'?'DISCONNECTED':'AUTH_REQUIRED');
   if(!ALLOWED.has(method))fail('METHOD_DENIED');
   const checked=commands.validate(method,params);
   if(method==='net.connect'&&(Object.hasOwn(checked.params,'psk')||checked.params.ssid!==SSID))fail('SIMULATION_INPUT');
   if(method==='robot.do'&&!discovered.has(checked.params.skill))fail('UNDISCOVERED_SKILL');
   if(checked.policy.mutation&&options?.confirmed!==true)fail('CONFIRMATION_REQUIRED');
   if(checked.policy.mutation&&actions.length>=MAX_ACTIONS)fail('ACTION_LIMIT');
   const result=await client.request(method,checked.params,options);
   if(method==='robot.policies'){discovered.clear();for(const name of result.skills)discovered.add(name);}
   return result;
  }
  return Object.freeze({simulation:true,start,request,snapshot,close(){client.close();discovered.clear();}});
 }
 const api=Object.freeze({createSession,NOTICE,SSID,IP,SKILLS,SOUNDS,MAX_ACTIONS,MAX_REQUESTS,TRACE_LIMIT});
 if(commonJS)module.exports=api;else root.MicroDuckSimulation=api;
})(typeof globalThis==='object'?globalThis:this);
