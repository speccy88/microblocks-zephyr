// SPDX-License-Identifier: MPL-2.0
'use strict';
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
const crypto = require('node:crypto');
const {LoopbackPort, install} = require('../web/js-editor/linux-compat.js');
const location = {href: 'http://127.0.0.1:18876/index.html'};
let count = 0;
function test(name, run) { run(); count++; }
class Socket {
    constructor(url) { this.url = url; this.readyState = 0; this.bufferedAmount = 0; this.sent = []; }
    open() { this.readyState = 1; this.onopen(); this.receive('ready'); }
    close() { this.readyState = 3; if (this.onclose) this.onclose(); }
    send(data) { this.sent.push(data); }
    receive(data) { this.onmessage({data}); }
}

test('requires exact loopback HTTP origin and explicit high port', () => {
    for (const href of ['https://example.com', 'http://localhost:18876/', 'http://127.0.0.1/',
        'http://127.0.0.1:80/', 'http://user@127.0.0.1:18876/', 'http://192.168.1.105:18876/']) {
        assert.throws(() => new LoopbackPort({href}, Socket), /requires/);
    }
});
test('socket-open waits for exactly one bridge readiness marker', () => {
    const p = new LoopbackPort(location, Socket);
    p.socket.readyState = 1; p.socket.onopen();
    assert.equal(p.isConnected(), false); assert.equal(p.write(new Uint8Array([1])), 0);
    p.socket.receive('ready'); assert.equal(p.isConnected(), true);
    p.socket.receive('ready'); assert.equal(p.isConnected(), false);
    const q = new LoopbackPort(location, Socket); q.socket.readyState = 1;
    q.socket.receive(new Uint8Array([1])); assert.equal(q.isConnected(), false);
});
test('ordered binary buffering copies input and drains once', () => {
    const p = new LoopbackPort(location, Socket); p.socket.open();
    assert.equal(p.socket.url, 'ws://127.0.0.1:18876/ws/vm');
    let arrivals = 0; p.dataArrived = () => arrivals++;
    const bytes = new Uint8Array([1, 2]); p.socket.receive(bytes); bytes[0] = 99;
    p.socket.receive(new Uint8Array([3]).buffer);
    assert.deepEqual([...p.read()], [1, 2, 3]); assert.equal(arrivals, 2);
    assert.equal(p.read().length, 0); p.disconnect();
});
test('rejects text, oversized frame and aggregate receive overflow', () => {
    for (const data of ['text', new Uint8Array(4097), new ArrayBuffer(0)]) {
        const p = new LoopbackPort(location, Socket); p.socket.open(); p.socket.receive(data);
        assert.equal(p.isConnected(), false); assert.ok(p.error); assert.equal(p.read().length, 0);
    }
    const p = new LoopbackPort(location, Socket); p.socket.open();
    for (let i = 0; i < 33; i++) p.socket.receive(new Uint8Array(4096));
    assert.equal(p.isConnected(), false); assert.equal(p.read().length, 0);
});
test('bounded output backpressure and closed/pending connection', () => {
    const p = new LoopbackPort(location, Socket), bytes = new Uint8Array([4, 5]);
    assert.equal(p.write(bytes), 0); p.socket.open(); p.socket.bufferedAmount = 32768;
    assert.equal(p.write(bytes), 0); p.socket.bufferedAmount = 0;
    assert.equal(p.write(bytes), 2); bytes[0] = 9; assert.equal(p.socket.sent[0][0], 4);
    assert.throws(() => p.write(new Uint8Array(4097))); p.disconnect();
    assert.equal(p.write(bytes), 0);
});
test('disconnected pending link ignores late data', () => {
    const p = new LoopbackPort(location, Socket); p.disconnect();
    p.socket.receive(new Uint8Array([1])); assert.equal(p.read().length, 0);
});

function upstream(assets, SocketType = Socket, page = location) {
    const events = [], errors = [];
    const context = vm.createContext({console, TextEncoder, TextDecoder, Uint8Array, ArrayBuffer,
        URL, setTimeout, clearTimeout, setInterval: () => 0, requestAnimationFrame: () => {},
        document: {hidden: false}, navigator: {}, location: page, WebSocket: SocketType,
        waitMSecs: ms => new Promise(resolve => setTimeout(resolve, ms)), isMobile: () => false,
        localized: s => s, storeIDEProperty: () => {},
        MB_editor: {clearRunningHighlights() {}, updateRunning() {},
            showResult(id, value) { events.push({id, value}); },
            showChunkError(id, error) { errors.push({id, error}); }}});
    vm.runInContext(`class BlockMorph {}
        class ReporterBlockMorph extends BlockMorph {
            constructor(selector, values = []) { super(); this.selector = selector; this.values = values; }
            inputs() { return this.values.map(v => v instanceof BlockMorph ? v : {evaluate: () => v}); }
            argInputs() { return this.inputs(); } nextBlock() { return null; }
        }
        class CommandBlockMorph extends BlockMorph {} class CommandSlotMorph {}
        class MB_Function {}
        const MB_Specs = {specs: new Map()};`, context);
    const manifest = JSON.parse(fs.readFileSync(path.join(assets, 'source-manifest.json')));
    for (const name of ['mb-code-manager.js', 'mb-compiler.js', 'mb-comm-port.js', 'mb-connection.js']) {
        const relative = 'engine/' + name, bytes = fs.readFileSync(path.join(assets, relative));
        const record = manifest.files.find(f => f.path === relative);
        assert.equal(crypto.createHash('sha256').update(bytes).digest('hex'), record.sha256);
        vm.runInContext(bytes.toString('utf8'), context, {filename: relative});
    }
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../web/js-editor/linux-compat.js'), 'utf8'), context);
    vm.runInContext('MicroBlocksLinux.install(MB_Compiler, MB_CommPort, location, WebSocket);', context);
    return {context, events, errors, evaluate: code => vm.runInContext(code, context)};
}

async function main() {
    const args = process.argv.slice(2), assets = args[0];
    if (!assets) throw new Error('Supply verified packaged JS editor directory');
    const u = upstream(assets);
    test('actual upstream compiler copies primitive map and refuses unknown sets', () => {
        u.evaluate('globalThis.compiler = new MB_Compiler(null);');
        assert.equal(u.evaluate('compiler.primsets.get("microduck")'), 22);
        assert.equal(u.evaluate('compiler.primsets.get("linux")'), 3);
        assert.equal(u.evaluate('MB_PRIMSET_TABLE.has("microduck")'), false);
        assert.throws(() => u.evaluate('compiler.compiledBytesFor(new ReporterBlockMorph("[p4:camera]"))'), /Unsupported primitive/);
    });
    test('actual compiler emits v417 arithmetic and named primitive bytecode', () => {
        const bytes = u.evaluate('compiler.compiledBytesFor(new ReporterBlockMorph("+", [5, 7]))');
        assert.ok(bytes.includes(50));
        const native = u.evaluate('compiler.compiledBytesFor(new ReporterBlockMorph("[microduck:configured]"))');
        const i = native.indexOf(37); assert.ok(i >= 0);
        assert.equal((native[i + 3] >> 2) & 63, 22);
        assert.ok(Buffer.from(native).includes(Buffer.from('configured')));
        const linux = u.evaluate('compiler.compiledBytesFor(new ReporterBlockMorph("[linux:test]"))');
        const j = linux.indexOf(37); assert.equal((linux[j + 3] >> 2) & 63, 3);
    });
    test('comm port extension retains stock serial dispatch', () => {
        assert.equal(u.evaluate('(() => {const p = new MB_CommPort(); p.serialConnect = () => 42; p.connect("serial"); return p.linuxPort === undefined;})()'), true);
    });
    test('upstream primitive layout collision fails visibly', () => {
        class C {initPrimsets() {this.primsets = new Map([['upstream-new', 22]]);} appendLiterals() {}}
        class P {connect() {} disconnect() {} read() {} write() {} isConnected() {}}
        install(C, P, location, Socket); assert.throws(() => new C().initPrimsets(), /layout changed/);
    });
    const endpoint = args[1];
    if (endpoint) {
        const page = {href: endpoint};
        // Node 24's bundled undici accepts headers. Supply the exact packaged
        // origin a browser supplies automatically, without changing bridge checks.
        class OriginSocket extends WebSocket {
            constructor(url) { super(url, {headers: {Origin: new URL(endpoint).origin}}); }
        }
        const live = upstream(assets, OriginSocket, page);
        live.evaluate('globalThis.MB_connection = new MB_Connection(); MB_connection.connect("linux-loopback");');
        const connection = live.evaluate('MB_connection');
        connection.setCodeManager(live.evaluate('new MB_CodeManager(null)'));
        async function until(check) {
            const deadline = Date.now() + 6000;
            while (!check()) {
                connection.processMessages();
                if (live.errors.length) throw new Error(JSON.stringify(live.errors));
                if (connection.port && connection.port.linuxPort && connection.port.linuxPort.error) {
                    throw new Error(connection.port.linuxPort.error);
                }
                if (Date.now() > deadline) throw new Error('Timed out waiting for real VM response');
                await new Promise(resolve => setTimeout(resolve, 10));
            }
        }
        try {
            await until(() => connection.isConnected());
            await connection.sendMsg('pingMsg');
            await until(() => connection.lastPingRecvMSecs > 0);
            await connection.sendMsg('getVersionMsg');
            await until(() => connection.vmVersion != null);
            assert.equal(connection.vmVersion, 417);
            const results = [];
            for (const [selector, values, expected] of [['+', [5, 7], 12], ['[microduck:configured]', [], false]]) {
                const code = live.evaluate(`new MB_Compiler(null).compiledBytesFor(new ReporterBlockMorph(${JSON.stringify(selector)}, ${JSON.stringify(values)}))`);
                // Match the upstream saveChunk padding and use its real CRC
                // acknowledgement path, not a hand-built mock uploader.
                while (code.length % 4) code.push(0);
                const crc = connection.codeManager.computeCRC(code);
                assert.equal(await connection.codeManager.storeChunkOnBoard(0, [2, ...code], crc), true);
                const before = live.events.length;
                await connection.sendMsg('startChunkMsg', 0);
                await until(() => live.events.length > before);
                assert.equal(live.events.at(-1).value, expected);
                results.push({selector, result: expected, crc, code_sha256: crypto.createHash('sha256').update(Buffer.from(code)).digest('hex')});
            }
            console.log(JSON.stringify({real_vm: true, graphical: false, robot_hardware: false,
                version: connection.vmVersion, board: connection.boardType, results}));
        } finally { connection.disconnect(); }
    }
    console.log(JSON.stringify({tests: count, passed: count, upstream_engine: 'unmodified', graphical: false}));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
