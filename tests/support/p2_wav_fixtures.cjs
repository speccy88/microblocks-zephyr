// SPDX-License-Identifier: MIT
const assert=require('node:assert/strict');
const {fixture}=require('./gp_sensor_fixture.cjs');
function chunk(id,bytes,pad=true){const h=Buffer.alloc(8);h.write(id);h.writeUInt32LE(bytes.length,4);return Buffer.concat([h,bytes,...(pad&&bytes.length%2?[Buffer.alloc(1)]:[])]);}
function wav({channels=1,bits=8,rate=8000,format=1,align=channels*bits/8,data=Buffer.from([0,128,255,30]),junk=false,unpad=false}={}){
 const f=Buffer.alloc(16);f.writeUInt16LE(format);f.writeUInt16LE(channels,2);f.writeUInt32LE(rate,4);f.writeUInt32LE(rate*align,8);f.writeUInt16LE(align,12);f.writeUInt16LE(bits,14);
 const body=Buffer.concat([Buffer.from('WAVE'),...(junk?[chunk('JUNK',Buffer.from([1,2,3]))]:[]),chunk('fmt ',f),chunk('data',data,!unpad)]);
 const h=Buffer.alloc(8);h.write('RIFF');h.writeUInt32LE(body.length,4);return new Uint8Array(Buffer.concat([h,body]));
}
module.exports=function(trees,audioTrees){
 function session(blob,extra={}){
  let cursor=0,closes=0,running=false,frames=0;
  const f=fixture([...trees,...audioTrees],{hooks:{
   '[file:fileSize]':()=>blob.length,'[file:open]':()=>{cursor=0;return true;},
   '[file:readBytes]':count=>{const b=blob.slice(cursor,cursor+count);cursor+=b.length;return b;},
   '[file:readPosition]':()=>cursor,'[file:setReadPosition]':position=>{cursor=position;return true;},
   '[file:close]':()=>{closes++;},waitMillis:()=>{},
   '[p2:p2AudioInit]':()=>{running=true;return true;},
   '[p2:p2AudioPCM]':(data,channels,bits,start)=>{const n=(data.length-start+1)/(channels*bits/8);frames+=n;return n;},
   '[p2:p2AudioFinish]':()=>{running=false;},'[p2:p2AudioRunning]':()=>running,
   '[p2:p2AudioStop]':()=>{running=false;},...extra
  }});
  return {f,state:()=>({cursor,closes,running,frames})};
 }
 for(const options of [{},{junk:true},{channels:2,bits:16,rate:22050},{data:Buffer.from([1,2,3]),unpad:true}]){
  const s=session(wav(options)),header=s.f.call('wavPCMHeader','sound.wav');
  assert.deepEqual(header,[options.rate??8000,options.channels??1,options.bits??8,(options.data??Buffer.from([0,128,255,30])).length]);
 }
 for(const options of [{format:3},{channels:3},{rate:48000},{align:2},{channels:2,bits:16,data:Buffer.from([1,2,3])}]){
  assert.equal(session(wav(options)).f.call('wavPCMHeader','sound.wav'),false);
 }
 const cut=wav().slice(0,-1);assert.equal(session(cut).f.call('wavPCMHeader','sound.wav'),false);
 const bad=wav();bad[0]=88;assert.equal(session(bad).f.call('wavPCMHeader','sound.wav'),false);
 const huge=wav();huge.set([255,255,255,63],16);assert.equal(session(huge).f.call('wavPCMHeader','sound.wav'),false);
 const s=session(wav({junk:true}));assert.equal(s.f.call('p2PlayWAV','sound.wav',16,3),true);
 assert.equal(s.state().frames,4);assert.equal(s.state().running,false);assert.equal(s.state().closes,1);
 const full=session(wav(),{'[p2:p2AudioPCM]':()=>0});assert.equal(full.f.call('p2PlayWAV','sound.wav',16,3),false);assert(!full.state().running);
 const stopped=session(wav(),{'[p2:p2AudioPCM]':()=>-1});assert.equal(stopped.f.call('p2PlayWAV','sound.wav',16,3),false);
 return {PCM8_16_mono_stereo:true,unknown_odd_chunks:true,truncation:true,unsupported_formats:true,cooperative_queue_timeout:true,physical:false};
};
