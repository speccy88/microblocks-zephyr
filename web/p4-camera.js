/* SPDX-License-Identifier: MIT */
(() => {
 'use strict';
 const pending=new Map(),controlPending=new Map();let next=0,previewing=false,downloadURL,controlNext=0,tuning=false;
 const el=(tag,text)=>{const node=document.createElement(tag);if(text)node.textContent=text;return node;};
 let panel,status,canvas,download,handleInput,settingsStatus,usedInfo,settingsExport,settingsURL;
 let resolution,widthInput,heightInput,estimate,linkBaud=115200;
 const sliders=new Map(),tuningButtons=[];
 const control=(op,session=0,values=[0,0,0])=>new Promise((resolve,reject)=>{
  const id=controlNext=(controlNext+1)>>>0||1,body=new Uint8Array(24),v=new DataView(body.buffer);
  body.set([80,52,67,67,1,op]);v.setUint32(8,id,true);v.setUint32(12,session,true);
  values.forEach((value,i)=>v.setUint16(16+i*2,value,true));
  const packet=new Uint8Array(30);packet.set([251,213,0,25,0]);packet.set(body,5);packet[29]=254;
  const timer=setTimeout(()=>{controlPending.delete(id);reject(Error('Camera controls timed out. Matching firmware is required.'));},5000);
  controlPending.set(id,{resolve,reject,timer,op,session});
  if(!window.P4Send||P4Send(packet)!==packet.length){clearTimeout(timer);controlPending.delete(id);reject(Error('Connect the P4 first.'));}
 });
 const showSettings=meta=>{
  for(const [name,fields]of sliders){fields.range.value=fields.number.value=meta[name];fields.output.textContent=gainText(name,meta[name]);}
  if([115200,460800,921600].includes(meta.baud))linkBaud=meta.baud;
  updateEstimate();
 };
 function dimensions(){
  const width=Number(widthInput.value),height=Number(heightInput.value);
  if(!Number.isInteger(width)||!Number.isInteger(height)||width<16||width>1280||height<16||height>720)throw Error('Choose width 16–1280 and height 16–720.');
  return [width,height];
 }
 function updateEstimate(){
  if(!estimate)return;
  try{const [w,h]=dimensions(),bytes=w*h*2,seconds=.3+bytes*10/linkBaud+Math.ceil(bytes/512)*.006;
   estimate.textContent=`${w} × ${h}, colour. About ${seconds.toFixed(1)} s at ${(linkBaud/1000).toFixed(1)} kbaud; actual time appears after capture.`;
  }catch(error){estimate.textContent=error.message;}
 }
 function gainText(name,value){return name==='analog'?`${(256/(256-value)).toFixed(2)}×`:name==='digital'?`${(value/256).toFixed(2)}×`:`${value} lines`;}
 function settingsValues(){
  return ['exposure','analog','digital'].map(name=>{const {number}=sliders.get(name),value=Number(number.value);if(!Number.isInteger(value)||value<Number(number.min)||value>Number(number.max))throw Error('Camera setting outside its labelled range.');return value;});
 }
 async function settingsAction(action){
  if(tuning)return;tuning=true;tuningButtons.forEach(b=>b.disabled=true);let session=0;const began=performance.now();
  try{
   if(action==='read'||action==='reset'){
    const reply=await control(action==='read'?0:2);if(!reply.meta.supported)throw Error('Manual settings require the IMX219 / Pi Camera v2.1.');
    showSettings(reply.meta);settingsStatus.textContent=action==='reset'?'Original settings restored in RAM.':'Camera settings read from P4.';return;
   }
   const applied=await control(1,0,settingsValues());
   if(applied.meta.baud)linkBaud=applied.meta.baud;updateEstimate();
   settingsStatus.textContent='Settings applied for the next capture (RAM only).';
   if(action!=='snapshot')return;
   const random=new Uint32Array(1);crypto.getRandomValues(random);session=(random[0]&0x1fffffff)||1;
   settingsStatus.textContent='Capturing a real image from the P4 camera…';
   const [width,height]=dimensions();
   await control(3,session,[width,height,0]);const deadline=performance.now()+8500;let reply;
   do{
    reply=await control(4,session);
    if(reply.state===3)throw Error('Camera capture failed. Check camera status, then try again.');
    if(reply.state===2)break;
    if(performance.now()>deadline)throw Error('Camera snapshot deadline exceeded.');
    await new Promise(resolve=>setTimeout(resolve,60));
   }while(true);
   const meta=reply.meta;
   settingsStatus.textContent='Transferring the snapshot over USB…';
   if(!await preview(meta.handle))throw Error('Snapshot preview could not be read.');
   const used={exposure:meta.used_exposure,analog:meta.used_analog,digital:meta.used_digital,test_pattern:meta.pattern,
    width:P4LastPreview.width,height:P4LastPreview.height,baud:meta.baud,capture_ms:meta.capture_ms,
    preview_ms:Math.round(P4LastPreview.preview_ms),total_ms:Math.round(performance.now()-began)};
   window.P4LastSnapshot={...used};
   usedInfo.textContent=`This snapshot: exposure ${used.exposure} lines; analogue ${used.analog} (${gainText('analog',used.analog)}); digital ${used.digital} (${gainText('digital',used.digital)}). ${used.test_pattern?'DIAGNOSTIC TEST PATTERN.':'Real camera image.'}`;
   if(settingsURL)URL.revokeObjectURL(settingsURL);settingsURL=URL.createObjectURL(new Blob([JSON.stringify(used,null,2)+'\n'],{type:'application/json'}));
   settingsExport.href=settingsURL;settingsExport.download='p4-snapshot-settings.json';settingsExport.hidden=false;
   settingsStatus.textContent=`Snapshot ready in ${(used.total_ms/1000).toFixed(2)} s. Capture ${used.capture_ms} ms; preview transfer ${(used.preview_ms/1000).toFixed(2)} s.`;
  }catch(error){settingsStatus.textContent=error.message;}
  finally{
   if(session)try{await control(5,session);}catch{}
   tuning=false;tuningButtons.forEach(b=>b.disabled=false);
  }
 }
 window.addEventListener('p4-vm-frame',event=>{
  const frame=event.detail;if(!(frame instanceof Uint8Array)||frame[0]!==251||frame[1]!==213||frame.length<21)return;
  const body=frame.subarray(5),v=new DataView(body.buffer,body.byteOffset,body.byteLength);
  if(String.fromCharCode(...body.subarray(0,4))!=='P4CC'||body[4]!==1)return;
  let meta;try{meta=JSON.parse(new TextDecoder().decode(body.subarray(16)));}catch{return;}
  if(body[5]===128){panel.open=true;showSettings(meta);settingsStatus.textContent='Move the sliders, choose a resolution, then Take snapshot.';return;}
  const id=v.getUint32(8,true),p=controlPending.get(id);if(!p||p.op!==body[5]||p.session!==v.getUint32(12,true))return;
  controlPending.delete(id);clearTimeout(p.timer);
  const messages=['','Invalid camera settings or expired snapshot.','Manual controls are unsupported for this sensor.','Camera is busy. Stop the tracking program or wait for its capture to finish.'];
  body[6]?p.reject(Error(messages[body[6]]||'Camera control failed.')):p.resolve({meta,state:body[7]});
 });
 const request=(op,handle,offset=0,count=0)=>new Promise((resolve,reject)=>{
  const id=next=next%255+1,body=new Uint8Array(16),v=new DataView(body.buffer);
  body.set([80,52,73,77,id,op]);v.setUint32(6,handle,true);v.setUint32(10,offset,true);v.setUint16(14,count,true);
  const packet=new Uint8Array(22);packet.set([251,206,0,17,0]);packet.set(body,5);packet[21]=254;
  const timer=setTimeout(()=>{pending.delete(id);reject(Error('Image transfer timed out. Keep the image handle alive.'));},5000);
  pending.set(id,{resolve,reject,timer});
  if(window.P4Send(packet)!==packet.length){clearTimeout(timer);pending.delete(id);reject(Error('Connect the P4 first.'));}
 });
 window.P4CameraAccept=frame=>{
  const body=frame.subarray(5);
  if(frame[1]===207&&body.length===4){void preview(new DataView(body.buffer,body.byteOffset,4).getUint32(0,true));return;}
  if(frame[1]!==206||body.length<2)return;
  const p=pending.get(body[0]);if(!p)return;pending.delete(body[0]);clearTimeout(p.timer);
  body[1]?p.reject(Error('Image handle or byte range is invalid.')):p.resolve(body.slice(2));
 };
 async function preview(handle){
  if(previewing)return false;previewing=true;const began=performance.now();
  try{
   panel.open=true;handleInput.value=handle;status.textContent='Reading image from P4…';
   const meta=JSON.parse(new TextDecoder().decode(await request(1,handle)));
   if(!Number.isInteger(meta.bytes)||meta.bytes<1||meta.bytes>1280*720*3||![1,2,3].includes(meta.format)||meta.width*meta.height*meta.format!==meta.bytes)throw Error('Invalid image metadata.');
   const raw=new Uint8Array(meta.bytes);
   for(let offset=0;offset<raw.length;offset+=512){const n=Math.min(512,raw.length-offset),chunk=await request(2,handle,offset,n);if(chunk.length!==n)throw Error('Short image chunk.');raw.set(chunk,offset);}
   canvas.width=meta.width;canvas.height=meta.height;const ctx=canvas.getContext('2d'),pixels=ctx.createImageData(meta.width,meta.height);
   for(let i=0,j=0;i<raw.length;i+=meta.format,j+=4){
    if(meta.format===1)pixels.data[j]=pixels.data[j+1]=pixels.data[j+2]=raw[i];
    else if(meta.format===3){pixels.data[j]=raw[i];pixels.data[j+1]=raw[i+1];pixels.data[j+2]=raw[i+2];}
    else {const p=raw[i]+256*raw[i+1];pixels.data[j]=(p>>11&31)*255/31;pixels.data[j+1]=(p>>5&63)*255/63;pixels.data[j+2]=(p&31)*255/31;}
    pixels.data[j+3]=255;
   }
   ctx.putImageData(pixels,0,0);const blob=await new Promise(resolve=>canvas.toBlob(resolve,'image/png'));
   if(downloadURL)URL.revokeObjectURL(downloadURL);downloadURL=URL.createObjectURL(blob);download.href=downloadURL;download.download='p4-image-'+handle+'.png';download.hidden=false;
   status.textContent=`${meta.width} × ${meta.height} snapshot. Image stays in this tab.`;
   window.P4LastPreview={handle,...meta,preview_ms:performance.now()-began};
   return true;
  }catch(error){status.textContent=error.message;return false;}
  finally{previewing=false;}
 }
 window.P4Preview=preview;
 document.addEventListener('board-ide-ready',()=>{
  panel=el('details');panel.className='portal-tools';panel.append(el('summary','Camera image'));const box=el('section');box.className='portal-panel';panel.append(box);
  box.style.cssText='max-height:82vh;overflow:auto;width:min(420px,calc(100vw - 56px));min-width:0;gap:6px';
  box.append(el('h3','Pi Camera v2.1 snapshot tuning'));
  box.append(el('p','Adjust settings and resolution, then Take snapshot. Smaller pictures transfer faster. Settings stay in RAM until reboot.'));
  const sizeRow=el('div');sizeRow.style.cssText='display:grid;grid-template-columns:1fr 72px 72px;gap:6px;align-items:center';
  const sizeLabel=el('label','Snapshot resolution');resolution=el('select');resolution.setAttribute('aria-label','Snapshot resolution');
  for(const [value,label]of [['160x90','160 × 90 — quick'],['320x180','320 × 180'],['640x360','640 × 360'],['1280x720','1280 × 720 — full'],['custom','Custom']]){const option=el('option',label);option.value=value;resolution.append(option);}
  resolution.value='320x180';sizeLabel.append(resolution);sizeRow.append(sizeLabel);
  widthInput=el('input');widthInput.type='number';widthInput.min=16;widthInput.max=1280;widthInput.value=320;widthInput.setAttribute('aria-label','Snapshot width');
  heightInput=el('input');heightInput.type='number';heightInput.min=16;heightInput.max=720;heightInput.value=180;heightInput.setAttribute('aria-label','Snapshot height');
  widthInput.style.padding=heightInput.style.padding='4px';
  resolution.onchange=()=>{if(resolution.value!=='custom'){const [w,h]=resolution.value.split('x');widthInput.value=w;heightInput.value=h;}updateEstimate();};
  widthInput.oninput=heightInput.oninput=()=>{const key=widthInput.value+'x'+heightInput.value;resolution.value=['160x90','320x180','640x360','1280x720'].includes(key)?key:'custom';updateEstimate();};
  sizeRow.append(widthInput,heightInput);box.append(sizeRow);estimate=el('p');box.append(estimate);updateEstimate();
  for(const [name,label,min,max,value]of [['exposure','Exposure (lines)',4,1156,800],['analog','Analogue gain (register)',0,232,128],['digital','Digital gain (register)',256,4095,256]]){
   const row=el('label',label);row.style.cssText='display:grid;grid-template-columns:1fr 80px 76px;gap:3px 8px;align-items:center;margin:2px 0';
   const range=el('input');range.type='range';range.min=min;range.max=max;range.step=1;range.value=value;range.style.gridColumn='1';range.setAttribute('aria-label',label+' slider');
   const number=el('input');number.type='number';number.min=min;number.max=max;number.step=1;number.value=value;number.style.cssText='width:78px;padding:4px';number.setAttribute('aria-label',label);
   const output=el('output',gainText(name,value));
   range.oninput=()=>{number.value=range.value;output.textContent=gainText(name,Number(range.value));};
   number.oninput=()=>{if(number.checkValidity()){range.value=number.value;output.textContent=gainText(name,Number(number.value));}};
   row.append(range,number,output);box.append(row);sliders.set(name,{range,number,output});
  }
  const actions=el('div');actions.style.cssText='display:grid;grid-template-columns:1fr 1fr;gap:6px';box.append(actions);
  for(const [label,action]of [['Take snapshot','snapshot'],['Apply settings','apply'],['Read current settings','read'],['Reset camera settings','reset']]){const button=el('button',label);button.onclick=()=>settingsAction(action);tuningButtons.push(button);actions.append(button);}
  settingsStatus=el('p','Connect the P4, then Take snapshot. The first firmware update adds these controls.');settingsStatus.setAttribute('role','status');box.append(settingsStatus);
  usedInfo=el('p');box.append(usedInfo);
  settingsExport=el('a','Download snapshot settings');settingsExport.hidden=true;box.append(settingsExport);
  status=el('p','No snapshot yet.');box.append(status);
  const advanced=el('details');advanced.append(el('summary','Read an existing image handle (advanced)'));
  handleInput=el('input');handleInput.type='number';handleInput.min='1';handleInput.value='1';handleInput.setAttribute('aria-label','Image handle');advanced.append(handleInput);
  const button=el('button','Read image');button.onclick=()=>preview(Number(handleInput.value));advanced.append(button);
  canvas=el('canvas');canvas.style.cssText='width:100%;max-width:320px;height:auto;image-rendering:pixelated;align-self:center';box.append(canvas);
  download=el('a','Download PNG');download.hidden=true;box.append(download);
  box.append(advanced);
  document.querySelector('[data-ide="controls"]').prepend(panel);
 });
})();
