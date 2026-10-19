/* SPDX-License-Identifier: MPL-2.0
 * Actual GP runtime adapter: browser projects, USB and optional secure WS.
 * No network credential requests, server project writes or analytics. */
(() => {
 'use strict';
 const {ProjectStore,ByteQueue,SerialTransport,MAX_PROJECT}=MicroBlocksPortal;
 const profile=PORTAL_BOARD,store=new ProjectStore(),input=new ByteQueue();
 const filters=profile.board==='fruit-jam'?[{usbVendorId:0x2fe3,usbProductId:4}]:profile.board==='waveshare'?[{usbVendorId:0x303a},{usbVendorId:0x10c4}]:[];
 let status,saveStatus,projectList,mode,endpoint,socket=null,ready=false,apiReady=false,lastSource=null,saving=false;
 let assembly=new Uint8Array(),caps=null,autosaveArmed=false;
 const requests=new Map();const encoder=new TextEncoder(),decoder=new TextDecoder();
 const notify=text=>{if(status)status.textContent=text;};
 const update=()=>{if(apiReady)GP.apiCall('ide.updateConnection');};
 const active=()=>!!serial.reader||!!socket&&socket.readyState===WebSocket.OPEN&&ready;
 const rejectControls=()=>{for(const p of requests.values()){clearTimeout(p.timer);p.reject(Error('Board disconnected.'));}requests.clear();};
 const accept=data=>{
  const joined=new Uint8Array(assembly.length+data.length);joined.set(assembly);joined.set(data,assembly.length);assembly=joined;
  if(assembly.length>16384)throw Error('Invalid board input size.');
  while(assembly.length){
   let size;
   if(assembly[0]===250){if(assembly.length<3)return;size=3;}
   else if(assembly[0]===251){if(assembly.length<5)return;size=5+assembly[3]+256*assembly[4];if(size>8197)throw Error('Invalid board frame size.');}
   else throw Error('This port is not a binary MicroBlocks VM.');
   if(assembly.length<size)return;
   const frame=assembly.slice(0,size);assembly=assembly.slice(size);
   if(frame[0]===251&&frame[1]===205){
    let response;try{response=JSON.parse(decoder.decode(frame.subarray(5)));}catch{throw Error('Invalid setup response.');}
    const pending=requests.get(response.request);
    if(pending){clearTimeout(pending.timer);requests.delete(response.request);pending.resolve(response);}
   }else input.push(frame);
  }
 };
 const serial=new SerialTransport(navigator.serial,filters,accept,(connected,message)=>{
  if(!connected){input.clear();assembly.fill(0);assembly=new Uint8Array();rejectControls();caps=null;}
  notify(message||(connected?'USB connected to '+profile.name:'Disconnected'));update();
 });
 const disconnect=()=>{if(socket){socket.close(1000,'Client disconnect');socket=null;}ready=false;void serial.disconnect();input.clear();rejectControls();update();};
 const connect=async()=>{
  try{
   if(profile.connection_enabled===false)throw Error('XRP development preview: edit and save projects here. Hardware connection awaits compatible XRP firmware and validation.');
   if(mode&&mode.value==='wifi'){
    const url=new URL(endpoint.value);
    if(url.protocol!=='wss:'||url.username||url.password||url.hash)throw Error('This HTTPS portal needs a secure wss:// endpoint. Use the board-hosted IDE for ws:// LAN boards.');
    socket=new WebSocket(url.href);socket.binaryType='arraybuffer';ready=false;
    socket.onmessage=e=>{try{if(!ready){if(e.data!=='ready')throw Error('Secure endpoint did not identify the VM transport.');ready=true;notify('Secure WebSocket connected');update();}else if(e.data instanceof ArrayBuffer)accept(new Uint8Array(e.data));else throw Error('Binary VM data required.');}catch(error){notify(error.message);disconnect();}};
    socket.onclose=()=>{socket=null;ready=false;input.clear();rejectControls();notify('Disconnected');update();};
    socket.onerror=()=>notify('Secure WebSocket unavailable. Open the board-hosted IDE for the current LAN firmware.');
   }else await serial.connect();
  }catch(error){notify(error.name==='NotFoundError'?'No USB port selected.':error.message);}
 };
 const write=data=>{
  if(serial.writer)return serial.write(data);
  if(socket&&ready&&socket.readyState===WebSocket.OPEN){
   if(socket.bufferedAmount+data.length>65536){notify('Output queue full. Reconnect.');disconnect();return 0;}
   for(let i=0;i<data.length;i+=2048)socket.send(data.slice(i,i+2048));return data.length;
  }return 0;
 };
 window.hasWebSerial=()=>true;window.webSerialConnect=connect;window.webSerialDisconnect=disconnect;
 window.webSerialIsConnected=active;window.GP_openSerialPort=()=>{void connect();return 1;};
 window.GP_isOpenSerialPort=active;window.GP_closeSerialPort=disconnect;
 window.GP_getSerialPorts=()=>{GP_serialPortNames=[toUTF8Array(profile.name)];};
 window.GP_readSerialPort=max=>input.read(max);window.GP_writeSerialPort=write;
 window.GP_setSerialPortDTR=()=>{};window.GP_setSerialPortRTS=()=>{};window.GP_setSerialPortDTRandRTS=()=>{};
 const call=(name,params=[])=>new Promise((resolve,reject)=>{
  const timer=setTimeout(()=>reject(Error('Editor did not respond. Keep this tab active and retry.')),6000);
  GP.apiCall(name,params,value=>{clearTimeout(timer);resolve(value);});
 });
 const listProjects=async()=>{
  const items=await store.list(profile.board);projectList.replaceChildren();
  for(const item of items){const option=document.createElement('option');option.value=item.id;option.textContent=(item.id.endsWith(':workspace')?'Autosaved workspace':item.name)+' — '+new Date(item.updated).toLocaleString();projectList.append(option);}
  return items;
 };
 const save=async(name,source,workspace=false)=>{
  const item=await store.save(profile.board,workspace?'workspace':'named:'+name,name,source);
  saveStatus.textContent=(workspace?'Autosaved':'Saved')+' in this browser at '+new Date(item.updated).toLocaleTimeString();
  if(!workspace)await listProjects();return item;
 };
 const originalWrite=GP_writeFile;
 window.GP_writeFile=async function(data,name,id){
  if(id!=='project')return originalWrite(data,name,id);
  try{await save(name,String(data));GP.lastSavedFileName=name;}
  catch(error){GP.lastSavedFileName='_no_file_selected_';saveStatus.textContent=error.message;}
 };
 const control=(version,operation,ssid,key,remember=false)=>{
  if(!serial.writer)return Promise.reject(Error('Wi-Fi setup requires a connected USB port.'));
  const id=crypto.getRandomValues(new Uint32Array(1))[0]||1;
  const body=[...(version===1?encoder.encode('FJNW'):encoder.encode('MBNW')),version,operation,id&255,id>>>8&255,id>>>16&255,id>>>24&255];
  if(operation===2){if(version===2)body.push(remember?1:0);body.push(ssid.length,key.length,...ssid,...key);}
  const packet=new Uint8Array([251,205,0,(body.length+1)&255,(body.length+1)>>>8,...body,254]);
  body.fill(0);
  return new Promise((resolve,reject)=>{
   const timer=setTimeout(()=>{requests.delete(id);reject(Error('Firmware did not answer this Wi-Fi setup protocol. Update the selected board firmware.'));},1800);
   requests.set(id,{resolve,reject,timer});if(write(packet)!==packet.length){clearTimeout(timer);requests.delete(id);reject(Error('USB setup write failed.'));}packet.fill(0);
  });
 };
 const probe=async()=>{
  let response;try{response=await control(2,1);}catch(error){if(profile.board!=='fruit-jam')throw error;response=await control(1,1);}
  if(!response.accepted||!response.status)throw Error('Board does not support the setup protocol.');
  const value=response.status;
  if(value.board&&value.board!==profile.board)throw Error('The connected board differs from the selected board.');
  if(![1,2].includes(value.setup_protocol))throw Error('Unsupported Wi-Fi setup protocol version.');
  caps={version:value.setup_protocol,persistent:value.persistence_supported===true,status:value};return caps;
 };
 const element=(tag,text)=>{const node=document.createElement(tag);if(text)node.textContent=text;return node;};
 document.addEventListener('board-ide-ready',async()=>{
  apiReady=true;document.documentElement.dataset.portalReady='true';
  const toolbar=element('details');toolbar.className='portal-tools';
  toolbar.append(element('summary','Projects & board'));const panel=element('section');panel.className='portal-panel';toolbar.append(panel);
  document.querySelector('[data-ide="controls"]').prepend(toolbar);
  panel.append(element('h2',profile.name));status=element('p','Choose Connect to select your USB board.');status.setAttribute('role','status');panel.append(status);
  panel.append(element('p',navigator.serial?'USB browser support is available. Connect opens the device chooser.':'USB is unavailable in this browser. Use desktop Chrome or Edge; project editing and browser saves still work.'));
  mode=element('select');mode.setAttribute('aria-label','Connection mode');
  for(const [value,label] of [['usb','USB Web Serial'],['wifi','Wi-Fi secure WebSocket']]){const option=element('option',label);option.value=value;mode.append(option);}panel.append(mode);
  endpoint=element('input');endpoint.placeholder='wss://your-secure-endpoint/ws/vm';endpoint.setAttribute('aria-label','Secure WebSocket address');endpoint.hidden=true;panel.append(endpoint);
  mode.onchange=()=>{disconnect();endpoint.hidden=mode.value!=='wifi';};
  panel.append(element('p','Current LAN firmware uses ws://. From this HTTPS portal, open its own IDE instead; browser security is not bypassed.'));
  const ip=element('input');ip.placeholder='Board address, e.g. 192.168.x.x';ip.setAttribute('aria-label','Self-hosted board address');panel.append(ip);
  const local=element('button','Open board-hosted IDE');local.onclick=()=>{
   try{const url=new URL(ip.value.includes('://')?ip.value:'http://'+ip.value);
    if(!['http:','https:'].includes(url.protocol)||url.username||url.password||url.search||url.hash)throw Error('Enter a board HTTP or HTTPS address.');
    window.open(url.origin+'/','_blank','noopener,noreferrer');
   }catch(error){notify(error.message);}
  };panel.append(local);
  const read=element('button','Read project from board');read.onclick=()=>GP.apiCall('board.retrieveProject');panel.append(read);
  read.disabled=profile.connection_enabled===false;
  panel.append(element('p','Read from board before connecting to retrieve its existing program. Connecting otherwise synchronizes the current editor project.'));
  panel.append(element('h3','Projects in this browser'));saveStatus=element('p','Autosave starts when the editor is ready.');saveStatus.setAttribute('role','status');panel.append(saveStatus);
  const name=element('input');name.value='My project';name.maxLength=100;name.setAttribute('aria-label','Project name');panel.append(name);
  const named=element('button','Save named copy');named.onclick=async()=>{try{await save(name.value.trim()||'My project',await call('portal.serialize'));autosaveArmed=true;}catch(error){saveStatus.textContent=error.message;}};panel.append(named);
  projectList=element('select');projectList.setAttribute('aria-label','Saved browser projects');panel.append(projectList);
  const restore=element('button','Restore selected project');restore.onclick=async()=>{
   try{const items=await store.list(profile.board),item=items.find(x=>x.id===projectList.value);if(!item)throw Error('No saved project selected.');
    if(!confirm('Replace the current workspace with this saved project? A connected board will be synchronized.'))return;
    await call('portal.load',[item.source,item.name.endsWith('.ubp')?item.name:item.name+'.ubp']);lastSource=null;autosaveArmed=true;saveStatus.textContent='Project restored in the editor.';
   }catch(error){saveStatus.textContent=error.message;}
  };panel.append(restore);
  const exportButton=element('button','Export .ubp file'),download=element('a','Download exported project');download.hidden=true;panel.append(exportButton,download);let lastURL;
  exportButton.onclick=async()=>{try{const source=await call('portal.serialize');if(lastURL)URL.revokeObjectURL(lastURL);
   lastURL=URL.createObjectURL(new Blob([source],{type:'text/plain;charset=utf-8'}));download.href=lastURL;download.download=(name.value.trim()||'project')+'.ubp';download.hidden=false;download.click();
  }catch(error){saveStatus.textContent=error.message;}};
  const importInput=element('input');importInput.type='file';importInput.accept='.ubp,text/plain';importInput.setAttribute('aria-label','Import UBP project');panel.append(importInput);
  importInput.onchange=async()=>{try{const file=importInput.files[0];if(!file)return;if(file.size>MAX_PROJECT)throw Error('Import limit is 4 MiB.');
   const source=await file.text();if(!confirm('Replace the current workspace with this file? A connected board will be synchronized.'))return;
   await call('portal.load',[source,file.name]);lastSource=null;autosaveArmed=true;saveStatus.textContent='Project imported.';
  }catch(error){saveStatus.textContent=error.message;}finally{importInput.value='';}};
  panel.append(element('p','Projects stay in this browser and on this site. Clearing site data, private mode or storage eviction may remove them. Export files for backups or another device. Wi-Fi passwords are never saved here.'));
  const wifi=element('details');wifi.append(element('summary','Wi-Fi setup over USB'));const form=element('form');wifi.append(form);panel.append(wifi);
  wifi.hidden=profile.connection_enabled===false;
  const ssid=element('input');ssid.placeholder='Network name (2.4 GHz)';ssid.required=true;ssid.autocomplete='off';ssid.maxLength=32;ssid.setAttribute('aria-label','Wi-Fi network name');
  const key=element('input');key.type='password';key.placeholder='Wi-Fi password';key.autocomplete='off';key.maxLength=64;key.setAttribute('aria-label','Wi-Fi password');
  const label=element('label'),remember=element('input');remember.type='checkbox';remember.disabled=true;label.append(remember,document.createTextNode(' Remember on the board (stored in flash)'));
  const check=element('button','Check board Wi-Fi support');check.type='button';check.onclick=async()=>{try{const c=await probe();remember.disabled=!c.persistent;notify(c.persistent?'Board supports saved Wi-Fi.':'This firmware can connect now; automatic connection after full power loss needs a firmware update.');}catch(error){notify(error.message);}};
  const submit=element('button','Connect board to my Wi-Fi');submit.type='submit';form.append(check,ssid,key,label,submit);
  form.onsubmit=async event=>{event.preventDefault();let sn,kn;
   try{if(!caps)throw Error('Check board Wi-Fi support first.');if(remember.checked&&!caps.persistent)throw Error('Firmware cannot save Wi-Fi yet.');
    sn=encoder.encode(ssid.value);kn=encoder.encode(key.value);
    if(sn.length<1||sn.length>32||kn.length<8||kn.length>64||sn.includes(0)||kn.includes(0)||kn.length===64&&!/^[0-9a-fA-F]{64}$/.test(key.value))throw Error('Use a network name up to 32 UTF-8 bytes and an 8–63 byte password, or a 64-digit hexadecimal key.');
    submit.disabled=true;const response=await control(caps.version,2,sn,kn,remember.checked);if(!response.accepted)throw Error('The board rejected Wi-Fi setup.');
    form.reset();notify('Connecting on the board…');const end=Date.now()+50000;
    while(Date.now()<end){await new Promise(resolve=>setTimeout(resolve,500));const c=await probe();if(c.status.network_ready){notify('Connected. Board IDE: http://'+c.status.ip+'/');ip.value=c.status.ip;return;}if(c.status.state===4)throw Error('Wi-Fi connection failed. Check the password and network.');}
    throw Error('Wi-Fi connection timed out.');
   }catch(error){notify(error.message);}finally{if(sn)sn.fill(0);if(kn)kn.fill(0);key.value='';submit.disabled=false;}
  };
  Menus.connection.items=[{label:'Connect '+profile.name,action:()=>GP.apiCall('board.connect',['USB']),hidden:()=>IDE.board.connected},
   {label:'Disconnect',action:()=>GP.apiCall('board.disconnect'),hidden:()=>!IDE.board.connected}];
  Menus.settings.items=Menus.settings.items.filter(x=>!/(firmware|ESP firmware|new versions)/i.test(x.label||''));
  const boardEndpoint={'fruit-jam':'fruitJam','waveshare':'rlcd','xrp-rp2350':'xrp'}[profile.board];GP.apiCall(boardEndpoint+'.loadLibrary');
  const examples=element('select');examples.setAttribute('aria-label','Board examples');
  for(const [value,text] of [['','Examples'],['arithmetic','5 + 7'],['output','50 outputs']]){const option=element('option',text);option.value=value;examples.append(option);}
  examples.onchange=()=>{if(examples.value)GP.apiCall(boardEndpoint+'.openExample',[examples.value]);examples.value='';toolbar.open=false;};panel.insertBefore(examples,read);
  if(profile.connection_enabled===false)notify('XRP development preview: the production RP2350 library is available for editing. Hardware connection is not enabled yet.');
  else if(!navigator.serial)notify('This browser cannot connect USB. Use desktop Chrome or Edge; you can still edit and save projects here.');
  else if(profile.board==='waveshare')notify('Current Waveshare standalone firmware uses its board-hosted Wi-Fi editor. USB requires the separate binary-USB VM firmware.');
  const fresh=element('button','Use this workspace for autosave');fresh.onclick=()=>{autosaveArmed=true;lastSource=null;saveStatus.textContent='Autosave enabled for this workspace.';};panel.insertBefore(fresh,name);
  try{const items=await listProjects();autosaveArmed=!items.some(item=>item.id.endsWith(':workspace'));if(items.length)saveStatus.textContent='Saved projects found. Restore one, or choose Use this workspace. Your old autosave is preserved until then.';}catch(error){saveStatus.textContent=error.message;}
  window.portalSaveBeforeLeaving=async()=>{
   const source=await call('portal.serialize');
   if(autosaveArmed)await save('Workspace',source,true);
   else await save('Workspace before switching '+new Date().toISOString(),source);
   // GP warns on every navigation. A completed browser save is the guard for
   // this explicit board switch; a failed save keeps the current editor open.
   window.onbeforeunload=null;
  };
  setInterval(async()=>{if(!autosaveArmed||saving||document.hidden)return;saving=true;try{const source=await call('portal.serialize');if(source!==lastSource){await save('Workspace',source,true);lastSource=source;}}catch(error){saveStatus.textContent=error.message;}finally{saving=false;}},3000);
 });
 document.addEventListener('board.type',event=>{
  const type=event.detail.value;if(!type)return;
  const expected={'fruit-jam':'Fruit Jam','waveshare':'Waveshare','xrp-rp2350':'XRP'}[profile.board];
  if(!expected||!type.includes(expected)){notify('The connected board differs from this editor selection.');disconnect();}
 });
 window.addEventListener('pagehide',disconnect);
})();
