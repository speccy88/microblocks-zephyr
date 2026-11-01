// SPDX-License-Identifier: MPL-2.0
// Local iOS transport overlay. The pinned compiler and engine stay unchanged.
(function (root) {
    'use strict';
    const MAX_FRAME = 1024, MAX_INPUT = 131072, MAX_OUTPUT = 32768;
    let active = null, serial = 0;
    const installed = new WeakSet();
    const compilers = new WeakSet();
    const nativeBridge = () => root.webkit?.messageHandlers?.microblocks;

    class NativePort {
        constructor(address, bridge = nativeBridge()) {
            if (!bridge || typeof bridge.postMessage !== 'function') {
                throw new Error('Wireless programming requires the iPhone app. This browser is offline editing only.');
            }
            if (active) active.disconnect();
            this.id = String(++serial);
            this.bridge = bridge;
            this.ready = false;
            this.closed = false;
            this.input = [];
            this.size = 0;
            this.pending = 0;
            this.error = null;
            active = this;
            this.timeout = setTimeout(() => this.fail('Board connection timed out. Check Wi-Fi and Local Network permission.'), 10000);
            try { this.post('connect', {address}); }
            catch (error) { this.fail(error.message); throw error; }
        }
        post(type, fields = {}) { this.bridge.postMessage({type, id: this.id, ...fields}); }
        isConnected() { return this.ready && !this.closed; }
        receive(event) {
            if (this.closed || event.id !== this.id) return;
            if (event.type === 'ready' && !this.ready) {
                this.ready = true;
                clearTimeout(this.timeout);
            } else if (event.type === 'data' && this.ready) {
                const bytes = event.bytes;
                if (!Array.isArray(bytes) || !bytes.length || bytes.length > 4096 ||
                    bytes.some(b => !Number.isInteger(b) || b < 0 || b > 255) ||
                    this.size + bytes.length > MAX_INPUT) {
                    this.fail('Board receive buffer limit or binary format exceeded'); return;
                }
                this.input.push(Uint8Array.from(bytes));
                this.size += bytes.length;
                if (this.dataArrived) this.dataArrived();
            } else if (event.type === 'sent' && this.ready) {
                if (!Number.isInteger(event.count) || event.count < 1 || event.count > this.pending) {
                    this.fail('Invalid native write acknowledgement'); return;
                }
                this.pending -= event.count;
            } else if (event.type === 'closed' || event.type === 'error') {
                this.fail(event.reason || 'Board link closed');
            } else { this.fail('Unexpected board transport event'); }
        }
        read() {
            const bytes = new Uint8Array(this.size);
            let offset = 0;
            for (const chunk of this.input) { bytes.set(chunk, offset); offset += chunk.length; }
            this.input = []; this.size = 0;
            return bytes;
        }
        write(bytes) {
            if (!(bytes instanceof Uint8Array)) throw new Error('Binary write required');
            if (!this.isConnected() || !bytes.length) return 0;
            const count = Math.min(bytes.length, MAX_FRAME, MAX_OUTPUT - this.pending);
            if (count <= 0) return 0;
            this.pending += count;
            try { this.post('write', {bytes: Array.from(bytes.subarray(0, count))}); }
            catch (error) { this.fail(error.message); return 0; }
            return count;
        }
        fail(reason) { this.error = reason; this.disconnect(); }
        disconnect() {
            if (this.closed) return;
            this.closed = true; this.ready = false;
            clearTimeout(this.timeout);
            this.input = []; this.size = 0; this.pending = 0;
            if (active === this) active = null;
            try { this.post('close'); } catch (_) { /* already unavailable */ }
        }
    }

    function install(CommPort, address, bridge = nativeBridge) {
        if (installed.has(CommPort)) return;
        const connect = CommPort.prototype.connect;
        const disconnect = CommPort.prototype.disconnect;
        CommPort.prototype.connect = function (type, frame) {
            if (type !== 'iphone-wifi') return connect.call(this, type, frame);
            this.disconnect();
            this.iphonePort = new NativePort(address(), bridge());
            this.iphonePort.dataArrived = () => { if (this.dataArrived) this.dataArrived(); };
        };
        CommPort.prototype.disconnect = function () {
            if (this.iphonePort) { this.iphonePort.disconnect(); this.iphonePort = null; }
            return disconnect.call(this);
        };
        for (const name of ['isConnected', 'read', 'write']) {
            const original = CommPort.prototype[name];
            CommPort.prototype[name] = function (...args) {
                return this.iphonePort ? this.iphonePort[name](...args) : original.apply(this, args);
            };
        }
        installed.add(CommPort);
    }
    function installCompiler(Compiler) {
        if (compilers.has(Compiler)) return;
        const init = Compiler.prototype.initPrimsets, append = Compiler.prototype.appendLiterals;
        Compiler.prototype.initPrimsets = function () {
            init.call(this);
            // Each canonical board port registers its named hardware table at
            // IOPrims, index 3 in the independently pinned v417 interp.h.
            if (this.primsets.get('io') !== 3) throw new Error('Review changed upstream IO primitive layout');
            this.primsets = new Map(this.primsets);
            for (const name of ['rlcd', 'fruitJam', 'xrp']) {
                if (this.primsets.has(name)) throw new Error('Review changed upstream board primitive layout');
                this.primsets.set(name, 3);
            }
        };
        Compiler.prototype.appendLiterals = function (instructions) {
            for (const item of instructions) {
                if (Array.isArray(item) && ['commandPrimitive', 'reporterPrimitive'].includes(item[0]) &&
                    !this.primsets.has(item[2])) {
                    throw new Error('Unsupported primitive set in iPhone board profile: ' + item[2]);
                }
            }
            return append.call(this, instructions);
        };
        compilers.add(Compiler);
    }
    const api = {NativePort, install, installCompiler, MAX_FRAME, MAX_INPUT, MAX_OUTPUT,
        receive: event => { if (active) active.receive(event); },
        close: () => { if (active) active.fail('Link closed when app left the foreground. Connect to resume.'); },
        status: () => active ? {ready: active.ready, pending: active.pending, received: active.size} : {ready: false}};
    root.MicroBlocksIPhone = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
