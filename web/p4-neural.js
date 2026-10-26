/* SPDX-License-Identifier: MIT */
(()=>{
 'use strict';const core=window.P4NeuralCore,encoder=new TextEncoder(),decoder=new TextDecoder(),pending=new Map();let next=0,token=0,uploading=false,cancelled=false,status,info;
 const request=(op,t=0,offset=0,arg=0,data=new Uint8Array())=>new Promise((resolve,reject)=>{
  if(pending.size)return reject(Error('Wait for the current neural request.'));
  const id=next=next%0xffffffff+1,frame=core.packet(op,id,t,offset,arg,data);
  const timer=setTimeout(()=>{pending.delete(id);reject(Error('Neural request timed out.'));},8000);pending.set(id,{resolve,reject,timer,op});
  if(window.P4Send?.(frame)!==frame.length){clearTimeout(timer);pending.delete(id);reject(Error('Connect the P4 first.'));}
 });
 window.P4NeuralAccept=frame=>{
  if(frame[1]!==216||frame.length<15)return;const b=frame.subarray(5),v=new DataView(b.buffer,b.byteOffset,b.length),id=v.getUint32(0,true),p=pending.get(id);if(!p)return;
  pending.delete(id);clearTimeout(p.timer);
  const messages={1:'Invalid model metadata/request.',2:'Neural backend busy, or unload its existing model first.',3:'Install the native neural firmware profile.',4:'Model/tensor exceeds limits or has invalid shape.',5:'Unsupported model.',6:'Not enough model memory.',7:'Model reference is stale.',8:'Model hash mismatch.',9:'Model/input upload is incomplete.'};
  if(b[5]!==p.op||b[4])p.reject(Error(messages[b[4]]||'Invalid neural response.'));else p.resolve({token:v.getUint32(6,true),data:b.slice(10)});
 };
 async function finish(t){
  const deadline=Date.now()+15000;
  for(;;){const state=JSON.parse(decoder.decode((await request(10)).data));if(!state.busy){if(!state.loaded)throw Error(state.message||'Model load failed.');break;}if(Date.now()>deadline)throw Error('Model loading deadline exceeded.');await new Promise(r=>setTimeout(r,40));}
  const model=JSON.parse(decoder.decode((await request(5,t)).data));if(model.error)throw Error(model.error);token=t;info.textContent=JSON.stringify(model,null,2);status.textContent='Loaded NN:'+t.toString(16).padStart(8,'0')+'. Use the current neural model block.';
 }
 const el=(tag,text)=>{const n=document.createElement(tag);if(text)n.textContent=text;return n;};
 document.addEventListener('board-ide-ready',()=>{
  const panel=el('details');panel.className='p4-neural';panel.append(el('summary','Neural networks'));panel.append(el('p','Local native TFLM inference. Compatible dense TFLite models only; ONNX requires supported offline conversion. No cloud inference or actuator binding.'));
  status=el('p','Connect the P4, then check the backend.');status.setAttribute('role','status');panel.append(status);
  info=el('pre');info.setAttribute('aria-label','Loaded model and tensor information');panel.append(info);
  const check=el('button','Check neural backend');check.onclick=async()=>{try{info.textContent=JSON.stringify(JSON.parse(decoder.decode((await request(0)).data)),null,2);status.textContent='Backend information read from the board.';}catch(e){status.textContent=e.message;}};panel.append(check);
  const load=el('button','Load catalog: INT8 sine');load.onclick=async()=>{try{await finish((await request(8,0,0,0,encoder.encode('sine-int8-v1'))).token);}catch(e){status.textContent=e.message;}};panel.append(load);
  const unload=el('button','Unload model');unload.onclick=async()=>{try{if(!token)throw Error('No model loaded by this panel.');await request(9,token);token=0;info.textContent='';status.textContent='Model unload requested.';}catch(e){status.textContent=e.message;}};panel.append(unload);
  panel.append(el('h3','Import a local model'));
  const manifest=el('input');manifest.type='file';manifest.accept='.json,application/json';manifest.setAttribute('aria-label','Neural model manifest JSON');panel.append(el('label','Model manifest'),manifest);
  const artifact=el('input');artifact.type='file';artifact.accept='.tflite';artifact.setAttribute('aria-label','TFLite model artifact');panel.append(el('label','Model artifact'),artifact);
  const submit=el('button','Validate and load local model');submit.onclick=async()=>{
   let raw;
   try{
    if(uploading)throw Error('An upload is already active.');const mf=manifest.files[0],file=artifact.files[0];if(!mf||!file)throw Error('Choose a model manifest and its TFLite file.');if(mf.size>16384||file.size>core.MAX_MODEL)throw Error('Manifest/model exceeds the local import limit.');
    const m=core.validateManifest(JSON.parse(await mf.text()),file.size);raw=new Uint8Array(await file.arrayBuffer());
    if(decoder.decode(raw.subarray(4,8))!=='TFL3')throw Error('The artifact is not TFLite. ONNX must be converted offline.');
    if(window.crypto?.subtle){const digest=new Uint8Array(await crypto.subtle.digest('SHA-256',raw)),actual=Array.from(digest,x=>x.toString(16).padStart(2,'0')).join('');if(actual!==m.sha256)throw Error('Local artifact SHA-256 differs from manifest.');}
    uploading=true;cancelled=false;submit.disabled=true;
    const t=(await request(1,0,m.arena_bytes,raw.length,core.metadata(m))).token;
    for(let offset=0;offset<raw.length;offset+=512){if(cancelled)throw Error('Import cancelled.');await request(2,t,offset,0,raw.subarray(offset,Math.min(raw.length,offset+512)));status.textContent='Sending local model '+Math.round(Math.min(raw.length,offset+512)*100/raw.length)+'%; board verifies SHA-256 and graph.';}
    await request(3,t);await finish(t);
   }catch(e){status.textContent=e.message;if(uploading&&!pending.size){try{await request(4);}catch{}}}
   finally{if(raw)raw.fill(0);uploading=false;submit.disabled=false;}
  };panel.append(submit);
  const cancel=el('button','Cancel neural job/import');cancel.onclick=async()=>{cancelled=true;try{if(!pending.size)await request(4);status.textContent='Cancellation requested.';}catch(e){status.textContent=e.message;}};panel.append(cancel);
  panel.append(el('p','Model bytes stay in this browser and on the connected board. They are not saved in the project or uploaded to a model service. Inspect the returned tensor shape, dtype, scale and zero point before running blocks.'));
  document.querySelector('[data-ide="controls"]')?.append(panel);
 });
 window.addEventListener('pagehide',()=>{for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Editor closed.'));}pending.clear();});
 document.addEventListener('board.type',event=>{
  if(event.detail.value&&event.detail.value!=='Connect')return;
  token=0;cancelled=true;
  if(info)info.textContent='';if(status)status.textContent='Disconnected. Connect the P4 and check its current backend.';
  for(const p of pending.values()){clearTimeout(p.timer);p.reject(Error('Board disconnected.'));}pending.clear();
 });
})();
