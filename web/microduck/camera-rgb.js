// SPDX-License-Identifier: Apache-2.0
// Adapted from Pollen uyvy/src/lib.rs at 96b89d8613f06722c1d64ce75ab0d7124fed9d8f.
// See camera-rgb-NOTICE.txt and camera-rgb-LICENSE.txt. Bounds/lifecycle are local.
(function(root){
 'use strict';
 const MAX_RAW=16*1024*1024,MAX_SIDE=160,MAX_RGBA=MAX_SIDE*MAX_SIDE*4;
 const integer=(n,min,max)=>Number.isSafeInteger(n)&&n>=min&&n<=max;
 const requireValue=(ok,code)=>{if(!ok)throw new Error(code);};
 function geometry(g,raw){
  requireValue(g&&Object.getPrototypeOf(g)===Object.prototype&&Object.keys(g).sort().join(',')==='bytes,format,height,rotate,width','GEOMETRY');
  requireValue(integer(g.width,2,MAX_RAW/2)&&g.width%2===0&&integer(g.height,1,MAX_RAW/4)&&g.format==='UYVY'&&
   integer(g.bytes,4,MAX_RAW)&&g.bytes===g.width*g.height*2&&[0,90,180,270].includes(g.rotate),'GEOMETRY');
  requireValue(raw instanceof Uint8Array&&raw.buffer instanceof ArrayBuffer&&raw.byteLength===g.bytes,'PIXEL_BYTES');
 }
 function rgb(y,u,v){
  requireValue([y,u,v].every(n=>integer(n,0,255)),'COMPONENT');
  const l=y-16,cb=u-128,cr=v-128,clamp=n=>Math.max(0,Math.min(255,n>>8));
  return [clamp(298*l+409*cr+128),clamp(298*l-100*cb-208*cr+128),clamp(298*l+516*cb+128)];
 }
 function convert(g,raw,{longest=160,applyRotation=false}={}){
  geometry(g,raw);requireValue(integer(longest,1,MAX_SIDE)&&typeof applyRotation==='boolean','OPTIONS');
  const turn=applyRotation?g.rotate:0,w=g.width,h=g.height;
  const uw=(turn===90||turn===270)?h:w,uh=(turn===90||turn===270)?w:h,den=Math.max(uw,uh),num=Math.min(longest,den);
  // Half-up integer sizing, never larger than the source or the requested box.
  const width=Math.max(1,Math.floor((2*uw*num+den)/(2*den))),height=Math.max(1,Math.floor((2*uh*num+den)/(2*den)));
  const bytes=width*height*4;requireValue(bytes<=MAX_RGBA,'OUTPUT_LIMIT');
  const rgba=new Uint8ClampedArray(bytes);
  for(let y=0;y<height;y++)for(let x=0;x<width;x++){
   const ux=Math.floor(x*uw/width),uy=Math.floor(y*uh/height);
   const [sx,sy]=turn===90?[uy,h-1-ux]:turn===180?[w-1-ux,h-1-uy]:turn===270?[w-1-uy,ux]:[ux,uy];
   const pair=(sy*w+Math.floor(sx/2)*2)*2,c=rgb(raw[pair+1+2*(sx%2)],raw[pair],raw[pair+2]),at=(y*width+x)*4;
   rgba[at]=c[0];rgba[at+1]=c[1];rgba[at+2]=c[2];rgba[at+3]=255;
  }
  return {width,height,rgba,reportedRotation:g.rotate,appliedRotation:turn,colorInterpretation:'BT.601 limited range',calibrationVerified:false};
 }
 class Preview{
  constructor(canvas){
   requireValue(canvas&&canvas.width===0&&canvas.height===0&&typeof canvas.getContext==='function','CANVAS_BUSY');
   this.canvas=canvas;this.closed=false;
  }
  clear(){this.canvas.width=0;this.canvas.height=0;}
  show(g,raw,options){
   requireValue(!this.closed,'CLOSED');this.clear();let result,pixels;
   try{
    result=convert(g,raw,options);const c=this.canvas;c.width=result.width;c.height=result.height;
    const ctx=c.getContext('2d');requireValue(ctx,'CANVAS_UNAVAILABLE');
    pixels=ctx.createImageData(result.width,result.height);pixels.data.set(result.rgba);ctx.putImageData(pixels,0,0);
    return {width:result.width,height:result.height,bytes:result.rgba.byteLength,reportedRotation:result.reportedRotation,appliedRotation:result.appliedRotation};
   }catch(e){this.clear();throw e;}
   finally{result?.rgba.fill(0);pixels?.data.fill(0);}
  }
  close(){this.clear();this.closed=true;}
 }
 const api=Object.freeze({MAX_RAW,MAX_SIDE,MAX_RGBA,rgb,convert,Preview});
 if(typeof module==='object'&&module.exports)module.exports=api;else root.MicroDuckCameraRGB=api;
})(globalThis);
