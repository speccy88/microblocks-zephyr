/* SPDX-License-Identifier: MIT */
((root)=>{
 'use strict';
 function mount({dialog,report,changed}) {
  const core=root.MicroBlocksFiles,SD=root.MicroBlocksSDFiles;
  const el=(tag,text,cls)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(cls)node.className=cls;return node;};
  const panel=el('section',undefined,'files-sd');panel.hidden=true;dialog.append(panel);
  panel.append(el('p','SD files stay on the card, inside MBFILES. This first version creates new files; it never replaces an existing name. Up to 8 KiB per file, uppercase 8.3 names.','files-banner'));
  const tools=el('div',undefined,'files-toolbar'),refresh=el('button','Refresh SD'),create=el('button','New SD text file');
  refresh.type=create.type='button';tools.append(refresh,create);panel.append(tools);
  const summary=el('p','Select SD to check firmware support.','files-capacity');panel.append(summary);
  const layout=el('div',undefined,'files-layout'),list=el('div',undefined,'files-list');list.setAttribute('aria-label','Files in SD MBFILES');
  const form=el('section',undefined,'files-editor'),pathLabel=el('label','Filename in MBFILES'),path=el('input');
  path.type='text';path.maxLength=12;path.placeholder='NOTE.TXT';path.setAttribute('aria-label','SD filename');pathLabel.append(path);
  const textLabel=el('label','Text'),area=el('textarea');area.rows=9;area.maxLength=8192;area.spellcheck=false;area.setAttribute('aria-label','SD file text');textLabel.append(area);
  const detail=el('p','','files-detail'),actions=el('div',undefined,'files-actions'),save=el('button','Save as new SD file'),remove=el('button','Remove file created here');
  save.type=remove.type='button';save.className='files-primary';actions.append(save,remove);form.append(pathLabel,textLabel,detail,actions);layout.append(list,form);panel.append(layout);
  const confirmation=el('div',undefined,'files-confirm'),question=el('p'),yes=el('button','Confirm remove'),no=el('button','Keep file');
  yes.type=no.type='button';confirmation.append(question,yes,no);confirmation.hidden=true;panel.append(confirmation);
  let client=null,sd=null,mode='disconnected',busy=false,epoch=0,supported=false,opened=null,baseline='',detached=false;
  const dirty=()=>!!opened&&(detached||area.value!==baseline||path.value!==opened.name);
  function controls(){
   refresh.disabled=busy||!client?.transport;create.disabled=busy||!supported||client?.uncertain;
   path.disabled=area.disabled=busy||!opened;pathLabel.hidden=textLabel.hidden=actions.hidden=detail.hidden=!opened;
   let valid=false,bytes=0;
   try{bytes=core.encodeText(area.value).length;valid=SD.validName(path.value);}catch{}
   save.disabled=busy||!supported||!opened||!valid||detached||client?.uncertain||!!sd?.ownNames.has(path.value);
   remove.disabled=busy||!supported||!opened||!sd?.ownNames.has(opened.name)||client?.uncertain||dirty();
   if(opened){
    textLabel.hidden=opened.binary;
    detail.textContent=opened.binary?`${opened.bytes.length} binary bytes opened. Text editing is unavailable.`:
     `${bytes} / 8,192 UTF-8 bytes. Save under a new name; the source remains unchanged.`;
    if(detached)detail.textContent+=' Draft retained after disconnect; reopen or create a new draft before saving.';
    if(opened.binary)save.disabled=true;
   }
   for(const button of list.querySelectorAll('button'))button.disabled=busy||button.dataset.oversize==='true';
  }
  async function task(action){
   if(busy){report('Wait for the current SD operation.',true);return;}
   const before=epoch,requestSD=sd,ensure=()=>{if(before!==epoch)throw new core.StorageError('DISCONNECTED');};busy=true;changed();controls();
   try{await action(requestSD,ensure);}
   catch(error){if(before===epoch)report(error instanceof core.StorageError?error.message:'The SD operation failed.',true);}
   finally{if(before===epoch){busy=false;changed();controls();}}
  }
  async function showList(requestSD,ensure){
   const value=await requestSD.list();ensure();list.replaceChildren();
   summary.textContent=`MBFILES: ${value.files.length} file${value.files.length===1?'':'s'} shown${value.truncated?' (list limited)':''}. This is not the card’s free-space reading. Files survive reboot.`;
   if(!value.files.length)list.append(el('p','No files in MBFILES yet. Existing files elsewhere on the card are untouched.','files-empty'));
   for(const file of value.files){
    const button=el('button');button.type='button';button.className='files-row';button.dataset.oversize=String(file.bytes>8192);
    button.setAttribute('aria-label','Open SD '+file.name);button.append(el('span',file.name),el('small',`${file.bytes.toLocaleString()} bytes${file.bytes>8192?' — larger than this editor limit':''}`));
    button.onclick=()=>{
     if(dirty()){report('Keep your SD draft or save it under a new name before opening another file.',true);return;}
     void task(async(requestSD,ensure)=>{
      const result=await requestSD.read(file.name);ensure();let text=null;try{text=core.decodeText(result.bytes);}catch{}
      opened={...result,binary:text===null};baseline=text||'';area.value=baseline;path.value=result.name;detached=false;
      report('Opened and closed the SD file. Save as new preserves this source.');
     });
    };list.append(button);
   }
  }
  function clear(){if(opened?.bytes)opened.bytes.fill(0);opened=null;baseline='';area.value='';path.value='';detached=false;confirmation.hidden=true;controls();}
  refresh.onclick=()=>{void task(async(requestSD,ensure)=>{const available=await requestSD.available();ensure();if(!available){supported=false;summary.textContent='SD file operations are unavailable in this firmware.';return;}supported=true;await showList(requestSD,ensure);report('SD list refreshed; no files were changed.');});};
  create.onclick=()=>{
   if(dirty()){report('Keep or save the current SD draft first.',true);return;}
   clear();opened={name:'',bytes:new Uint8Array(),binary:false};path.value='';area.value='';report('Choose a new uppercase 8.3 name. Existing names are refused.');controls();path.focus();
  };
  save.onclick=()=>{void task(async(requestSD,ensure)=>{
   const result=await requestSD.create(path.value,core.encodeText(area.value));ensure();if(opened?.bytes)opened.bytes.fill(0);
   opened={...result,binary:false};baseline=area.value;detached=false;await showList(requestSD,ensure);report('SD file created, synced, closed, reopened and verified byte for byte.');
  });};
  remove.onclick=()=>{question.textContent=`Remove ${opened.name}? Only a file created successfully during this firmware session can be removed, after its current bytes are verified.`;confirmation.hidden=false;yes.focus();};
  no.onclick=()=>{confirmation.hidden=true;};
  yes.onclick=()=>{confirmation.hidden=true;void task(async(requestSD,ensure)=>{await requestSD.removeOwn(opened.name);ensure();clear();await showList(requestSD,ensure);report('Removed only the selected file created here.');});};
  path.addEventListener('input',controls);area.addEventListener('input',controls);
  return {
   get busy(){return busy;},dirty,clear,
   bind(next,nextMode){
    epoch++;busy=false;if(dirty())detached=true;else clear();
    client=next;sd=new SD.Client(next);mode=nextMode;supported=false;list.replaceChildren();summary.textContent='Select SD to check firmware support.';controls();
   },
   select(value){panel.hidden=value!=='SD';if(value==='SD'&&mode==='device')refresh.onclick();},controls
  };
 }
 root.MicroBlocksSDUI={mount};
})(typeof window==='object'?window:globalThis);
