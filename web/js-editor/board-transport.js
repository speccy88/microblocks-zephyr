// SPDX-License-Identifier: MPL-2.0
// Explicit USB ownership and profile identity; no firmware installation.
(function (root) {
    'use strict';
    const MAX_INPUT=131072,MAX_OUTPUT=32768,installed=new WeakMap();
    class USBPort {
        constructor(provider, profile, notify=()=>{}) {
            this.provider=provider;this.profile=profile;this.notify=notify;
            this.generation=0;this.ready=false;this.parts=[];this.size=0;
            this.pending=0;this.chain=Promise.resolve();this.cleanup=null;this.opening=null;
        }
        async connect() {
            if(this.opening)return this.opening;
            if(this.cleanup)throw Error('USB cleanup is still pending');
            const token=++this.generation;
            this.opening=this.open(token).finally(()=>{this.opening=null;if(this.settled)this.settled();});
            return this.opening;
        }
        async open(token) {
            let port,reader,writer,opened=false;
            try {
                if(!this.provider?.requestPort)throw Error('USB needs desktop Chrome or Edge with Web Serial');
                port=await this.provider.requestPort({filters:this.profile.usb_filters});
                if(token!==this.generation)return;
                await port.open({baudRate:115200,bufferSize:8192});opened=true;
                if(token!==this.generation)return;
                await port.setSignals({dataTerminalReady:this.profile.dtr,requestToSend:false});
                if(token!==this.generation)return;
                reader=port.readable.getReader();writer=port.writable.getWriter();
                Object.assign(this,{port,reader,writer,ready:true});
                this.loop=this.readLoop(port,reader,token);
            } catch(error) {this.error=error.message;this.notify(error.message);throw error;}
            finally {if(!this.ready||token!==this.generation)await this.release({port:opened?port:null,reader,writer});}
        }
        async release({port,reader,writer}) {
            if(reader){try{await reader.cancel();}catch{}try{reader.releaseLock();}catch{}}
            if(writer){try{if(writer.abort)await writer.abort();}catch{}try{writer.releaseLock();}catch{}}
            if(port){try{await port.setSignals({dataTerminalReady:false,requestToSend:false});}catch{}try{await port.close();}catch(error){this.error='USB close failed: '+error.message;this.notify(this.error);}}
        }
        async readLoop(port,reader,token) {
            try {
                while(this.ready&&token===this.generation){
                    const {value,done}=await reader.read();
                    if(done||token!==this.generation)break;
                    if(value?.length){
                        if(!(value instanceof Uint8Array)||this.size+value.length>MAX_INPUT)throw Error('USB input limit exceeded');
                        this.parts.push(value.slice());this.size+=value.length;
                        if(this.dataArrived)this.dataArrived();
                    }
                }
            } catch(error){if(token===this.generation){this.error=error.message;this.notify(error.message);}}
            finally{if(token===this.generation)void this.disconnect();}
        }
        isConnected(){return this.ready;}
        read(){const bytes=new Uint8Array(this.size);let offset=0;for(const part of this.parts){bytes.set(part,offset);offset+=part.length;part.fill(0);}this.parts=[];this.size=0;return bytes;}
        write(bytes){
            if(!(bytes instanceof Uint8Array)||bytes.length<1||bytes.length>4096)throw Error('USB write requires 1..4096 bytes');
            if(!this.ready||this.pending+bytes.length>MAX_OUTPUT)return 0;
            const copy=bytes.slice(),writer=this.writer,token=this.generation;this.pending+=copy.length;
            this.chain=this.chain.then(()=>token===this.generation&&this.ready?writer.write(copy):undefined)
                .catch(error=>{if(token===this.generation){this.error=error.message;this.notify(error.message);void this.disconnect();}})
                .finally(()=>{this.pending-=copy.length;copy.fill(0);});
            return bytes.length;
        }
        disconnect(){
            ++this.generation;this.ready=false;for(const part of this.parts)part.fill(0);this.parts=[];this.size=0;
            if(this.cleanup)return this.cleanup;
            const resources={port:this.port,reader:this.reader,writer:this.writer};this.port=this.reader=this.writer=null;
            this.cleanup=this.release(resources).finally(()=>{this.cleanup=null;if(this.settled)this.settled();});return this.cleanup;
        }
    }
    function install(CommPort,Connection,profile,provider,editor,notify=()=>{}) {
        if(installed.has(Connection)){if(installed.get(Connection)!==profile.id)throw Error('Board profile already installed');return;}
        for(const name of ['connect','disconnect','sendMsg','versionReceived','justConnected'])if(typeof Connection.prototype[name]!=='function')throw Error('Upstream board hook changed: '+name);
        const opening=new Set(),states=new WeakMap();
        const state=connection=>{if(!states.has(connection))states.set(connection,{epoch:0,verified:false,pending:0});return states.get(connection);};
        const originalPortConnect=CommPort.prototype.connect;
        CommPort.prototype.connect=function(type,...args){
            if(type!=='serial')return originalPortConnect.call(this,type,...args);
            if([...opening].some(port=>port.opening||port.cleanup))throw Error('Previous USB selection or cleanup is still pending');
            this.boardUSB=new USBPort(provider,profile,notify);const own=this.boardUSB;
            own.dataArrived=()=>{if(this.boardUSB===own&&this.dataArrived)this.dataArrived();};
            own.settled=()=>{if(!own.ready&&!own.opening&&!own.cleanup)opening.delete(own);};
            // Keep ready ports tracked: a read failure can start asynchronous
            // cleanup before the connection controller notices disconnection.
            opening.add(own);void own.connect().catch(()=>{}).finally(own.settled);
        };
        for(const name of ['isConnected','read','write','disconnect']){
            const original=CommPort.prototype[name];
            CommPort.prototype[name]=function(...args){
                if(!this.boardUSB)return original.apply(this,args);
                const own=this.boardUSB;
                if(name==='disconnect'){opening.add(own);void own.disconnect().finally(()=>{if(!own.opening)opening.delete(own);});return;}
                return own[name](...args);
            };
        }
        const connect=Connection.prototype.connect,disconnect=Connection.prototype.disconnect,version=Connection.prototype.versionReceived;
        Connection.prototype.connect=function(...args){this.disconnect();return connect.apply(this,args);};
        Connection.prototype.disconnect=function(...args){const own=state(this);own.epoch++;own.verified=false;if(this.recvBuf instanceof Uint8Array)this.recvBuf.fill(0);this.recvBuf=new Uint8Array(0);return disconnect.apply(this,args);};
        Connection.prototype.versionReceived=function(text){
            const own=state(this),type=typeof text==='string'?this.extractBoardType(text):'',number=typeof text==='string'?this.extractVersionNumber(text):-1;
            if(typeof text!=='string'||text.length>220||!/^v\d+\s/.test(text)||/[\x00-\x1f\x7f]/.test(text)||!profile.vm_versions.includes(number)||
                !(type===profile.board_type_prefix||type.startsWith(profile.board_type_prefix+' '))){
                notify('Board identity/version does not match '+profile.name+'. No program was uploaded.');this.disconnect();return;
            }
            own.verified=true;return version.call(this,text);
        };
        // Pin each queued write to its originating port/session. A reconnect
        // must never receive a previously queued program from another board.
        Connection.prototype.sendMsg=function(name,chunk=0,body=null){
            const own=state(this),id=this.msgNameToID(name),port=this.port,epoch=own.epoch;
            if(!this.isConnected())return Promise.resolve(false);
            if(!own.verified&&id!==this.msgNameToID('getVersionMsg')&&id!==this.msgNameToID('pingMsg')){notify('Waiting for the selected board identity');return Promise.resolve(false);}
            if(!Number.isInteger(id)||id<1||id>255||!Number.isInteger(chunk??0)||(chunk??0)<0||(chunk??0)>255)throw Error('Invalid VM message header');
            let bytes;
            if(body==null)bytes=new Uint8Array([250,id,chunk??0]);
            else{
                if((!Array.isArray(body)&&!(body instanceof Uint8Array))||body.length>4090||[...body].some(n=>!Number.isInteger(n)||n<0||n>255))throw Error('Invalid VM message body');
                const size=body.length+1;bytes=new Uint8Array([251,id,chunk??0,size&255,size>>8,...body,254]);
            }
            if(own.pending+bytes.length>MAX_OUTPUT){notify('VM output queue is full');return Promise.resolve(false);}
            own.pending+=bytes.length;
            const active=()=>state(this).epoch===epoch&&this.port===port&&this.isConnected();
            const task=this.sendQueue.catch(()=>{}).then(async()=>{
                let offset=0;const deadline=Date.now()+5000;
                while(offset<bytes.length){
                    if(!active())return false;
                    if(Date.now()>deadline)throw Error('VM output stalled');
                    const count=Math.min(63,bytes.length-offset),sent=port.write(bytes.slice(offset,offset+count));
                    if(!Number.isInteger(sent)||sent<0||sent>count)throw Error('Invalid USB write result');
                    offset+=sent;await new Promise(resolve=>setTimeout(resolve,sent?3:25));
                }
                return true;
            }).finally(()=>{own.pending-=bytes.length;bytes.fill(0);});
            this.sendQueue=task.catch(error=>{if(active()){notify(error.message);this.disconnect();}});return task;
        };
        Connection.prototype.justConnected=async function(){
            const own=state(this),epoch=own.epoch;this.connectionStartTime=null;this.vmVersion=null;
            await this.sendMsgSync('getVersionMsg');this.processMessages();await this.waitForVersion();
            if(own.epoch!==epoch||!own.verified||!this.isConnected())return;
            this.pushToIDE('board.connected',true);await this.sendMsg('stopAllMsg');
            editor().clearRunningHighlights();this.setSerialDelay('reset to default');
            if(own.epoch===epoch&&own.verified)await editor().justConnected();
        };
        Connection.prototype.checkVmVersion=async()=>false;
        Connection.prototype.installBoardSpecificBlocks=async()=>{};
        installed.set(Connection,profile.id);
        return {verified:connection=>state(connection).verified};
    }
    const api=Object.freeze({USBPort,install,MAX_INPUT,MAX_OUTPUT});root.MicroBlocksBoardTransport=api;
    if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
