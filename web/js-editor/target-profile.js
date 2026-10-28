// SPDX-License-Identifier: MPL-2.0
// Local target policy; no edits to upstream source or implicit connections.
(function (root) {
    'use strict';
    const installed = new WeakMap();
    const source = typeof MicroBlocksJSTargets === 'object' ? MicroBlocksJSTargets : require('../../dependencies/editor-targets.json').targets;
    function freeze(value) {if(value && typeof value === 'object'){for(const child of Object.values(value))freeze(child);Object.freeze(value);}return value;}
    const profiles = freeze(Object.fromEntries(Object.entries(JSON.parse(JSON.stringify(source))).map(([id,value])=>[id,{...value,id}])));
    function get(id) {
        if (!Object.hasOwn(profiles, id)) throw Error('Unknown JavaScript editor target');
        return profiles[id];
    }
    function canConnect(profile, location) {
        if (profile.placeholder || profile.connection_enabled === false) return false;
        const url = new URL(location.href);
        if (profile.kind === 'serial') return !url.username && !url.password &&
            (url.protocol === 'https:' || url.protocol === 'http:' && url.hostname === '127.0.0.1');
        return url.protocol === 'http:' && url.hostname === '127.0.0.1' &&
            !url.username && !url.password && /^\d+$/.test(url.port) &&
            Number(url.port) >= 1024 && Number(url.port) <= 65535;
    }
    function install(CommPort, id, location) {
        const profile = get(id);
        if (typeof CommPort?.prototype?.connect !== 'function') throw Error('Upstream target connection hook changed');
        if (installed.has(CommPort)) {
            if (installed.get(CommPort) !== id) throw Error('Cannot change an installed editor target');
            return profile;
        }
        const original = CommPort.prototype.connect;
        CommPort.prototype.connect = function (type, ...args) {
            if (profile.placeholder || profile.connection_enabled === false) throw Error(profile.name + ' is an experimental placeholder; offline editing only');
            if (profile.kind === 'serial') {
                if (!canConnect(profile, location) || !(type === 'serial' || type === 'board-wss' && profile.secure_websocket)) throw Error('Use the selected target USB connection or its explicitly supported secure WebSocket');
                return original.call(this, type, ...args);
            }
            if (id !== 'development' && (!canConnect(profile, location) || type !== 'linux-loopback')) {
                throw Error('Use the Pi-hosted editor through its local SSH tunnel and Connect local VM; hosted WSS is not commissioned');
            }
            return original.call(this, type, ...args);
        };
        installed.set(CommPort, id);
        return profile;
    }
    const firmwareInstalled = new WeakSet();
    function protectFirmware(Firmware, id) {
        if(id==='development'||!Firmware)return;
        get(id);
        if(typeof Firmware.installVM!=='function')throw Error('Upstream firmware entry point changed');
        if(firmwareInstalled.has(Firmware))return;
        Firmware.installVM=()=>{throw Error('Use the project firmware installation procedure; this editor preview preserves the existing runtime');};
        firmwareInstalled.add(Firmware);
    }
    const api = Object.freeze({get, canConnect, install, protectFirmware});
    root.MicroBlocksTarget = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
