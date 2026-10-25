/* SPDX-License-Identifier: MPL-2.0 */
(() => {
 const board=document.getElementById('board'),frame=document.getElementById('ide'),status=document.getElementById('portal-status');
 let selected='fruit-jam';
 document.getElementById('open-editor').onclick=async()=>{
  if(board.value===selected){document.getElementById('editor').scrollIntoView({behavior:'smooth'});return;}
  const button=document.getElementById('open-editor');button.disabled=true;
  try{
   if(frame.contentWindow.portalSaveBeforeLeaving)await frame.contentWindow.portalSaveBeforeLeaving();
   selected=board.value;const path='editor/'+selected+'/microblocks.html';
   frame.src=path;frame.title='MicroBlocks editor for '+board.selectedOptions[0].textContent;
   document.getElementById('full-editor').href=path;status.textContent='Loading '+board.selectedOptions[0].textContent+' editor…';
  }catch(error){status.textContent=error.message+' Export your project before switching boards.';board.value=selected;}
  finally{button.disabled=false;}
 };
 frame.onload=()=>{status.textContent=selected==='esp32p4'?'P4 camera: native Zephyr USB programming, camera blocks and image preview. USB needs desktop Chrome or Edge. Wi-Fi hosting is not enabled yet.':selected==='xrp-rp2350'?'XRP development preview: edit and save projects. Hardware connection is not enabled yet.':'Choose Projects & board inside the editor for USB, Wi-Fi setup and browser projects. A board never connects automatically.';};
})();
