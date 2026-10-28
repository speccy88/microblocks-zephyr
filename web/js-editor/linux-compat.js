// SPDX-License-Identifier: MPL-2.0
// Local adapter. The pinned upstream editor sources remain unchanged.
(function (root) {
    'use strict';
    const MAX_FRAME = 4096, MAX_INPUT = 131072, MAX_OUTPUT = 32768;
    const installed = new WeakMap();

    class LoopbackPort {
        constructor(location, Socket) {
            const page = new URL(location.href);
            if (page.protocol !== 'http:' || page.hostname !== '127.0.0.1' ||
                page.username || page.password || !/^\d+$/.test(page.port) ||
                Number(page.port) < 1024 || Number(page.port) > 65535) {
                throw new Error('Linux VM connection requires the local packaged editor on 127.0.0.1');
            }
            this.input = [];
            this.size = 0;
            this.ready = false;
            this.error = null;
            this.socket = new Socket('ws://' + page.host + '/ws/vm');
            this.socket.binaryType = 'arraybuffer';
            this.timeout = setTimeout(() => this.fail('Local VM connection timed out'), 5000);
            this.socket.onopen = () => {};
            this.socket.onmessage = event => {
                if (this.socket.readyState !== 1) return;
                const data = event.data;
                // The existing verified bridge sends this control marker only
                // after acquiring and validating the VM PTY. An open socket
                // alone is not a ready VM transport.
                if (!this.ready) {
                    if (data !== 'ready') { this.fail('Expected local VM readiness marker'); return; }
                    this.ready = true;
                    clearTimeout(this.timeout);
                    return;
                }
                if (!(data instanceof ArrayBuffer) && !(data instanceof Uint8Array)) {
                    this.fail('VM transport requires binary data');
                    return;
                }
                const bytes = new Uint8Array(data);
                if (!bytes.length || bytes.length > MAX_FRAME || this.size + bytes.length > MAX_INPUT) {
                    this.fail('VM receive buffer limit exceeded');
                    return;
                }
                this.input.push(bytes.slice());
                this.size += bytes.length;
                if (this.dataArrived) this.dataArrived();
            };
            this.socket.onerror = () => this.fail('Local VM connection failed');
            this.socket.onclose = () => {
                clearTimeout(this.timeout);
                this.ready = false;
                this.input = [];
                this.size = 0;
            };
        }
        isConnected() { return this.socket.readyState === 1 && this.ready; }
        fail(reason) { this.error = reason; this.disconnect(); }
        disconnect() {
            clearTimeout(this.timeout);
            this.ready = false;
            this.input = [];
            this.size = 0;
            if (this.socket.readyState < 2) this.socket.close();
        }
        read() {
            const result = new Uint8Array(this.size);
            let offset = 0;
            for (const bytes of this.input) { result.set(bytes, offset); offset += bytes.length; }
            this.input = [];
            this.size = 0;
            return result;
        }
        write(bytes) {
            if (!(bytes instanceof Uint8Array) || !bytes.length || bytes.length > MAX_FRAME) {
                throw new Error('VM write requires 1..4096 binary bytes');
            }
            if (!this.isConnected() || this.socket.bufferedAmount + bytes.length > MAX_OUTPUT) return 0;
            this.socket.send(bytes.slice());
            return bytes.length;
        }
    }

    function install(Compiler, CommPort, location, Socket, aliases = {linux: 3, microduck: 22}, functionNames = []) {
        const mappings = Object.entries(aliases);
        const signature = JSON.stringify([mappings.slice().sort(), [...functionNames].sort()]);
        if (installed.has(Compiler)) {
            if (installed.get(Compiler) !== signature) throw Error('Cannot change installed target compiler mappings');
            return;
        }
        const requiredFunctions = new Set(functionNames);
        for (const [name, index] of mappings) {
            if (!/^[A-Za-z][A-Za-z0-9_]*$/.test(name) || !Number.isInteger(index) || index < 0 || index > 63) {
                throw Error('Invalid target primitive-set mapping');
            }
        }
        const init = Compiler.prototype.initPrimsets;
        const literals = Compiler.prototype.appendLiterals;
        const primitive = Compiler.prototype.primitive;
        Compiler.prototype.primitive = function (op, inputs, isCommand) {
            if (requiredFunctions.has(op) && !this.codeManager.functionChunkIDs.has(op)) {
                throw new Error('Missing target function dependency: ' + op);
            }
            if (typeof op === 'string' && /^microduck[A-Z]/.test(op) &&
                !this.codeManager.functionChunkIDs.has(op)) {
                throw new Error('Missing MicroDuck function dependency: ' + op);
            }
            return primitive.call(this, op, inputs, isCommand);
        };
        Compiler.prototype.initPrimsets = function () {
            init.call(this);
            this.primsets = new Map(this.primsets);
            if ([...this.primsets.values()].some(value => value >= 22)) {
                throw new Error('Upstream primitive-set layout changed; review the target profile');
            }
            for (const [name, index] of mappings) {
                if (this.primsets.has(name) && this.primsets.get(name) !== index) throw Error('Target primitive-set conflict: ' + name);
                this.primsets.set(name, index);
            }
        };
        Compiler.prototype.appendLiterals = function (instructions) {
            for (const item of instructions) {
                if (Array.isArray(item) && ['commandPrimitive', 'reporterPrimitive'].includes(item[0]) &&
                    !this.primsets.has(item[2])) {
                    throw new Error('Unsupported primitive set in selected target: ' + item[2]);
                }
            }
            return literals.call(this, instructions);
        };
        const connect = CommPort.prototype.connect;
        CommPort.prototype.connect = function (type, frame) {
            if (type !== 'linux-loopback') return connect.call(this, type, frame);
            this.disconnect();
            this.linuxPort = new LoopbackPort(location, Socket);
            this.linuxPort.dataArrived = () => { if (this.dataArrived) this.dataArrived(); };
        };
        for (const name of ['isConnected', 'read', 'write', 'disconnect']) {
            const original = CommPort.prototype[name];
            CommPort.prototype[name] = function (...args) {
                return this.linuxPort ? this.linuxPort[name](...args) : original.apply(this, args);
            };
        }
        installed.set(Compiler, signature);
    }
    const api = Object.freeze({LoopbackPort, install, MAX_FRAME, MAX_INPUT, MAX_OUTPUT});
    root.MicroBlocksLinux = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
