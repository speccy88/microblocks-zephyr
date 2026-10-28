// SPDX-License-Identifier: MIT
// Fixed fictional input only: no URLs, network, file import, VM or camera connection.
(function(){
 'use strict';
 const $=id=>document.getElementById(id),canvas=$('preview'),view=new MicroDuckCameraRGB.Preview(canvas),status=$('status');
 function clear(){view.clear();status.textContent='Cleared. No pixels retained.';}
 $('convert').addEventListener('click',()=>{
  // Four 2-pixel bands: black, white, red and blue. White top-left marks rotation.
  const row=[128,16,128,16,128,235,128,235,90,81,240,81,240,41,110,41];
  const raw=new Uint8Array([...row,...row,...row,...row]);raw[1]=235;
  const broken=$('fixture').value==='truncated';
  try{
   const m=view.show({width:8,height:4,format:'UYVY',bytes:64,rotate:Number($('rotation').value)},broken?raw.subarray(0,63):raw,
    {longest:Number($('size').value),applyRotation:$('apply').checked});
   status.textContent=`FICTIONAL snapshot: ${m.width} × ${m.height} pixels; ${m.bytes} RGBA bytes. Reported rotation ${m.reportedRotation}°; applied ${m.appliedRotation}°. BT.601 limited range; calibration unverified.`;
  }catch{status.textContent='Preview unavailable: invalid fixture bytes. Previous pixels cleared.';}
  finally{raw.fill(0);}
 });
 $('clear').addEventListener('click',clear);
 document.addEventListener('visibilitychange',()=>{if(document.hidden)clear();});
 window.addEventListener('pagehide',()=>view.close(),{once:true});
})();
