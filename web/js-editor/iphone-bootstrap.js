// SPDX-License-Identifier: MPL-2.0
// iPhone chrome around the unmodified, pinned MicroBlocks JS editor.
(() => {
    'use strict';
    let address = '', blocksVisible = false, profiles = [], lastPort = null, connectingPort = null;
    MicroBlocksIPhone.installCompiler(MB_Compiler);
    const browser = window.MicroBlocksBrowser;
    MicroBlocksIPhone.install(MB_CommPort, () => address, browser ? () => browser.bridge : undefined);
    const native = () => window.webkit?.messageHandlers?.microblocks;
    // Stock icon labels are literal English. The phone displays them as menu
    // captions too. Keep them bound to GetText without changing pinned assets.
    const phoneStrings = {
        fr: {'Settings':'Paramètres', 'Project':'Projet', 'Menu':'Menu', 'Blocks':'Blocs', 'Pan workspace':'Déplacer la zone de travail', 'Connect board':'Connecter la carte', 'Save project':'Enregistrer le projet', 'Hide controls':'Masquer les commandes', 'Show controls':'Afficher les commandes', 'View tools':'Outils de vue', 'Workspace zoom':'Zoom de la zone de travail', 'Offline editing':'Édition hors ligne', 'Desktop editor':'Éditeur pour ordinateur', 'Graph':'Graphique', 'Stop scripts':'Arrêter les scripts', 'Programming workspace':'Zone de programmation', 'Resize palette':'Redimensionner la palette', 'Wide palette':'Élargir la palette', 'Close connection sheet':'Fermer la connexion', 'Close':'Fermer', 'Program over Wi-Fi':'Programmer par Wi-Fi', 'Board IP address':'Adresse IP de la carte', 'Close link':'Fermer la liaison', 'Open board website':'Ouvrir le site de la carte', 'Waiting for board reply.':'En attente de la carte.', 'Connecting to board.':'Connexion à la carte.', 'Drag empty space to pan. Drag blocks to move them. Use two fingers to pan and pinch to zoom. Hand mode pans over blocks.':'Glissez sur le fond pour déplacer la vue et sur les blocs pour les déplacer. Pincez à deux doigts pour zoomer. Le mode main déplace la vue même sur les blocs.'},
        de: {'Settings':'Einstellungen', 'Project':'Projekt', 'Menu':'Menü', 'Blocks':'Blöcke', 'Pan workspace':'Arbeitsbereich verschieben', 'Connect board':'Board verbinden', 'Save project':'Projekt speichern', 'Hide controls':'Bedienelemente ausblenden', 'Show controls':'Bedienelemente anzeigen', 'View tools':'Ansichtswerkzeuge', 'Workspace zoom':'Arbeitsbereich-Zoom', 'Offline editing':'Offline bearbeiten', 'Desktop editor':'Desktop-Editor', 'Graph':'Diagramm', 'Stop scripts':'Skripte stoppen', 'Programming workspace':'Programmierbereich', 'Resize palette':'Palette vergrößern oder verkleinern', 'Wide palette':'Palette verbreitern', 'Close connection sheet':'Verbindung schließen', 'Close':'Schließen', 'Program over Wi-Fi':'Über WLAN programmieren', 'Board IP address':'IP-Adresse des Boards', 'Close link':'Verbindung trennen', 'Open board website':'Board-Webseite öffnen', 'Waiting for board reply.':'Warte auf Antwort des Boards.', 'Connecting to board.':'Verbindung zum Board wird hergestellt.', 'Drag empty space to pan. Drag blocks to move them. Use two fingers to pan and pinch to zoom. Hand mode pans over blocks.':'Den Hintergrund ziehen, um die Ansicht zu verschieben. Blöcke zum Verschieben ziehen. Mit zwei Fingern verschieben und zoomen. Im Handmodus auch über Blöcken verschieben.'},
        es: {'Settings':'Ajustes', 'Project':'Proyecto', 'Menu':'Menú', 'Blocks':'Bloques', 'Pan workspace':'Desplazar el área de trabajo', 'Connect board':'Conectar placa', 'Save project':'Guardar proyecto', 'Hide controls':'Ocultar controles', 'Show controls':'Mostrar controles', 'View tools':'Herramientas de vista', 'Workspace zoom':'Zoom del área de trabajo', 'Offline editing':'Edición sin conexión', 'Desktop editor':'Editor de escritorio', 'Graph':'Gráfico', 'Stop scripts':'Detener programas', 'Programming workspace':'Área de programación', 'Resize palette':'Cambiar el ancho de la paleta', 'Wide palette':'Ampliar la paleta', 'Close connection sheet':'Cerrar conexión', 'Close':'Cerrar', 'Program over Wi-Fi':'Programar por Wi-Fi', 'Board IP address':'Dirección IP de la placa', 'Close link':'Cerrar enlace', 'Open board website':'Abrir el sitio de la placa', 'Waiting for board reply.':'Esperando respuesta de la placa.', 'Connecting to board.':'Conectando con la placa.', 'Drag empty space to pan. Drag blocks to move them. Use two fingers to pan and pinch to zoom. Hand mode pans over blocks.':'Arrastra el fondo para desplazar la vista y los bloques para moverlos. Usa dos dedos para desplazar y pellizcar para ampliar. El modo mano desplaza incluso sobre los bloques.'}
    };
    const translate = key => phoneStrings[GetText.currentLocale]?.[key] || GetText.localize(key);
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

    window.addEventListener(browser?.startupEvent || 'DOMContentLoaded', async () => {
        const toolbar = document.createElement('div');
        toolbar.className = 'iphone-toolbar';
        toolbar.setAttribute('aria-busy', 'true');
        const icon = path => '<svg viewBox="0 0 24 24" aria-hidden="true"><path d="' + path + '"/></svg>';
        const button = (id, label, path, state = '') => '<button id="' + id + '" type="button" aria-label="' +
            label + '" title="' + label + '" ' + state + '>' + icon(path) + '</button>';
        toolbar.innerHTML = button('iphone-menu', 'Menu', 'M4 6h16M4 12h16M4 18h16', 'aria-expanded="false" aria-controls="iphone-menu-panel"') +
            button('iphone-blocks', 'Blocks', 'M4 4h6v3h4V4h6v7h-3v4h3v5H4v-5h3v-4H4z', 'aria-pressed="false"') +
            button('iphone-hand', 'Pan workspace', 'M8 12V6a2 2 0 0 1 4 0v5-7a2 2 0 0 1 4 0v7-4a2 2 0 0 1 4 0v8c0 5-3 7-7 7-3 0-5-3-7-6l-2-3a2 2 0 0 1 3-2l3 3', 'aria-pressed="false"') +
            '<span class="iphone-toolbar-spacer"></span>' +
            button('iphone-connect', 'Connect board', 'M3 8a14 14 0 0 1 18 0M6 12a9 9 0 0 1 12 0M9 16a4 4 0 0 1 6 0M12 20h.01');
        const readyControls = Array.from(toolbar.querySelectorAll('button'));
        readyControls.forEach(control => { control.disabled = true; });
        const ide = document.querySelector('[data-ide="ide"]');
        ide.prepend(toolbar);
        const menu = document.createElement('div');
        menu.id = 'iphone-menu-panel'; menu.className = 'iphone-menu-panel'; menu.hidden = true;
        menu.innerHTML = '<div id="iphone-original-menus"></div>' +
            '<button id="iphone-save" type="button">Save project</button>' +
            '<button id="iphone-focus" type="button">Hide controls</button>' +
            '<p id="iphone-gesture-help">Drag empty space to pan. Drag blocks to move them. Use two fingers to pan and pinch to zoom. Hand mode pans over blocks.</p>' +
            '<span id="iphone-status" role="status" aria-live="polite">Offline editing</span>';
        ide.append(menu);
        const restore = document.createElement('div');
        restore.className = 'iphone-restore';
        restore.innerHTML = button('iphone-restore', 'Show controls', 'M4 6h16M4 12h16M4 18h16');
        restore.querySelector('button').disabled = true;
        readyControls.push(restore.querySelector('button'));
        ide.append(restore);
        const tools = document.createElement('div');
        tools.className = 'iphone-view';
        tools.innerHTML = '<button id="iphone-view" type="button" aria-label="View tools" title="View tools" aria-describedby="iphone-zoom-status" aria-expanded="false"><span id="iphone-scale" aria-hidden="true">100%</span></button>' +
            '<output id="iphone-zoom-status" class="iphone-sr-only" role="status">Workspace zoom 100%</output>';
        document.querySelector('.workspace__canvas-wrapper').append(tools);
        tools.querySelector('button').disabled = true;
        readyControls.push(tools.querySelector('button'));
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
        if (browser) {
            sheet.querySelector('.iphone-limit').textContent = browser.help();
            if (browser.runtime === 'pages') {
                const openBoard = document.createElement('button');
                openBoard.type = 'button'; openBoard.id = 'mobile-open-board'; openBoard.textContent = 'Open board website';
                sheet.querySelector('#iphone-address-form').append(openBoard);
                openBoard.onclick = () => {
                    try { location.href = browser.boardURL($('iphone-address').value); }
                    catch (error) { $('iphone-sheet-status').textContent = error.message; }
                };
            }
        }
        const $ = id => document.getElementById(id);
        const textKeys = new Map(), labelKeys = new Map();
        ['iphone-save', 'iphone-focus', 'iphone-status', 'iphone-gesture-help', 'iphone-sheet-title', 'iphone-open', 'iphone-close', 'mobile-open-board'].forEach(id => {
            const node = $(id); if (node) textKeys.set(node, node.textContent);
        });
        sheet.querySelectorAll('label, .iphone-dismiss').forEach(node => textKeys.set(node, node.textContent));
        toolbar.querySelectorAll('[aria-label]').forEach(node => labelKeys.set(node, node.ariaLabel));
        [restore.querySelector('button'), $('iphone-view')].forEach(node => labelKeys.set(node, node.ariaLabel));
        function refreshLanguage() {
            const desktop = $('mobile-desktop-editor'); if (desktop) textKeys.set(desktop, 'Desktop editor');
            document.querySelectorAll('#iphone-original-menus button, #iphone-quick-stop, .iphone-dismiss, #iphone-palette-resize, #iphone-palette-wide, #canvas').forEach(node => {
                if (node.ariaLabel && !labelKeys.has(node)) labelKeys.set(node, node.ariaLabel);
            });
            textKeys.forEach((key, node) => { if (node.id !== 'iphone-status') node.textContent = translate(key); });
            labelKeys.forEach((key, node) => { node.ariaLabel = translate(key); node.title = translate(key); });
            $('iphone-zoom-status').textContent = translate('Workspace zoom') + ' ' + Math.round(MB_editor.blockSize || 100) + '%';
            document.documentElement.lang = GetText.currentLocale;
            if (!lastPort?.error && !MB_connection.port?.iphonePort) $('iphone-status').textContent = translate('Offline editing');
        }
        GetText.addLocalizable({localize: refreshLanguage});
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
        let paletteWidth = null, widePalette = false;
        const workspaceWrapper = document.querySelector('.workspace__canvas-wrapper');
        const grip = document.createElement('div');
        grip.className = 'iphone-palette-grip';
        grip.innerHTML = '<div id="iphone-palette-resize" role="separator" tabindex="0" aria-orientation="vertical" aria-label="Resize palette"></div>' +
            '<button id="iphone-palette-wide" type="button" aria-label="Wide palette" aria-pressed="false">↔</button>';
        workspaceWrapper.append(grip);
        const paletteLimits = () => ({min: 90, max: Math.max(90, workspaceWrapper.clientWidth - (widePalette ? 44 : 96))});
        function resizePalette(width) {
            const limits = paletteLimits();
            paletteWidth = Math.max(limits.min, Math.min(limits.max, width));
            MB_editor.paletteWidth = paletteWidth;
            MB_editor.fixLayout();
            grip.style.left = paletteWidth + 'px';
            const handle = $('iphone-palette-resize');
            handle.setAttribute('aria-valuemin', limits.min); handle.setAttribute('aria-valuemax', limits.max);
            handle.setAttribute('aria-valuenow', Math.round(paletteWidth));
            world.changed(); world.updateBroken();
        }
        let resizing = false;
        $('iphone-palette-resize').addEventListener('pointerdown', event => {
            resizing = true; event.currentTarget.setPointerCapture(event.pointerId); event.preventDefault();
        });
        $('iphone-palette-resize').addEventListener('pointermove', event => {
            if (resizing) resizePalette(event.clientX - workspaceWrapper.getBoundingClientRect().left);
        });
        const endResize = () => { resizing = false; };
        ['pointerup', 'pointercancel', 'lostpointercapture'].forEach(type => $('iphone-palette-resize').addEventListener(type, endResize));
        $('iphone-palette-resize').addEventListener('keydown', event => {
            if (!['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(event.key)) return;
            event.preventDefault(); event.stopPropagation(); const limits = paletteLimits();
            resizePalette(event.key === 'Home' ? limits.min : event.key === 'End' ? limits.max :
                paletteWidth + (event.key === 'ArrowLeft' ? -20 : 20));
        });
        $('iphone-palette-wide').onclick = () => {
            widePalette = !widePalette;
            $('iphone-palette-wide').setAttribute('aria-pressed', String(widePalette));
            resizePalette(widePalette ? paletteLimits().max : Math.min(240, workspaceWrapper.clientWidth * .46));
        };
        function layout() {
            if (typeof world === 'undefined' || !world || !MB_editor.palette) return;
            const compact = window.innerWidth < 600;
            document.body.classList.toggle('iphone-blocks-visible', blocksVisible);
            const show = blocksVisible && !document.body.classList.contains('iphone-focus');
            MB_editor.paletteWidth = show ? Math.max(90, Math.min(paletteLimits().max,
                paletteWidth ?? (compact ? Math.min(190, window.innerWidth * 0.46) : 240))) : 0;
            if (show) paletteWidth = MB_editor.paletteWidth;
            grip.hidden = !show; grip.style.left = MB_editor.paletteWidth + 'px';
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
            if (browser && !browser.canConnect(profiles.find(p => p.id === $('iphone-board').value))) return;
            address = $('iphone-address').value.trim();
            try {
                $('iphone-sheet-status').textContent = translate('Connecting to board.');
                $('iphone-open').disabled = true;
                MB_connection.disconnect();
                await MB_connection.connect('iphone-wifi');
                lastPort = MB_connection.port?.iphonePort;
                if (!lastPort) throw new Error(native() ? 'Native board link was not created' : 'Board link was not created');
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
            if (browser?.board) $('iphone-board').value = browser.board;
            if (browser?.runtime === 'board') {
                $('iphone-board').disabled = true;
                $('iphone-address').value = location.hostname; $('iphone-address').readOnly = true;
            }
        } catch (_) { $('iphone-sheet-status').textContent = native() ? 'Board profiles could not load. Rebuild the app bundle.' : 'Board choices could not load. Reload and try again.'; }
        function profileChanged() {
            const profile = profiles.find(p => p.id === $('iphone-board').value);
            $('iphone-board-note').textContent = profile?.note || 'Board unavailable';
            $('iphone-open').disabled = profile?.transport !== 'wifi' || !(browser ? browser.canConnect(profile) : native()) || !!connectingPort;
            $('iphone-address').disabled = profile?.transport !== 'wifi';
            if (browser) {
                const openBoard = $('mobile-open-board'); if (openBoard) openBoard.disabled = profile?.transport !== 'wifi';
            } else if (!native()) $('iphone-sheet-status').textContent = 'Browser preview: offline editing only. Install the native app for Wi-Fi.';
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
        IDE.resize = (paint = true) => {
            const wrapper = document.querySelector('[data-ide="canvas-wrapper"]') || document.querySelector('.workspace__canvas-wrapper');
            const canvas = document.querySelector('#canvas');
            if (!wrapper || !canvas || typeof world === 'undefined' || !world) return;
            const rect = wrapper.getBoundingClientRect();
            const width = Math.max(1, Math.floor(rect.width)), height = Math.max(1, Math.floor(rect.height));
            canvas.style.width = width + 'px'; canvas.style.height = height + 'px';
            // Canvas dimension assignment clears its bitmap even if unchanged.
            // Keep the world at the workspace size during zoom, never window size.
            const rendered = world.worldCanvas;
            rendered.style.position = 'unset';
            for (const surface of new Set([canvas, rendered])) {
                if (surface.width !== width) surface.width = width;
                if (surface.height !== height) surface.height = height;
            }
            world.setExtent(new Point(width, height).divideBy(ZOOM));
            if (MB_editor.palette && MB_editor.scriptsFrame) MB_editor.fixLayout();
            world.changed();
            if (paint) world.updateBroken();
        };
        const timer = setInterval(() => {
            if (typeof world === 'undefined' || !world || !MB_editor.palette) return;
            if (!document.querySelector('.top-bar__controls-run')) return;
            if (!document.querySelector('[data-ide="main-menu"] .--project')) return;
            const preloader = document.querySelector('[data-ide="app-preloader"]');
            if (preloader && getComputedStyle(preloader).visibility !== 'hidden') return;
            clearInterval(timer);
            world.fillPage = () => IDE.resize(false);
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
            refreshLanguage();
            MicroBlocksIPhone.installGestures(canvas, {
                scaleChanged: percent => {
                    $('iphone-scale').textContent = Math.round(percent) + '%';
                    $('iphone-zoom-status').textContent = translate('Workspace zoom') + ' ' + Math.round(percent) + '%';
                },
                paletteDrop: () => { if (blocksVisible) { blocksVisible = false; layout(); } }
            });
            $('iphone-hand').onclick = () => {
                const active = MicroBlocksIPhone.gestures.toggleHand();
                $('iphone-hand').setAttribute('aria-pressed', String(active));
            };
            layout();
            readyControls.forEach(control => { control.disabled = false; });
            toolbar.setAttribute('aria-busy', 'false');
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
                } else $('iphone-sheet-status').textContent = translate('Waiting for board reply.');
            }
            const status = verified ? (MB_connection.boardType || 'Board') + ' · VM ' + MB_connection.vmVersion :
                lastPort?.error || translate(MB_connection.port?.iphonePort ? 'Waiting for board reply.' : 'Offline editing');
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
