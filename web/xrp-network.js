/* SPDX-License-Identifier: MPL-2.0
 * XRP transport for the real MicroBlocks GP editor; derived from the
 * speccy88/uno-q-microblocks bounded binary WebSocket adapter. */
(() => {
 const state={ws:null,ready:false,rx:[],rxBytes:0,tx:[],txBytes:0,error:null};
 const LIMIT=65536;
 const update=()=>{if(typeof GP!=='undefined')GP.apiCall('ide.updateConnection');};
 const notice=text=>{const e=document.getElementById('board-status');if(e)e.textContent=text;};
 // Remove the obsolete value from existing browser sessions.
 sessionStorage.removeItem('microblocks-pair-code');
 const disconnect=()=>{if(state.ws)state.ws.close(1000,'Client disconnect');state.ws=null;state.ready=false;state.rx=[];state.rxBytes=0;state.tx=[];state.txBytes=0;notice('Disconnected - Connect to resume');update();};
 const connect=()=>{
  if(state.ws)return;
  state.error=null;notice('Connecting to XRP…');
  const socket=new WebSocket((location.protocol==='https:'?'wss://':'ws://')+location.host+'/ws/vm');
  socket.binaryType='arraybuffer';state.ws=socket;
  socket.onmessage=e=>{
   if(state.ws!==socket)return;
   if(!state.ready){
    if(e.data!=='ready'){socket.close(1002,'Transport not ready');return;}
    state.ready=true;for(const bytes of state.tx)for(let p=0;p<bytes.byteLength;p+=2048)socket.send(bytes.slice(p,p+2048));state.tx=[];state.txBytes=0;notice('XRP MicroBlocks');update();return;
   }
   if(!(e.data instanceof ArrayBuffer)){socket.close(1003,'Binary response required');return;}
   const bytes=new Uint8Array(e.data);
   if(state.rxBytes+bytes.length>LIMIT){socket.close(1009,'Browser input queue full');return;}
   state.rx.push(bytes);state.rxBytes+=bytes.length;
  };
  socket.onclose=e=>{if(state.ws!==socket)return;state.ws=null;state.ready=false;state.rx=[];state.rxBytes=0;state.tx=[];state.txBytes=0;notice(e.reason||'Disconnected - Connect to resume');update();};
  socket.onerror=()=>{if(state.ws===socket)notice('Board connection unavailable');};
 };
 window.hasWebSerial=()=>true;
 window.webSerialIsConnected=()=>!!state.ws&&[WebSocket.CONNECTING,WebSocket.OPEN].includes(state.ws.readyState);
 window.webSerialConnect=connect;window.webSerialDisconnect=disconnect;
 window.GP_openSerialPort=()=>{connect();return 1;};window.GP_isOpenSerialPort=window.webSerialIsConnected;window.GP_closeSerialPort=disconnect;
 window.GP_getSerialPorts=()=>{GP_serialPortNames=[toUTF8Array('XRP MicroBlocks')];};
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
 GP.apiCall=(endpoint,params,callback)=>{if(endpoint.startsWith('board.installVM')||endpoint==='board.toggleBLE'){notice('Use USB recovery to install firmware');if(callback)callback(0);return;}return original(endpoint,params,callback);};
 document.addEventListener('board-ide-ready',()=>{
  Menus.settings.items=Menus.settings.items.filter(x=>!/(firmware|ESP firmware|new versions)/i.test(x.label||''));
  Menus.connection.items=[{label:'Connect XRP',action:()=>GP.apiCall('board.connect',['connect (USB)']),hidden:()=>IDE.board.connected},{label:'Disconnect',action:()=>{disconnect();GP.apiCall('board.disconnect');},hidden:()=>!IDE.board.connected}];
  const bar=document.querySelector('[data-ide="controls"]'),tools=document.createElement('details'),summary=document.createElement('summary'),panel=document.createElement('div');
  summary.textContent='Board';summary.setAttribute('aria-label','Board tools');summary.style.cssText='cursor:pointer;padding:10px;color:white;font:14px sans-serif';
  tools.style.cssText='position:relative;flex:none';panel.style.cssText='position:absolute;right:0;top:100%;z-index:10000;min-width:200px;padding:12px;background:#303247;border-radius:6px;box-shadow:0 4px 16px #0005;display:flex;flex-direction:column;gap:10px';tools.append(summary,panel);bar.prepend(tools);
  const status=document.createElement('span');status.id='board-status';status.setAttribute('role','status');status.style.cssText='color:white;font:12px sans-serif';panel.append(status);
  const wifi=document.createElement('a');wifi.href='https://github.com/speccy88/microblocks-zephyr/blob/main/docs/COMMON_WIFI_SETUP.md';wifi.textContent='USB Wi-Fi setup instructions';wifi.style.cssText='color:white;font:14px sans-serif';panel.append(wifi);
  const hardware=document.createElement('button');hardware.textContent='XRP blocks';hardware.style.cssText='padding:8px;font:14px sans-serif';hardware.onclick=()=>{GP.apiCall('xrp.loadLibrary');tools.open=false;};panel.append(hardware);
  const examples=document.createElement('select');examples.setAttribute('aria-label','XRP examples');
  [['','Examples'],['arithmetic','5 + 7'],['output','50 outputs']].forEach(([value,text])=>{const option=document.createElement('option');option.value=value;option.textContent=text;examples.append(option);});
  examples.style.cssText='padding:8px;font:14px sans-serif';examples.onchange=()=>{if(examples.value)GP.apiCall('xrp.openExample',[examples.value]);examples.value='';tools.open=false;};panel.prepend(examples);
  GP.apiCall('xrp.loadLibrary');
 });
 window.MicroBlocksTransportStatus=()=>({connected:state.ready,rxBytes:state.rxBytes,error:state.error});
})();
