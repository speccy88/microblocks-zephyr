// SPDX-License-Identifier: MPL-2.0
// Pi native release workflow. Other boards keep their existing USB guard.
(function(root){
    'use strict';
    const MAX=64*1024*1024,installed=new WeakSet();
    const compatible=version=>version===417;
    function installVersionPolicy(Connection,notify){
        if(installed.has(Connection))return;
        if(typeof Connection?.prototype?.checkVmVersion!=='function')throw Error('Review changed VM version hook');
        Connection.prototype.checkVmVersion=async function(){
            if(this.vmVersion==null)return false;
            if(!compatible(this.vmVersion)){notify('Version native v'+this.vmVersion+' non validée pour ce port Pi. Version validée : v417.');if(typeof this.disconnect==='function')this.disconnect();}
            return false;
        };
        installed.add(Connection);
    }
    function digest(value){const result=String(value).trim().toLowerCase();if(!/^[a-f0-9]{64}$/.test(result))throw Error('Saisissez le SHA-256 de 64 caractères fourni avec le paquet.');return result;}
    class Client{
        constructor(location,Socket){this.location=new URL(location.href);this.Socket=Socket;}
        async operation(command,file,progress=()=>{}){
            const url=new URL('/ws/update',this.location);url.protocol=this.location.protocol==='https:'?'wss:':'ws:';
            if(this.location.protocol!=='http:'||url.origin.replace('ws:','http:')!==this.location.origin)throw Error('Ouvrez les mises à jour depuis le site local du Pi.');
            return new Promise((resolve,reject)=>{
                const socket=this.socket=new this.Socket(url.href);let done=false;
                const timer=setTimeout(()=>finish(Error('Délai de mise à jour dépassé. Le SmallVM précédent est conservé.')),120000);
                const finish=(error,value)=>{if(done)return;done=true;clearTimeout(timer);if(socket.readyState<2)socket.close();error?reject(error):resolve(value);};
                socket.onopen=()=>socket.send(JSON.stringify(command));
                socket.onmessage=event=>{
                    let value;try{value=JSON.parse(event.data);}catch{finish(Error('Réponse de mise à jour invalide.'));return;}
                    progress(value);
                    if(value.state==='error')finish(Error(value.error));
                    else if(value.state==='prepared'||value.state==='restarting')finish(null,value);
                    else if(value.state==='uploading'&&value.received===0&&file){
                        const selected=file;file=null;
                        (async()=>{for(let offset=0;offset<selected.size;offset+=4096){
                            while(socket.bufferedAmount>32768&&!done)await new Promise(r=>setTimeout(r,20));
                            if(done||socket.readyState!==1)throw Error('Envoi interrompu; reconnectez-vous et réessayez.');
                            socket.send(await selected.slice(offset,offset+4096).arrayBuffer());
                        }socket.send(JSON.stringify({action:'finish'}));})().catch(error=>finish(error));
                    }
                };
                socket.onerror=()=>finish(Error('Connexion de mise à jour impossible. Le SmallVM précédent est conservé.'));
                socket.onclose=()=>{if(!done)finish(Error('Envoi interrompu. Gardez cette page au premier plan et réessayez.'));};
            });
        }
        upload(file,sha,progress){if(!file||!Number.isInteger(file.size)||file.size<64||file.size>MAX)throw Error('Choisissez un paquet Linux ARM64 .tar.gz de moins de 64 Mio.');return this.operation({action:'upload',size:file.size,sha256:digest(sha)},file,progress);}
        apply(review,progress){return this.operation({action:'apply',sha256:review.sha256,version:review.version,confirmed:true},null,progress);}
        close(){if(this.socket?.readyState<2)this.socket.close();}
    }
    const api={Client,compatible,installVersionPolicy,digest,MAX};
    if(typeof module==='object'&&module.exports){module.exports=api;return;}
    let dialog,review,currentStatus,keyboardBefore=false;
    const client=new Client(location,root.WebSocket);
    const config=JSON.parse(document.getElementById('mobile-load-config').textContent).profile;
    if(config.board!=='pi5'||config.local_pi!=='open-http-v1')return;
    const $=id=>document.getElementById(id);
    const status=text=>{$('pi-update-status').textContent=text;};
    async function refresh(){
        const response=await fetch('/api/pi/update',{cache:'no-store'});
        if(!response.ok)throw Error('Le gestionnaire de mise à jour du Pi est indisponible.');
        currentStatus=await response.json();
        $('pi-update-version').textContent='SmallVM installé : v'+currentStatus.current_vm_version+' · Version validée pour le Pi : v417.';
        $('pi-update-check').disabled=!currentStatus.upload_enabled;
        $('pi-update-policy').textContent=currentStatus.native_install_enabled?
            'Un paquet Linux ARM64 vérifié et votre confirmation sont nécessaires. Les programmes seront conservés.':
            'La vérification du paquet est disponible. L’installation native doit être autorisée avant activation.';
        const update=currentStatus.update||{};
        if(update.state==='rolled_back'||update.state==='failed')status(update.error||'Échec de mise à jour; la version précédente est conservée.');
        if(update.state==='prepared'){review=update;showReview(update);}
        return currentStatus;
    }
    function showReview(value){
        $('pi-update-review').textContent='Version du paquet : '+value.version+' · SmallVM v'+value.vm_version+' · '+value.architecture+'\nSHA-256 : '+value.sha256;
        $('pi-update-install').disabled=!(currentStatus?.native_install_enabled&&review);
        status('Paquet vérifié. Aucune installation n’a encore été effectuée.');
    }
    function progress(value){
        const labels={checking_archive:'Vérification du paquet…',validating_native:'Validation native et auto-test…',preserving_program:'Conservation du programme…',restarting:'Redémarrage du SmallVM…'};
        if(value.state==='uploading'){$('pi-update-progress').value=value.received;$('pi-update-progress').max=value.total;status('Envoi : '+Math.round(100*value.received/value.total)+' %');}
        else if(labels[value.state])status(labels[value.state]);
    }
    function create(){
        if(dialog)return;
        dialog=document.createElement('dialog');dialog.id='pi-update-dialog';dialog.className='pi-update-dialog';
        dialog.innerHTML='<button type="button" id="pi-update-close">Fermer</button><h2>Mise à jour du SmallVM du Pi</h2>'+
            '<p id="pi-update-version"></p><p>La version amont de l’éditeur peut être v421. Elle ne constitue pas une version Linux ARM64 validée pour ce port.</p>'+
            '<p id="pi-update-policy"></p><label for="pi-update-file">Paquet natif Linux ARM64 (.tar.gz)</label><input id="pi-update-file" type="file" accept=".tar.gz,.tgz,application/gzip">'+
            '<label for="pi-update-sha">SHA-256 fourni avec la version</label><input id="pi-update-sha" type="text" inputmode="text" autocomplete="off" autocapitalize="off" spellcheck="false" maxlength="64">'+
            '<button id="pi-update-check" type="button">Vérifier le paquet</button><progress id="pi-update-progress" value="0" max="100"></progress>'+
            '<p id="pi-update-status" role="status" aria-live="polite"></p><p id="pi-update-review"></p><button id="pi-update-install" type="button" disabled>Installer cette version</button>';
        document.body.append(dialog);
        $('pi-update-close').onclick=()=>dialog.close();
        dialog.addEventListener('focusin',()=>{GP.delegateKeyboardEvents=true;});
        dialog.addEventListener('close',()=>{GP.delegateKeyboardEvents=keyboardBefore;client.close();});
        $('pi-update-check').onclick=async()=>{
            try{$('pi-update-check').disabled=true;$('pi-update-install').disabled=true;review=null;
                review=await client.upload($('pi-update-file').files[0],$('pi-update-sha').value,progress);showReview(review);
            }catch(error){status(error.message);}finally{$('pi-update-check').disabled=!currentStatus?.upload_enabled;}
        };
        $('pi-update-install').onclick=async()=>{
            if(!review||!root.confirm('Installer le SmallVM natif '+review.version+' sur ce Pi et le redémarrer en conservant les programmes ?\nSHA-256 : '+review.sha256))return;
            try{$('pi-update-install').disabled=true;MB_connection.disconnect();await new Promise(r=>setTimeout(r,300));
                await client.apply(review,progress);
                for(let tries=0;tries<60;tries++){
                    await new Promise(r=>setTimeout(r,500));
                    try{const value=await refresh();if(value.update?.state==='complete'){status('Mise à jour terminée. Reconnectez l’éditeur au Pi.');return;}
                        if(['failed','rolled_back'].includes(value.update?.state))return;
                    }catch{status('Redémarrage du SmallVM…');}
                }
                status('Le redémarrage prend plus de temps que prévu. Actualisez pour consulter le résultat.');
            }catch(error){status(error.message);}
        };
    }
    async function open(){create();keyboardBefore=GP.delegateKeyboardEvents;GP.delegateKeyboardEvents=true;dialog.showModal();status('Lecture de l’état du Pi…');try{await refresh();}catch(error){status(error.message);}}
    root.MicroBlocksPiUpdates={...api,open};
    installVersionPolicy(MB_Connection,text=>MB_editor.inform(text,'SmallVM du Pi'));
    const attach=()=>{const menu=$('iphone-menu-panel');const save=$('iphone-save');if(!save||$('pi-update-open'))return;
        const button=document.createElement('button');button.type='button';button.id='pi-update-open';button.textContent='Mises à jour du Pi';button.onclick=open;save.after(button);};
    new MutationObserver(attach).observe(document.body,{subtree:true,childList:true});attach();
})(globalThis);
