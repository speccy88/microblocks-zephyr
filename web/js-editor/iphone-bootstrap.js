// SPDX-License-Identifier: MPL-2.0
// iPhone chrome around the unmodified, pinned MicroBlocks JS editor.
(() => {
    'use strict';
    let address = '', blocksVisible = false, profiles = [], lastPort = null, connectingPort = null;
    MicroBlocksIPhone.installCompiler(MB_Compiler);
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
        const icon = path => '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + path + '"/></svg>';
        const button = (id, label, path, state = '') => '<button id="' + id + '" type="button" aria-label="' +
            label + '" title="' + label + '" ' + state + '>' + icon(path) + '</button>';
        toolbar.innerHTML = button('iphone-menu', 'Menu', 'M4 6h16M4 12h16M4 18h16', 'aria-expanded="false" aria-controls="iphone-menu-panel"') +
            button('iphone-blocks', 'Blocks', 'M4 4h6v3h4V4h6v7h-3v4h3v5H4v-5h3v-4H4z', 'aria-pressed="false"') +
            button('iphone-hand', 'Pan workspace', 'M8 12V6a2 2 0 0 1 4 0v5-7a2 2 0 0 1 4 0v7-4a2 2 0 0 1 4 0v8c0 5-3 7-7 7-3 0-5-3-7-6l-2-3a2 2 0 0 1 3-2l3 3', 'aria-pressed="false"') +
            '<span class="iphone-toolbar-spacer"></span>' +
            button('iphone-connect', 'Connect board', 'M3 8a14 14 0 0 1 18 0M6 12a9 9 0 0 1 12 0M9 16a4 4 0 0 1 6 0M12 20h.01');
        const ide = document.querySelector('[data-ide="ide"]');
        ide.prepend(toolbar);
        const menu = document.createElement('div');
        menu.id = 'iphone-menu-panel'; menu.className = 'iphone-menu-panel'; menu.hidden = true;
        menu.innerHTML = '<div id="iphone-original-menus"></div>' +
            '<button id="iphone-save" type="button">Save project</button>' +
            '<button id="iphone-focus" type="button">Hide controls</button>' +
            '<p>Drag empty space to pan. Drag blocks to move them. Use two fingers to pan and pinch to zoom. Hand mode pans over blocks.</p>' +
            '<span id="iphone-status" role="status" aria-live="polite">Offline editing</span>';
        ide.append(menu);
        const restore = document.createElement('div');
        restore.className = 'iphone-restore';
        restore.innerHTML = button('iphone-restore', 'Show controls', 'M4 6h16M4 12h16M4 18h16');
        ide.append(restore);
        const tools = document.createElement('div');
        tools.className = 'iphone-view';
        tools.innerHTML = '<button id="iphone-view" type="button" aria-label="View tools" title="View tools" aria-describedby="iphone-zoom-status" aria-expanded="false"><span id="iphone-scale" aria-hidden="true">100%</span></button>' +
            '<output id="iphone-zoom-status" class="iphone-sr-only" role="status">Workspace zoom 100%</output>';
        document.querySelector('.workspace__canvas-wrapper').append(tools);
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
        let previousKeyboardDelegate = false;
        function closeMenu() {
            menu.hidden = true; $('iphone-menu').setAttribute('aria-expanded', 'false');
            if (typeof Menus !== 'undefined') Menus.close();
        }
        const showSheet = () => {
            closeMenu();
            // Follow the editor's HTML-dialog keyboard contract. Morphic's
            // hidden textarea must not reclaim the keys from this form.
            MB_editor.endOpenEdit();
            previousKeyboardDelegate = GP.delegateKeyboardEvents;
            GP.delegateKeyboardEvents = true;
            sheet.showModal();
        };
        sheet.addEventListener('focusin', () => { GP.delegateKeyboardEvents = true; });
        sheet.addEventListener('close', () => {
            GP.delegateKeyboardEvents = previousKeyboardDelegate;
            if (connectingPort) { MB_connection.disconnect(); connectingPort = null; }
            profileChanged();
        });
        $('iphone-connect').onclick = showSheet;
        $('iphone-save').onclick = () => MB_editor.saveProject();
        $('iphone-menu').onclick = () => {
            if (!menu.hidden) closeMenu();
            else { menu.hidden = false; $('iphone-menu').setAttribute('aria-expanded', 'true'); }
        };
        document.addEventListener('keydown', event => { if (event.key === 'Escape') closeMenu(); });
        const setFocus = value => {
            closeMenu(); blocksVisible = false;
            document.body.classList.toggle('iphone-focus', value);
            document.body.classList.remove('iphone-tools-visible');
            $('iphone-view').setAttribute('aria-expanded', 'false'); layout();
        };
        $('iphone-focus').onclick = () => setFocus(true);
        $('iphone-restore').onclick = () => { setFocus(false); $('iphone-menu').focus(); };
        $('iphone-view').onclick = () => {
            const visible = document.body.classList.toggle('iphone-tools-visible');
            $('iphone-view').setAttribute('aria-expanded', String(visible));
        };
        function layout() {
            if (typeof world === 'undefined' || !world || !MB_editor.palette) return;
            const compact = window.innerWidth < 600;
            document.body.classList.toggle('iphone-blocks-visible', blocksVisible);
            const show = blocksVisible && !document.body.classList.contains('iphone-focus');
            MB_editor.paletteWidth = show ? (compact ? Math.min(190, window.innerWidth * 0.46) : 240) : 0;
            MB_editor.palette[show ? 'show' : 'hide']();
            if (MB_editor.paletteResizer) MB_editor.paletteResizer.hide();
            IDE.resize();
            MB_editor.fixLayout();
            $('iphone-blocks').setAttribute('aria-pressed', String(blocksVisible));
        }
        $('iphone-blocks').onclick = () => { blocksVisible = !blocksVisible; layout(); };
        const canvas = document.querySelector('#canvas');
        canvas.setAttribute('role', 'img'); canvas.setAttribute('aria-label', 'Programming workspace');
        // Run before gesture capture consumes an empty-space pan.
        canvas.addEventListener('touchstart', closeMenu, {capture: true, passive: true});
        canvas.addEventListener('mousedown', closeMenu);
        window.addEventListener('resize', layout);
        window.visualViewport?.addEventListener('resize', layout);
        $('iphone-close').onclick = () => { MB_connection.disconnect(); connectingPort = null; sheet.close(); };
        $('iphone-address-form').onsubmit = async event => {
            event.preventDefault();
            if (profiles.find(p => p.id === $('iphone-board').value)?.transport !== 'wifi') return;
            address = $('iphone-address').value.trim();
            try {
                $('iphone-sheet-status').textContent = 'Connecting to board…';
                $('iphone-open').disabled = true;
                MB_connection.disconnect();
                await MB_connection.connect('iphone-wifi');
                lastPort = MB_connection.port?.iphonePort;
                if (!lastPort) throw new Error('Native board link was not created');
                connectingPort = lastPort;
                // Native validation and socket readiness arrive asynchronously.
                // Keep the form visible until the real VM handshake completes.
            } catch (error) {
                connectingPort = null; $('iphone-sheet-status').textContent = error.message; profileChanged();
            }
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
            $('iphone-open').disabled = profile?.transport !== 'wifi' || !native() || !!connectingPort;
            $('iphone-address').disabled = profile?.transport !== 'wifi';
            if (!native()) $('iphone-sheet-status').textContent = 'Browser preview: offline editing only. Install the native app for Wi-Fi.';
        }
        $('iphone-board').onchange = () => {
            if (connectingPort) { MB_connection.disconnect(); connectingPort = null; }
            profileChanged();
        };
        profileChanged();

        // Keep original run/stop/project handlers; route connection UI to the
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
            if (!document.querySelector('.top-bar__controls-run')) return;
            clearInterval(timer);
            const originalMenus = document.querySelector('[data-ide="main-menu"]');
            $('iphone-original-menus').append(originalMenus);
            const graph = document.querySelector('.top-bar__button-rounded');
            if (graph) originalMenus.append(graph);
            toolbar.append(document.querySelector('.top-bar__controls-run'), document.querySelector('.top-bar__controls-stop'));
            // Keep a quick Stop in focus mode, with the exact stock handler.
            const stop = document.querySelector('.top-bar__controls-stop');
            const quickStop = stop.cloneNode(true); quickStop.id = 'iphone-quick-stop';
            quickStop.setAttribute('aria-label', 'Stop scripts'); quickStop.onclick = () => stop.click();
            restore.append(quickStop);
            MicroBlocksIPhone.installGestures(canvas, {
                scaleChanged: percent => {
                    $('iphone-scale').textContent = Math.round(percent) + '%';
                    $('iphone-zoom-status').textContent = 'Workspace zoom ' + Math.round(percent) + '%';
                },
                paletteDrop: () => { if (blocksVisible) { blocksVisible = false; layout(); } }
            });
            $('iphone-hand').onclick = () => {
                const active = MicroBlocksIPhone.gestures.toggleHand();
                $('iphone-hand').setAttribute('aria-pressed', String(active));
            };
            layout();
        }, 100);
        setInterval(() => {
            const verified = MB_connection.port?.iphonePort?.isConnected() &&
                MB_connection.connectedToBoard() && Number.isInteger(MB_connection.vmVersion);
            if (connectingPort) {
                if (connectingPort.error || connectingPort.closed) {
                    $('iphone-sheet-status').textContent = connectingPort.error || 'Board link closed. Connect to retry.';
                    $('iphone-sheet-status').scrollIntoView({block: 'nearest'});
                    connectingPort = null; profileChanged();
                } else if (verified && MB_connection.port?.iphonePort === connectingPort) {
                    connectingPort = null; profileChanged(); sheet.close();
                } else $('iphone-sheet-status').textContent = 'Waiting for board reply…';
            }
            const status = verified ? (MB_connection.boardType || 'Board') + ' · VM ' + MB_connection.vmVersion :
                lastPort?.error || (MB_connection.port?.iphonePort ? 'Waiting for board reply…' : 'Offline editing');
            $('iphone-status').textContent = status;
            $('iphone-status').dataset.connected = String(!!verified);
            $('iphone-connect').dataset.connected = String(!!verified);
            document.body.classList.toggle('iphone-connected', !!verified);
            // Never leave run/stop enabled against an unverified native link.
            document.querySelectorAll('.top-bar__controls-run, .top-bar__controls-stop').forEach(button => {
                button.disabled = !verified;
            });
        }, 500);
    });
})();
