/* SPDX-License-Identifier: MIT */
(()=>{
 'use strict';
 const core=window.MicroBlocksFiles;
 const el=(tag,text,cls)=>{const n=document.createElement(tag);if(text!==undefined)n.textContent=text;if(cls)n.className=cls;return n;};
 // The shared portal registers later in the document. Let every ready listener
 // finish its synchronous toolbar construction before looking for the menu.
 document.addEventListener('board-ide-ready',()=>queueMicrotask(()=>{
  const projectPanel=document.querySelector('[data-device-project-panel]');if(!projectPanel||document.getElementById('device-files-dialog'))return;
  let client=new core.Client(),transport=null,mode='disconnected',snapshot=null,editor=null,pendingDiscard=null,uiEpoch=0;
  const connection=window.MicroBlocksFilesConnection;let connectionState='disconnected';
  const urls=new Map();
  const entry=el('button','Device files');entry.type='button';entry.setAttribute('aria-haspopup','dialog');projectPanel.prepend(entry);
  const dialog=el('dialog',undefined,'device-files');dialog.id='device-files-dialog';dialog.setAttribute('aria-labelledby','device-files-title');document.body.append(dialog);
  const header=el('header',undefined,'files-header'),title=el('h2','Device files');title.id='device-files-title';
  const close=el('button','Close');close.type='button';header.append(title,close);dialog.append(header);
  const banner=el('p','Connect your board, then Connect files. Compatible storage firmware is required.','files-banner');dialog.append(banner);
  const toolbar=el('div',undefined,'files-toolbar'),backend=el('select');backend.setAttribute('aria-label','Storage backend');
  for(const [name,label,disabled] of [['RAM','RAM · temporary',false],['Flash','Flash · unavailable',true],['SD','SD · unavailable',true]]){
   const option=el('option',label);option.value=name;option.disabled=disabled;backend.append(option);
  }
  const connectFiles=el('button','Connect files'),refresh=el('button','Refresh'),create=el('button','New text file'),cancel=el('button','Cancel operation');
  for(const button of [connectFiles,refresh,create,cancel])button.type='button';toolbar.append(backend,connectFiles,refresh,create,cancel);dialog.append(toolbar);
  const capacity=el('p','Connect a supported file transport to read capacity.','files-capacity');dialog.append(capacity);
  const layout=el('div',undefined,'files-layout'),list=el('div',undefined,'files-list');list.setAttribute('aria-label','Files in RAM');
  const edit=el('section',undefined,'files-editor'),empty=el('p','Choose a file, or create a small text file.','files-empty');
  const pathLabel=el('label','Path'),path=el('input');path.type='text';path.maxLength=63;path.placeholder='/RAM/note.txt';path.setAttribute('aria-label','File path');pathLabel.append(path);
  const textLabel=el('label','Text'),area=el('textarea');area.rows=9;area.maxLength=8192;area.spellcheck=false;area.setAttribute('aria-label','File text');textLabel.append(area);
  const detail=el('p','','files-detail'),buttons=el('div',undefined,'files-actions'),save=el('button','Save changes'),download=el('button','Download');
  save.type=download.type='button';save.className='files-primary';download.title='Download the version opened here. Unsaved edits are not included.';buttons.append(save,download);
  edit.append(empty,pathLabel,textLabel,detail,buttons);layout.append(list,edit);dialog.append(layout);
  const status=el('p','No device files have been accessed.','files-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');dialog.append(status);
  const confirm=el('div',undefined,'files-confirm');confirm.hidden=true;
  const discard=el('button','Discard edits'),keep=el('button','Keep editing');discard.type=keep.type='button';
  confirm.append(el('p','Discard the unsaved text in this editor?'),discard,keep);dialog.append(confirm);
  let fixtureButton;
  if(window.MicroBlocksFilesFixture&&location.protocol==='http:'&&location.hostname==='127.0.0.1'){
   fixtureButton=el('button','Load sample files');fixtureButton.type='button';fixtureButton.className='files-fixture';
   dialog.append(el('p','Local development preview only: sample files use browser memory.','files-fixture-note'),fixtureButton);
  }
  const dirty=()=>!!editor&&editor.text!==null&&(area.value!==editor.baseline||(!editor.meta&&path.value!==editor.initialPath));
  function message(value,error=false){status.textContent=value;status.dataset.error=String(error);}
  function controls(){
   const busy=client.busy,connected=!!transport,editable=!!editor&&editor.text!==null;
   connectFiles.textContent=connectionState==='ready'?'Disconnect files':'Connect files';
   connectFiles.disabled=!connection||connectionState==='disconnected'||['connecting','closing'].includes(connectionState)||busy;
   refresh.disabled=!connected||busy;create.disabled=!snapshot||busy||client.uncertain||snapshot.list.freeSlots===0;cancel.disabled=!busy;
   path.disabled=!editable||busy;path.readOnly=!!editor?.meta;area.disabled=!editable||busy;
   empty.hidden=!!editor;pathLabel.hidden=textLabel.hidden=buttons.hidden=detail.hidden=!editor;
   textLabel.hidden=!editor||editor.text===null;
   save.textContent=editor?.meta?'Save changes':'Create file';
   let bytes=0,valid=editable;
   if(editable){try{bytes=core.encodeText(area.value,client.caps?.maxFileBytes||8192).length;core.path(path.value);}catch{valid=false;}}
   save.disabled=busy||!editable||!valid||client.uncertain||(!!editor?.meta&&!dirty());
   download.disabled=busy||!editor?.meta;
   if(editor)detail.textContent=editor.text===null?`Binary file · ${editor.bytes.length} bytes · download to inspect.`:
    `${bytes} / ${client.caps?.maxFileBytes||8192} UTF-8 bytes${dirty()?' · unsaved changes':''}${valid?'':' · check path/text limits'}`;
   if(fixtureButton)fixtureButton.disabled=busy||connectionState!=='disconnected';
   for(const b of list.querySelectorAll('button'))b.disabled=busy;
  }
  function clearEditor(){if(editor?.bytes)editor.bytes.fill(0);editor=null;area.value='';path.value='';controls();}
  function guard(action){
   if(client.busy){message('Cancel the current operation before leaving.',true);return;}
   if(dirty()){pendingDiscard=action;confirm.hidden=false;keep.focus();}else action();
  }
  discard.onclick=()=>{const action=pendingDiscard;pendingDiscard=null;confirm.hidden=true;if(action)action();};
  keep.onclick=()=>{pendingDiscard=null;confirm.hidden=true;area.focus();};
  async function task(action){
   const epoch=uiEpoch,context={client,ensure(){if(epoch!==uiEpoch)throw new core.StorageError('DISCONNECTED');}};
   try{const pending=action(context);controls();await pending;}
   catch(e){if(epoch===uiEpoch)message(e instanceof core.StorageError?e.message:'The file operation failed.',true);}
   finally{if(epoch===uiEpoch)controls();}
  }
  function renderList(){
   list.replaceChildren();
   if(!snapshot){list.append(el('p','No file connection.','files-empty'));return;}
   const {caps,list:state}=snapshot;
   capacity.textContent=`RAM: ${state.used.toLocaleString()} / ${state.capacity.toLocaleString()} bytes · ${state.freeSlots} of ${caps.maxFiles} file slots free · ${caps.maxFileBytes.toLocaleString()} bytes per file. ${mode==='fixture'?'Samples disappear when this page closes.':'Lost on reboot.'}`;
   if(!state.files.length){list.append(el('p','RAM is empty.','files-empty'));return;}
   for(const file of state.files){
    const button=el('button');button.type='button';button.className='files-row';button.setAttribute('aria-label','Open '+file.path);button.setAttribute('aria-pressed',String(editor?.meta?.path===file.path));
    button.append(el('span',file.path),el('small',`${file.bytes.toLocaleString()} bytes`));
    button.onclick=()=>guard(()=>task(async context=>{
     const opened=await context.client.read(file.path);context.ensure();let text=null;
     try{text=core.decodeText(opened.bytes);}catch{}
     clearEditor();editor={...opened,text,baseline:text,initialPath:opened.meta.path};path.value=opened.meta.path;area.value=text||'';
     renderList();message(text===null?'Binary content is available as a download.':'Opened file. Changes stay in the editor until saved.');controls();if(text!==null)area.focus();
    }));list.append(button);
   }
  }
  async function refreshFiles(context){const next=await context.client.refresh();context.ensure();snapshot=next;renderList();message(client.uncertain?'A write result is uncertain. Reconnect before another change.':'File list refreshed.');}
  entry.onclick=()=>{entry.closest('details')?.removeAttribute('open');dialog.showModal();controls();};
  const leave=()=>{clearEditor();dialog.close();entry.closest('details')?.querySelector('summary')?.focus();};
  close.onclick=()=>guard(leave);dialog.addEventListener('cancel',event=>{event.preventDefault();guard(leave);});
  refresh.onclick=()=>task(refreshFiles);
  create.onclick=()=>guard(()=>{clearEditor();editor={meta:null,bytes:null,text:'',baseline:'',initialPath:'/RAM/'};path.value='/RAM/';area.value='';message('Choose a /RAM/ path. Create file will refuse to overwrite an existing file.');controls();path.focus();});
  area.addEventListener('input',controls);path.addEventListener('input',controls);
  cancel.onclick=()=>{client.cancel();message('Cancellation requested. Waiting for the transfer to settle.');};
  save.onclick=()=>task(async context=>{
   const value=path.value,data=core.encodeText(area.value,context.client.caps.maxFileBytes),expected=editor.meta?.revision||null;
   const meta=await context.client.save(value,data,expected);context.ensure();
   if(editor.bytes)editor.bytes.fill(0);editor={meta,bytes:data,text:area.value,baseline:area.value,initialPath:value};
   await refreshFiles(context);message(mode==='fixture'?'Saved in browser fixture memory only.':'Saved on the connected device.');
  });
  download.onclick=()=>{
   try{
    const item=core.download(editor.meta.path,editor.bytes),url=URL.createObjectURL(new Blob([item.bytes],{type:item.type}));
    const link=el('a');link.href=url;link.download=item.name;link.rel='noopener';link.hidden=true;dialog.append(link);link.click();link.remove();
    const timer=setTimeout(()=>{URL.revokeObjectURL(url);urls.delete(url);},1000);urls.set(url,timer);
    message(mode==='fixture'?'Download requested for the synthetic fixture file.':'Download requested for the loaded file version.');
   }catch(e){message(e instanceof core.StorageError?e.message:'Download failed.',true);}
  };
  function bind(next,nextMode){
   uiEpoch++;client.cancel();transport?.close?.();transport=next;client=new core.Client(next);mode=nextMode;
   clearEditor();snapshot=null;pendingDiscard=null;confirm.hidden=true;
   for(const [url,timer] of urls){clearTimeout(timer);URL.revokeObjectURL(url);}urls.clear();
   capacity.textContent='No file capacity has been read for this connection.';renderList();controls();
  }
  if(fixtureButton)fixtureButton.onclick=()=>guard(()=>{
   bind(window.MicroBlocksFilesFixture.create(),'fixture');
   banner.textContent='Browser fixture — not the board';banner.dataset.fixture='true';fixtureButton.textContent='Reset sample files';
   void task(async context=>{await refreshFiles(context);message('Synthetic samples loaded into browser memory. No device or host files were accessed.');});
  });
  connectFiles.onclick=()=>guard(()=>{
   const operation=connectionState==='ready'?connection.close():connection.open();
   const linkEpoch=connection.epoch;
   void operation.catch(e=>{if(connection.epoch===linkEpoch)message(e instanceof core.StorageError?e.message:'File connection failed.',true);});
  });
  const unsubscribe=connection?.subscribe(state=>{
   connectionState=state.state;bind(state.transport,state.transport?'device':'disconnected');banner.dataset.fixture='false';
   const labels={disconnected:'Connect your board, then Connect files. Compatible storage firmware is required.',available:'Board connection ready. Select Connect files to access its RAM.',connecting:'Checking file support on the connected board…',ready:'Connected device RAM — temporary; files are lost on reboot.',closing:'Closing the file session…',error:'File connection failed. Compatible storage firmware is required; check the message below.'};
   banner.textContent=labels[state.state];message(state.error?new core.StorageError(state.error).message:'File session '+state.state+'.',!!state.error);
   if(state.transport)void task(refreshFiles);controls();
  });
  window.addEventListener('pagehide',()=>{
   unsubscribe?.();bind(null,'disconnected');
  });
  renderList();controls();
 }));
})();
