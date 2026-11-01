// SPDX-License-Identifier: MPL-2.0
// Same-origin portal hook; no compiler, project-store or transport replacement.
(() => {
    'use strict';
    window.portalSaveBeforeLeaving = async () => {
        if (typeof MB_editor !== 'object' || !MB_editor.scripts || !MB_editor.project) {
            throw new Error('Editor is still loading. Wait before switching.');
        }
        MB_editor.endOpenEdit();
        const linked = typeof MB_connection === 'object' && !!MB_connection.port;
        if (MB_editor.hasUnsavedEdits() || linked) {
            const message = linked ? 'Switch editors and close the board link? Export any unsaved project first.' :
                'Switch editors? Export your unsaved project first.';
            if (!(await MB_editor.confirm(message, false))) throw new Error('Editor switch cancelled.');
        }
        if (linked) MB_connection.disconnect();
    };
})();
