// SPDX-License-Identifier: MPL-2.0
// Additive layout choice. Existing desktop editor code and project stores stay intact.
(function (root) {
    'use strict';
    const key = 'microblocks.layout.v1';
    const isTouch = env => Number(env.navigator?.maxTouchPoints) > 0 &&
        (env.matchMedia?.('(pointer: coarse)').matches || Math.min(env.innerWidth, env.innerHeight) <= 600);
    const mode = (query, saved, touch) => ['mobile', 'desktop'].includes(query) ? query :
        ['mobile', 'desktop'].includes(saved) ? saved : touch ? 'offer' : 'desktop';
    const safeURL = (path, location) => {
        const url = new URL(path, location.href);
        if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol) || url.username || url.password) throw new Error('Layout target must stay on this website.');
        return url;
    };
    if (typeof module === 'object' && module.exports) { module.exports = {isTouch, mode, safeURL}; return; }
    const config = root.MicroBlocksBrowser || JSON.parse(document.getElementById('mobile-layout-config').textContent);
    const read = () => { try { return localStorage.getItem(key); } catch (_) { return null; } };
    const remember = value => { try { localStorage.setItem(key, value); } catch (_) { /* choice works without persistence */ } };
    const mobileURL = () => {
        const url = safeURL(config.mobile || 'mobile/index.html', location);
        const board = document.getElementById('board')?.value;
        if (['waveshare', 'fruit-jam', 'xrp-rp2350', 'propeller2', 'esp32p4', 'raspberry-pi5', 'microduck'].includes(board)) url.searchParams.set('board', board);
        return url;
    };
    async function leave(value) {
        try {
            if (config.surface === 'mobile' && MB_editor.hasUnsavedEdits()) {
                if (!(await MB_editor.confirm('Switch to the desktop editor? Export your project first to carry your edits across.', false))) return;
            } else if (config.surface === 'portal') {
                const frame = document.getElementById('ide');
                if (typeof frame?.contentWindow?.portalSaveBeforeLeaving === 'function') await frame.contentWindow.portalSaveBeforeLeaving();
                else if (frame?.getAttribute('src') && !confirm('Switch editors? Export your project first if you have unsaved work.')) return;
            } else if (config.surface === 'desktop' && !confirm('Switch to the touch editor? Save or export your project first.')) return;
            const url = value === 'mobile' ? mobileURL() : safeURL(config.desktop || '../?layout=desktop', location);
            remember(value); location.href = url.href;
        } catch (error) {
            const status = document.getElementById('portal-status');
            if (status) status.textContent = error.message + ' Export your project before switching.';
            else alert(error.message);
        }
    }
    function link(label, value) {
        const node = document.createElement('a');
        node.className = 'mobile-layout-link'; node.textContent = label;
        node.href = value === 'mobile' ? mobileURL().href : safeURL(config.desktop || '../?layout=desktop', location).href;
        node.onclick = e => { e.preventDefault(); void leave(value); };
        return node;
    }
    function desktop(explicit = false) {
        if (explicit) remember('desktop'); document.documentElement.removeAttribute('data-touch-offer');
        const offer = document.getElementById('mobile-editor-offer'); if (offer) offer.hidden = true;
        const frame = document.getElementById('ide');
        if (frame && !frame.getAttribute('src')) frame.src = frame.dataset.desktopSrc;
    }
    function offer() {
        if (document.getElementById('mobile-editor-offer')) return;
        const box = document.createElement('aside'); box.id = 'mobile-editor-offer'; box.className = 'mobile-layout-offer';
        box.setAttribute('aria-labelledby', 'mobile-offer-title');
        box.innerHTML = '<h2 id="mobile-offer-title">A workspace made for touch</h2>' +
            '<p>Compact controls, pinch to zoom, and easy panning. Choose the view that suits you.</p>';
        const open = link('Open touch editor', 'mobile'); open.id = 'mobile-open-editor'; box.append(open);
        const keep = document.createElement('button'); keep.type = 'button'; keep.id = 'mobile-keep-desktop'; keep.textContent = 'Use desktop editor';
        keep.onclick = () => {
            if (config.surface === 'portal') desktop(true);
            else { remember('desktop'); location.replace(safeURL(config.desktop, location).href); }
        };
        box.append(keep);
        const note = document.createElement('p'); note.className = 'mobile-layout-note';
        note.textContent = config.surface === 'portal' ?
            'Touch editing works on this website. For Wi-Fi programming, open a compatible board’s local website. iPhone Safari has no USB serial or Web Bluetooth connection here.' :
            'Wireless programming requires compatible board firmware and an explicit connection. USB-only targets use the desktop editor.';
        box.append(note);
        (document.querySelector('main') || document.body).prepend(box);
        document.documentElement.dataset.touchOffer = 'true';
    }
    function start() {
        if (config.surface === 'mobile') {
            const menu = document.getElementById('iphone-menu-panel');
            if (menu && !document.getElementById('mobile-desktop-editor')) {
                const node = link('Desktop editor', 'desktop'); node.id = 'mobile-desktop-editor';
                menu.insertBefore(node, menu.querySelector('p'));
            }
            return;
        }
        if (config.surface === 'desktop') {
            const menus = document.querySelector('[data-ide="main-menu"]');
            if (menus && !document.getElementById('mobile-layout-switch')) {
                const node = link('Touch editor', 'mobile'); node.id = 'mobile-layout-switch'; menus.append(node);
            }
            return;
        }
        const query = new URLSearchParams(location.search).get('layout');
        const selected = mode(query, read(), isTouch(root));
        if (['desktop', 'mobile'].includes(query)) remember(query);
        if (selected === 'mobile') { location.replace(mobileURL().href); return; }
        if (config.surface === 'chooser') {
            if (selected === 'desktop') location.replace(safeURL(config.desktop, location).href);
            else offer();
            return;
        }
        const notes = document.querySelector('.editor-notes');
        if (notes && !document.getElementById('mobile-layout-switch')) {
            const node = link('Touch editor', 'mobile'); node.id = 'mobile-layout-switch'; notes.append(node);
        }
        if (selected === 'offer') offer(); else desktop();
    }
    root.MicroBlocksLayout = {leave, key};
    const event = config.startupEvent || 'DOMContentLoaded';
    if (event !== 'DOMContentLoaded' || document.readyState === 'loading') root.addEventListener(event, start, {once: true});
    else start();
    if (config.surface === 'desktop') document.addEventListener('board-ide-ready', start);
})(globalThis);
