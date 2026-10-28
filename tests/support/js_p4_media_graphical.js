// SPDX-License-Identifier: MPL-2.0
// TEST ONLY: inserted into a separate local fixture entry, never a product build.
(() => {
 'use strict';let ui,saved;
 const attach=MicroBlocksP4UI.attach;
 MicroBlocksP4UI={...MicroBlocksP4UI,attach(...args){ui=attach(...args);return ui;}};
 window.addEventListener('load',()=>{
  const panel=document.createElement('section');panel.dataset.ide='controls';panel.style.cssText='position:fixed;left:8px;bottom:40px;z-index:99;padding:8px;background:#fff5cc;color:#111;font:14px sans-serif';
  const message=document.createElement('p');message.setAttribute('role','status');message.textContent='STORED FIXTURES ONLY — no camera, microphone or board connection.';panel.append(message);
  function button(label,fn){const b=document.createElement('button');b.textContent=label;b.onclick=async()=>{try{await fn();}catch(e){message.textContent='FIXTURE ERROR: '+e.message;throw e;}};panel.append(b);}
  button('Load stored image and PCM fixtures',async()=>{
   await MB_editor.openProjectFromString('module main\nscript 30 30 ([p4:imageTestPattern] 160 90 3)\nscript 300 30 ([p4:audioResult])\n','MediaFixtures');
   await MB_Files.initialize();await MB_editor.openLibraryFile(MicroBlocksJSProfile.bundle);
   ui.media.tick();const blocks=MB_editor.project.main.scripts.map(s=>s[2]);saved=MB_editor.project.codeString();
   const picture=ui.media.ensure(blocks[0]),sound=ui.media.ensure(blocks[1]),pixels=new Uint8Array(160*90*3);
   for(let y=0;y<90;y++)for(let x=0;x<160;x++){const i=3*(y*160+x);pixels[i]=x<53?255:0;pixels[i+1]=x>=53&&x<106?255:0;pixels[i+2]=x>=106?255:0;}
   ui.media.apply(picture.uid,{kind:1,width:160,height:90,source_width:160,source_height:90,format:3,bytes:pixels.length},pixels);pixels.fill(0);
   const pcm=new Uint8Array(128000);ui.media.apply(sound.uid,{kind:2,frames:64000,rate:16000,channels:1,bytes:pcm.length},pcm);pcm.fill(0);
   if(saved!==MB_editor.project.codeString())throw Error('Project changed by media');
   message.textContent='FIXTURE PASS: RGB bars and 4 s silent PCM; project text unchanged; no autoplay.';
  });
  button('Reopen saved fixture source',async()=>{if(!saved)throw Error('Load fixtures first');await MB_editor.openProjectFromString(saved,'MediaFixtures');ui.media.tick();if(MB_editor.project.codeString()!==saved)throw Error('Reopen changed source');message.textContent='REOPEN PASS: source unchanged; no pixels, PCM or site IDs restored.';});
  button('Expire fixture results',()=>{ui.media.clearResults();message.textContent='EXPIRE PASS: browser media cleared; explicit collapse is preserved.';});
  document.body.append(panel);
 });
})();
