// SPDX-License-Identifier: MIT
'use strict';
const {test}=require('node:test'),assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path'),crypto=require('node:crypto');
if (!process.env.PI_EDITOR) { test('Pi LAN package', {skip:'Set PI_EDITOR to a freshly built Pi package'},()=>{}); } else {
const root=path.resolve(process.env.PI_EDITOR);
const api=require(path.join(root,'mobile/mobile-browser.js'));
function fixture(href='http://192.168.1.105:8877/',profile={runtime:'board',board:'pi5',local_pi:'open-http-v1'}){
    const sockets=[],received=[];
    class Socket{constructor(url){this.url=url;this.readyState=1;this.bufferedAmount=0;this.sent=[];sockets.push(this);}send(x){this.sent.push(x);}close(){this.readyState=3;this.closed=true;}}
    const location=new URL(href),client=api.create({profile,location,Socket,receive:x=>received.push(x),schedule:()=>1,cancel:()=>{}});
    return {client,sockets,received,connect:()=>client.bridge.postMessage({type:'connect',id:'a',address:location.hostname})};
}
test('open HTTP Pi connects without key or authentication frame',()=>{
    const f=fixture();assert(f.client.available);f.connect();const s=f.sockets[0];
    assert.equal(s.url,'ws://192.168.1.105:8877/ws/vm');assert.equal(s.onopen,undefined);assert.deepEqual(s.sent,[]);
    s.onmessage({data:'ready'});assert.equal(f.received[0].type,'ready');
    f.client.bridge.postMessage({type:'write',id:'a',bytes:[250,12,0]});assert.deepEqual(Array.from(s.sent[0]),[250,12,0]);
});
test('an explicit Pi package supports loopback-only fresh installations',()=>{
    const f=fixture('http://127.0.0.1:38877/');assert(f.client.available);f.connect();
    assert.equal(f.sockets[0].url,'ws://127.0.0.1:38877/ws/vm');
});
test('Pages, HTTPS, public hosts and non-Pi packages cannot use this HTTP adapter',()=>{
    for(const f of [fixture('https://192.168.1.105:8877/'),fixture('http://public.example/'),
        fixture(undefined,{runtime:'pages',board:'pi5',local_pi:'open-http-v1'}),fixture(undefined,{runtime:'board',board:'rlcd',local_pi:'open-http-v1'})]){
        assert(!f.client.available);assert.throws(f.connect);assert.equal(f.sockets.length,0);
    }
});
test('same origin is fixed and malformed ready/frames close the link',()=>{
    const f=fixture();f.connect();assert.throws(()=>f.client.bridge.postMessage({type:'connect',id:'b',address:'192.168.1.106'}));
    f.sockets[0].onmessage({data:'wrong'});assert(f.sockets[0].closed);
    const g=fixture();g.connect();g.sockets[0].onmessage({data:'ready'});g.sockets[0].onmessage({data:new ArrayBuffer(4097)});assert(g.sockets[0].closed);
});
test('upstream files and output receipt remain hash-identical',()=>{
    const hash=x=>crypto.createHash('sha256').update(x).digest('hex'),receipt=JSON.parse(fs.readFileSync(path.join(root,'pi-build-manifest.json')));
    assert.equal(receipt.authentication,false);assert.equal(receipt.encryption,false);
    for(const [name,sha] of Object.entries(receipt.files))assert.equal(hash(fs.readFileSync(path.join(root,name))),sha,name);
    const source=JSON.parse(fs.readFileSync(path.join(root,'mobile/source-manifest.json')));
    for(const file of source.files)assert.equal(hash(fs.readFileSync(path.join(root,'mobile',file.path))),file.sha256,file.path);
    assert(!fs.existsSync(path.join(root,'mobile/pi-session.js')));
    assert(!fs.readFileSync(path.join(root,'microblocks.html'),'utf8').includes('pi-session-key'));
});

}

