/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 const rpc=typeof module==='object'&&module.exports?require('./rpc.js'):root.MicroDuckRpc;
 const SERVICE_UUID='6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019',RPC_UUID='6f5d2a11-3b47-4c8e-9a1f-2d7e8c4b6019';
 const fail=code=>{throw new rpc.DuckError(code);};
 class BleTransport{
  constructor(device,characteristic){this.device=device;this.characteristic=characteristic;this.receive=null;this.dropped=null;this.closed=false;Object.defineProperty(this,'confidential',{value:false,enumerable:true});
   this.notification=event=>{const v=event.target.value;if(!(v instanceof DataView)){const f=this.dropped;this.close();f?.();return;}this.receive?.(new Uint8Array(v.buffer,v.byteOffset,v.byteLength).slice());};
   this.disconnect=()=>{const f=this.dropped;this.close();f?.();};
   characteristic.addEventListener('characteristicvaluechanged',this.notification);device.addEventListener('gattserverdisconnected',this.disconnect);
  }
  subscribe(receive,dropped){if(this.closed)fail('DISCONNECTED');if(this.receive)fail('BUSY');this.receive=receive;this.dropped=dropped;return ()=>{this.receive=null;this.dropped=null;};}
  async write(bytes){if(this.closed||!this.device.gatt.connected)fail('DISCONNECTED');if(!(bytes instanceof Uint8Array)||bytes.length>20)fail('PROTOCOL');await this.characteristic.writeValueWithResponse(bytes);}
  close(){if(this.closed)return;this.closed=true;this.characteristic.removeEventListener('characteristicvaluechanged',this.notification);this.device.removeEventListener('gattserverdisconnected',this.disconnect);this.receive=null;this.dropped=null;if(this.device.gatt.connected)this.device.gatt.disconnect();}
 }
 function stage(operation,timeoutMs,device){
  let expired=false,timer;
  const work=Promise.resolve().then(operation);
  // A late connect must not leave a device connected after the timeout was shown.
  void work.then(()=>{if(expired&&device.gatt?.connected)device.gatt.disconnect();},()=>{});
  const deadline=new Promise((_,reject)=>{timer=setTimeout(()=>{expired=true;if(device.gatt?.connected)device.gatt.disconnect();reject(new rpc.DuckError('GATT_TIMEOUT'));},timeoutMs);});
  return Promise.race([work,deadline]).finally(()=>clearTimeout(timer));
 }
 async function connect({bluetooth=root.navigator?.bluetooth,timeoutMs=10000}={}){
  if(root.isSecureContext===false||!bluetooth||typeof bluetooth.requestDevice!=='function')fail('WEB_BLUETOOTH_UNAVAILABLE');
  if(!Number.isInteger(timeoutMs)||timeoutMs<1||timeoutMs>120000)fail('PARAMS');
  // Call directly from the user's click handler; browsers enforce transient activation.
  const device=await bluetooth.requestDevice({filters:[{services:[SERVICE_UUID]}]});let transport;
  try{
   const server=await stage(()=>device.gatt.connect(),timeoutMs,device),service=await stage(()=>server.getPrimaryService(SERVICE_UUID),timeoutMs,device),characteristic=await stage(()=>service.getCharacteristic(RPC_UUID),timeoutMs,device);
   if(!characteristic.properties?.read||!characteristic.properties?.write||!characteristic.properties?.notify||typeof characteristic.writeValueWithResponse!=='function')fail('GATT_PROPERTIES');
   const version=await stage(()=>characteristic.readValue(),timeoutMs,device);if(!(version instanceof DataView)||version.byteLength!==1)fail('API_VERSION');
   const apiVersion=version.getUint8(0);transport=new BleTransport(device,characteristic);
   await stage(()=>characteristic.startNotifications(),timeoutMs,device);
   const client=new rpc.RpcClient(transport,{timeoutMs});
   return {client,device,apiVersion,confidential:false,status:'discovery-only-confidentiality-unverified'};
  }catch(error){transport?.close();if(device.gatt?.connected)device.gatt.disconnect();throw error;}
 }
 const api=Object.freeze({SERVICE_UUID,RPC_UUID,BleTransport,connect});
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckBluetooth=api;
})(typeof globalThis==='object'?globalThis:this);
