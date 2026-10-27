// SPDX-License-Identifier: MPL-2.0
'use strict';
const fs = require('node:fs'), path = require('node:path'), crypto = require('node:crypto');
const assert = require('node:assert/strict');
const {load} = require('./support/js_editor_headless.cjs');
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
async function main() {
    const [assets, endpoint, mode] = process.argv.slice(2);
    const options = {};
    if (endpoint) {
        options.location = {href: endpoint};
        options.Socket = class extends WebSocket {constructor(url) {super(url, {headers: {Origin: new URL(endpoint).origin}});}};
    }
    const h = load(assets, options), meta = JSON.parse(fs.readFileSync(path.join(assets, 'microduck-libraries.json')));
    const bundle = fs.readFileSync(path.join(assets, meta.bundle));
    let passed = 0;
    for (const entry of meta.sources) {
        const bytes = fs.readFileSync(path.join(assets, entry.packaged_source));
        assert.equal(sha(bytes), entry.sha256);
        assert.deepEqual(bundle.subarray(entry.bundle_offset, entry.bundle_offset + entry.bytes), bytes);
    }
    passed++;
    h.set('libraryPath', meta.bundle);
    await h.evaluate('MB_Files.initialize()');
    assert.ok(h.evaluate('MB_Files.listFiles("Libraries").includes(libraryPath)')); passed++;
    h.set('bundleText', bundle.toString('utf8'));
    assert.equal(h.evaluate('(()=>{const problems=[]; MB_Parser.parse(bundleText,"bundle",problems); return problems.length;})()'), 0); passed++;
    // This is the real editor's file-open/import path, not a replacement parser.
    await h.evaluate('MB_editor.openLibraryFile(libraryPath)');
    assert.equal(h.evaluate('MB_editor.project.libraries.size'), 6);
    assert.equal(h.evaluate('MB_editor.project.allFunctions().length'), 140);
    assert.equal(h.evaluate('MB_connection.port'), null); passed++;
    const compiled = h.evaluate(`(()=>{let p=MB_editor.project;MB_editor.codeManager.assignFunctionIDs();let c=new MB_Compiler(p,MB_editor.codeManager);
        return p.allFunctions().map(f=>({name:f.functionName,id:MB_editor.codeManager.functionChunkIDs.get(f.functionName),bytes:c.compiledBytesFor(f)}));})()`);
    assert.equal(new Set(compiled.map(f => f.id)).size, 140);
    assert.ok(compiled.every(f => Number.isInteger(f.id) && f.id < 250));
    assert.ok(compiled.every(f => f.bytes.length > 0 && f.bytes.length <= 1000)); passed++;
    h.set('expressionText', 'microduckReadingStatus (microduckDepthCapture)');
    assert.equal(h.evaluate('MB_Parser.blockFor(MB_Parser.parse(expressionText)[0],true) instanceof ReporterBlockMorph'), true); passed++;
    const missing = load(assets);
    missing.set('depthText', fs.readFileSync(path.join(assets, 'sources/microduck/Depth.ubl'), 'utf8'));
    missing.evaluate('MB_editor.project.addLibraryFromString(depthText,"Depth",null)');
    assert.throws(() => missing.evaluate('new MB_Compiler(MB_editor.project).compiledBytesFor("microduckDepthCapture")'), /Missing MicroDuck function dependency/); passed++;
    const report = {tests: passed, passed, modules: 6, functions: compiled.length,
        max_function_bytes: Math.max(...compiled.map(f => f.bytes.length)), graphical: false,
        robot_hardware: false, imported_via: 'MB_editor.openLibraryFile -> MB_Project/MB_Parser, actual morph classes',
        compiled: compiled.map(f => ({name: f.name, chunk: f.id, bytes: f.bytes.length, sha256: sha(Buffer.from(f.bytes))}))};
    if (endpoint) {
        const results = [], errors = [];
        let activeSource = null;
        h.set('recordResult', (id, value) => results.push({id, value}));
        h.set('recordError', (id, message, location) => errors.push({id, message, location}));
        h.evaluate('MB_editor.showResult=recordResult; MB_editor.showChunkError=recordError; MB_editor.updateRunning=()=>{};');
        const connection = h.evaluate('MB_connection');
        await connection.connect('linux-loopback');
        async function until(check) {
            const deadline = Date.now() + 6000;
            while (!check()) {
                connection.processMessages();
                if (errors.length) throw new Error(JSON.stringify({errors, source: activeSource}));
                if (connection.port?.linuxPort?.error) throw new Error(connection.port.linuxPort.error);
                if (Date.now() > deadline) throw new Error('Typed library VM response timeout');
                await new Promise(resolve => setTimeout(resolve, 5));
            }
        }
        async function store(id, bytes, type) {
            const code = [...bytes]; while (code.length % 4) code.push(0);
            const crc = connection.codeManager.computeCRC(code);
            assert.equal(await connection.codeManager.storeChunkOnBoard(id, [type, ...code], crc), true);
        }
        try {
            await until(() => connection.isConnected());
            await connection.sendMsg('pingMsg'); await until(() => connection.lastPingRecvMSecs > 0);
            await connection.sendMsg('getVersionMsg'); await until(() => connection.vmVersion != null);
            assert.equal(connection.vmVersion, 417);
            for (const f of compiled) await store(f.id, f.bytes, 3); // upstream function chunk type
            const health = JSON.stringify({jsonrpc: '2.0', id: 1, result: {healthy: false, simulation: true, battery: {percent: 0}}});
            const missingHealth = JSON.stringify({jsonrpc: '2.0', id: 1, result: {healthy: false}});
            const reading = `microduckBatteryPercent '${health}'`;
            const checks = [
                [`microduckReadingStatus (${reading})`, 'ok'],
                [`'[microduck:readingValue]' (${reading})`, 0],
                [`microduckReadingUnit (${reading})`, '0.01%'],
                [`microduckReadingOrigin (${reading})`, 'simulation'],
                [`microduckReadingKnown (microduckBatteryPercent '${missingHealth}')`, false],
                [`microduckReadingStatus (microduckBatteryPercent '${missingHealth}')`, 'unknown'],
                [`microduckReadingStatus (microduckBatteryPercent '{"healthy":false}')`, 'invalid']
            ];
            if (mode !== 'simulated-sensors') {
                for (const f of ['HeadImu','Depth','Gamepad','RobotHealth','PadImu']) checks.push([`microduckReadingStatus (microduck${f}Capture)`, 'error']);
            } else {
                const depth = (getter, row = 1, col = 1) => `local 'sample' (microduckDepthCapture)\nlocal 'reading' (microduckDepthDistance sample ${row} ${col})\nmicroduckDepthRelease sample\nreturn (${getter} reading)`;
                checks.push([depth("'[microduck:readingValue]'"), 1000, false]);
                checks.push([depth('microduckReadingUnit'), 'mm', false]);
                checks.push([depth('microduckReadingOrigin'), 'local_ipc', false]);
                checks.push([depth('microduckReadingStatus', 1, 2), 'no_target', false]);
                checks.push([`local 'sample' (microduckGamepadCapture)\nlocal 'reading' (microduckGamepadAxis sample 0)\nmicroduckGamepadRelease sample\nreturn ('[microduck:readingValue]' reading)`, 1583, false]);
                checks.push([`local 'sample' (microduckGamepadCapture)\nlocal 'reading' (microduckGamepadAxis sample 1)\nmicroduckGamepadRelease sample\nreturn (microduckReadingKnown reading)`, false, false]);
            }
            const observations = [];
            for (const [source, expected, reporter = true] of checks) {
                activeSource = source;
                h.set('probeSource', source); h.set('probeReporter', reporter);
                const bytes = h.evaluate(`(()=>{const nodes=MB_Parser.parse(probeSource);const b=MB_Parser.blockFor(probeReporter?nodes[0]:nodes,probeReporter);return new MB_Compiler(MB_editor.project,MB_editor.codeManager).compiledBytesFor(b);})()`);
                await store(250, bytes, 2);
                const before = results.length;
                await connection.sendMsg('startChunkMsg', 250);
                await until(() => results.length > before);
                const actual = results.at(-1).value;
                assert.equal(actual, expected, source);
                observations.push({source, expected, actual, sha256: sha(Buffer.from(bytes))});
            }
            report.real_vm = {version: connection.vmVersion, board: connection.boardType,
                functions_uploaded_with_crc: compiled.length, checks: observations,
                simulated_sensor_services: mode === 'simulated-sensors', physical_robot: false};
        } finally {connection.disconnect();}
    }
    console.log(JSON.stringify(report));
}
main().catch(error => {console.error(error); process.exitCode = 1;});
