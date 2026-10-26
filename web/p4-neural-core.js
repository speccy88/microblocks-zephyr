/* SPDX-License-Identifier: MIT */
(function(root,factory){const api=factory();if(typeof module==='object'&&module.exports)module.exports=api;else root.P4NeuralCore=api;})(typeof globalThis==='object'?globalThis:this,function(){
 'use strict';
 const encoder=new TextEncoder(),MAX_MODEL=262144,MAX_ARENA=524288;
 const clean=(v,n)=>typeof v==='string'&&v.length>0&&encoder.encode(v).length<=n&&/^[\x20-\x21\x23-\x5b\x5d-\x7e]+$/.test(v);
 const hash=v=>typeof v==='string'&&/^[a-f0-9]{64}$/.test(v);
 function validateManifest(m,size){
  if(!m||m.schema!==1||m.artifact_format!=='tflite'||m.backend!=='tflm-reference-dense-v1')throw Error('Requires a TFLite artifact for the native dense backend. ONNX needs supported offline conversion.');
  if(!clean(m.id,32)||!clean(m.license,48)||!clean(m.source,120)||!hash(m.sha256))throw Error('Model id, license, source and SHA-256 are required.');
  if(!Number.isInteger(size)||size<32||size>MAX_MODEL||m.bytes!==size)throw Error('Model size mismatch or 256 KiB limit exceeded.');
  if(!Number.isInteger(m.arena_bytes)||m.arena_bytes<4096||m.arena_bytes>MAX_ARENA)throw Error('Tensor arena must be 4..512 KiB.');
  if(!Array.isArray(m.operators)||!m.operators.length||m.operators.length>16||m.operators.some(x=>x!=='FULLY_CONNECTED'))throw Error('This backend supports bounded FULLY_CONNECTED graphs only.');
  if(!['tflite','onnx'].includes(m.source_format)||m.source_format==='onnx'&&!hash(m.source_sha256)||m.source_sha256!==undefined&&!hash(m.source_sha256))throw Error('Converted ONNX requires its original source hash.');
  return {id:m.id,license:m.license,source:m.source,sha256:m.sha256,source_format:m.source_format,source_sha256:m.source_sha256||'0'.repeat(64),arena_bytes:m.arena_bytes,bytes:size};
 }
 function metadata(m){
  const text=[m.id,m.license,m.source].map(x=>encoder.encode(x)),out=new Uint8Array(68+text.reduce((n,x)=>n+x.length,0));
  const fromHex=s=>Uint8Array.from(s.match(/../g),x=>parseInt(x,16));out.set(fromHex(m.sha256));out.set(fromHex(m.source_sha256),32);out[64]=m.source_format==='onnx'?1:0;
  let pos=65;for(const t of text){out[pos++]=t.length;out.set(t,pos);pos+=t.length;}return out;
 }
 function packet(op,id,token=0,offset=0,arg=0,payload=new Uint8Array(),readCount=0){
  for(const x of [op,id,token,offset,arg,readCount])if(!Number.isInteger(x)||x<0||x>0xffffffff)throw Error('Invalid NN request field.');
  if(op>255||payload.length>512||readCount>512)throw Error('NN request bounds exceeded.');
  const count=op===6?readCount:payload.length,body=new Uint8Array(24+payload.length),v=new DataView(body.buffer);
  body.set([80,52,78,78,op,1]);v.setUint32(6,id,true);v.setUint32(10,token,true);v.setUint32(14,offset,true);v.setUint16(18,count,true);v.setUint32(20,arg,true);body.set(payload,24);
  const frame=new Uint8Array(body.length+6),f=new DataView(frame.buffer);frame.set([251,216,0]);f.setUint16(3,body.length+1,true);frame.set(body,5);frame[frame.length-1]=254;return frame;
 }
 return {MAX_MODEL,MAX_ARENA,validateManifest,metadata,packet};
});
