/* SPDX-License-Identifier: MPL-2.0
 * Waveshare transport for the real MicroBlocks GP editor; derived from the
 * speccy88/uno-q-microblocks bounded binary WebSocket adapter. */
(() => {
 const state={ws:null,ready:false,rx:[],rxBytes:0,tx:[],txBytes:0,error:null};
 const LIMIT=65536;
 const update=()=>{if(typeof GP!=='undefined')GP.apiCall('ide.updateConnection');};
 const notice=text=>{const e=document.getElementById('board-status');if(e)e.textContent=text;};
 const requestPairing=resume=>{
  const existing=document.getElementById('board-pairing');if(existing){existing.querySelector('input').focus();return;}
  const dialog=document.createElement('dialog');dialog.id='board-pairing';dialog.setAttribute('aria-label','Pair with Waveshare');
  dialog.style.cssText='border:0;border-radius:12px;padding:24px;max-width:360px;font:16px sans-serif;color:#292b3e';
  const form=document.createElement('form'),title=document.createElement('h2'),label=document.createElement('label'),input=document.createElement('input'),actions=document.createElement('div');
  title.textContent='Pair with Waveshare';label.textContent='Pairing code shown on the board display';
  input.type='password';input.name='pairing-code';input.required=true;input.autocomplete='off';input.maxLength=64;
  input.setAttribute('aria-label','Pairing code');input.style.cssText='display:block;width:100%;box-sizing:border-box;margin:12px 0;padding:8px';
  const advanced=document.createElement('details'),summary=document.createElement('summary'),file=document.createElement('input'),fileStatus=document.createElement('p');
  summary.textContent='Use a private build pairing file';file.type='file';file.accept='.json,application/json';file.setAttribute('aria-label','Private build pairing file');
  fileStatus.textContent='Optional: open device-private.json from your own build. Only the pairing code is used locally; the file is never uploaded.';
  fileStatus.style.cssText='font-size:12px;line-height:1.4';advanced.append(summary,fileStatus,file);
  file.onchange=async()=>{try{const selected=file.files[0];if(!selected||selected.size>4096)throw Error();const value=JSON.parse(await selected.text()).pair;if(typeof value!=='string'||!value.trim()||value.length>64)throw Error();input.value=value.trim();fileStatus.textContent='Pairing code loaded. Select Connect.';}catch{fileStatus.textContent='Could not read a valid private pairing file.';}finally{file.value='';}};
  const accept=document.createElement('button'),cancel=document.createElement('button');accept.type='submit';accept.textContent='Connect';cancel.type='button';cancel.textContent='Cancel';
  actions.style.cssText='display:flex;gap:12px;justify-content:flex-end;margin-top:16px';actions.append(cancel,accept);label.append(input);form.append(title,label,advanced,actions);dialog.append(form);document.body.append(dialog);
  const close=()=>{dialog.close();dialog.remove();};
  cancel.onclick=()=>{close();notice('Pairing cancelled');};dialog.addEventListener('cancel',()=>{dialog.remove();notice('Pairing cancelled');});
  form.onsubmit=e=>{e.preventDefault();const code=input.value.trim();if(!code)return;sessionStorage.setItem('microblocks-pair-code',code);input.value='';close();resume();};
  dialog.showModal();input.focus();
 };
 const disconnect=()=>{if(state.ws)state.ws.close(1000,'Client disconnect');state.ws=null;state.ready=false;state.rx=[];state.rxBytes=0;state.tx=[];state.txBytes=0;notice('Disconnected - Connect to resume');update();};
 const connect=()=>{
  if(state.ws)return;
  let code=sessionStorage.getItem('microblocks-pair-code');
  if(!code){requestPairing(()=>GP.apiCall('board.connect',['connect (USB)']));return;}
  state.error=null;notice('Connecting to Waveshare…');
  const socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws/vm');
  socket.binaryType='arraybuffer';state.ws=socket;
  socket.onopen=()=>socket.send('auth:'+code.trim());
  socket.onmessage=e=>{
   if(state.ws!==socket)return;
   if(!state.ready){
    if(e.data!=='ready'){sessionStorage.removeItem('microblocks-pair-code');socket.close(1008,'Pairing failed');return;}
    state.ready=true;for(const bytes of state.tx)for(let p=0;p<bytes.byteLength;p+=2048)socket.send(bytes.slice(p,p+2048));state.tx=[];state.txBytes=0;notice('Waveshare MicroBlocks');update();return;
   }
   if(!(e.data instanceof ArrayBuffer)){socket.close(1003,'Binary response required');return;}
   const bytes=new Uint8Array(e.data);
   if(state.rxBytes+bytes.length>LIMIT){socket.close(1009,'Browser input queue full');return;}
   state.rx.push(bytes);state.rxBytes+=bytes.length;
  };
  socket.onclose=e=>{if(state.ws!==socket)return;if(!state.ready)sessionStorage.removeItem('microblocks-pair-code');state.ws=null;state.ready=false;state.rx=[];state.rxBytes=0;state.tx=[];state.txBytes=0;notice(e.reason||'Disconnected - Connect to resume');update();};
  socket.onerror=()=>{if(state.ws===socket)notice('Board connection unavailable');};
 };
 window.hasWebSerial=()=>true;
 window.webSerialIsConnected=()=>!!state.ws&&[WebSocket.CONNECTING,WebSocket.OPEN].includes(state.ws.readyState);
 window.webSerialConnect=connect;window.webSerialDisconnect=disconnect;
 window.GP_openSerialPort=()=>{connect();return 1;};window.GP_isOpenSerialPort=window.webSerialIsConnected;window.GP_closeSerialPort=disconnect;
 window.GP_getSerialPorts=()=>{GP_serialPortNames=[toUTF8Array('Waveshare MicroBlocks')];};
 window.GP_readSerialPort=max=>{
  const count=Math.min(max,state.rxBytes),out=new Uint8Array(count);let pos=0;
  while(pos<count){const first=state.rx[0],n=Math.min(first.length,count-pos);out.set(first.subarray(0,n),pos);pos+=n;if(n===first.length)state.rx.shift();else state.rx[0]=first.subarray(n);}
  state.rxBytes-=count;return out;
 };
 window.GP_writeSerialPort=data=>{
  const socket=state.ws;if(!socket)return 0;
  if(!state.ready){if(state.txBytes+data.byteLength>LIMIT){disconnect();return 0;}state.tx.push(data.slice());state.txBytes+=data.byteLength;return data.byteLength;}
  if(socket.readyState!==WebSocket.OPEN)return 0;
  if(socket.bufferedAmount+data.byteLength>LIMIT){socket.close(1009,'Browser output queue full');return 0;}
  // The VM consumes a byte stream. Keep individual WebSocket messages bounded.
  for(let p=0;p<data.byteLength;p+=2048)socket.send(data.slice(p,p+2048));return data.byteLength;
 };
 window.GP_setSerialPortDTR=()=>{};window.GP_setSerialPortRTS=()=>{};window.GP_setSerialPortDTRandRTS=()=>{};
 const original=GP.apiCall.bind(GP);
 GP.apiCall=(endpoint,params,callback)=>{if(endpoint==='board.connect'&&!sessionStorage.getItem('microblocks-pair-code')){requestPairing(()=>original(endpoint,params,callback));return;}if(endpoint.startsWith('board.installVM')||endpoint==='board.toggleBLE'){notice('Use USB recovery to install firmware');if(callback)callback(0);return;}return original(endpoint,params,callback);};
 document.addEventListener('ready',()=>{
  Menus.settings.items=Menus.settings.items.filter(x=>!/(firmware|ESP firmware|new versions)/i.test(x.label||''));
  Menus.connection.items=[{label:'Connect Waveshare',action:()=>GP.apiCall('board.connect',['connect (USB)']),hidden:()=>IDE.board.connected},{label:'Disconnect',action:()=>{disconnect();GP.apiCall('board.disconnect');},hidden:()=>!IDE.board.connected}];
  const bar=document.querySelector('[data-ide="controls"]'),status=document.createElement('span');status.id='board-status';status.setAttribute('role','status');status.style.cssText='color:white;font-size:12px;max-width:130px';bar.prepend(status);
  const wifi=document.createElement('a');wifi.href='/setup';wifi.textContent='Wi-Fi settings';wifi.style.marginRight='1em';bar.prepend(wifi);
  const hardware=document.createElement('button');hardware.textContent='Waveshare blocks';hardware.onclick=()=>GP.apiCall('rlcd.loadLibrary');bar.prepend(hardware);
  const examples=document.createElement('select');examples.setAttribute('aria-label','Waveshare examples');
  [['','Examples'],['arithmetic','5 + 7'],['output','500 outputs']].forEach(([value,text])=>{const option=document.createElement('option');option.value=value;option.textContent=text;examples.append(option);});
  examples.onchange=()=>{if(examples.value)GP.apiCall('rlcd.openExample',[examples.value]);examples.value='';};bar.prepend(examples);
  GP.apiCall('rlcd.loadLibrary');
 });
 window.MicroBlocksTransportStatus=()=>({connected:state.ready,rxBytes:state.rxBytes,error:state.error});
})();
