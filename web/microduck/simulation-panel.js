/* SPDX-License-Identifier: MIT */
/* Standalone simulation UI. No transport injection, secrets or raw command input. */
((root)=>{
 'use strict';
 const commonJS=typeof module==='object'&&module.exports;
 const simulation=commonJS?require('./simulation.js'):root.MicroDuckSimulation;
 function mount(container,{lifecycleTarget=root}={}){
  if(!container?.ownerDocument||!simulation)throw Error('A simulation container and fixture module are required.');
  const document=container.ownerDocument;
  const make=(tag,className,text)=>{const e=document.createElement(tag);if(className)e.className=className;if(text!==undefined)e.textContent=text;return e;};
  const panel=make('article','simulation-panel');panel.setAttribute('aria-label','MicroDuck simulation commissioning');
  const badge=make('p','simulation-badge','SIMULATION / NO ROBOT');
  const title=make('h2','','Try commissioning with fictional data');
  const scope=make('p','simulation-notice',simulation.NOTICE+' No Bluetooth, network connection, account, PIN or Wi-Fi password is used.');
  const status=make('p','simulation-status','Ready. Click Start SIMULATION to create an in-memory session.');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const start=make('button','primary','Start SIMULATION'),refresh=make('button','','Refresh fictional data'),end=make('button','','End simulation');
  for(const button of [start,refresh,end])button.type='button';
  const toolbar=make('div','simulation-toolbar');toolbar.append(start,refresh,end);
  const cards=make('div','simulation-cards');
  const outputs={};
  for(const [key,label] of [['identity','Fictional identity'],['network','Fictional Wi-Fi'],['health','Fictional health and battery'],['policies','Fictional skills and policies']]){
   const card=make('section','simulation-card');card.append(make('h3','',label));outputs[key]=make('p','simulation-'+key,'Start the simulation to read this fixture.');card.append(outputs[key]);cards.append(card);
  }
  const controls=make('div','simulation-controls'),groups=[];
  function group(key,label,items,method,parameter){
   const field=make('fieldset','simulation-action');field.append(make('legend','',label));
   const labelElement=make('label','','Choose a fictional value');const select=make('select','simulation-'+key+'-choice');
   select.setAttribute('aria-label',label+' value');labelElement.append(select);
   const confirmation=make('label','simulation-confirm');const check=make('input','simulation-'+key+'-confirm');check.type='checkbox';
   const checkText=make('span');confirmation.append(check,checkText);
   const button=make('button','simulation-'+key+'-run',label);button.type='button';
   const record={key,select,check,checkText,button,method,parameter};groups.push(record);
   function populate(values){select.replaceChildren();for(const value of values){const option=make('option','',value);option.value=value;select.append(option);}select.value=values[0]||'';}
   populate(items);record.populate=populate;
   record.clear=()=>{check.checked=false;checkText.textContent='I confirm this simulated action only: '+select.value;};record.clear();
   select.addEventListener('change',()=>{record.clear();update();});check.addEventListener('change',update);
   button.addEventListener('click',async()=>{
    if(disposed||busy||!ready||!check.checked||!select.value)return;
    const value=select.value;record.clear();
    await run(async()=>{const result=await session.request(method,{[parameter]:value},{confirmed:true});await readFixtures();status.textContent='SIMULATION recorded '+method+'. No physical action occurred. '+JSON.stringify(result);});
   });
   field.append(labelElement,confirmation,button);controls.append(field);return record;
  }
  group('network','Simulate joining the demo network',[simulation.SSID],'net.connect','ssid');
  group('sound','Record a simulated sound',simulation.SOUNDS,'robot.sound','tag');
  const skills=group('skill','Record a simulated skill',[],'robot.do','skill');
  const log=make('pre','simulation-log','No simulated actions recorded.');log.setAttribute('aria-label','Bounded simulated action history');
  panel.append(badge,title,scope,toolbar,status,cards,controls,make('h3','','Simulated action history'),log);container.append(panel);
  let disposed=false,busy=false,ready=false,generation=0,session=null;
  function update(){
   start.disabled=disposed||busy||ready;refresh.disabled=disposed||busy||!ready;end.disabled=disposed||!session;
   for(const g of groups){g.select.disabled=g.check.disabled=disposed||busy||!ready||!g.select.value;g.button.disabled=g.check.disabled||!g.check.checked;}
  }
  function clearConfirmations(){for(const g of groups)g.clear();}
  async function readFixtures(){
   const info=await session.request('system.info'),network=await session.request('net.status'),scan=await session.request('net.scan');
   const health=await session.request('robot.health'),policies=await session.request('robot.policies'),details=await session.request('robot.skills');
   outputs.identity.textContent=info.name+' / API 44 / simulated: '+info.simulated+' / no physical serial';
   outputs.network.textContent='SIMULATION: '+network.state+'. Demo SSID: '+scan.networks[0].ssid+'. Fictional IPv4: '+(network.ip4||'not joined')+'. 192.0.2.44 is a documentation address; no installation command is generated.';
   outputs.health.textContent='FICTIONAL battery: '+health.battery.percent+'% / '+health.battery.volts+' V. '+health.reason;
   outputs.policies.textContent='SIMULATION: policies enabled: '+policies.enabled+'; discovered skills: '+details.skills.map(s=>s.name).join(', ')+'. These are fixtures, not measured robot capabilities.';
   skills.populate(policies.skills);clearConfirmations();
   const entries=session.snapshot().actions;log.textContent=entries.length?JSON.stringify(entries,null,2):'No simulated actions recorded.';
  }
  async function run(action){
   if(disposed||busy)return;const ticket=generation;busy=true;update();
   try{await action();}catch(error){if(!disposed&&ticket===generation)status.textContent='SIMULATION stopped this operation: '+String(error?.code||'FAILED').replace(/[^A-Z0-9_-]/g,'').slice(0,64);}
   finally{if(!disposed&&ticket===generation){busy=false;update();}}
  }
  start.addEventListener('click',async()=>{
   if(disposed||busy||ready)return;session=simulation.createSession();
   await run(async()=>{await session.start();await readFixtures();ready=true;status.textContent='SIMULATION session ready. All data is fictional; confirm each simulated action separately.';});
  });
  refresh.addEventListener('click',async()=>{if(ready&&!busy&&!disposed)await run(async()=>{await readFixtures();status.textContent='SIMULATION fixtures refreshed. Nothing was read from hardware.';});});
  function stop(){
   ++generation;session?.close();session=null;ready=false;busy=false;clearConfirmations();skills.populate([]);
   for(const output of Object.values(outputs))output.textContent='Simulation ended. Start again for fresh fictional data.';
   log.textContent='No simulated actions recorded.';status.textContent='SIMULATION ended. Nothing was sent to a robot.';update();
  }
  end.addEventListener('click',()=>{if(!disposed)stop();});
  const pagehide=()=>{if(!disposed)stop();};lifecycleTarget?.addEventListener?.('pagehide',pagehide);update();
  return Object.freeze({element:panel,snapshot:()=>session?.snapshot()||null,destroy(){if(disposed)return;stop();disposed=true;lifecycleTarget?.removeEventListener?.('pagehide',pagehide);panel.remove();}});
 }
 const api=Object.freeze({mount});if(commonJS)module.exports=api;else root.MicroDuckSimulationPanel=api;
 const target=root.document?.currentScript?.dataset?.mount;if(target){const container=root.document.getElementById(target);if(container)mount(container);}
})(typeof globalThis==='object'?globalThis:this);
