// SPDX-License-Identifier: MIT
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const {Client,compatible,installVersionPolicy,digest}=require('../web/js-editor/pi-updates.js');
test('Pi supported version is separate from upstream latest and never flashes automatically',async()=>{
    const notices=[];class Connection{constructor(){this.vmVersion=417;this.latestVmVersion=421;this.closed=false;}disconnect(){this.closed=true;}async checkVmVersion(){throw Error('generic firmware hook should not run');}}
    installVersionPolicy(Connection,text=>notices.push(text));const c=new Connection();
    assert.equal(await c.checkVmVersion(),false);assert.deepEqual(notices,[]);assert.equal(c.latestVmVersion,421);
    c.vmVersion=421;await c.checkVmVersion();assert.match(notices[0],/non validée/);assert(!compatible(421));assert(c.closed);
    c.vmVersion=null;await c.checkVmVersion();assert.equal(notices.length,1);
});
test('independent digest is canonicalized and malformed upload is refused before connecting',()=>{
    assert.equal(digest(' A'.trim().repeat(64)),'a'.repeat(64));assert.throws(()=>digest('bad'));
    const client=new Client(new URL('http://192.168.2.50/'),class{constructor(){throw Error('must not connect');}});
    assert.throws(()=>client.upload({size:65*1024*1024},'a'.repeat(64)),/64 Mio/);
});
test('HTTP workflow uploads bounded bytes on its own origin with progress and review',async()=>{
    const urls=[],sent=[],progress=[];const data=new Blob([new Uint8Array(9000)]);
    class Socket{
        constructor(url){urls.push(url);this.readyState=1;this.bufferedAmount=0;queueMicrotask(()=>this.onopen());}
        send(value){sent.push(value);if(typeof value==='string'){
            const command=JSON.parse(value);
            if(command.action==='upload')queueMicrotask(()=>this.onmessage({data:JSON.stringify({state:'uploading',received:0,total:9000})}));
            if(command.action==='finish')queueMicrotask(()=>this.onmessage({data:JSON.stringify({state:'prepared',version:'pi417-test',sha256:'a'.repeat(64),vm_version:417})}));
        }}
        close(){this.readyState=3;this.onclose?.();}
    }
    const client=new Client(new URL('http://192.168.2.50/'),Socket);
    const result=await client.upload(data,'a'.repeat(64),x=>progress.push(x.state));
    assert.deepEqual(urls,['ws://192.168.2.50/ws/update']);assert.equal(result.state,'prepared');
    const chunks=sent.filter(x=>x instanceof ArrayBuffer);assert.equal(chunks.length,3);assert(chunks.every(x=>x.byteLength<=4096));
    assert.equal(chunks.reduce((n,x)=>n+x.byteLength,0),9000);assert.deepEqual(progress,['uploading','prepared']);
    assert(!sent.some(x=>typeof x==='string'&&x.includes('authenticate')));
});
test('apply sends the exact reviewed identity and surfaces server errors',async()=>{
    let command;
    class Socket{
        constructor(){this.readyState=1;this.bufferedAmount=0;queueMicrotask(()=>this.onopen());}
        send(raw){command=JSON.parse(raw);queueMicrotask(()=>this.onmessage({data:JSON.stringify({state:'error',error:'Native installation is not authorized'})}));}
        close(){this.readyState=3;this.onclose?.();}
    }
    const client=new Client(new URL('http://192.168.2.50/'),Socket);
    await assert.rejects(()=>client.apply({sha256:'b'.repeat(64),version:'pi417-new'}),/not authorized/);
    assert.deepEqual(command,{action:'apply',sha256:'b'.repeat(64),version:'pi417-new',confirmed:true});
});

test('GitHub check and verified selection send no URLs or file bytes',async()=>{
    const commands=[],events=[];
    class Socket{
        constructor(url){assert.equal(url,'ws://192.168.2.50/ws/update');this.readyState=1;queueMicrotask(()=>this.onopen());}
        send(raw){const command=JSON.parse(raw);commands.push(command);
            queueMicrotask(()=>this.onmessage({data:JSON.stringify(command.action==='github_check'?
                {state:'github_checked',choices:[],message:'No compatible release'}:{state:'prepared',version:'next',sha256:'a'.repeat(64)})}));}
        close(){this.readyState=3;}
    }
    const client=new Client(new URL('http://192.168.2.50/'),Socket);
    assert.equal((await client.checkGitHub(false,x=>events.push(x.state))).state,'github_checked');
    assert.equal((await client.chooseGitHub('11:22')).state,'prepared');
    assert.deepEqual(commands,[{action:'github_check',include_prereleases:false},{action:'github_choose',choice:'11:22'}]);
    assert.deepEqual(events,['github_checked']);assert.throws(()=>client.chooseGitHub('https://evil.invalid/'));
});
test('HTTPS updater keeps WSS and the exact current origin',async()=>{
    const urls=[];
    class Socket{
        constructor(url){urls.push(url);this.readyState=1;queueMicrotask(()=>this.onopen());}
        send(raw){assert.equal(JSON.parse(raw).action,'github_check');queueMicrotask(()=>this.onmessage({data:JSON.stringify({state:'github_checked',choices:[]})}));}
        close(){this.readyState=3;}
    }
    const client=new Client(new URL('https://pi.tail-example.ts.net/'),Socket);
    assert.equal((await client.checkGitHub()).state,'github_checked');
    assert.deepEqual(urls,['wss://pi.tail-example.ts.net/ws/update']);
    const invalid=new Client(new URL('file:///tmp/pi.html'),class{constructor(){throw Error('Must not connect');}});
    await assert.rejects(()=>invalid.operation({action:'github_check'}),/site local/);
});
