// SPDX-License-Identifier: MPL-2.0
// Local target policy; no edits to upstream source or implicit connections.
(function (root) {
    'use strict';
    const installed = new WeakMap();
    const profiles = Object.freeze({
        development: Object.freeze({id: 'development', name: 'Experimental Linux development', placeholder: false}),
        'raspberry-pi5': Object.freeze({id: 'raspberry-pi5', name: 'Raspberry Pi 5', placeholder: false}),
        microduck: Object.freeze({id: 'microduck', name: 'MicroDuck Rockchip RK3566', placeholder: true})
    });
    function get(id) {
        if (!Object.hasOwn(profiles, id)) throw Error('Unknown JavaScript editor target');
        return profiles[id];
    }
    function canConnect(profile, location) {
        if (profile.placeholder) return false;
        const url = new URL(location.href);
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
            if (profile.placeholder) throw Error('MicroDuck is an experimental placeholder; offline editing only');
            if (id !== 'development' && (!canConnect(profile, location) || type !== 'linux-loopback')) {
                throw Error('Use the Pi-hosted editor through its local SSH tunnel and Connect local VM; hosted WSS is not commissioned');
            }
            return original.call(this, type, ...args);
        };
        installed.set(CommPort, id);
        return profile;
    }
    const api = Object.freeze({get, canConnect, install});
    root.MicroBlocksTarget = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
