// SPDX-License-Identifier: MPL-2.0
// Actual pinned compiler/connection classes with minimal block-view fixtures.
// Explicit loopback only. No graphical acceptance or robot/peripheral commands.
'use strict';
const assert = require('node:assert/strict');
const crypto = require('node:crypto');
const {upstream} = require('./js-editor-compat.test.cjs');

async function main() {
    const [assets, endpoint, mode = 'readback'] = process.argv.slice(2);
    assert.ok(assets, 'Supply verified packaged editor assets');
    assert.ok(['upload', 'readback'].includes(mode));
    const isolated = upstream(assets);
    const code = isolated.evaluate('new MB_Compiler(null).compiledBytesFor(new ReporterBlockMorph("+", [20, 22]))');
    while (code.length % 4) code.push(0);
    isolated.evaluate('globalThis.manager = new MB_CodeManager(null)');
    const crc = Array.from(isolated.evaluate('manager').computeCRC(code));
    const report = {graphical: false, real_compiler: true, block_views: 'minimal fixtures',
        expression: '20 + 22', expected: 42, crc,
        code_sha256: crypto.createHash('sha256').update(Buffer.from(code)).digest('hex'), connections: []};
    if (endpoint === '--offline') { console.log(JSON.stringify(report)); return; }
    const page = new URL(endpoint);
    assert.equal(page.protocol, 'http:'); assert.equal(page.hostname, '127.0.0.1');
    assert.equal(page.username + page.password + page.search + page.hash, '');
    assert.ok(Number(page.port) >= 1024 && Number(page.port) <= 65535);
    for (let pass = 0; pass < 2; pass++) {
        const sent = [];
        class OriginSocket extends WebSocket {
            constructor(url) { super(url, {headers: {Origin: page.origin}}); }
            send(bytes) { sent.push(bytes[1]); return super.send(bytes); }
        }
        const live = upstream(assets, OriginSocket, {href: page.href});
        live.evaluate('globalThis.MB_connection = new MB_Connection(); MB_connection.connect("linux-loopback")');
        const connection = live.evaluate('MB_connection');
        connection.setCodeManager(live.evaluate('new MB_CodeManager(null)'));
        async function until(check) {
            const deadline = Date.now() + 6000;
            while (!check()) {
                connection.processMessages();
                if (live.errors.length) throw Error(JSON.stringify(live.errors));
                if (connection.port?.linuxPort?.error) throw Error(connection.port.linuxPort.error);
                if (Date.now() > deadline) throw Error('Standalone response timed out');
                await new Promise(resolve => setTimeout(resolve, 10));
            }
        }
        try {
            await until(() => connection.isConnected());
            await connection.sendMsg('pingMsg'); await until(() => connection.lastPingRecvMSecs > 0);
            await connection.sendMsg('getVersionMsg'); await until(() => connection.vmVersion != null);
            assert.equal(connection.vmVersion, 417);
            if (mode === 'upload' && pass === 0) {
                assert.equal(await connection.codeManager.storeChunkOnBoard(0, [2, ...code], crc), true);
            }
            connection.codeManager.lastCRC = null;
            await connection.sendMsg('getChunkCRCMsg', 0);
            await until(() => connection.codeManager.lastCRC != null);
            assert.deepEqual(Array.from(connection.codeManager.lastCRC), crc);
            await connection.sendMsg('startChunkMsg', 0);
            await until(() => live.events.length > 0);
            assert.equal(live.events.at(-1).value, 42);
            const readOnly = mode === 'readback' || pass > 0;
            if (readOnly) assert.ok(sent.every(kind => [3, 11, 12, 26].includes(kind)), 'Readback must not clear or upload code');
            report.connections.push({pass, result: 42, crc_verified: true, no_code_upload: readOnly, sent_message_types: sent});
        } finally { connection.disconnect(); }
        await new Promise(resolve => setTimeout(resolve, 100));
    }
    console.log(JSON.stringify(report));
}
main().catch(error => { console.error(error); process.exitCode = 1; });
