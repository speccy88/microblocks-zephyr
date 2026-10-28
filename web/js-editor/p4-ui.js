// SPDX-License-Identifier: MPL-2.0
// Local JS editor integration; preserved GP UI/protocol sources are untouched.
(function(root){
 'use strict';const encoder=new TextEncoder(),decoder=new TextDecoder('utf-8',{fatal:true});
 const json=data=>{const value=JSON.parse(decoder.decode(data));if(!value||typeof value!=='object'||Array.isArray(value))throw Error('Invalid neural information.');return value;};
 function attach(Connection,connection,runtime){
  const controls=document.createElement('section');controls.dataset.ide='controls';controls.setAttribute('aria-label','P4 services');
  controls.style.cssText='position:fixed;right:8px;top:50px;z-index:50;max-width:380px;background:#fff;color:#17212b;font:14px system-ui;border:1px solid #bbb;border-radius:6px;padding:6px';
  const projects=document.createElement('div');projects.dataset.deviceProjectPanel='true';controls.append(projects);document.body.append(controls);
  const broker=MicroBlocksP4Services.install(Connection,connection,runtime,{files:MicroBlocksFilesConnection,
   frameEvent:frame=>root.dispatchEvent(new CustomEvent('p4-vm-frame',{detail:frame})),
   error:message=>root.dispatchEvent(new CustomEvent('microblocks-target-status',{detail:message}))});
  const neural=new MicroBlocksP4Neural.Client(broker,P4NeuralCore);
  const panel=document.createElement('details');panel.className='p4-neural';const title=document.createElement('summary');title.textContent='Neural networks';panel.append(title);controls.append(panel);
  const el=(tag,text)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;return n;};
  panel.append(el('p','Native TFLM dense models. ONNX needs the supported offline conversion. Inference uses the Neural Networks blocks; no actuator binding.'));
  const status=el('p','Connect the P4, then check the backend.');status.setAttribute('role','status');panel.append(status);
  const info=el('pre');info.setAttribute('aria-label','Loaded model and tensor information');panel.append(info);
  let token=0,busy=false,cancelled=false,action=0;
  async function task(fn){
   if(busy){status.textContent='Wait for the current neural action, or cancel it.';return;}
   const stamp=++action;let session;
   try{session=neural.bind();busy=true;cancelled=false;await fn(session,()=>{if(cancelled||!session.valid())throw Error('Neural action cancelled or session changed.');});}
   catch(e){if(stamp===action)status.textContent=e.message;}
   finally{if(stamp===action)busy=false;}
  }
  async function finish(session,t,ensure){
   const end=Date.now()+15000;
   for(;;){ensure();const state=json((await session.request(10)).data);ensure();if(typeof state.busy!=='boolean'||typeof state.loaded!=='boolean')throw Error('Invalid neural load status.');if(!state.busy){if(!state.loaded)throw Error(state.message||'Model load failed.');break;}
    if(Date.now()>end)throw Error('Model load deadline exceeded; check the backend.');await new Promise(resolve=>setTimeout(resolve,40));}
   const model=json((await session.request(5,t)).data);ensure();if(model.error)throw Error(model.error);token=t;info.textContent=JSON.stringify(model,null,2);status.textContent='Loaded NN:'+t.toString(16).padStart(8,'0')+'. Use the current neural model block.';
  }
  function button(label,fn){const b=el('button',label);b.type='button';b.onclick=()=>void task(fn);panel.append(b);return b;}
  button('Check neural backend',async(session,ensure)=>{const caps=json((await session.request(0)).data);ensure();if(typeof caps.available!=='boolean')throw Error('Invalid neural backend capabilities.');info.textContent=JSON.stringify(caps,null,2);status.textContent=caps.available?'Backend information read from the connected board.':'Neural backend unavailable on the connected firmware.';});
  button('Load catalog: INT8 sine',async(session,ensure)=>{const reply=await session.request(8,0,0,0,encoder.encode('sine-int8-v1'));ensure();if(!reply.token)throw Error('No model reference returned.');await finish(session,reply.token,ensure);});
  button('Unload model',async(session,ensure)=>{if(!token)throw Error('No model loaded by this panel.');await session.request(9,token);ensure();token=0;info.textContent='';status.textContent='Model unload requested.';});
  panel.append(el('h3','Import a local model'));
  const manifest=el('input');manifest.type='file';manifest.accept='.json,application/json';manifest.setAttribute('aria-label','Neural model manifest JSON');panel.append(el('label','Model manifest'),manifest);
  const artifact=el('input');artifact.type='file';artifact.accept='.tflite';artifact.setAttribute('aria-label','TFLite model artifact');panel.append(el('label','Model artifact'),artifact);
  button('Validate and load local model',async(session,ensure)=>{
   let raw;
   try{const mf=manifest.files[0],file=artifact.files[0];if(!mf||!file)throw Error('Choose the manifest and TFLite model.');if(mf.size>16384||file.size>P4NeuralCore.MAX_MODEL)throw Error('Manifest/model exceeds import limits.');
    const m=P4NeuralCore.validateManifest(JSON.parse(await mf.text()),file.size);ensure();raw=new Uint8Array(await file.arrayBuffer());ensure();
    if(decoder.decode(raw.subarray(4,8))!=='TFL3')throw Error('Expected TFLite; ONNX requires offline conversion.');
    if(!root.crypto?.subtle)throw Error('Model SHA-256 requires a secure browser context.');
    const digest=new Uint8Array(await root.crypto.subtle.digest('SHA-256',raw));ensure();if(Array.from(digest,x=>x.toString(16).padStart(2,'0')).join('')!==m.sha256)throw Error('Model SHA-256 differs from the manifest.');
    const t=(await session.request(1,0,m.arena_bytes,raw.length,P4NeuralCore.metadata(m))).token;ensure();if(!t)throw Error('No upload reference returned.');
    for(let offset=0;offset<raw.length;offset+=512){ensure();await session.request(2,t,offset,0,raw.subarray(offset,Math.min(raw.length,offset+512)));ensure();status.textContent='Sending model '+Math.round(Math.min(raw.length,offset+512)*100/raw.length)+'%; the board verifies its hash and graph.';}
    await session.request(3,t);ensure();await finish(session,t,ensure);
   }finally{if(raw)raw.fill(0);}
  });
  const cancel=el('button','Cancel neural job/import');cancel.type='button';cancel.onclick=async()=>{cancelled=true;let session;try{session=neural.bind();await session.request(4);if(session.valid())status.textContent='Cancellation requested.';}catch(e){if(!session||session.valid())status.textContent=e.message;}};panel.append(cancel);
  panel.append(el('p','Model bytes stay in this tab and the selected board. They are not saved in the project or sent to a model service. Check tensor shape, dtype, scale and zero point before using blocks.'));
  const off=broker.subscribeState(state=>{if(!state.verified){action++;busy=false;cancelled=true;token=0;info.textContent='';status.textContent='Disconnected. Check the backend after reconnecting.';}});
  document.dispatchEvent(new CustomEvent('board-ide-ready'));
  root.addEventListener('pagehide',()=>{off();neural.close();broker.close();connection.disconnect();controls.remove();});
  return Object.freeze({broker,neural});
 }
 const api=Object.freeze({attach});root.MicroBlocksP4UI=api;if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
