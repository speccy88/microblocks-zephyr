// SPDX-License-Identifier: MPL-2.0
// iPhone chrome around the unmodified, pinned MicroBlocks JS editor.
(() => {
    'use strict';
    let address = '', blocksVisible = false, profiles = [], lastPort = null;
    MicroBlocksIPhone.install(MB_CommPort, () => address);
    const native = () => window.webkit?.messageHandlers?.microblocks;
    const exports = new Map();
    const receive = MicroBlocksIPhone.receive;
    MicroBlocksIPhone.receive = event => {
        if (event.type === 'exported') {
            const done = exports.get(event.id);
            if (done) { exports.delete(event.id); done(event.saved ? {name: event.name, downloaded: true} : null); }
        } else receive(event);
    };
    // Preserve upstream save/cancel/unsaved behavior, including file naming.
    const save = MB_Editor.prototype.saveFileWithDialog;
    MB_Editor.prototype.saveFileWithDialog = function (data, name, kind, mime) {
        if (!native() || typeof data !== 'string') return save.call(this, data, name, kind, mime);
        if (new TextEncoder().encode(data).length > 4 * 1024 * 1024) {
            return Promise.reject(new Error('Project exceeds the 4 MiB iPhone export limit'));
        }
        return new Promise((resolve, reject) => {
            const id = 'export-' + Date.now();
            exports.set(id, resolve);
            try { native().postMessage({type: 'export', id, name, text: data}); }
            catch (error) { exports.delete(id); reject(error); }
        });
    };

    window.addEventListener('DOMContentLoaded', async () => {
        const toolbar = document.createElement('div');
        toolbar.className = 'iphone-toolbar';
        toolbar.innerHTML = '<button id="iphone-connect" type="button">Connect board</button>' +
            '<button id="iphone-blocks" type="button" aria-pressed="false">Blocks</button>' +
            '<button id="iphone-save" type="button">Save</button>' +
            '<span id="iphone-status" role="status" aria-live="polite">Offline editing</span>';
        document.querySelector('[data-ide="ide"]').prepend(toolbar);
        const sheet = document.createElement('dialog');
        sheet.className = 'iphone-connect-sheet';
        sheet.setAttribute('aria-labelledby', 'iphone-sheet-title');
        sheet.innerHTML = '<form method="dialog"><button class="iphone-dismiss" aria-label="Close connection sheet">Close</button></form>' +
            '<h1 id="iphone-sheet-title">Program over Wi-Fi</h1>' +
            '<p>Join the same network as your board. Its MicroBlocks Wi-Fi firmware must already be installed.</p>' +
            '<label for="iphone-board">Board</label><select id="iphone-board"></select>' +
            '<p id="iphone-board-note"></p><form id="iphone-address-form">' +
            '<label for="iphone-address">Board IP address</label>' +
            '<input id="iphone-address" type="text" inputmode="decimal" placeholder="192.168.1.42" autocomplete="off" autocapitalize="off" spellcheck="false" required>' +
            '<button id="iphone-open" type="submit">Connect</button></form>' +
            '<button id="iphone-close" type="button">Close link</button>' +
            '<p id="iphone-sheet-status" role="status"></p>' +
            '<p class="iphone-limit">USB-only boards, including Propeller 2, use the desktop editor. Bluetooth is planned.</p>';
        document.body.append(sheet);
        const $ = id => document.getElementById(id);
        const showSheet = () => sheet.showModal();
        $('iphone-connect').onclick = showSheet;
        $('iphone-save').onclick = () => MB_editor.saveProject();
        function layout() {
            if (typeof world === 'undefined' || !world || !MB_editor.palette) return;
            const compact = window.innerWidth < 600;
            document.body.classList.toggle('iphone-blocks-visible', blocksVisible);
            const show = !compact || blocksVisible;
            MB_editor.paletteWidth = show ? (compact ? Math.min(190, window.innerWidth * 0.46) : 240) : 0;
            MB_editor.palette[show ? 'show' : 'hide']();
            if (MB_editor.paletteResizer) MB_editor.paletteResizer.hide();
            IDE.resize();
            MB_editor.fixLayout();
            $('iphone-blocks').setAttribute('aria-pressed', String(blocksVisible));
        }
        $('iphone-blocks').onclick = () => { blocksVisible = !blocksVisible; layout(); };
        window.addEventListener('resize', layout);
        window.visualViewport?.addEventListener('resize', layout);
        $('iphone-close').onclick = () => { MB_connection.disconnect(); sheet.close(); };
        $('iphone-address-form').onsubmit = async event => {
            event.preventDefault();
            if (profiles.find(p => p.id === $('iphone-board').value)?.transport !== 'wifi') return;
            address = $('iphone-address').value.trim();
            try {
                MB_connection.disconnect();
                await MB_connection.connect('iphone-wifi');
                lastPort = MB_connection.port?.iphonePort;
                sheet.close();
            } catch (error) { $('iphone-sheet-status').textContent = error.message; }
        };
        try {
            profiles = (await (await fetch('iphone-boards.json')).json()).boards;
            for (const p of profiles) {
                const option = document.createElement('option');
                option.value = p.id; option.textContent = p.name; $('iphone-board').append(option);
            }
        } catch (_) { $('iphone-sheet-status').textContent = 'Board profiles could not load. Rebuild the app bundle.'; }
        function profileChanged() {
            const profile = profiles.find(p => p.id === $('iphone-board').value);
            $('iphone-board-note').textContent = profile?.note || 'Board unavailable';
            $('iphone-open').disabled = profile?.transport !== 'wifi' || !native();
            $('iphone-address').disabled = profile?.transport !== 'wifi';
            if (!native()) $('iphone-sheet-status').textContent = 'Browser preview: offline editing only. Install the native app for Wi-Fi.';
        }
        $('iphone-board').onchange = profileChanged;
        profileChanged();

        // Keep original run/stop/project controls; route connection UI to the
        // only supported phone transport and make first-flash actions explicit.
        const call = GP.apiCall.bind(GP);
        GP.apiCall = (endpoint, params, callback) => {
            if (endpoint === 'board.connect') { showSheet(); if (callback) callback(0); return; }
            if (endpoint === 'board.disconnect') { MB_connection.disconnect(); if (callback) callback(0); return; }
            if (endpoint.startsWith('board.installVM') || endpoint === 'board.toggleBLE') {
                MB_editor.inform('Install or update board firmware using the desktop USB editor.');
                if (callback) callback(0); return;
            }
            return call(endpoint, params, callback);
        };
        // Measure the real workspace: safe-area/keyboard/rotation and toolbar
        // height cannot be represented by the upstream desktop constants.
        IDE.resize = () => {
            const wrapper = document.querySelector('[data-ide="canvas-wrapper"]') || document.querySelector('.workspace__canvas-wrapper');
            const canvas = document.querySelector('#canvas');
            if (!wrapper || !canvas || typeof world === 'undefined' || !world) return;
            const rect = wrapper.getBoundingClientRect();
            const width = Math.max(1, Math.floor(rect.width)), height = Math.max(1, Math.floor(rect.height));
            canvas.style.width = width + 'px'; canvas.style.height = height + 'px';
            canvas.width = width * 2; canvas.height = height * 2;
            call('ide.resize', [width, height]);
        };
        const timer = setInterval(() => {
            if (typeof world === 'undefined' || !world || !MB_editor.palette) return;
            clearInterval(timer); layout();
        }, 100);
        setInterval(() => {
            const verified = MB_connection.port?.iphonePort?.isConnected() &&
                MB_connection.connectedToBoard() && Number.isInteger(MB_connection.vmVersion);
            const status = verified ? (MB_connection.boardType || 'Board') + ' · VM ' + MB_connection.vmVersion :
                lastPort?.error || (MB_connection.port?.iphonePort ? 'Waiting for board reply…' : 'Offline editing');
            $('iphone-status').textContent = status;
            $('iphone-status').dataset.connected = String(!!verified);
            // Never leave run/stop enabled against an unverified native link.
            document.querySelectorAll('.top-bar__controls-run, .top-bar__controls-stop').forEach(button => {
                button.disabled = !verified;
            });
        }, 500);
    });
})();
