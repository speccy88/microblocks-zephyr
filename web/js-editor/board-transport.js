// SPDX-License-Identifier: MPL-2.0
// Explicit USB ownership and profile identity; no firmware installation.
(function (root) {
    'use strict';
    const MAX_INPUT=131072,MAX_OUTPUT=32768,installed=new WeakMap();
    function secureEndpoint(value){
        if(typeof value!=='string'||value.length>512||/[\x00-\x20\x7f]/.test(value))throw Error('Invalid secure board address');
        const url=new URL(value);
        if(url.protocol!=='wss:'||!url.hostname||url.username||url.password||url.search||url.hash||url.pathname!=='/ws/vm')throw Error('Use a trusted wss:// board address ending in /ws/vm, without credentials, query or fragment');
        return url.href;
    }
    class WSSPort{
        constructor(Socket,endpoint,notify=()=>{}){this.Socket=Socket;this.endpoint=secureEndpoint(endpoint);this.notify=notify;this.ready=false;this.closed=false;this.parts=[];this.size=0;this.opening=null;}
        connect(){
            if(this.opening)return this.opening;
            this.opening=new Promise((resolve,reject)=>{
                this.reject=reject;
                if(typeof this.Socket!=='function'){reject(Error('WebSocket is unavailable'));return;}
                const socket=this.socket=new this.Socket(this.endpoint);socket.binaryType='arraybuffer';
                const fail=message=>{if(this.closed)return;this.error=message;this.notify(message);this.disconnect();};
                this.timer=setTimeout(()=>fail('Secure board readiness timed out'),5000);
                socket.onmessage=event=>{
                    if(this.closed)return;
                    if(!this.ready){if(event.data!=='ready'){fail('Expected board readiness marker');return;}this.ready=true;clearTimeout(this.timer);this.reject=null;resolve();return;}
                    if(!(event.data instanceof ArrayBuffer)&&!(event.data instanceof Uint8Array)){fail('Secure board stream requires binary data');return;}
                    const bytes=new Uint8Array(event.data);
                    if(!bytes.length||bytes.length>4096||this.size+bytes.length>MAX_INPUT){fail('Secure board input limit exceeded');return;}
                    this.parts.push(bytes.slice());this.size+=bytes.length;if(this.dataArrived)this.dataArrived();
                };
                socket.onerror=()=>fail('Secure board connection failed; check the address and certificate without bypassing browser warnings');
                socket.onclose=()=>{if(!this.closed){this.notify('Secure board connection closed');this.disconnect();}};
            }).catch(error=>{if(!this.closed){this.error=error.message;this.notify(error.message);this.disconnect();}throw error;}).finally(()=>{this.opening=null;if(this.settled)this.settled();});return this.opening;
        }
        isConnected(){return !this.closed&&this.ready&&this.socket?.readyState===1;}
        read(){const bytes=new Uint8Array(this.size);let offset=0;for(const part of this.parts){bytes.set(part,offset);offset+=part.length;part.fill(0);}this.parts=[];this.size=0;return bytes;}
        write(bytes){if(!(bytes instanceof Uint8Array)||bytes.length<1||bytes.length>4096)throw Error('Secure board write requires 1..4096 bytes');if(!this.isConnected()||this.socket.bufferedAmount+bytes.length>MAX_OUTPUT)return 0;this.socket.send(bytes.slice());return bytes.length;}
        disconnect(){if(this.closed)return;this.closed=true;this.ready=false;clearTimeout(this.timer);if(this.reject){this.reject(Error(this.error||'Secure board connection cancelled'));this.reject=null;}for(const part of this.parts)part.fill(0);this.parts=[];this.size=0;if(this.socket?.readyState<2)this.socket.close();if(this.settled)this.settled();}
    }
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
    function install(CommPort,Connection,profile,provider,editor,notify=()=>{},Socket=root.WebSocket) {
        if(installed.has(Connection)){const prior=installed.get(Connection);if(prior.id!==profile.id)throw Error('Board profile already installed');return prior.api;}
        for(const name of ['connect','disconnect','sendMsg','versionReceived','justConnected'])if(typeof Connection.prototype[name]!=='function')throw Error('Upstream board hook changed: '+name);
        const opening=new Set(),states=new WeakMap();
        const state=connection=>{if(!states.has(connection))states.set(connection,{epoch:0,verified:false,pending:0,listeners:new Set()});return states.get(connection);};
        const snapshot=connection=>Object.freeze({epoch:state(connection).epoch,verified:state(connection).verified&&connection.isConnected()});
        const signal=connection=>{const update=snapshot(connection);for(const fn of [...state(connection).listeners]){try{fn(update);}catch(error){notify('Target service listener failed: '+error.message);}}};
        const originalPortConnect=CommPort.prototype.connect;
        CommPort.prototype.connect=function(type,...args){
            if(type!=='serial'&&!(type==='board-wss'&&profile.secure_websocket))return originalPortConnect.call(this,type,...args);
            if([...opening].some(port=>port.opening||port.cleanup))throw Error('Previous USB selection or cleanup is still pending');
            this.boardUSB=type==='serial'?new USBPort(provider,profile,notify):new WSSPort(Socket,args[0],notify);const own=this.boardUSB;
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
                if(name==='disconnect'){opening.add(own);void Promise.resolve(own.disconnect()).finally(()=>{if(!own.opening)opening.delete(own);});return;}
                return own[name](...args);
            };
        }
        const connect=Connection.prototype.connect,disconnect=Connection.prototype.disconnect,version=Connection.prototype.versionReceived;
        Connection.prototype.connect=function(...args){this.disconnect();return connect.apply(this,args);};
        Connection.prototype.disconnect=function(...args){const own=state(this);own.epoch++;own.verified=false;if(this.recvBuf instanceof Uint8Array)this.recvBuf.fill(0);this.recvBuf=new Uint8Array(0);try{return disconnect.apply(this,args);}finally{signal(this);}};
        Connection.prototype.versionReceived=function(text){
            const own=state(this),type=typeof text==='string'?this.extractBoardType(text):'',number=typeof text==='string'?this.extractVersionNumber(text):-1;
            if(typeof text!=='string'||text.length>220||!/^v\d+\s/.test(text)||/[\x00-\x1f\x7f]/.test(text)||!profile.vm_versions.includes(number)||
                !(type===profile.board_type_prefix||type.startsWith(profile.board_type_prefix+' '))){
                notify('Board identity/version does not match '+profile.name+'. No program was uploaded.');this.disconnect();return;
            }
            own.verified=true;const result=version.call(this,text);signal(this);return result;
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
        const api={verified:connection=>snapshot(connection).verified,
            subscribe(connection,fn){if(typeof fn!=='function')throw Error('Target listener must be a function');state(connection).listeners.add(fn);fn(snapshot(connection));return ()=>state(connection).listeners.delete(fn);},
            sendFrame(connection,frame){
                if(!(frame instanceof Uint8Array)||frame.length<6||frame.length>4096||frame[0]!==251||frame[1]<1||frame[3]+256*frame[4]!==frame.length-5||frame[frame.length-1]!==254)throw Error('Invalid framed target request');
                if(!snapshot(connection).verified||state(connection).pending+frame.length>MAX_OUTPUT)return 0;
                // sendMsg validates/copies and reserves the queue synchronously.
                // Returning a byte count acknowledges that reservation only.
                void connection.sendMsg(frame[1],frame[2],frame.slice(5,-1)).catch(()=>{});return frame.length;
            }};
        installed.set(Connection,{id:profile.id,api});return api;
    }
    const api=Object.freeze({USBPort,WSSPort,secureEndpoint,install,MAX_INPUT,MAX_OUTPUT});root.MicroBlocksBoardTransport=api;
    if(typeof module==='object'&&module.exports)module.exports=api;
})(globalThis);
