/* SPDX-License-Identifier: MPL-2.0 */
(() => {
 const board=document.getElementById('board'),frame=document.getElementById('ide'),status=document.getElementById('portal-status');
 const linuxContainer=document.getElementById('linux-install'),endpoints=new Map();
 const isLinux=id=>id==='raspberry-pi5'||id==='microduck';
 let selected='fruit-jam',linuxPanel;
 const duckContainer=document.getElementById('microduck-discovery'),duckPanel=MicroDuckPanel.mount(duckContainer);
 const applyEndpoint=()=>{if(isLinux(selected)&&endpoints.has(selected)&&typeof frame.contentWindow.microblocksLinuxSetEndpoint==='function')frame.contentWindow.microblocksLinuxSetEndpoint(endpoints.get(selected));};
 async function openEditor(){
  if(board.value===selected){applyEndpoint();document.getElementById('editor').scrollIntoView({behavior:'smooth'});return;}
  const button=document.getElementById('open-editor');button.disabled=true;
  try{
   if(frame.contentWindow.portalSaveBeforeLeaving)await frame.contentWindow.portalSaveBeforeLeaving();
   selected=board.value;const path='editor/'+selected+'/microblocks.html';
   frame.src=path;frame.title='MicroBlocks editor for '+board.selectedOptions[0].textContent;
   document.getElementById('full-editor').href=path;status.textContent='Loading '+board.selectedOptions[0].textContent+' editor…';
  }catch(error){status.textContent=error.message+' Export your project before switching boards.';board.value=selected;throw error;}
  finally{button.disabled=false;}
 }
 document.getElementById('open-editor').onclick=()=>{void openEditor().catch(()=>{});};
 linuxPanel=MicroBlocksLinuxPanel.mount(linuxContainer,{
  onOpenEditor:async({profile})=>{board.value=profile;await openEditor();},
  onEndpoint:async({profile,endpoint})=>{endpoints.set(profile,endpoint);board.value=profile;await openEditor();}
 });
 board.onchange=()=>{linuxContainer.hidden=!isLinux(board.value);if(!linuxContainer.hidden)linuxPanel.setProfile(board.value);duckContainer.hidden=board.value!=='microduck';if(duckContainer.hidden)duckPanel.disconnect();};
 fetch('linux-release.json',{cache:'no-store'}).then(response=>{if(!response.ok)throw Error('Release manifest unavailable');return response.json();}).then(value=>linuxPanel.setReleaseManifest(value)).catch(()=>{});
 frame.onload=()=>{
  applyEndpoint();
  status.textContent=isLinux(selected)?(selected==='microduck'?'MicroDuck preparation: Linux core editor; robot hardware validation is pending.':'Linux ARM64: use a trusted WSS bridge here, or open the Pi editor through a local SSH tunnel.'):selected==='esp32p4'?'P4 camera: native Zephyr USB programming, camera blocks and image preview. USB needs desktop Chrome or Edge. Wi-Fi hosting is not enabled yet.':selected==='xrp-rp2350'?'XRP development preview: edit and save projects. Hardware connection is not enabled yet.':'Choose Projects & board inside the editor for USB, Wi-Fi setup and browser projects. A board never connects automatically.';
 };
})();
