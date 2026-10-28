// SPDX-License-Identifier: MIT
// Test-only DOM/canvas fixture. No pixels, browser or graphical acceptance.
// Parser, project, block morphs, functions and compiler are pristine upstream.
'use strict';
const vm = require('node:vm'), fs = require('node:fs'), path = require('node:path');
const crypto = require('node:crypto');
function element(tag) {
    const e = {tagName: tag.toUpperCase(), style: {}, dataset: {}, children: [], width: 300, height: 150,
        appendChild(child) {this.children.push(child); return child;}, removeChild() {},
        setAttribute() {}, addEventListener() {}, removeEventListener() {}, focus() {}, select() {},
        getBoundingClientRect() {return {width: 300, height: 150, x: 0, y: 0, left: 0, top: 0};},
        toDataURL() {return 'data:image/png;base64,';}};
    const noop = () => {};
    const ctx = {canvas: e, backingStorePixelRatio: 1, measureText(s) {return {width: String(s).length * 7, actualBoundingBoxAscent: 10, actualBoundingBoxDescent: 3};},
        getImageData(x, y, w, h) {return {data: new Uint8ClampedArray(Math.max(4, w * h * 4)), width: w, height: h};},
        createImageData(w, h) {return {data: new Uint8ClampedArray(w * h * 4)};},
        createLinearGradient() {return {addColorStop: noop};}, createRadialGradient() {return {addColorStop: noop};}};
    e.getContext = () => new Proxy(ctx, {get(o, key) {
        if (String(key).endsWith('BackingStorePixelRatio')) return 1;
        return key in o ? o[key] : noop;
    }});
    return e;
}
function load(assets, options = {}) {
    const body = element('body'), document = {body, documentElement: {clientWidth: 1024, clientHeight: 768},
        createElement: element, addEventListener() {}, dispatchEvent() {},
        getElementById() {return null;}, querySelector() {return element('canvas');}};
    const sandbox = {console: options.console || console, TextEncoder, TextDecoder, Uint8Array, Uint8ClampedArray, ArrayBuffer,
        URL, setTimeout, clearTimeout, setInterval() {return 0;}, requestAnimationFrame() {}, document,
        location: options.location || {href: 'http://127.0.0.1:18876/'}, WebSocket: options.Socket,
        async fetch(name) {
            if (typeof name !== 'string' || name.includes('..') || name.includes(':') || name.startsWith('/')) throw new Error('Fixture accepts packaged paths only');
            const p = path.join(assets, name);
            return {ok: fs.existsSync(p), text: async () => fs.readFileSync(p, 'utf8')};
        },
        navigator: {userAgent: 'Headless logic fixture', platform: 'test', serial: options.serial},
        Image: class {}, HTMLCanvasElement: class {}, CanvasRenderingContext2D: class {},
        GetText: {localize: s => s, getLanguage: () => 'en', locales: {}, currentLocale: 'en'}, CustomEvent: class {},
        storeIDEProperty() {}, localized: s => s, MB: {},
        MB_editor: {project: null, error() {}, palette: null}};
    sandbox.window = sandbox; sandbox.devicePixelRatio = 1; sandbox.addEventListener = () => {};
    const context = vm.createContext(sandbox);
    const manifest = JSON.parse(fs.readFileSync(path.join(assets, 'source-manifest.json')));
    for (const name of ['morphic.js', 'mb-support.js', 'mb-blocks.js', 'mb-slots.js', 'mb-code-manager.js',
        'mb-compiler.js', 'mb-comm-port.js', 'mb-connection.js', 'mb-parser.js', 'mb-function.js',
        'mb-project.js', 'mb-specs.js', 'mb-files.js', 'mb-editor.js', 'mb-decompiler.js']) {
        const p = 'engine/' + name, data = fs.readFileSync(path.join(assets, p));
        const record = manifest.files.find(f => f.path === p);
        if (!record || crypto.createHash('sha256').update(data).digest('hex') !== record.sha256) throw new Error('Upstream source mismatch: ' + p);
        vm.runInContext(data.toString('utf8'), context, {filename: p, timeout: 10000});
    }
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../web/js-editor/linux-compat.js'), 'utf8'), context);
    vm.runInContext(fs.readFileSync(path.join(assets, 'target-config.js'), 'utf8'), context);
    vm.runInContext(fs.readFileSync(path.join(assets, 'target-profile.js'), 'utf8'), context);
    vm.runInContext(fs.readFileSync(path.join(assets, 'board-transport.js'), 'utf8'), context);
    vm.runInContext(fs.readFileSync(path.join(__dirname, '../../web/js-editor/legacy-slots.js'), 'utf8'), context);
    if (options.readback !== false) {
        vm.runInContext(fs.readFileSync(path.join(__dirname, '../../web/js-editor/readback-compat.js'), 'utf8'), context);
        vm.runInContext('MicroBlocksReadback.install(MB_Decompiler,MB_CodeManager,ScriptsMorph,()=>MB_editor);', context);
    }
    vm.runInContext(`MicroBlocksLinux.install(MB_Compiler, MB_CommPort, location, WebSocket,MicroBlocksJSProfile.primitive_sets,MicroBlocksJSProfile.function_names);
        if(MicroBlocksJSProfile.kind==='serial')MicroBlocksBoardTransport.install(MB_CommPort,MB_Connection,MicroBlocksJSProfile,navigator.serial,()=>MB_editor);
        MicroBlocksTarget.install(MB_CommPort,MicroBlocksJSProfile.id,location);
        MicroBlocksLegacySlots.install(MB_Specs,SyntaxElementMorph,MicroBitDisplaySlotMorph,ArgMorph,Color,Point,MenuMorph);
        MB_Specs.initialize();`, context, {timeout: 10000});
    return {context, evaluate: (s, timeout = 20000) => vm.runInContext(s, context, {timeout}),
        set: (name, value) => {context[name] = value;}};
}
module.exports = {load};
