// SPDX-License-Identifier: MIT
(() => {
    'use strict';
    const el=id=>document.getElementById(id), L=P2WebLoader;
    const status=message=>{el('status').textContent=message;};
    const available=!!navigator.serial&&isSecureContext;
    let port=null,busy=false,vmRunning=false,controller=null,committed=false;
    const destination=()=>document.querySelector('input[name="destination"]:checked')?.value;
    function refresh(){
        el('check').disabled=!available||busy;
        el('module').disabled=busy;
        for(const radio of document.querySelectorAll('input[name="destination"]'))radio.disabled=busy;
        el('acknowledge').disabled=busy;
        el('install').disabled=!available||busy||!port||vmRunning||!el('module').value||!destination()||!el('acknowledge').checked;
        el('cancel').disabled=!busy||committed;
        el('boot-note').hidden=destination()!=='flash';
    }
    status(available?'Choose your P2 USB adapter to check whether SmallVM is already running.':'Web Serial is unavailable. Use desktop Chrome or Edge on this HTTPS page.');
    el('installation').addEventListener('change',refresh);
    el('check').onclick=async()=>{
        if(busy||!available)return;
        busy=true;committed=true;refresh();el('open-editor').hidden=true;
        let link;
        try{
            port=await navigator.serial.requestPort({filters:[{usbVendorId:0x0403}]});
            link=new L.BrowserLink(port);await link.open(115200);
            const version=await L.probeVM(link);
            if(version&&!/^v\d+ Parallax P2 /.test(version)){port=null;throw Error('A different MicroBlocks board answered. Choose the P2 adapter.');}
            vmRunning=!!version;
            if(version){status(version+' is already running. Installation is not needed.');el('open-editor').hidden=false;}
            else status('No SmallVM response. Choose the exact module and destination; installation will verify the P2 ROM before transferring firmware.');
        }catch(error){port=null;status(error.name==='NotFoundError'?'USB selection cancelled.':error.message);}
        finally{if(link)await link.close().catch(error=>status(error.message));busy=false;committed=false;refresh();}
    };
    el('installation').onsubmit=async event=>{
        event.preventDefault();if(el('install').disabled)return;
        const chosen=port,board=el('module').value,mode=destination();
        busy=true;committed=false;controller=new AbortController();el('progress').value=0;refresh();
        try{
            status('Checking the selected firmware build…');
            const metaResponse=await fetch('firmware.json',{cache:'no-cache'});if(!metaResponse.ok)throw Error('Firmware manifest is unavailable');
            const manifest=await metaResponse.json(),entry=manifest.images[board];
            if(!entry||!/^vm_propeller2_(eval|edge|edge32)\.bin$/.test(entry.file))throw Error('Invalid P2 firmware entry');
            const get=async file=>{const response=await fetch(file);if(!response.ok)throw Error('Firmware download failed: '+response.status);return new Uint8Array(await response.arrayBuffer());};
            const image=await get(entry.file),stub=mode==='flash'?await get('flash-loader.bin'):new Uint8Array();
            const result=await L.install(new L.BrowserLink(chosen),image,stub,manifest,board,mode,{
                signal:controller.signal,
                progress:update=>{
                    if(update.committed){committed=true;refresh();}
                    if(update.phase==='transfer'){const percent=Math.floor(100*update.sent/update.total);el('progress').value=percent;status('Transferring to P2: '+percent+'%');}
                    else status({identify:'Identifying the P2 ROM…',programming:'Programming flash. Keep the board powered and connected.',verify:'Verifying the running VM identity…',boot:'Resetting and verifying boot from flash…'}[update.phase]||'Installing…');
                }
            });
            vmRunning=true;el('open-editor').hidden=false;
            status(result.already_running?result.version+' is already running; no firmware was transferred.':
                result.version+(result.flash_boot_verified?' installed and verified after flash boot.':' loaded to RAM; ROM checksum and running identity verified.'));
        }catch(error){status((error.name==='AbortError'?'Transfer cancelled.':error.message)+(error.flash_programming_started?' Flash programming may have started; its boot result is unverified.':''));}
        finally{busy=false;controller=null;refresh();}
    };
    el('cancel').onclick=()=>{if(controller&&!committed)controller.abort();};
    refresh();
})();
