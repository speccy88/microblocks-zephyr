// SPDX-License-Identifier: MPL-2.0
// TEST ONLY. Synthetic USB provider and stored code; never opens hardware/network.
(() => {
 'use strict';let chunks=[],queued=[],waiting=[],incoming=[],audit=[],hold=false,reading=false,saved=null,status;
 const feed=bytes=>{const value=new Uint8Array(bytes);if(waiting.length)waiting.shift()({value,done:false});else queued.push(value);};
 const long=(type,body,id=0)=>new Uint8Array([251,type,id,body.length&255,body.length>>8,...body]);
 function handle(frame){
  audit.push({type:frame[1],duringRead:!!MB_connection.readbackInProgress});
  if(frame[1]===26)feed([250,26,frame[2]]);
  else if(frame[1]===12)feed(long(22,[2,...new TextEncoder().encode('v417 Waveshare ESP32-P4 SIMULATED')]));
  else if(frame[1]===13&&!hold)for(const c of [...chunks].reverse()){const f=long(32,[c.kind,...c.bytes],c.id);feed(f.subarray(0,3));feed(f.subarray(3));}
  else if(frame[1]===208){const v=new DataView(frame.buffer,frame.byteOffset),body=new Uint8Array(14),out=new DataView(body.buffer);out.setUint32(0,v.getUint32(11,true),true);body[4]=1;body[5]=frame[9];out.setUint32(6,v.getUint32(15,true),true);out.setUint32(10,v.getUint32(19,true),true);feed(long(208,body));}
 }
 const reader={async read(){return queued.length?{value:queued.shift(),done:false}:new Promise(resolve=>waiting.push(resolve));},async cancel(){for(const fn of waiting.splice(0))fn({done:true});},releaseLock(){}};
 const writer={async write(bytes){incoming.push(...bytes);while(incoming.length>=3){const size=incoming[0]===250?3:incoming.length>=5?5+incoming[3]+256*incoming[4]:Infinity;if(incoming.length<size)break;handle(new Uint8Array(incoming.splice(0,size)));}},async abort(){},releaseLock(){}};
 const serial={async requestPort(){return {async open(){},async setSignals(){},async close(){},readable:{getReader:()=>reader},writable:{getWriter:()=>writer}};}};
 Object.defineProperty(navigator,'serial',{value:serial});
 const pad=bytes=>{while(bytes.length%4)bytes.push(0);return bytes;};
 async function prepare(){
  await MB_Files.initialize();await MB_editor.openLibraryFile(MicroBlocksJSProfile.bundle);MB_editor.codeManager.assignFunctionIDs();
  const compiler=new MB_Compiler(MB_editor.project,MB_editor.codeManager);
  chunks=MB_editor.project.allFunctions().map(f=>({id:MB_editor.codeManager.functionChunkIDs.get(f.functionName),kind:3,bytes:pad(compiler.compiledBytesFor(f))}));
  for(const expression of ['+ 20 22','p4TakePicture',"p4SmoothResize ('[p4:imageTestPattern]' 3 2 3) 2 2"]){const b=MB_Parser.blockFor(MB_Parser.parse(expression)[0],true);chunks.push({id:200+chunks.length-64,kind:2,bytes:pad(compiler.compiledBytesFor(b))});}
  await MB_editor.clearProject();MB_editor.readFromBoard=true;await MB_connection.connect('serial');
 }
 function verify(){
  const invalid=audit.filter(x=>x.duringRead&&![9,12,13,26].includes(x.type));if(invalid.length)throw Error('Mutation during readback');
  if(MB_editor.project.allFunctions().length!==64||MB_editor.project.blockSpecs.size!==189||MB_editor.project.main.scripts.length!==3)throw Error('Incomplete board project');
  saved=MB_editor.project.codeString();status.textContent='SIMULATED READBACK PASS:64 functions,189 definitions,3 scripts; readback sent queries only. Handshake uses fixture-only control frames. No hardware validation.';
 }
 window.addEventListener('load',()=>{
  const panel=document.createElement('section');panel.dataset.ide='controls';panel.style.cssText='position:fixed;left:8px;bottom:38px;z-index:99;background:#fff5cc;color:#111;padding:8px;font:14px sans-serif;max-width:850px';
  status=document.createElement('p');status.setAttribute('role','status');status.textContent='SIMULATED USB BOARD ONLY — stored code, no physical board or camera/audio.';panel.append(status);
  function button(label,fn){const b=document.createElement('button');b.textContent=label;b.style.cssText='padding:4px;margin:3px;border:1px solid #666';b.onclick=()=>void fn().catch(e=>{status.textContent='FIXTURE ERROR: '+e.message;});panel.append(b);}
  button('Connect and read SIMULATED board',async()=>{if(reading||MB_connection.port)throw Error('Fixture already connected');reading=true;try{await prepare();status.textContent='SIMULATED board connected; wait for readback, then verify.';}finally{reading=false;}});
  button('Verify simulated readback',async()=>verify());
  button('Cancel a simulated read without clearing',async()=>{hold=true;const start=audit.length,pending=MB_editor.openProjectFromBoard();setTimeout(()=>void MB_connection.stopDecompilation(),400);await pending;hold=false;if(audit.slice(start).some(x=>x.duringRead&&![9,12,13,26].includes(x.type)))throw Error('Cancel wrote to board');status.textContent='SIMULATED CANCEL PASS: no clear, reset, upload or run during cancelled read.';});
  button('Reopen saved readback source',async()=>{if(!saved)throw Error('Verify readback first');MB_connection.disconnect();await MB_editor.openProjectFromString(saved,'SimulatedReadback');if(MB_editor.project.blockSpecs.size!==189||MB_editor.project.main.scripts.length!==3)throw Error('Reopen incomplete');status.textContent='SIMULATED REOPEN PASS:189 definitions and3 scripts; no media or transient site IDs.';});
  document.body.append(panel);
 });
})();
