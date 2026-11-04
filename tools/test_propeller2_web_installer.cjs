// SPDX-License-Identifier: MIT
// Actual production JS loader against one explicitly authorized physical P2.
// This tests the shared core, not a browser's native USB chooser.
'use strict';
const fs=require('node:fs'),path=require('node:path'),{spawn}=require('node:child_process'),readline=require('node:readline'),crypto=require('node:crypto');
const L=require('../web/p2-installer/loader.js');
function arg(name){const i=process.argv.indexOf(name);if(i<0)throw Error('Required '+name);return process.argv[i+1];}
async function main(){
 if(!process.argv.includes('--allow-erase'))throw Error('Explicit --allow-erase is required');
 const port=arg('--port'),serial=arg('--usb-serial'),python=arg('--python'),assets=arg('--assets'),output=arg('--evidence');
 const child=spawn(python,[path.join(__dirname,'p2_installer_serial_bridge.py'),'--port',port,'--usb-serial',serial,'--allow-erase'],{stdio:['pipe','pipe','inherit'],windowsHide:true});
 let counter=0,resets=0;const waiting=new Map();
 readline.createInterface({input:child.stdout}).on('line',line=>{const reply=JSON.parse(line),item=waiting.get(reply.id);if(!item)return;waiting.delete(reply.id);clearTimeout(item.timer);reply.error?item.reject(Error(reply.error)):item.resolve(reply.value);});
 const rpc=(command,args={})=>new Promise((resolve,reject)=>{const id=++counter,timer=setTimeout(()=>{waiting.delete(id);reject(Error('Serial bridge timed out: '+command));},15000);waiting.set(id,{resolve,reject,timer});child.stdin.write(JSON.stringify({id,command,...args})+'\n');});
 const link={open:baud=>rpc('open',{baud}),close:()=>rpc('close'),clear:()=>rpc('clear'),
  write:bytes=>rpc('write',{data:Buffer.from(bytes).toString('base64')}),
  read:async timeout=>new Uint8Array(Buffer.from(await rpc('read',{timeout}),'base64')),
  setSignals:signals=>{if(signals.dataTerminalReady)resets++;return rpc('signals',{dtr:signals.dataTerminalReady});}};
 const report={status:'FAIL',checked_at_utc:new Date().toISOString(),port,usb_serial:serial,board:'edge32',
  environment:'production JavaScript loader core with guarded native serial transport; no browser chooser',
  firmware_source_unchanged:true,original_project_backup:'private-p2-before-grouped.json',operations:[]};
 try{
  await link.open(115200);const before=await L.probeVM(link);await link.close();
  if(before!=='v405 Parallax P2 Edge 32MB')throw Error('Expected known P2 VM before authorized replacement: '+before);
  report.initial_version=before;
  const manifest=JSON.parse(fs.readFileSync(path.join(assets,'firmware.json'))),entry=manifest.images.edge32;
  const image=new Uint8Array(fs.readFileSync(path.join(assets,entry.file))),stub=new Uint8Array(fs.readFileSync(path.join(assets,'flash-loader.bin')));
  report.image_sha256=await L.sha256(image);report.loader_sha256=crypto.createHash('sha256').update(fs.readFileSync(path.join(__dirname,'../web/p2-installer/loader.js'))).digest('hex');
  for(const mode of ['ram','flash']){
   let last=-10;const start=Date.now(),previous=resets;
   const result=await L.install(link,image,stub,manifest,'edge32',mode,{replaceExistingP2:true,
    progress:event=>{if(event.phase==='transfer'){const n=Math.floor(100*event.sent/event.total);if(n>=last+10){last=n;console.log(mode+' '+n+'%');}}else console.log(mode+' '+event.phase);}});
   if(!result.firmware_transferred||result.already_running)throw Error('Image was not transferred');
   if(mode==='ram'&&!result.rom_checksum_verified)throw Error('RAM checksum not verified');
   if(mode==='flash'&&!result.flash_boot_verified)throw Error('Flash boot not verified');
   report.operations.push({...result,seconds:(Date.now()-start)/1000,hardware_resets:resets-previous});
  }
  report.status='PASS';report.hardware_resets=resets;
 }catch(error){report.error=error.message;if(error.rom_reply_hex!==undefined)report.rom_reply_hex=error.rom_reply_hex;throw error;}
 finally{report.hardware_resets=resets;await link.close().catch(()=>{});child.stdin.end();fs.writeFileSync(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report));}
}
main().catch(error=>{console.error(error);process.exitCode=1;});
