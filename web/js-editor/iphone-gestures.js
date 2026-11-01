// SPDX-License-Identifier: MPL-2.0
// Touch navigation for the pinned Morphic editor. No CSS camera or VM writes.
(() => {
    'use strict';
    MicroBlocksIPhone.installGestures = (canvas, callbacks) => {
        let mode = null, handMode = false, primary = null, fromPalette = false;
        let basis = null, pending = null, raf = 0, pinched = false;
        const frame = () => MB_editor.scriptsFrame;
        const pane = () => MB_editor.scriptsPane();
        const hand = () => world.hand;
        const point = touch => {
            const r = canvas.getBoundingClientRect();
            return new Point((touch.clientX - r.left) / ZOOM + world.left(),
                (touch.clientY - r.top) / ZOOM + world.top());
        };
        const center = touches => {
            if (touches.length === 1) return {clientX: touches[0].clientX, clientY: touches[0].clientY};
            return {clientX: (touches[0].clientX + touches[1].clientX) / 2,
                clientY: (touches[0].clientY + touches[1].clientY) / 2};
        };
        const distance = touches => touches.length < 2 ? 0 :
            Math.hypot(touches[0].clientX - touches[1].clientX, touches[0].clientY - touches[1].clientY);
        const owns = (morph, owner) => morph && morph.allParents().includes(owner);
        const stop = event => { event.preventDefault(); event.stopImmediatePropagation(); };
        const clearHand = () => {
            clearInterval(hand().touchHoldTimeout);
            hand().mouseButton = hand().clickTarget = hand().inputTarget = hand().morphToGrab = null;
        };
        const saveScale = () => {
            if (!pinched) return;
            try {
                const prefs = MB_editor.readUserPreferences();
                prefs.blockSizePercent = MB_editor.blockSize;
                localStorage['user-prefs'] = JSON.stringify(prefs);
            } catch (_) { /* Navigation also works when browser storage is unavailable. */ }
            pinched = false;
        };
        function begin(touches) {
            clearHand(); frame().step = nop;
            basis = {anchor: point(center(touches)).subtract(pane().position()),
                distance: distance(touches), scale: ZOOM};
            mode = 'navigate';
        }
        function apply() {
            raf = 0;
            if (!pending || !basis) return;
            const update = pending; pending = null;
            if (basis.distance > 0 && update.distance > 0) {
                const percent = Math.round(Math.max(50, Math.min(250,
                    basis.scale * 100 * update.distance / basis.distance)));
                if (percent !== MB_editor.blockSize) {
                    // setBlockScalePercent also syncs scripts. View gestures use
                    // the pure scale operation and save the preference on lift.
                    MB_editor.applyBlockSize(percent); pinched = true;
                    callbacks.scaleChanged(percent);
                }
            }
            const delta = point(update.center).subtract(basis.anchor).subtract(pane().position());
            frame().scrollX(delta.x); frame().scrollY(delta.y); frame().adjustScrollBars();
        }
        function flush() { if (raf) cancelAnimationFrame(raf); apply(); }
        function reset() {
            flush(); saveScale();
            basis = pending = null; primary = null; fromPalette = false;
            mode = null; clearHand();
        }
        function interrupted() {
            // Finish an already grabbed block at its last valid pointer location.
            // Never leave it owned by the hand after an OS interruption.
            if (hand().children.length) hand().processMouseUp();
            reset();
        }
        canvas.addEventListener('touchstart', event => {
            const touches = Array.from(event.touches);
            if (mode === 'drain') { stop(event); return; }
            if (mode === 'navigate') { flush(); begin(touches); stop(event); return; }
            if (mode === 'stock' && touches.length > 1) {
                // An actual block grab owns its primary finger until lift.
                // Do not send the secondary lift to upstream's unconditional drop.
                if (hand().children.length) { stop(event); return; }
                if (touches.every(t => frame().bounds.containsPoint(point(t)))) {
                    begin(touches); stop(event);
                }
                return;
            }
            if (mode) return;
            primary = touches[0].identifier;
            const pos = point(touches[0]), hit = world.topMorphAt(pos);
            const inScripts = frame().bounds.containsPoint(pos) && owns(hit, frame());
            if (inScripts && (touches.length > 1 || handMode || hit === pane() || hit === frame())) {
                MB_editor.endOpenEdit(); begin(touches); stop(event);
            } else {
                mode = 'stock'; fromPalette = owns(hit, MB_editor.palette);
            }
        }, {capture: true, passive: false});
        canvas.addEventListener('touchmove', event => {
            if (mode === 'drain') { stop(event); return; }
            if (mode === 'navigate') {
                const touches = Array.from(event.touches);
                pending = {center: center(touches), distance: distance(touches)};
                if (!raf) raf = requestAnimationFrame(apply);
                stop(event);
            } else if (mode === 'stock' && event.touches.length > 1) stop(event);
        }, {capture: true, passive: false});
        canvas.addEventListener('touchend', event => {
            if (mode === 'navigate') {
                flush(); saveScale();
                // Remaining fingers stay navigation; a single remaining finger
                // pans without a scale jump or a fresh block grab.
                if (event.touches.length) begin(Array.from(event.touches));
                else reset();
                stop(event); return;
            }
            if (mode === 'drain') { if (!event.touches.length) reset(); stop(event); return; }
            if (mode === 'stock') {
                if (Array.from(event.touches).some(t => t.identifier === primary)) { stop(event); return; }
                const dropped = fromPalette && hand().children[0];
                mode = event.touches.length ? 'drain' : null;
                clearInterval(hand().touchHoldTimeout);
                // Upstream performs the actual drop first. An inserted block
                // can have a block parent, so top-level script counts cannot
                // establish success.
                setTimeout(() => {
                    if (dropped && owns(dropped, pane())) callbacks.paletteDrop();
                }, 0);
            }
        }, {capture: true, passive: false});
        canvas.addEventListener('touchcancel', event => { interrupted(); stop(event); }, {capture: true, passive: false});
        window.addEventListener('blur', interrupted);
        window.addEventListener('resize', interrupted);
        document.addEventListener('visibilitychange', () => { if (document.hidden) interrupted(); });
        // Clamp the phone's discrete buttons to the same scale range, without
        // uploading unchanged scripts merely because the view changed.
        MB_editor.setBlockScalePercent = async percent => {
            if (!Number.isFinite(percent)) return;
            MB_editor.applyBlockSize(Math.max(50, Math.min(250, percent)));
            callbacks.scaleChanged(MB_editor.blockSize); pinched = true; saveScale();
        };
        callbacks.scaleChanged(MB_editor.blockSize);
        MicroBlocksIPhone.gestures = {
            toggleHand() {
                handMode = !handMode; canvas.classList.toggle('iphone-hand-active', handMode);
                return handMode;
            }
        };
    };
})();
