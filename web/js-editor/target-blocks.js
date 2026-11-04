// SPDX-License-Identifier: MPL-2.0
// Target-library startup policy, separate from the pristine upstream engine.
(function (root) {
    'use strict';
    const pending = new WeakMap();
    const status = message => root.dispatchEvent(new CustomEvent('microblocks-target-status', {detail: message}));
    async function ensure(editor) {
        const profile = typeof MicroBlocksJSProfile === 'object' ? MicroBlocksJSProfile : null;
        if (!profile?.auto_load_target_blocks) return;
        const project = editor.project;
        // Saved/custom P2 libraries belong to the project. Never replace one
        // merely because the browser was opened with a newer target package.
        if (project.libraryNamed(profile.target_library_module)) return;
        if (pending.has(project)) return pending.get(project);
        const operation = (async () => {
            const names = new Set(project.allFunctions().map(fn => fn.functionName));
            if (profile.function_names.some(name => names.has(name))) {
                status('Existing P2 function definitions preserved. Use Load target blocks to update them explicitly.');
                return;
            }
            const response = await fetch(profile.bundle + '?v=' + profile.target_library_sha256);
            if (!response.ok) throw Error('Could not load P2 Hardware blocks (' + response.status + ')');
            const data = await response.text();
            const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
            const sha = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
            if (sha !== profile.target_library_sha256) throw Error('P2 Hardware library does not match this editor build');
            // A file opening while the library is fetched owns the new project.
            if (editor.project !== project || project.libraryNamed(profile.target_library_module)) return;
            const dirty = editor.unsavedEdits;
            const loaded = await editor.importLibraryFromString(data, profile.bundle);
            if (loaded !== profile.target_library_module) throw Error('P2 Hardware library could not be imported');
            editor.unsavedEdits = dirty;
            status('P2 Hardware blocks ready — native extension ' + profile.required_extension_revision + ' required.');
        })();
        pending.set(project, operation);
        try { return await operation; }
        catch (error) { status(error.message); throw error; }
        finally { pending.delete(project); }
    }
    if (typeof MB_Editor === 'function' && typeof MicroBlocksJSProfile === 'object' && MicroBlocksJSProfile.auto_load_target_blocks) {
        for (const name of ['importFromURL', 'newProject', 'openProjectFromString']) {
            const original = MB_Editor.prototype[name];
            if (typeof original !== 'function') throw Error('Review target-library editor hook: ' + name);
            MB_Editor.prototype[name] = async function (...args) {
                const before = this.project;
                const result = await original.apply(this, args);
                // importFromURL ends startup after autosave recovery. Other
                // methods only add blocks if their replacement was accepted.
                if (name === 'importFromURL' || before !== this.project) await ensure(this);
                return result;
            };
        }
    }
    root.MicroBlocksTargetBlocks = Object.freeze({ensure});
})(globalThis);
