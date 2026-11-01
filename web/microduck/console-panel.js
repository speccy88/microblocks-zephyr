/* SPDX-License-Identifier: MIT */
/* Protected API44 UI. No transport opens and no RPC is sent by mount/attach. */
(function(root){
 'use strict';
 const commonJS=typeof module==='object'&&module.exports;
 const core=commonJS?require('./console-core.js'):root.MicroDuckConsole;
 const bluetooth=commonJS?require('./bluetooth.js'):root.MicroDuckBluetooth;
 const fixtures=commonJS?require('./console-fixture.js'):root.MicroDuckConsoleFixture;
 const RESULT_LIMIT=8192;
 const cleanText=(value,limit=256)=>String(value).replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g,' ').slice(0,limit);
 function resultText(value){
  const seen=new WeakSet();
  function copy(item,depth=0){
   if(item===null||typeof item==='boolean'||typeof item==='number')return item;
   if(typeof item==='string')return cleanText(item,4096);
   if(typeof item!=='object')return '[unsupported value]';
   if(depth>=8)return '[depth limit]';
   if(seen.has(item))return '[circular value]';seen.add(item);
   if(Array.isArray(item))return item.slice(0,32).map(value=>copy(value,depth+1));
   const output=Object.create(null);
   for(const key of Object.keys(item).slice(0,32))output[cleanText(key,128)]=/^(?:pin|psk|password|passphrase|token|access_token|refresh_token|secret|credentials?)$/i.test(key)?'[redacted]':copy(item[key],depth+1);
   return output;
  }
  const text=JSON.stringify(copy(value),null,2)??'null';
  return text.length>RESULT_LIMIT?text.slice(0,RESULT_LIMIT)+'\n[result truncated]':text;
 }
 function mount(container,options={}){
  if(!container?.ownerDocument||!core?.Controller||!Array.isArray(core.METHODS)||!fixtures?.createFixture)throw Error('Load the reviewed console core and fixture before mounting.');
  const controller=new core.Controller(),document=container.ownerDocument;
  const provider=Object.hasOwn(options,'bluetooth')?options.bluetooth:root.navigator?.bluetooth;
  const lifecycle=options.lifecycleTarget||root,timeoutMs=options.timeoutMs??10000,watchDurationMs=options.watchDurationMs??60000;
  if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>120000)throw Error('Invalid console timeout.');
  if(!Number.isInteger(watchDurationMs)||watchDurationMs<1||watchDurationMs>300000)throw Error('Invalid watch duration.');
  const supported=root.isSecureContext!==false&&typeof provider?.requestDevice==='function';
  const make=(tag,className,text)=>{const element=document.createElement(tag);if(className)element.className=className;if(text!==undefined)element.textContent=text;return element;};
  const button=(className,text)=>{const element=make('button',className,text);element.type='button';return element;};
  const label=(text,input)=>{const element=make('label','console-field',text);element.append(input);return element;};
  const option=(select,value,text=value)=>{const element=make('option','',text);element.value=value;select.append(element);};
  const panel=make('article','connection-card hosted microduck-console');panel.setAttribute('aria-label','Protected MicroDuck console');
  const heading=make('h2','','Protected MicroDuck console');
  const scope=make('p','tag','API 44 / physical MicroDuck validation pending. Preparing a request sends nothing.');
  const status=make('p','console-status','Detached. Choose in-memory simulation or explicitly select a Bluetooth device.');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const simulation=button('console-simulation','Use in-memory simulation'),choose=button('console-bluetooth','Choose Web Bluetooth device'),disconnect=button('console-disconnect','Disconnect');
  const toolbar=make('div','board-picker console-toolbar');toolbar.append(simulation,choose,disconnect);
  const identity=make('p','console-identity','No client attached.');
  const confidentiality=make('p','console-confidentiality','No PIN or Wi-Fi password form is available without an attached, verified confidential client. Web Bluetooth cannot establish that guarantee.');
  const credentials=make('div','console-credentials');
  const method=make('select','console-method');method.setAttribute('aria-label','Reviewed method');
  const methods=core.METHODS.filter(name=>typeof name==='string'&&!['system.authenticate','net.connect','update.subscribe'].includes(name));
  for(const name of methods)option(method,name);
  method.value=methods[0]||'';
  const params=make('textarea','console-params');params.rows=7;params.maxLength=8192;params.spellcheck=false;params.setAttribute('aria-label','JSON parameters');params.value=core.EXAMPLES?.[method.value]||'{}';
  const jsonField=label('Strict JSON object parameters',params);
  const skill=make('select','console-skill');skill.setAttribute('aria-label','Previously discovered skill');
  const skillField=label('Skill from the latest explicit discovery',skill);
  const skillHelp=make('p','console-skill-help','First prepare and execute robot.policies. Only discovered skills can be selected. A skill is rechecked before dispatch.');skillField.append(skillHelp);
  const prepare=button('console-prepare','Prepare / Review'),refresh=button('console-refresh','Clear review and result');
  const reviewActions=make('div','board-picker console-review-actions');reviewActions.append(prepare,refresh);
  const previewBox=make('pre','console-preview','No request prepared.');previewBox.setAttribute('aria-label','Redacted request preview');
  const confirm=make('input','console-confirm');confirm.type='checkbox';
  const confirmText=make('span','','Prepare a specific request before confirming.');
  const confirmLabel=make('label','console-confirm-label');confirmLabel.append(confirm,confirmText);
  const execute=button('console-execute','Execute prepared request'),cancel=button('console-cancel','Cancel and close session');
  const executeActions=make('div','board-picker console-execute-actions');executeActions.append(execute,cancel);
  const cancelScope=make('p','console-cancel-scope','Cancel closes the local RPC session. An accepted remote operation may already have happened. This is not an emergency stop, rollback or retry.');
  const result=make('pre','console-result','No transient result.');result.setAttribute('aria-label','Transient bounded result');
  const resultScope=make('p','console-result-scope','Results are temporary text and are never saved or exported automatically. Daemon log text may contain sensitive data; clear it when finished.');
  const watch=button('console-watch','Watch update progress'),watchStop=button('console-watch-stop','Stop watching and disconnect'),watchAdvance=button('console-watch-advance','Advance fictional progress sample');
  const watchActions=make('div','board-picker console-watch-actions');watchActions.append(watch,watchStop,watchAdvance);
  const watchStatus=make('p','console-watch-status','No read-only watch. Starting consumes any prepared confirmation; other requests require a new session after watching.');watchStatus.setAttribute('role','status');
  const watchResult=make('pre','console-watch-result','No progress samples.');watchResult.setAttribute('aria-label','Latest eight update progress samples');
  const watchScope=make('p','console-watch-scope','Watch sends only update.subscribe. It observes for at most '+watchDurationMs+' ms or 128 notifications, then closes the session. Only the latest eight typed samples appear; arbitrary detail text is omitted. Idle and 100 percent do not prove success. Stopping observation cannot cancel or roll back an update. Physical robot validation remains pending.');
  const audit=make('pre','console-audit','No request metadata.');audit.setAttribute('aria-label','Bounded audit metadata');
  const docs=make('a','console-docs','Read the console contract and hardware boundaries');docs.href='https://github.com/speccy88/microblocks-zephyr/blob/main/linux/microduck/CONSOLE.md';docs.target='_blank';docs.rel='noopener noreferrer';
  panel.append(heading,scope,status,toolbar,identity,confidentiality,credentials,label('Reviewed method',method),jsonField,skillField,reviewActions,previewBox,confirmLabel,executeActions,cancelScope,make('h3','','Transient result'),result,resultScope,make('h3','','Read-only update observation'),watchActions,watchStatus,watchResult,watchScope,make('h3','','Audit metadata only'),audit,docs);container.append(panel);
  let disposed=false,generation=0,revision=0,busy=false,operation=null,choosing=false,pendingDevice=null,unknownOutcome=false,watching=false,watchHandle=null,watchRows=[];
  const unknownNotice='A sent operation has an unknown outcome; inspect remote state before another action.';
  let client=null,connection=null,fixture=null,prepared=null,credentialMode=null,skillChoices=null,secretInputs=[],authButton=null,networkButton=null;
  const snapshot=()=>controller.snapshot();
  const prefix=()=>snapshot().simulation?'SIMULATION / FICTIONAL: ':'';
  const fixedCode=error=>core.safeCode?core.safeCode(error):'FAILED';
  function clearSecrets(){for(const field of secretInputs)field.value='';}
  function clearReview(message){
   ++revision;prepared=null;confirm.checked=false;previewBox.textContent='No request prepared.';confirmText.textContent='Prepare a specific request before confirming.';result.textContent='No transient result.';controller.invalidate();
   if(message)status.textContent=prefix()+message;
  }
  function renderAudit(state){
   const allowed=new Set([...methods,'system.authenticate','net.connect']);
   const rows=(Array.isArray(state.history)?state.history:[]).slice(-32).map(entry=>({
    sequence:Number.isSafeInteger(entry.sequence)&&entry.sequence>=0?entry.sequence:0,
    method:allowed.has(entry.method)?entry.method:'[unavailable]',
    outcome:['completed','not_sent','rejected','unknown','cancelled','pending'].includes(entry.outcome)?entry.outcome:'unavailable',
    code:entry.code?fixedCode({code:entry.code}):'',simulation:entry.simulation===true
   }));
   audit.textContent=rows.length?JSON.stringify(rows,null,2):'No request metadata.';
  }
  function setPreview(value){
   prepared=value;confirm.checked=false;
   previewBox.textContent=prefix()+cleanText(value.method,64)+'\n'+cleanText(value.paramsPreview,8192)+'\nMutation: '+(value.mutation===true)+' / motion: '+(value.motion===true);
   confirmText.textContent=value.mutation?'I confirm '+(value.simulation?'the simulated ':'')+value.method+' request with exactly the reviewed parameters.'+(value.motion?' This request may cause motion on real hardware.':''):'This reviewed request is read-only; no mutation confirmation is needed.';
  }
  function closeConnection(value){
   if(!value)return;
   value.device?.removeEventListener?.('gattserverdisconnected',value.panelDrop);
   try{value.client?.close('DISCONNECTED');}catch{}
  }
  function closeOwned(){
   const previous=connection;connection=null;closeConnection(previous);
   const previousFixture=fixture;fixture=null;try{previousFixture?.close();}catch{}
  }
  function detach(message='Disconnected. Reconnect explicitly; nothing is replayed.'){
   const previousState=snapshot(),simulationPrefix=previousState.simulation?'SIMULATION / FICTIONAL: ':'';
   if((busy||previousState.busy)&&!watching)unknownOutcome=true;
   ++generation;++revision;operation=null;busy=false;clearSecrets();closeOwned();controller.detach();client=null;
   watching=false;watchHandle=null;watchRows=[];watchResult.textContent='No progress samples.';watchStatus.textContent='No read-only watch. Observation does not start, cancel or roll back an updater operation.';
   try{pendingDevice?.gatt?.disconnect();}catch{}
   prepared=null;confirm.checked=false;params.value='{}';previewBox.textContent='No request prepared.';result.textContent='No transient result.';confirmText.textContent='Prepare a specific request before confirming.';
   status.textContent=simulationPrefix+message;update();
  }
  function attach(value,metadata){
   if(disposed){try{value?.close('DISCONNECTED');}catch{}throw Error('Console destroyed.');}
   detach('Replacing session.');
   try{controller.attach(value,metadata);client=value;clearReview();status.textContent=prefix()+'Client attached, API 44. No hello, authentication or protected request has been sent.';update();}
   catch(error){try{value?.close('DISCONNECTED');}catch{}client=null;status.textContent='Client refused: '+fixedCode(error)+'. No request sent.';update();throw error;}
  }
  async function run(action,onSuccess){
   if(disposed||busy||!client)return;
   const ticket=generation,edit=revision,token={};busy=true;operation=token;update();
   try{
    const value=await action();
    if(!disposed&&ticket===generation&&edit===revision&&operation===token){onSuccess?.(value);}
   }catch(error){
    if(!disposed&&ticket===generation&&edit===revision&&operation===token){
     clearSecrets();result.textContent='No transient result.';
     const outcome=['not_sent','rejected','unknown'].includes(error?.outcome)?error.outcome:'unavailable';
     if(outcome==='unknown')unknownOutcome=true;
     status.textContent=prefix()+'Request stopped: '+fixedCode(error)+' / '+outcome+'. '+(outcome==='unknown'?'Inspect the remote state before any new action. No retry occurred.':'No automatic retry occurred.');
    }
   }finally{if(!disposed&&ticket===generation&&operation===token){busy=false;operation=null;update();}}
  }
  function renderCredentials(state){
   const mode=!client?'none':state.simulation?'simulation':state.confidential===true?'confidential':'blocked';
   if(mode===credentialMode)return;
   clearSecrets();secretInputs=[];authButton=null;networkButton=null;credentialMode=mode;credentials.replaceChildren();
   if(mode==='none'||mode==='blocked')return;
   const credentialGeneration=generation;
   const current=()=>!disposed&&credentialGeneration===generation&&mode===credentialMode&&!!client;
   const group=make('fieldset','console-auth');group.append(make('legend','',mode==='simulation'?'Fixed fictional authentication':'Transient confidential authentication'));
   let pin;
   if(mode==='confidential'){
    pin=make('input','console-pin');pin.type='password';pin.maxLength=6;pin.autocomplete='off';pin.inputMode='numeric';pin.setAttribute('aria-label','Transient six-digit PIN');secretInputs.push(pin);group.append(label('Six-digit PIN; cleared on submit',pin));pin.addEventListener('input',()=>{if(!current())return;clearReview('Authentication input edited; prior review cleared.');update();});
   }
   authButton=button('console-authenticate',mode==='simulation'?'Authenticate fixed fictional fixture':'Authenticate once');group.append(authButton);
   authButton.addEventListener('click',async()=>{
    if(!current()||busy)return;clearReview();
    let request;try{request=controller.authenticate(mode==='simulation'?core.FIXTURE_PIN:pin.value);}catch(error){request=Promise.reject(error);}finally{clearSecrets();}
    await run(()=>request,()=>{result.textContent='No transient result.';status.textContent=prefix()+'Authentication request completed. Only the authentication state is retained.';});
   });
   const network=make('fieldset','console-provisioning');network.append(make('legend','',mode==='simulation'?'Fictional open network':'Transient confidential Wi-Fi provisioning'));
   let ssid,psk;
   if(mode==='simulation'){
    ssid=make('select','console-ssid');option(ssid,core.FIXTURE_SSID);ssid.value=core.FIXTURE_SSID;network.append(label('Fictional open SSID only',ssid));
   }else{
    ssid=make('input','console-ssid');ssid.type='text';ssid.maxLength=32;ssid.autocomplete='off';
    psk=make('input','console-psk');psk.type='password';psk.maxLength=64;psk.autocomplete='off';secretInputs.push(ssid,psk);
    network.append(label('SSID; cleared on prepare',ssid),label('PSK; cleared on prepare, omitted for an open network',psk));
   }
   for(const field of [ssid,psk].filter(Boolean))field.addEventListener('input',()=>{if(!current())return;clearReview('Network input edited; prior review cleared.');update();});
   ssid.addEventListener('change',()=>{if(!current())return;clearReview('Network choice changed; prior review cleared.');update();});
   networkButton=button('console-provision-prepare','Prepare network request');network.append(networkButton);
   networkButton.addEventListener('click',()=>{
    if(!current()||busy)return;clearReview();
    try{const value=controller.previewProvisioning({ssid:ssid.value,...(psk?.value?{psk:psk.value}:{})});setPreview(value);status.textContent=prefix()+'Network request prepared locally. Review the redacted parameters and confirm this specific request.';}
    catch(error){status.textContent=prefix()+'Preparation refused: '+fixedCode(error)+'. No request sent.';}
    finally{clearSecrets();update();}
   });
   credentials.append(group,network);
  }
  function update(){
   if(disposed)return;
   const state=snapshot();
   const attached=!!client&&!client.closed&&state.apiVersion===44;
   if(client&&!attached){++revision;prepared=null;confirm.checked=false;clearSecrets();result.textContent='No transient result.';previewBox.textContent='No request prepared.';client=null;closeOwned();status.textContent=status.textContent.includes(' / unknown.')?status.textContent+' Session closed.':(state.simulation?'SIMULATION / FICTIONAL: ':'')+'Session closed. Reconnect explicitly; no operation will be replayed.';}
   renderCredentials(state);
   identity.textContent=attached?(state.simulation?'SIMULATION / FICTIONAL client':'Attached client')+' / API 44 / authenticated: '+(state.authenticated===true)+' / confidential transport: '+(state.confidential===true):'No client attached.';
   confidentiality.textContent=attached&&state.simulation?'SIMULATION / FICTIONAL: the in-memory fixture accepts only its public fixture PIN and fictional open SSID. No robot or network is contacted.':attached&&state.confidential===true?'The attached client declares verified confidentiality. PIN and PSK fields are transient, cleared on submit, and absent from review/audit. Physical MicroDuck validation is still pending.':'Web Bluetooth confidentiality is unverified. Authentication and Wi-Fi provisioning forms are absent; protected requests require authentication. There is no override checkbox or insecure fallback.';
   const advertised=(Array.isArray(state.skills)?state.skills:[]).filter(name=>typeof name==='string'&&name.length>0&&name.length<=128).slice(0,128);
   const choices=JSON.stringify(advertised);
   if(choices!==skillChoices){const previousSkill=skill.value;skill.replaceChildren();for(const name of advertised)option(skill,name,cleanText(name,128));skill.value=advertised.includes(previousSkill)?previousSkill:advertised[0]||'';skillChoices=choices;}
   skillField.hidden=method.value!=='robot.do';jsonField.hidden=method.value==='robot.do';
   simulation.disabled=disposed||busy||choosing;choose.disabled=disposed||busy||choosing||!supported;disconnect.disabled=!client&&!choosing;
   method.disabled=params.disabled=busy||!attached;skill.disabled=busy||!attached||!advertised.length;
   prepare.disabled=busy||!attached||(method.value==='robot.do'&&!skill.value);refresh.disabled=busy||!attached&&!watchRows.length;
   confirm.disabled=busy||!prepared||!prepared.mutation;execute.disabled=busy||!attached||!prepared||(prepared.mutation&&!confirm.checked);
   cancel.disabled=!attached&&!choosing;
   watch.disabled=busy||!attached||state.authenticated!==true;watchStop.disabled=!watching;
   watchAdvance.hidden=!state.simulation;watchAdvance.disabled=!watching||!attached||!fixture;
   if(authButton)authButton.disabled=busy||!attached;
   if(networkButton)networkButton.disabled=busy||!attached||state.authenticated!==true;
   for(const field of secretInputs)field.disabled=busy||!attached;
   if(state.simulation&&result.textContent==='No transient result.')result.textContent='SIMULATION / FICTIONAL: No transient result.';
   if(unknownOutcome&&!status.textContent.includes(unknownNotice))status.textContent+=' '+unknownNotice;
   renderAudit(state);
  }
  const edited=()=>{if(disposed)return;clearReview('Inputs changed. Prepare and confirm a fresh request.');update();};
  method.addEventListener('change',()=>{params.value=core.EXAMPLES?.[method.value]||'{}';clearSecrets();edited();});params.addEventListener('input',edited);params.addEventListener('change',edited);skill.addEventListener('change',edited);
  confirm.addEventListener('change',()=>{if(!disposed)update();});
  refresh.addEventListener('click',()=>{if(disposed||busy)return;clearSecrets();clearReview('Review and transient result cleared locally. No refresh request was sent.');watchRows=[];watchResult.textContent='No progress samples.';watchStatus.textContent='No read-only watch. Previous observation cleared locally.';update();});
  prepare.addEventListener('click',()=>{
   if(disposed||busy||!client)return;clearReview();
   try{
    if(!methods.includes(method.value))throw {code:'METHOD_DENIED'};
    let text=params.value;
    if(method.value==='robot.do'){
     if(!snapshot().skills?.includes(skill.value))throw {code:'UNDISCOVERED_SKILL'};
     text=JSON.stringify({skill:skill.value});
    }
    setPreview(controller.preview(method.value,text));status.textContent=prefix()+'Prepared locally. Review the exact method and parameters before executing.';
   }catch(error){const code=fixedCode(error);if(code==='SECRET_INPUT_DENIED'||code==='SECRET_FORM_REQUIRED')params.value='{}';status.textContent=prefix()+'Preparation refused: '+code+'. No request sent.';}
   update();
  });
  execute.addEventListener('click',async()=>{
   if(disposed||busy||!client||!prepared||(prepared.mutation&&!confirm.checked))return;
   const value=prepared,confirmed=confirm.checked;prepared=null;confirm.checked=false;previewBox.textContent='Prepared request consumed; no replay is available.';confirmText.textContent='Prepare a new request for another execution.';
   await run(()=>controller.execute(value,{confirmed}),response=>{result.textContent=prefix()+resultText(response.result);status.textContent=prefix()+cleanText(response.method,64)+' completed. This result is transient; no automatic retry occurred.';});
  });
  watch.addEventListener('click',async()=>{
   if(disposed||busy||!client||snapshot().authenticated!==true)return;
   clearSecrets();clearReview();watchRows=[];watchResult.textContent=prefix()+'No progress samples.';
   const ticket=generation,active=client;busy=true;watching=true;watchHandle=null;watchStatus.textContent=prefix()+'Starting read-only observation; awaiting write acknowledgements.';update();
   const current=()=>!disposed&&ticket===generation&&client===active;
   try{
    const handle=await active.watchUpdates({durationMs:watchDurationMs,maxEvents:128,
     onProgress:sample=>{if(!current())return;watchRows.push(sample);if(watchRows.length>8)watchRows.shift();watchResult.textContent=prefix()+JSON.stringify(watchRows,null,2);},
     onEnd:end=>{if(!current())return;busy=false;watching=false;watchHandle=null;watchStatus.textContent=prefix()+'Read-only observation ended: '+fixedCode({code:end.code})+'. This is not an update outcome; no retry occurred.';update();}
    });
    if(current()&&!active.closed){watchHandle=handle;watchStatus.textContent=prefix()+'Read-only watch active. Write ACKs do not prove daemon acceptance or update completion.';update();}
   }catch(error){if(current()){busy=false;watching=false;watchHandle=null;watchStatus.textContent=prefix()+'Read-only watch stopped: '+fixedCode(error)+'. No automatic retry or updater action occurred.';update();}}
  });
  watchStop.addEventListener('click',()=>{if(disposed||!watching)return;if(watchHandle)watchHandle.stop();else client?.close('WATCH_STOPPED');});
  watchAdvance.addEventListener('click',()=>{if(disposed||!watching||!fixture||!snapshot().simulation)return;try{fixture.advanceUpdate();}catch(error){watchStatus.textContent=prefix()+'Fictional sample refused: '+fixedCode(error)+'.';}update();});
  cancel.addEventListener('click',()=>{if(disposed)return;controller.cancel();detach('Local session cancelled and closed. A sent operation may already have happened; this is not an emergency stop.');});
  disconnect.addEventListener('click',()=>{if(!disposed)detach();});
  simulation.addEventListener('click',()=>{
   if(disposed||busy||choosing)return;
   const value=fixtures.createFixture({timeoutMs});
   try{attach(value.client,{apiVersion:value.apiVersion,simulation:true});fixture=value;update();}
   catch{value.close();}
  });
  choose.addEventListener('click',async()=>{
   if(disposed||busy||choosing||!supported)return;
   detach('Select a device explicitly. GATT API discovery sends no JSON-RPC request.');
   const ticket=generation;choosing=true;pendingDevice=null;update();
   const guarded={requestDevice(filters){return Promise.resolve(provider.requestDevice(filters)).then(device=>{
    if(disposed||ticket!==generation){try{if(device?.gatt?.connected)device.gatt.disconnect();}catch{}throw {code:'CANCELLED'};}
    pendingDevice=device;return device;
   });}};
   let value;
   try{
    value=await bluetooth.connect({bluetooth:guarded,timeoutMs});
    if(disposed||ticket!==generation){closeConnection(value);return;}
    pendingDevice=null;attach(value.client,{apiVersion:value.apiVersion,simulation:false});connection=value;
    value.panelDrop=()=>{if(!disposed&&connection===value)detach('Bluetooth disconnected. A new session requires explicit selection; nothing is replayed.');};
    value.device.addEventListener('gattserverdisconnected',value.panelDrop);update();
   }catch(error){
    closeConnection(value);
    if(!disposed&&ticket===generation){
     if(error?.name==='NotFoundError')status.textContent='Bluetooth chooser cancelled. No request was sent.';
     else if(['NotAllowedError','SecurityError'].includes(error?.name))status.textContent='Bluetooth access was not granted. No request was sent.';
     else if(error?.code==='GATT_TIMEOUT')status.textContent='Bluetooth discovery timed out. Any established connection has been closed; no JSON-RPC request was sent.';
     else status.textContent='Bluetooth selection refused: '+(['GATT_PROPERTIES','API_VERSION','WEB_BLUETOOTH_UNAVAILABLE','CANCELLED'].includes(error?.code)?error.code:fixedCode(error))+'. No automatic retry occurred.';
    }
   }finally{choosing=false;pendingDevice=null;if(!disposed)update();}
  });
  const pagehide=()=>{if(!disposed)detach('Session closed on page exit; transient credentials and results cleared.');};lifecycle?.addEventListener?.('pagehide',pagehide);
  if(!supported)status.textContent+=' Web Bluetooth is unavailable in this browser/context; the explicit in-memory simulation remains available.';
  update();
  return Object.freeze({element:panel,controller,attach,detach(){if(!disposed)detach();},destroy(){if(disposed)return;detach('Console closed.');disposed=true;lifecycle?.removeEventListener?.('pagehide',pagehide);panel.remove();}});
 }
 const api=Object.freeze({mount});if(commonJS)module.exports=api;else root.MicroDuckConsolePanel=api;
 const target=root.document?.currentScript?.dataset?.mount;if(target){const container=root.document.getElementById(target);if(container)mount(container);}
})(typeof globalThis==='object'?globalThis:this);
