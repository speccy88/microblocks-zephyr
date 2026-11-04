// SPDX-License-Identifier: MIT
// P2 ROM single-stage serial loader. Hex/flash protocol adapted from MIT loadp2 at
// c20afedd4253d09da449fa740f8d4304481fc560; see third_party/loadp2/LICENSE.
(function(root){
    'use strict';
    const text=new TextEncoder(), decode=new TextDecoder();
    const boards=Object.freeze({eval:'Parallax P2 Eval Rev C',edge:'Parallax P2 Edge',edge32:'Parallax P2 Edge 32MB'});
    const pause=ms=>new Promise(resolve=>setTimeout(resolve,ms));
    const abort=signal=>{if(signal?.aborted){const e=Error('Installation cancelled');e.name='AbortError';throw e;}};
    async function sha256(bytes){
        const hash=await root.crypto.subtle.digest('SHA-256',bytes);
        return Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
    }
    function sumWords(bytes){
        if(!(bytes instanceof Uint8Array)||bytes.length%4)throw Error('P2 image must contain complete 32-bit words');
        const view=new DataView(bytes.buffer,bytes.byteOffset,bytes.byteLength);let sum=0;
        for(let p=0;p<bytes.length;p+=4)sum=(sum+view.getUint32(p,true))>>>0;
        return sum;
    }
    function flashPayload(image,stub){
        const result=new Uint8Array(stub.length+image.length);result.set(stub);result.set(image,stub.length);
        const view=new DataView(result.buffer);view.setUint32(4,0,true);view.setUint32(8,0,true);
        view.setUint32(4,(-sumWords(result))>>>0,true);return result;
    }
    async function receive(link,predicate,timeout,options={}){
        const now=options.now||Date.now, end=now()+timeout;let bytes=[];
        while(now()<end){
            abort(options.signal);
            const chunk=await link.read(Math.min(100,Math.max(1,end-now())));
            bytes.push(...chunk);
            if(bytes.length>65536)throw Error('Unexpectedly large P2 response');
            const found=predicate(Uint8Array.from(bytes));if(found!==undefined)return found;
        }
        return null;
    }
    async function probeVM(link,options={}){
        await link.clear();await link.write(Uint8Array.of(250,12,0,250,26,73));
        return receive(link,bytes=>{
            for(let p=0;p+5<=bytes.length;p++){
                if(bytes[p]!==251||bytes[p+1]!==22||bytes[p+2]!==0)continue;
                const n=bytes[p+3]|bytes[p+4]<<8;
                if(n>4096)throw Error('Invalid VM identity response');
                if(p+5+n>bytes.length)continue;
                return decode.decode(bytes.slice(p+6,p+5+n)).replace(/\0+$/,'');
            }
        },options.timeout||1500,options);
    }
    async function reset(link,options={}){
        const sleep=options.sleep||pause;
        await link.setSignals({dataTerminalReady:true,requestToSend:false});await sleep(10);
        await link.setSignals({dataTerminalReady:false,requestToSend:false});await sleep(25);
        await link.clear();
    }
    async function identifyROM(link,options={}){
        await reset(link,options);
        for(let attempt=0;attempt<3;attempt++){
            abort(options.signal);await link.write(text.encode('> Prop_Chk 0 0 0 0  '));
            const version=await receive(link,bytes=>{
                const found=/\r\nProp_Ver ([A-Z])\r\n/.exec(decode.decode(bytes));return found?.[1];
            },500,options);
            if(version){if(!['A','G'].includes(version))throw Error('Unsupported P2 ROM revision: '+version);return version;}
        }
        throw Error('No supported P2 ROM response; no firmware was transferred');
    }
    async function transfer(link,payload,mode,options={}){
        const progress=options.progress||(()=>{});
        await link.clear();
        if(mode==='ram'){
            // ROM boot falls back after 60 seconds. Hex at the VM's 115200
            // baud exceeds that window; Base64 takes about 54 seconds for
            // the reviewed images and avoids a RAM-destroying baud reopen.
            const checked=new Uint8Array(payload.length+4);checked.set(payload);
            new DataView(checked.buffer).setUint32(payload.length,(0x706f7250-sumWords(payload))>>>0,true);
            const encoded=root.btoa(Array.from(checked,b=>String.fromCharCode(b)).join(''));
            if((encoded.length+Math.ceil(encoded.length/2048)*3)*10/115200>55)throw Error('P2 RAM image exceeds the ROM loading time budget');
            await link.write(text.encode('> Prop_Txt 0 0 0 0 '));
            for(let p=0;p<encoded.length;p+=2048){
                abort(options.signal);await link.write(text.encode('> '+encoded.slice(p,p+2048)+' '));
                progress({phase:'transfer',sent:Math.min(payload.length,Math.floor((p+2048)*3/4)),total:payload.length});
            }
            abort(options.signal);
            progress({phase:'verify',committed:true});
            await link.write(text.encode('?'));
            let reply=new Uint8Array();
            // Web Serial has no drain operation. Allow the configured USB/OS
            // transmit queue to empty before declaring a missing reply.
            const ack=await receive(link,bytes=>{reply=bytes;return bytes.includes(46)?true:bytes.includes(33)?false:undefined;},10000,{...options,signal:null});
            if(ack!==true){const error=Error('P2 ROM did not confirm the RAM image checksum');error.rom_reply_hex=Array.from(reply.slice(-64),b=>b.toString(16).padStart(2,'0')).join('');throw error;}
        }else{
            await link.write(text.encode('> Prop_Hex 0 0 0 0'));
            for(let p=0;p<payload.length;p+=128){
                abort(options.signal);const block=payload.slice(p,p+128);
                await link.write(text.encode(Array.from(block,b=>' '+b.toString(16).padStart(2,'0')).join('')+' > '));
                if(p%8192===0||p+128>=payload.length)progress({phase:'transfer',sent:Math.min(p+128,payload.length),total:payload.length});
            }
            abort(options.signal);
            // The flash programmer uses GETPTR to determine image size, so
            // the ROM checksum word must not be appended in flash mode.
            progress({phase:'programming',committed:true});
            await link.write(text.encode('~'));
        }
    }
    async function waitVM(link,expected,options={}){
        for(let attempt=0;attempt<10;attempt++){
            const version=await probeVM(link,{...options,timeout:1000});
            if(version){if(version!=='v405 '+expected)throw Error('Unexpected VM identity: '+version);return version;}
            await (options.sleep||pause)(250);
        }
        throw Error('The installed P2 VM did not answer its identity query');
    }
    async function install(link,image,stub,manifest,board,mode,options={}){
        if(!Object.hasOwn(boards,board)||!['ram','flash'].includes(mode))throw Error('Choose the exact P2 module and RAM or flash');
        const entry=manifest.images[board], expected=boards[board], progress=options.progress||(()=>{});
        if(!entry||entry.board_type!==expected||manifest.vm_version!==405||manifest.extension_revision!==8)throw Error('Unexpected P2 firmware manifest');
        if(image.length!==entry.bytes||await sha256(image)!==entry.sha256)throw Error('P2 firmware hash or size mismatch');
        if(mode==='flash'&&(stub.length!==manifest.flasher.bytes||await sha256(stub)!==manifest.flasher.sha256))throw Error('P2 flash programmer hash or size mismatch');
        const payload=mode==='flash'?flashPayload(image,stub):image;
        sumWords(payload);if(payload.length>512*1024-1024)throw Error('P2 payload exceeds the safe hub-memory bound');
        let opened=false, committed=false;
        try{
            abort(options.signal);await link.open(115200);opened=true;
            const running=await probeVM(link,options);
            if(running){
                if(!/^v\d+ Parallax P2 /.test(running))throw Error('A different MicroBlocks board answered; P2 installation refused');
                if(!options.replaceExistingP2)return {already_running:true,version:running,reset:false,firmware_transferred:false};
            }
            // RAM stays at the VM baud throughout, avoiding a close/reopen
            // that could reset a RAM-only program on some USB drivers.
            if(mode==='flash'){await link.close();opened=false;await link.open(460800);opened=true;}
            progress({phase:'identify'});const rom=await identifyROM(link,options);
            await transfer(link,payload,mode,{...options,progress:event=>{if(event.committed&&mode==='flash')committed=true;progress(event);}});
            if(mode==='flash'){
                // Once the flash programmer starts, cancellation must not
                // close or reset it mid-write. Wait before changing baud.
                await (options.sleep||pause)(8000);
                await link.close();opened=false;await link.open(115200);opened=true;
            }
            progress({phase:'verify'});
            const finishOptions={...options,signal:null};
            let version=await waitVM(link,expected,finishOptions);
            if(mode==='flash'){
                progress({phase:'boot'});await reset(link,finishOptions);
                await (options.sleep||pause)(750);
                try{version=await waitVM(link,expected,finishOptions);}catch(error){throw Error('Flash transfer completed, but boot verification failed: '+error.message);}
            }
            return {already_running:false,mode,rom,version,firmware_transferred:true,
                rom_checksum_verified:mode==='ram',flash_boot_verified:mode==='flash',
                project_storage_may_initialize:true};
        }catch(error){error.flash_programming_started=committed;throw error;}
        finally{if(opened)await link.close();}
    }
    class BrowserLink{
        constructor(port){this.port=port;this.queue=[];this.waiter=null;this.error=null;}
        async open(baudRate){
            await this.port.open({baudRate,bufferSize:65536});
            this.opened=true;
            try{
            await this.port.setSignals({dataTerminalReady:false,requestToSend:false});
            this.queue=[];this.error=null;this.reader=this.port.readable.getReader();this.writer=this.port.writable.getWriter();
            this.pump=(async()=>{try{while(true){const {value,done}=await this.reader.read();if(done)break;if(value?.length){this.queue.push(value);if(this.queue.reduce((n,b)=>n+b.length,0)>65536)throw Error('P2 receive queue overflow');this.wake();}}}catch(error){this.error=error;this.wake();}})();
            }catch(error){await this.close().catch(()=>{});throw error;}
        }
        wake(){if(this.waiter){const ready=this.waiter;this.waiter=null;ready();}}
        async read(timeout){
            if(!this.queue.length&&!this.error)await new Promise(resolve=>{const timer=setTimeout(()=>{if(this.waiter===ready)this.waiter=null;resolve();},timeout);const ready=()=>{clearTimeout(timer);resolve();};this.waiter=ready;});
            if(this.error)throw this.error;return this.queue.shift()||new Uint8Array();
        }
        async write(bytes){await this.writer.write(bytes);}
        async clear(){this.queue=[];}
        async setSignals(signals){await this.port.setSignals(signals);}
        async close(){
            if(this.reader){await this.reader.cancel().catch(()=>{});await this.pump;this.reader.releaseLock();}
            if(this.writer)this.writer.releaseLock();
            this.reader=null;this.writer=null;
            if(this.opened){await this.port.close();this.opened=false;}
        }
    }
    const api=Object.freeze({boards,sha256,sumWords,flashPayload,probeVM,reset,identifyROM,transfer,install,BrowserLink});
    if(typeof module==='object'&&module.exports)module.exports=api;else root.P2WebLoader=api;
})(globalThis);
