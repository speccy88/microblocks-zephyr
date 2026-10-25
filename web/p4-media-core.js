/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 const integer=(n,min,max)=>Number.isInteger(n)&&n>=min&&n<=max;
 function metadata(m){
  if(!m||!integer(m.bytes,1,256000))throw Error('Invalid result size.');
  if(m.kind===1){
   if(!integer(m.width,1,160)||!integer(m.height,1,90)||!integer(m.format,1,3)||m.width*m.height*m.format!==m.bytes||
      !integer(m.source_width,1,1280)||!integer(m.source_height,1,720))throw Error('Invalid image result.');
  }else if(m.kind===2){
   if(!integer(m.frames,1,128000)||m.rate!==16000||m.channels!==1||m.frames*2!==m.bytes)throw Error('Invalid PCM result.');
  }else throw Error('Unsupported result kind.');
  return m;
 }
 function rgba(m,data){
  metadata(m);if(m.kind!==1||data.length!==m.bytes)throw Error('Image length differs.');
  const out=new Uint8ClampedArray(m.width*m.height*4);
  for(let i=0,j=0;i<data.length;i+=m.format,j+=4){
   if(m.format===1)out[j]=out[j+1]=out[j+2]=data[i];
   else if(m.format===3){out[j]=data[i];out[j+1]=data[i+1];out[j+2]=data[i+2];}
   else{const p=data[i]|data[i+1]<<8;out[j]=(p>>11&31)*255/31;out[j+1]=(p>>5&63)*255/63;out[j+2]=(p&31)*255/31;}
   out[j+3]=255;
  }return out;
 }
 function wav(m,data){
  metadata(m);if(m.kind!==2||data.length!==m.bytes)throw Error('PCM length differs.');
  const out=new Uint8Array(44+data.length),v=new DataView(out.buffer);
  const put=(p,s)=>{for(let i=0;i<s.length;i++)out[p+i]=s.charCodeAt(i);};
  put(0,'RIFF');v.setUint32(4,36+data.length,true);put(8,'WAVEfmt ');v.setUint32(16,16,true);
  v.setUint16(20,1,true);v.setUint16(22,1,true);v.setUint32(24,m.rate,true);v.setUint32(28,m.rate*2,true);
  v.setUint16(32,2,true);v.setUint16(34,16,true);put(36,'data');v.setUint32(40,data.length,true);out.set(data,44);return out;
 }
 class Cache{
  constructor(dispose,{bytes=1048576,entries=8,audio=2}={}){Object.assign(this,{dispose,limit:bytes,max:entries,maxAudio:audio});this.items=new Map();this.bytes=0;}
  drop(uid,reason='evict'){const item=this.items.get(uid);if(!item)return;this.items.delete(uid);this.bytes-=item.cost;this.dispose(uid,item,reason);}
  clear(){for(const uid of [...this.items.keys()])this.drop(uid);}
  get(uid){const item=this.items.get(uid);if(item){this.items.delete(uid);this.items.set(uid,item);}return item;}
  put(uid,item){
   this.drop(uid,'replace');
   if(!integer(item.cost,1,this.limit))throw Error('Result exceeds browser cache.');
   while(this.items.size && (this.bytes+item.cost>this.limit||this.items.size>=this.max||
     item.kind===2&&[...this.items.values()].filter(x=>x.kind===2).length>=this.maxAudio))this.drop(this.items.keys().next().value);
   this.items.set(uid,item);this.bytes+=item.cost;
  }
 }
 function packet(id,op,session=0,token=0,offset=0,count=0,uid=0){
  const out=new Uint8Array(34),v=new DataView(out.buffer);out.set([251,208,0,29,0,80,52,77,82,op,0]);
  v.setUint32(11,id,true);v.setUint32(15,session,true);v.setUint32(19,token,true);v.setUint32(23,offset,true);v.setUint16(27,count,true);v.setUint32(29,uid,true);out[33]=254;return out;
 }
 function serialCalls(invoke){let tail=Promise.resolve();return(...args)=>{const task=()=>invoke(...args),answer=tail.then(task,task);tail=answer.catch(()=>{});return answer;};}
 const api={metadata,rgba,wav,Cache,packet,serialCalls};root.P4MediaCore=api;if(typeof module!=='undefined')module.exports=api;
})(typeof window==='undefined'?globalThis:window);
