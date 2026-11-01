// SPDX-License-Identifier: MPL-2.0
// Main's JavaScript entry. Target packages own their connection policy.
(() => {
    'use strict';
    const board = document.getElementById('board'), frame = document.getElementById('ide');
    const status = document.getElementById('portal-status'), full = document.getElementById('full-editor');
    const ids = new Set(Array.from(board.options, option => option.value));
    let selected = 'fruit-jam', switching = false;
    const path = id => 'js-preview/' + id + '/index.html';
    const guidance = id => id === 'microduck' || id === 'unoq' ?
        'Offline preview. Hardware connection is disabled for this target.' : id === 'raspberry-pi5' ?
        'Standalone Raspberry Pi 5 editor. Use its documented local SSH tunnel; hosted WSS is not commissioned.' :
        (id === 'propeller2' ? 'Propeller 2 uses USB only. ' : '') +
        'Choose Connect explicitly in desktop Chrome or Edge. The selected board identity is checked. Physical JavaScript hardware acceptance remains pending.';
    document.getElementById('open-editor').onclick = async () => {
        if (switching || !ids.has(board.value)) return;
        if (board.value === selected && frame.getAttribute('src')) {
            document.getElementById('editor').scrollIntoView({behavior: 'smooth'}); return;
        }
        const requested = board.value, button = document.getElementById('open-editor');
        switching = button.disabled = true;
        try {
            if (frame.getAttribute('src')) {
                if (typeof frame.contentWindow.portalSaveBeforeLeaving === 'function') await frame.contentWindow.portalSaveBeforeLeaving();
                else if (!confirm('Switch boards? Export any unsaved project first.')) throw Error('Editor switch cancelled.');
            }
            selected = requested; full.href = path(selected);
            frame.title = 'MicroBlocks JavaScript editor for ' + board.selectedOptions[0].textContent;
            status.textContent = 'Loading ' + board.selectedOptions[0].textContent + ' JavaScript editor…';
            frame.src = path(selected);
        } catch (error) { board.value = selected; status.textContent = error.message; }
        finally { switching = button.disabled = false; }
    };
    frame.onload = () => { status.textContent = guidance(selected); };
})();
