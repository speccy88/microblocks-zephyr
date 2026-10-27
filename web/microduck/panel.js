/* SPDX-License-Identifier: MIT */
/* Discovery-only UI. No JSON-RPC request, PIN, Wi-Fi secret or motion control. */
(function(root){
 'use strict';
 const commonJS=typeof module==='object'&&module.exports;
 const bluetoothAPI=commonJS?require('./bluetooth.js'):root.MicroDuckBluetooth;
 const commands=commonJS?require('./commands.js'):root.MicroDuckCommands;
 const EXPECTED_API=commands?.API_VERSION;
 function mount(container,options={}){
  if(!bluetoothAPI||EXPECTED_API!==44)throw Error('Load the reviewed MicroDuck commands and Bluetooth client before its panel.');
  if(!container?.ownerDocument)throw Error('A MicroDuck panel container is required.');
  const provider=Object.hasOwn(options,'bluetooth')?options.bluetooth:root.navigator?.bluetooth;
  const timeoutMs=options.timeoutMs??10000;
  if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>120000)throw Error('Invalid Bluetooth discovery timeout.');
  const lifecycle=options.lifecycleTarget||root;
  const supported=root.isSecureContext!==false&&typeof provider?.requestDevice==='function';
  const document=container.ownerDocument;
  const make=(tag,className,text)=>{const element=document.createElement(tag);if(className)element.className=className;if(text!==undefined)element.textContent=text;return element;};
  const panel=make('article','connection-card hosted microduck-discovery-panel');panel.setAttribute('aria-label','MicroDuck Bluetooth discovery');
  const heading=make('h3','','MicroDuck Bluetooth discovery');
  const validation=make('p','tag','Protocol and panel tests use mock devices. No physical MicroDuck has been validated.');
  const status=make('p','microduck-discovery-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const name=make('p','microduck-device-name','No MicroDuck is connected.');
  const version=make('p','microduck-api-version','Reviewed upstream API: 44. The device API version is read after selection.');
  const discover=make('button','','Discover MicroDuck'),disconnect=make('button','','Disconnect');discover.type=disconnect.type='button';
  const actions=make('div','board-picker microduck-discovery-actions');actions.append(discover,disconnect);
  const scope=make('p','microduck-discovery-scope','Discovery reads the public GATT API-version byte and subscribes to notifications. This panel sends no JSON-RPC commands.');
  const confidentiality=make('p','microduck-confidentiality','Web Bluetooth does not establish link confidentiality for this client. Authentication and Wi-Fi provisioning remain unavailable here; use the robot’s trusted local console until secure transport and hardware validation are completed.');
  const docs=make('a','','Read MicroDuck protocol coverage and security limits');docs.href='https://github.com/speccy88/microblocks-zephyr/blob/main/docs/MICRODUCK_PROTOCOL.md';docs.target='_blank';docs.rel='noopener noreferrer';
  const simulation=make('a','microduck-simulation-link','Open the fictional commissioning simulation');simulation.href='microduck/simulation.html';simulation.target='_blank';simulation.rel='noopener noreferrer';
  const consoleLink=make('a','microduck-console-link','Open the protected API 44 console');consoleLink.href='microduck/console.html';consoleLink.target='_blank';consoleLink.rel='noopener noreferrer';
  const camera=make('a','microduck-camera-link','Open the fictional camera viewer lab');camera.href='microduck/camera.html';camera.target='_blank';camera.rel='noopener noreferrer';
  panel.append(heading,validation,status,name,version,actions,scope,confidentiality,docs,simulation,consoleLink,camera);container.append(panel);
  let disposed=false,generation=0,busy=false,cancelled=false,pendingDevice=null,session=null;

  function updateButtons(){discover.disabled=!supported||busy||disposed;discover.textContent=session?'Choose another MicroDuck':'Discover MicroDuck';disconnect.disabled=disposed||(!session&&!busy)||cancelled;}
  function closeConnection(connection){
   if(!connection)return;
   if(connection.panelDrop)connection.device?.removeEventListener?.('gattserverdisconnected',connection.panelDrop);
   try{connection.client?.close('DISCONNECTED');}catch{}
   try{if(connection.device?.gatt?.connected)connection.device.gatt.disconnect();}catch{}
  }
  function clearIdentity(){name.textContent='No MicroDuck is connected.';version.textContent='Reviewed upstream API: 44. No device API version is currently connected.';}
  function stop(message){
   ++generation;
   const previous=session;session=null;closeConnection(previous);clearIdentity();
   if(busy){
    cancelled=true;
    // The browser chooser itself cannot be dismissed by this panel. Keep the
    // next chooser disabled until the old operation settles, so a stale GATT
    // connect cannot disconnect a replacement session on the same device.
    try{pendingDevice?.gatt?.disconnect();}catch{}
    status.textContent='Discovery cancelled. Close any open browser chooser; a late selection will be discarded.';
   }else status.textContent=message||'Disconnected. Discover again to create a fresh session.';
   updateButtons();
  }
  function errorText(error){
   if(error?.name==='NotFoundError')return 'Device chooser cancelled. No MicroDuck is connected.';
   if(['NotAllowedError','SecurityError'].includes(error?.name))return 'Bluetooth access was not granted. No MicroDuck is connected.';
   switch(error?.code){
    case 'WEB_BLUETOOTH_UNAVAILABLE':return 'Web Bluetooth is unavailable. Use a compatible browser in an HTTPS or localhost secure context.';
    case 'GATT_TIMEOUT':return 'Bluetooth discovery timed out. Any established GATT connection has been closed.';
    case 'GATT_PROPERTIES':return 'The selected device lacks the required MicroDuck read/write/notify characteristic. It was disconnected.';
    case 'API_VERSION':return 'The selected device did not provide the required one-byte API version. It was disconnected.';
    default:return 'Bluetooth discovery failed. Any completed connection has been closed; no command was sent.';
   }
  }
  function deviceName(device){
   return typeof device?.name==='string'&&device.name?device.name.replace(/[\x00-\x1f\x7f\u202a-\u202e\u2066-\u2069]/g,' ').slice(0,128):'Unnamed service device';
  }
  discover.addEventListener('click',async()=>{
   if(disposed||busy||!supported)return;
   const ticket=++generation;
   const previous=session;session=null;closeConnection(previous);clearIdentity();
   busy=true;cancelled=false;pendingDevice=null;status.textContent='Choose a MicroDuck service device in the browser’s Bluetooth chooser.';updateButtons();
   // The real client still opens requestDevice synchronously within this click.
   // This wrapper only discards cancelled chooser results before GATT starts.
   const guardedProvider={requestDevice(filters){
    const selection=provider.requestDevice(filters);
    return Promise.resolve(selection).then(device=>{
     if(disposed||ticket!==generation){try{if(device?.gatt?.connected)device.gatt.disconnect();}catch{}const error=Error('Cancelled');error.code='CANCELLED';throw error;}
     pendingDevice=device;return device;
    });
   }};
   let connection;
   try{
    connection=await bluetoothAPI.connect({bluetooth:guardedProvider,timeoutMs});
    if(disposed||ticket!==generation){closeConnection(connection);return;}
    const reportedName=deviceName(connection.device);
    name.textContent='Browser-reported device name: '+reportedName;
    version.textContent='Observed GATT API: '+connection.apiVersion+'; reviewed upstream API: '+EXPECTED_API+'.';
    if(connection.apiVersion!==EXPECTED_API){
     closeConnection(connection);
     status.textContent='API version mismatch. Expected 44, observed '+connection.apiVersion+'. Device disconnected; no JSON-RPC command was sent.';
     return;
    }
    session=connection;
    connection.panelDrop=()=>{
     if(disposed||session!==connection)return;
     session=null;closeConnection(connection);clearIdentity();
     status.textContent='Bluetooth disconnected. Discover again to create a fresh discovery-only session.';updateButtons();
    };
    connection.device.addEventListener('gattserverdisconnected',connection.panelDrop);
    version.textContent='GATT API 44 matches the reviewed upstream API 44.';
    status.textContent='GATT connected for discovery only. Link confidentiality is unverified. No authentication, Wi-Fi provisioning or JSON-RPC command was sent.';
   }catch(error){
    closeConnection(connection);
    if(!disposed&&ticket===generation){clearIdentity();status.textContent=errorText(error);}
   }finally{
    busy=false;pendingDevice=null;
    if(!disposed&&ticket!==generation&&cancelled)status.textContent='Discovery cancelled. No MicroDuck is connected.';
    cancelled=false;updateButtons();
   }
  });
  disconnect.addEventListener('click',()=>{if(!disposed)stop();});
  const pagehide=()=>{if(!disposed)stop('Disconnected when leaving the page. Discover again to open a fresh session.');};
  lifecycle?.addEventListener?.('pagehide',pagehide);
  status.textContent=supported?'Ready for explicit discovery. No Bluetooth chooser or connection opens until you click Discover.':'Web Bluetooth is unavailable. Use a compatible browser in an HTTPS or localhost secure context; project editing remains available.';
  updateButtons();
  return Object.freeze({element:panel,disconnect(){if(!disposed)stop();},destroy(){
   if(disposed)return;
   stop();disposed=true;lifecycle?.removeEventListener?.('pagehide',pagehide);updateButtons();panel.remove();
  }});
 }
 const api=Object.freeze({mount,EXPECTED_API});if(commonJS)module.exports=api;else root.MicroDuckPanel=api;
})(typeof globalThis==='object'?globalThis:this);
