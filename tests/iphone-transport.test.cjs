// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const api = require('../web/js-editor/iphone-transport.js');
let passed = 0;
function test(name, run) { run(); passed++; }
const make = () => {
    const sent = [], p = new api.NativePort('192.168.1.42', {postMessage: event => sent.push(event)});
    return {p, sent, event: (type, fields = {}) => api.receive({type, id: p.id, ...fields})};
};
test('browser without native bridge cannot pretend to connect', () => {
    assert.throws(() => new api.NativePort('192.168.1.42'), /requires the iPhone app/);
});
test('pending link cannot send and readiness is explicit', () => {
    const {p, sent, event} = make();
    assert.equal(p.isConnected(), false); assert.equal(p.write(new Uint8Array([1])), 0);
    assert.equal(sent[0].type, 'connect'); event('ready'); assert.equal(p.isConnected(), true); p.disconnect();
});
test('binary input copies, orders and drains exactly once', () => {
    const {p, event} = make(); event('ready'); const bytes = [1, 2]; let arrivals = 0;
    p.dataArrived = () => arrivals++; event('data', {bytes}); bytes[0] = 99;
    event('data', {bytes: [3]}); assert.deepEqual([...p.read()], [1, 2, 3]);
    assert.equal(p.read().length, 0); assert.equal(arrivals, 2); p.disconnect();
});
test('malformed, early or duplicate events fail closed', () => {
    for (const [type, fields, ready] of [
        ['data', {bytes: [1]}, false], ['ready', {}, true], ['data', {bytes: 'abc'}, true],
        ['data', {bytes: [-1]}, true], ['data', {bytes: [true]}, true], ['data', {bytes: [1.2]}, true],
        ['data', {bytes: [256]}, true], ['data', {bytes: []}, true], ['bogus', {}, true],
        ['data', {bytes: Array(4097).fill(1)}, true], ['sent', {count: 0}, true]
    ]) {
        const {p, event} = make(); if (ready) event('ready'); event(type, fields);
        assert.equal(p.isConnected(), false); assert.ok(p.error); assert.equal(p.read().length, 0);
    }
});
test('bounded write credit is returned by actual native acknowledgement', () => {
    const {p, event, sent} = make(); event('ready'); const bytes = new Uint8Array(2000).fill(7);
    assert.equal(p.write(bytes), 1024); bytes[0] = 9; assert.equal(sent.at(-1).bytes[0], 7);
    for (let i = 1; i < 32; i++) assert.equal(p.write(bytes), 1024);
    assert.equal(p.pending, api.MAX_OUTPUT); assert.equal(p.write(bytes), 0);
    event('sent', {count: 1024}); assert.equal(p.write(bytes), 1024); p.disconnect();
    assert.equal(p.pending, 0); assert.equal(p.write(bytes), 0);
});
test('receive aggregate overflow closes and discards', () => {
    const {p, event} = make(); event('ready');
    for (let i = 0; i < 33; i++) event('data', {bytes: Array(4096).fill(1)});
    assert.equal(p.isConnected(), false); assert.equal(p.read().length, 0);
});
test('stale sessions and disconnect races cannot affect replacement', () => {
    const old = make(); old.event('ready'); const fresh = make(); fresh.event('ready');
    assert.equal(old.p.isConnected(), false); old.event('error', {reason: 'old'});
    old.event('data', {bytes: [2]}); assert.equal(fresh.p.isConnected(), true);
    assert.equal(fresh.p.read().length, 0); fresh.p.disconnect(); fresh.event('ready');
    assert.equal(fresh.p.isConnected(), false);
});
test('bridge failures, background and erroneous acknowledgements close link', () => {
    const a = make(); a.event('ready'); a.event('sent', {count: 1}); assert.ok(a.p.error);
    const b = make(); b.event('ready'); api.close(); assert.equal(b.p.isConnected(), false);
    const c = make(); c.event('ready'); c.p.bridge = {postMessage() {throw Error('failed');}};
    assert.equal(c.p.write(new Uint8Array([1])), 0); assert.equal(c.p.isConnected(), false);
});

async function realCompiler(assets, endpoint) {
    const results = [], errors = [], frames = [], kinds = [];
    let context, rx = [], current = '', savedCRC, socket;
    const page = endpoint && new URL(endpoint);
    if (page) {
        assert.equal(page.protocol, 'http:'); assert.equal(page.hostname, '127.0.0.1');
        assert.ok(Number(page.port) >= 1024 && Number(page.port) <= 65535);
        assert.equal(page.username + page.password + page.search + page.hash, '');
    }
    const deliver = (type, fields = {}) => vm.runInContext(
        `MicroBlocksIPhone.receive(${JSON.stringify({type, id: current, ...fields})})`, context);
    const long = (kind, index, body) => {
        const bytes = [251, kind, index, body.length & 255, body.length >> 8, ...body];
        // Deliberately fragment the protocol header and body across bridge events.
        deliver('data', {bytes: bytes.slice(0, 2)}); deliver('data', {bytes: bytes.slice(2)});
    };
    const bridge = {postMessage(event) {
        if (event.type === 'connect') {
            current = event.id; rx = [];
            if (!endpoint) { deliver('ready'); return; }
            const owned = new WebSocket('ws://' + page.host + '/ws/vm', {headers: {Origin: page.origin}});
            socket = owned; owned.binaryType = 'arraybuffer'; let ready = false;
            owned.onmessage = message => {
                if (socket !== owned) return;
                if (!ready) {
                    assert.equal(message.data, 'ready'); ready = true; deliver('ready');
                } else {
                    assert.ok(message.data instanceof ArrayBuffer);
                    deliver('data', {bytes: [...new Uint8Array(message.data)]});
                }
            };
            owned.onerror = () => deliver('error', {reason: 'Loopback test socket failed'});
            return;
        }
        if (event.type === 'close') {
            if (socket) { const old = socket; socket = null; old.close(); }
            return;
        }
        if (event.type !== 'write') return;
        frames.push(event.bytes.length); rx.push(...event.bytes);
        if (socket) socket.send(Uint8Array.from(event.bytes));
        deliver('sent', {count: event.bytes.length});
        while (rx.length >= 3) {
            const size = rx[0] === 250 ? 3 : rx.length >= 5 ? 5 + rx[3] + (rx[4] << 8) : Infinity;
            if (rx.length < size) break;
            const msg = rx.splice(0, size), kind = msg[1], index = msg[2]; kinds.push(kind);
            if (endpoint) continue; // real VM supplies every response
            if (kind === 26) deliver('data', {bytes: [250, 26, index]});
            if (kind === 12) long(22, index, [2, ...Buffer.from('v417 iPhone protocol fixture')]);
            if (kind === 32) {
                assert.equal(msg.at(-1), 254);
                savedCRC = context.manager.computeCRC(msg.slice(6, -1));
                long(23, index, Array.from(savedCRC));
            }
            if (kind === 11) long(23, index, Array.from(savedCRC));
            // Protocol fixture only: this result is injected, not VM execution.
            if (kind === 3) long(18, index, [1, 42, 0, 0, 0]);
        }
    }};
    context = vm.createContext({console, Uint8Array, ArrayBuffer, TextEncoder, TextDecoder,
        setTimeout, clearTimeout, setInterval: () => 0, requestAnimationFrame: () => {},
        document: {hidden: false}, navigator: {}, isMobile: () => true,
        webkit: {messageHandlers: {microblocks: bridge}},
        waitMSecs: ms => new Promise(resolve => setTimeout(resolve, ms)), localized: s => s,
        storeIDEProperty() {}, MB_editor: {clearRunningHighlights() {}, updateRunning() {}, inform() {},
            showResult(id, value) { results.push(value); }, showChunkError(id, error) { errors.push(error); }}});
    vm.runInContext(`class BlockMorph {}
        class ReporterBlockMorph extends BlockMorph {
            constructor(selector, values) { super(); this.selector=selector; this.values=values; }
            inputs() {return this.values.map(e=>({evaluate:()=>e}));}
            argInputs() {return this.inputs();} nextBlock() {return null;}
        }
        class CommandBlockMorph extends BlockMorph {} class CommandSlotMorph {} class MB_Function {}
        const MB_Specs={specs:new Map()};`, context);
    const manifest = JSON.parse(fs.readFileSync(path.join(assets, 'source-manifest.json')));
    for (const name of ['mb-code-manager.js', 'mb-compiler.js', 'mb-comm-port.js', 'mb-connection.js']) {
        const relative = 'engine/' + name, data = fs.readFileSync(path.join(assets, relative));
        assert.equal(crypto.createHash('sha256').update(data).digest('hex'), manifest.files.find(r => r.path === relative).sha256);
        vm.runInContext(data.toString('utf8'), context);
    }
    vm.runInContext(fs.readFileSync(path.join(assets, 'iphone-transport.js'), 'utf8'), context);
    const run = script => vm.runInContext(script, context);
    run('MicroBlocksIPhone.install(MB_CommPort, () => "192.168.1.42"); globalThis.MB_connection = new MB_Connection(); globalThis.manager = new MB_CodeManager(null); MB_connection.setCodeManager(manager);');
    assert.equal(run('new MB_Compiler(null).primsets.has("microduck")'), false, 'No Linux compiler overlay on boards');
    async function until(check) {
        const deadline = Date.now() + 8000;
        while (!check()) {
            run('MB_connection.processMessages()');
            if (Date.now() > deadline) throw Error('Timed out waiting for actual VM protocol');
            await new Promise(resolve => setTimeout(resolve, 5));
        }
    }
    for (let pass = 0; pass < 2; pass++) {
        await run('MB_connection.connect("iphone-wifi")');
        await until(() => run('MB_connection.isConnected()'));
        await run('MB_connection.sendMsg("pingMsg")'); run('MB_connection.processMessages()');
        await until(() => run('MB_connection.lastPingRecvMSecs > 0'));
        assert.equal(run('MB_connection.connectedToBoard()'), true);
        await run('MB_connection.sendMsg("getVersionMsg")'); run('MB_connection.processMessages()');
        await until(() => run('MB_connection.vmVersion !== null'));
        assert.equal(run('MB_connection.vmVersion'), 417);
        if (pass === 0) {
            run('globalThis.code = new MB_Compiler(null).compiledBytesFor(new ReporterBlockMorph("+", [20,22])); while(code.length%4) code.push(0);');
            savedCRC = run('manager.computeCRC(code)');
            assert.equal(await run('manager.storeChunkOnBoard(0, [2,...code], manager.computeCRC(code))'), true);
        } else {
            run('manager.lastCRC = null'); await run('MB_connection.sendMsg("getChunkCRCMsg",0)');
            await until(() => context.manager.lastCRC !== null);
            assert.deepEqual(Array.from(context.manager.lastCRC), Array.from(savedCRC));
        }
        const before = results.length;
        await run('MB_connection.sendMsg("startChunkMsg",0)'); run('MB_connection.processMessages()');
        await until(() => results.length > before);
        assert.equal(results.at(-1), 42);
        await run('MB_connection.sendMsg("stopAllMsg")'); run('MB_connection.disconnect()');
        assert.equal(run('MB_connection.isConnected()'), false);
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    assert.equal(errors.length, 0); assert.ok(kinds.includes(6)); assert.ok(frames.every(n => n <= 1024));
    passed++;
    return {real_compiler: true, protocol_peer: endpoint ? 'real native SmallVM v417 via loopback' : 'synthetic fixture',
        native_ios_socket: false, physical_board: false,
        ping_version: true, crc_upload: true, fragmented_input: true, run_stop_reconnect: true};
}

(async () => {
    const assets = process.argv[2];
    const protocol = assets ? await realCompiler(assets, process.argv[3]) : null;
    console.log(JSON.stringify({passed, protocol}));
})().catch(error => { console.error(error); process.exitCode = 1; });
