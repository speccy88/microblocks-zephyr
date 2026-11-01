/* SPDX-License-Identifier: MIT */
// Reviewed against pollen-robotics/microduck 96b89d8613f06722c1d64ce75ab0d7124fed9d8f.
((root)=>{
 'use strict';
 const API_VERSION=44,table=Object.create(null);
 class DuckError extends Error{constructor(code){super(code);this.name='DuckError';this.code=code;}}
 const fail=code=>{throw new DuckError(code);};
 const object=p=>{if(!p||Object.getPrototypeOf(p)!==Object.prototype)fail('PARAMS');return p;};
 const keys=(p,allowed)=>{object(p);if(Object.keys(p).some(k=>!allowed.includes(k)))fail('PARAMS');};
 const str=(x,max=128)=>typeof x==='string'&&x.length>0&&x.length<=max&&!/[\x00-\x1f\x7f]/.test(x);
 const integer=(x,min,max)=>Number.isSafeInteger(x)&&x>=min&&x<=max;
 const empty=p=>{keys(p,[]);return {};};
 const define=(names,validate=empty,options={})=>names.split(' ').forEach(name=>{table[name]=Object.freeze({validate,...options});});
 const component=p=>{keys(p,['component']);if(!str(p.component,64)||!/^[a-z][a-z0-9_-]*$/.test(p.component))fail('PARAMS');return {component:p.component};};
 const semver=x=>typeof x==='string'&&/^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-[0-9A-Za-z.-]+)?(?:\+[0-9A-Za-z.-]+)?$/.test(x)&&x.length<=128;
 const ssid=x=>str(x,32)&&new TextEncoder().encode(x).length<=32;
 define('hello',p=>{keys(p,['api_version']);const v=p.api_version??API_VERSION;if(!integer(v,1,255))fail('PARAMS');return {api_version:v};},{public:true});
 define('system.authenticate',p=>{keys(p,['pin']);if(typeof p.pin!=='string'||!/^\d{6}$/.test(p.pin))fail('PARAMS');return {pin:p.pin};},{public:true,secret:true});
 define('system.info system.services net.status net.scan robot.health robot.policies robot.skills robot.model robot.vetbook pad.status pad.bindings update.status');
 define('update.subscribe',empty,{stream:true});
 define('update.check update.listInstalled',component);
 define('update.log',p=>{keys(p,['limit']);const n=p.limit??20;if(!integer(n,1,100))fail('PARAMS');return {limit:n};});
 define('update.show',p=>{keys(p,['run']);const n=p.run??null;if(n!==null&&!integer(n,0,Number.MAX_SAFE_INTEGER))fail('PARAMS');return {run:n};});
 define('system.logs',p=>{keys(p,['unit','lines','boot']);const n=p.lines??50,b=p.boot??0;if(!str(p.unit,64)||!/^[A-Za-z0-9_-]+(?:\.service)?$/.test(p.unit)||!integer(n,1,500)||!integer(b,-1000,0))fail('PARAMS');return {unit:p.unit,lines:n,boot:b};});
 define('system.setName',p=>{keys(p,['name']);if(!str(p.name,64))fail('PARAMS');return {name:p.name};},{mutation:true});
 define('net.forget',p=>{keys(p,['ssid']);if(!ssid(p.ssid))fail('PARAMS');return {ssid:p.ssid};},{mutation:true});
 define('net.connect',p=>{keys(p,['ssid','psk']);if(!ssid(p.ssid))fail('PARAMS');const q={ssid:p.ssid};if(p.psk!==undefined&&p.psk!==null){if(typeof p.psk!=='string'||!((p.psk.length>=8&&p.psk.length<=63&&!/[\x00-\x1f\x7f]/.test(p.psk))||/^[a-f0-9]{64}$/i.test(p.psk)))fail('PARAMS');q.psk=p.psk;}return q;},{mutation:true,secret:true});
 define('robot.init',empty,{mutation:true,motion:true});
 define('robot.enable',p=>{keys(p,['on','toggle']);if(typeof p.on!=='boolean'||(p.toggle!==undefined&&typeof p.toggle!=='boolean'))fail('PARAMS');return {on:p.on,toggle:p.toggle??false};},{mutation:true,motion:true});
 define('robot.do',p=>{keys(p,['skill']);if(!str(p.skill,128))fail('PARAMS');return {skill:p.skill};},{mutation:true,motion:true});
 define('robot.sound',p=>{keys(p,['tag']);if(!['alarm','greet','inquire','peck','chirp','coo'].includes(p.tag))fail('PARAMS');return {tag:p.tag};},{mutation:true});
 define('update.rollback',component,{mutation:true});
 define('update.select',p=>{keys(p,['component','version']);const q=component({component:p.component});if(!semver(p.version))fail('PARAMS');return {...q,version:p.version};},{mutation:true});
 define('update.apply',p=>{keys(p,['component','target']);const q=component({component:p.component}),t=p.target??'latest';if(t!=='latest'){keys(t,['exact']);if(!semver(t.exact))fail('PARAMS');}return {...q,target:t,options:{}};},{mutation:true});
 function validate(method,params={}){if(typeof method!=='string'||!Object.hasOwn(table,method))fail('METHOD_DENIED');const policy=table[method];return {policy,params:policy.validate(params)};}
 // The helper asks the robot what it supports; it never assumes a fixed skill list.
 class Controls{
  constructor(client){this.client=client;this.skills=new Set();}
  async discover(){this.skills.clear();const policies=await this.client.request('robot.policies');const s=policies?.skills;if(Array.isArray(s))for(const name of s)if(str(name,128))this.skills.add(name);return policies;}
  performSkill(name,options={}){if(!this.skills.has(name))return Promise.reject(new DuckError('UNDISCOVERED_SKILL'));return this.client.request('robot.do',{skill:name},options);}
  quack(options={}){return this.client.request('robot.sound',{tag:'chirp'},options);}
 }
 const api=Object.freeze({API_VERSION,DuckError,validate,Controls,methods:Object.freeze(Object.keys(table))});
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckCommands=api;
})(typeof globalThis==='object'?globalThis:this);
