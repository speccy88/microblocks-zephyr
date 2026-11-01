// SPDX-License-Identifier: MPL-2.0
// Real browser WebSocket bridge. Never impersonates WKWebView or changes Origin.
(function (root) {
    'use strict';
    const privateIP = value => {
        if (!/^(?:0|[1-9]\d{0,2})(?:\.(?:0|[1-9]\d{0,2})){3}$/.test(value)) return false;
        const p = value.split('.').map(Number);
        return p.every(n => n <= 255) && (p[0] === 10 || (p[0] === 172 && p[1] >= 16 && p[1] <= 31) || (p[0] === 192 && p[1] === 168));
    };
    const boardURL = value => {
        const ip = String(value).trim();
        if (!privateIP(ip)) throw new Error('Enter a private IPv4 board address, such as 192.168.1.42.');
        return 'http://' + ip + '/?layout=mobile';
    };
    function create({profile, location, Socket, receive, schedule = setTimeout, cancel = clearTimeout}) {
        const supported = ['rlcd', 'fruit-jam', 'xrp'];
        const local = location.protocol === 'http:' && (privateIP(location.hostname) || ['127.0.0.1', 'localhost'].includes(location.hostname));
        const available = profile.runtime === 'board' && local && supported.includes(profile.board);
        let session = null;
        const close = () => {
            const previous = session; session = null;
            if (!previous) return;
            cancel(previous.timer);
            previous.socket.onmessage = previous.socket.onclose = previous.socket.onerror = null;
            previous.socket.close(1000, 'Editor link closed');
        };
        const emit = (s, type, fields = {}) => {
            if (session === s) receive({type, id: s.id, ...fields});
        };
        const fail = (s, reason) => { if (session === s) { emit(s, 'error', {reason}); close(); } };
        const drain = s => {
            if (session !== s) return;
            if (s.socket.bufferedAmount === 0 && s.owed) {
                const count = s.owed; s.owed = 0; s.timer = null;
                emit(s, 'sent', {count});
            } else if (s.owed) s.timer = schedule(() => drain(s), 20);
        };
        const help = () => profile.runtime === 'pages' ?
            'Touch editing is available here. To program a Wi-Fi board, open its local website. This HTTPS page cannot use the current plain-HTTP board socket. Safari on iPhone has no Web Serial or Web Bluetooth path here.' :
            available ? 'Connect uses this board’s same-origin /ws/vm. Compatible Wi-Fi firmware is required. A socket alone does not confirm the VM is ready.' :
            'Wireless programming is unavailable for this target or origin. Use the supported desktop connection. Propeller 2 uses desktop USB serial.';
        return {
            ...profile, startupEvent: profile.startupEvent || 'microblocks-mobile-assets',
            available, boardURL, privateIP, help,
            canConnect: p => available && p.id === profile.board && p.transport === 'wifi',
            bridge: {postMessage(event) {
                if (event.type === 'connect') {
                    if (!available || event.address !== location.hostname) throw new Error(help());
                    close();
                    const endpoint = new URL('/ws/vm', location.href);
                    endpoint.protocol = 'ws:';
                    let socket;
                    try { socket = new Socket(endpoint.href); }
                    catch (error) { throw new Error('Cannot open the board WebSocket: ' + error.message); }
                    const s = {id: event.id, socket, ready: false, owed: 0, timer: null};
                    session = s; socket.binaryType = 'arraybuffer';
                    socket.onmessage = e => {
                        if (session !== s) return;
                        if (!s.ready) {
                            if (e.data !== 'ready') { fail(s, 'Expected the board ready marker.'); return; }
                            s.ready = true; emit(s, 'ready'); return;
                        }
                        if (!(e.data instanceof ArrayBuffer) || !e.data.byteLength || e.data.byteLength > 4096) {
                            fail(s, 'Unexpected board frame or receive bound exceeded.'); return;
                        }
                        emit(s, 'data', {bytes: Array.from(new Uint8Array(e.data))});
                    };
                    socket.onerror = () => fail(s, 'Board connection failed. Check its address, firmware, network permission and controller availability.');
                    socket.onclose = () => { if (session === s) { emit(s, 'closed', {reason: 'Board link closed. Connect to retry.'}); close(); } };
                } else if (event.type === 'close') {
                    if (session?.id === event.id) close();
                } else if (event.type === 'write') {
                    const s = session, bytes = event.bytes;
                    if (!s || s.id !== event.id || !s.ready || s.socket.readyState !== 1) return;
                    if (!Array.isArray(bytes) || !bytes.length || bytes.length > 1024 ||
                        bytes.some(b => !Number.isInteger(b) || b < 0 || b > 255) ||
                        s.socket.bufferedAmount + bytes.length > 32768) {
                        fail(s, 'Board output queue or binary format exceeded.'); return;
                    }
                    try { s.socket.send(Uint8Array.from(bytes)); s.owed += bytes.length; }
                    catch (error) { fail(s, error.message); return; }
                    if (s.timer === null) s.timer = schedule(() => drain(s), 0);
                }
            }},
            close
        };
    }
    if (typeof module === 'object' && module.exports) module.exports = {create, privateIP, boardURL};
    else {
        const config = JSON.parse(document.getElementById('mobile-load-config').textContent).profile;
        const map = {'waveshare': 'rlcd', 'xrp-rp2350': 'xrp', 'propeller2': 'p2', 'esp32p4': 'p4', 'fruit-jam': 'fruit-jam'};
        const selected = new URLSearchParams(location.search).get('board');
        if (config.runtime === 'pages' && map[selected]) config.board = map[selected];
        root.MicroBlocksBrowser = create({profile: config, location: root.location, Socket: root.WebSocket,
            receive: e => root.MicroBlocksIPhone.receive(e)});
        document.addEventListener('visibilitychange', () => { if (document.hidden) root.MicroBlocksIPhone.close(); });
    }
})(globalThis);
