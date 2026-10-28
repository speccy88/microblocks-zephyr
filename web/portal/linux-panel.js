/* SPDX-License-Identifier: MIT */
/* Explicit terminal handoff only. This panel never executes SSH or probes LAN. */
(function(root){
 'use strict';
 const core=root.MicroBlocksLinux||(typeof require==='function'?require('./linux-core.js'):null);
 let nextPanel=0;
 function mount(container,options={}){
  if(!core)throw Error('Load linux-core.js before linux-panel.js.');
  if(!container?.ownerDocument)throw Error('A portal container is required.');
  const document=container.ownerDocument,prefix='linux-install-'+(++nextPanel);
  let profile=options.profile||'raspberry-pi5',release=options.releaseManifest||{schemaVersion:1,available:false},commands=null,copyPending=false;
  core.profileInfo(profile);
  const make=(tag,className,text)=>{const element=document.createElement(tag);if(className)element.className=className;if(text!==undefined)element.textContent=text;return element;};
  const panel=make('article','connection-card hosted linux-install-panel');panel.setAttribute('aria-label','Linux ARM64 installation');
  const eyebrow=make('p','eyebrow','LINUX ARM64'),title=make('h3'),hardware=make('p'),validation=make('p','tag linux-validation');
  const releaseStatus=make('p','linux-release-status');releaseStatus.setAttribute('role','status');
  const releaseLink=make('a','linux-release-link','Review the pinned GitHub Release');releaseLink.target='_blank';releaseLink.rel='noopener noreferrer';releaseLink.hidden=true;
  const docs=make('nav','linux-docs');docs.setAttribute('aria-label','Linux board documentation');
  const form=make('form','linux-install-form');form.addEventListener('submit',event=>event.preventDefault());
  function field(text,name,placeholder){
   const label=make('label','linux-install-field',text),input=make('input');
   input.type='text';input.name=name;input.id=prefix+'-'+name;input.autocomplete='off';input.spellcheck=false;input.placeholder=placeholder;
   label.htmlFor=input.id;label.append(input);form.append(label);return input;
  }
  const username=field('SSH username','username','Your Linux account'),host=field('Board IP address or hostname','host','');
  username.maxLength=32;host.maxLength=253;
  const terminalLabel=make('label','linux-install-field','Terminal'),terminal=make('select');terminal.id=prefix+'-terminal';terminalLabel.htmlFor=terminal.id;
  for(const [value,text] of [['powershell','Windows PowerShell'],['posix','macOS / Linux terminal']]){const option=make('option','',text);option.value=value;terminal.append(option);}
  terminalLabel.append(terminal);form.append(terminalLabel);
  const serviceLabel=make('label','linux-service-choice'),service=make('input');service.type='checkbox';service.id=prefix+'-service';service.checked=false;
  serviceLabel.htmlFor=service.id;serviceLabel.append(service,make('span','',' Start SmallVM as an optional user systemd service'));
  form.append(serviceLabel,make('p','linux-service-note','The service belongs to your Linux account. Startup before login is not enabled by this command.'));
  const commandLabel=make('label','linux-install-field','Reviewed installation command'),command=make('textarea','linux-install-command');
  command.id=prefix+'-command';command.rows=5;command.readOnly=true;command.spellcheck=false;commandLabel.htmlFor=command.id;commandLabel.append(command);
  const copy=make('button','','Copy installation command');copy.type='button';copy.disabled=true;
  const actions=make('div','board-picker linux-install-actions');actions.append(copy);
  const status=make('p','linux-command-status');status.setAttribute('role','status');status.setAttribute('aria-live','polite');
  const details=make('details','linux-script-review'),summary=make('summary','','Review the decoded script'),pre=make('pre'),script=make('code');pre.append(script);details.append(summary,pre);
  const handoff=make('p','linux-handoff','Paste the command into your own terminal. SSH requires a saved, verified matching host key and handles password entry itself. This page never requests SSH credentials.');
  const network=make('p','linux-network-note','The HTTPS portal cannot probe SSH or the local PTY. Graphical network access needs a separately configured trusted WSS bridge or an appropriate board-local editor. No insecure fallback is used.');
  const editorLink=make('a','linux-editor-link','Open graphical editor (editing available)');
  editorLink.addEventListener('click',event=>{
   if(typeof options.onOpenEditor!=='function')return;
   event.preventDefault();
   Promise.resolve(options.onOpenEditor({profile,endpoint:null})).catch(error=>{status.textContent=error.message||'The editor could not be opened.';});
  });
  const endpointLabel=make('label','linux-install-field','Optional trusted WSS bridge endpoint'),endpoint=make('input');endpoint.type='url';endpoint.id=prefix+'-wss';endpoint.autocomplete='off';endpoint.placeholder='wss://board.example/ws/vm';endpoint.maxLength=512;endpointLabel.htmlFor=endpoint.id;endpointLabel.append(endpoint);
  const endpointButton=make('button','','Use endpoint for the editor');endpointButton.type='button';endpointButton.disabled=true;
  const endpointActions=make('div','board-picker linux-endpoint-actions');endpointActions.append(endpointButton);
  const endpointStatus=make('p','linux-endpoint-status');endpointStatus.setAttribute('role','status');
  panel.append(eyebrow,title,hardware,validation,releaseStatus,releaseLink,docs,form,commandLabel,actions,status,details,handoff,network,editorLink,endpointLabel,endpointActions,endpointStatus);
  container.append(panel);

  function refreshCommand(){
   commands=null;command.value='';script.textContent='No install script is offered until a reviewed release is available.';releaseLink.hidden=true;
   const placeholder=core.profileInfo(profile).placeholder===true;
   for(const field of [username,host,terminal,service,endpoint])field.disabled=placeholder;
   endpointButton.disabled=placeholder||!endpoint.value;
   editorLink.textContent=placeholder?'Open placeholder editor (editing only)':'Open graphical editor (editing available)';
   if(placeholder){
    service.checked=false;copy.disabled=true;
    releaseStatus.textContent='Experimental placeholder: no verified MicroDuck installation is available.';
    status.textContent='MicroDuck Rockchip RK3566 hardware and OS/service acceptance are pending.';
    script.textContent='No installation command is offered for this placeholder.';
    return;
   }
   try{
    const pinned=core.validateReleaseManifest(release);
    releaseStatus.textContent='Pinned release: '+pinned.version+'. Installer and binary archive SHA-256 values are fixed by the release manifest.';
    releaseLink.href=pinned.releaseURL;releaseLink.hidden=false;
    script.textContent=core.remoteInstallScript(pinned,{service:service.checked});
    if(!username.value||!host.value){status.textContent='Enter the SSH username and board address to prepare the command.';}
    else{
     commands=core.generateInstallCommands({profile,username:username.value,host:host.value,release:pinned,service:service.checked});
     command.value=commands[terminal.value];status.textContent='Review the decoded script, then copy and run the command in your terminal.';
    }
   }catch(error){
    if(error instanceof core.ReleaseUnavailableError){releaseStatus.textContent=error.message;status.textContent='Installation command unavailable until a reviewed release is published.';}
    else{status.textContent=error.message;releaseStatus.textContent=release?.available===true?'A release manifest was supplied; correct the fields or manifest before copying.':'No reviewed ARM64 release is available.';}
   }
   copy.disabled=!commands||copyPending;
  }
  function setProfile(id,{preserveTarget=false}={}){
   const info=core.profileInfo(id),changed=id!==profile;profile=id;
   title.textContent=info.name;hardware.textContent=info.hardware;validation.textContent=info.validation;validation.dataset.validationKind=info.validationKind;
   host.placeholder=info.hostPlaceholder;editorLink.href=info.editorPath;
   docs.replaceChildren();
   for(const item of info.docs){const link=make('a','',item.label);link.href='https://github.com/'+core.REPOSITORY+'/blob/'+core.DOCUMENTATION_REF+'/'+item.path;link.target='_blank';link.rel='noopener noreferrer';docs.append(link,make('span','',' '));}
   if(changed&&!preserveTarget){username.value='';host.value='';endpoint.value='';endpointButton.disabled=true;endpointStatus.textContent='';}
   refreshCommand();
  }
  for(const input of [username,host,terminal,service])input.addEventListener('input',refreshCommand);
  copy.addEventListener('click',async()=>{
   if(!commands||copyPending)return;
   const snapshot=commands,text=snapshot[terminal.value],clipboard=options.clipboard||root.navigator?.clipboard;
   if(typeof clipboard?.writeText!=='function'){status.textContent='Clipboard access is unavailable. Select the reviewed command and copy it manually.';return;}
   copyPending=true;copy.disabled=true;
   try{await clipboard.writeText(text);status.textContent=commands===snapshot?'Installation command copied. Run it in your terminal; no SSH connection was made by this page.':'The previous reviewed command was copied; the fields have since changed.';}
   catch{status.textContent='The browser did not allow copying. Select the reviewed command and copy it manually.';}
   finally{copyPending=false;copy.disabled=!commands;}
  });
  endpoint.addEventListener('input',()=>{endpointButton.disabled=core.profileInfo(profile).placeholder===true||!endpoint.value;endpointStatus.textContent='';});
  endpointButton.addEventListener('click',async()=>{
   try{
    if(core.profileInfo(profile).placeholder)throw Error('This experimental placeholder has no live hardware connection.');
    const url=core.validateWSSEndpoint(endpoint.value);
    if(typeof options.onEndpoint==='function')await options.onEndpoint({profile,endpoint:url});
    else if(typeof root.CustomEvent==='function')panel.dispatchEvent(new root.CustomEvent('microblocks-linux-endpoint',{bubbles:true,detail:{profile,endpoint:url}}));
    else throw Error('This browser cannot pass the endpoint to the editor.');
    endpointStatus.textContent='Endpoint selected for explicit Connect in the editor. Reachability and certificate trust have not been tested by this page.';
   }catch(error){endpointStatus.textContent=error.message||'The endpoint could not be selected.';}
  });
  if(typeof options.username==='string')username.value=options.username;
  if(typeof options.host==='string')host.value=options.host;
  setProfile(profile,{preserveTarget:true});
  return Object.freeze({element:panel,setProfile,setReleaseManifest(value){release=value;refreshCommand();},destroy(){panel.remove();}});
 }
 const api=Object.freeze({mount});root.MicroBlocksLinuxPanel=api;if(typeof module!=='undefined'&&module.exports)module.exports=api;
})(typeof window==='undefined'?globalThis:window);
