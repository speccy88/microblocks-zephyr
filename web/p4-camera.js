/* SPDX-License-Identifier: MIT */
(() => {
 'use strict';
 const pending=new Map();let next=0,previewing=false,downloadURL;
 const el=(tag,text)=>{const node=document.createElement(tag);if(text)node.textContent=text;return node;};
 let panel,status,canvas,download,handleInput;
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
  if(previewing)return;previewing=true;
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
   status.textContent=`${meta.width} × ${meta.height}; ${['','GRAY8','RGB565','RGB888'][meta.format]}; ${meta.bytes} bytes. Image stays in this tab.`;
   window.P4LastPreview={handle,...meta};
  }catch(error){status.textContent=error.message;}
  finally{previewing=false;}
 }
 window.P4Preview=preview;
 document.addEventListener('board-ide-ready',()=>{
  panel=el('details');panel.className='portal-tools';panel.append(el('summary','Camera image'));const box=el('section');box.className='portal-panel';panel.append(box);
  status=el('p','Use the preview / export block, or enter a live image handle.');box.append(status);
  handleInput=el('input');handleInput.type='number';handleInput.min='1';handleInput.value='1';handleInput.setAttribute('aria-label','Image handle');box.append(handleInput);
  const button=el('button','Read image');button.onclick=()=>preview(Number(handleInput.value));box.append(button);
  canvas=el('canvas');canvas.style.cssText='max-width:100%;height:auto;image-rendering:pixelated';box.append(canvas);
  download=el('a','Download PNG');download.hidden=true;box.append(download);
  document.querySelector('[data-ide="controls"]').prepend(panel);
 });
})();
