// SPDX-License-Identifier: MPL-2.0
// Target-library startup policy, separate from the pristine upstream engine.
(function (root) {
    'use strict';
    const pending = new WeakMap();
    const status = message => root.dispatchEvent(new CustomEvent('microblocks-target-status', {detail: message}));
    function announceReady(editor,profile) {
        const optional=profile.optional_target_library_modules?.some(name=>editor.project.libraryNamed(name));
        status(optional ? 'P2 optional blocks need candidate extension ' + profile.optional_extension_revision +
            ' (installer: ' + profile.required_extension_revision + ').' :
            'P2 libraries ready - native extension ' + profile.required_extension_revision + ' required.');
    }
    function organizeLegacy(editor, profile) {
        const project = editor.project, old = project.libraryNamed(profile.legacy_target_library_module);
        if (!old) return false;
        const names = profile.target_library_modules;
        if (names.some(name => project.libraryNamed(name)) || old.isImplementation || old.implementedLibs.length || old.variableNames.length || old.scripts.length) {
            status('Custom P2 library layout preserved. Export it before replacing target libraries.');
            return true;
        }
        // Move the existing objects, rather than importing newer definitions.
        // Selectors, function objects, variables, choices, scripts and the
        // code manager's function IDs stay intact; no board operation occurs.
        const groups = new Map(names.map(name => [name, new MB_Module(name)]));
        const core = groups.get(names[0]);
        const owner = selector => groups.get(profile.target_library_owners[selector]) || core;
        for (const lib of groups.values()) {
            lib.author = old.author; lib.version = [...old.version];
            lib.description = old.description; lib.tags = [...old.tags];
            lib.translationSources = new Map(old.translationSources);
            lib.moduleCategory = old.moduleCategory;
            lib.dependencies = lib === core ? [...old.dependencies] : [core.moduleName];
        }
        core.choices = new Map(old.choices);
        core.variableNames = [...old.variableNames]; core.scripts = [...old.scripts];
        for (const fn of old.functions) owner(fn.functionName).functions.push(fn);
        for (const [selector, spec] of old.blockSpecs) owner(selector).blockSpecs.set(selector, spec);
        let advanced = false;
        for (const selector of old.blockList) {
            if (selector === 'advanced') { advanced = true; continue; }
            if (selector === '-') continue;
            const list = owner(selector).blockList;
            if (advanced && !list.includes('advanced')) list.push('advanced');
            list.push(selector);
        }
        project.libraries.delete(old.moduleName);
        for (const [name, lib] of groups) {
            if (lib === core || lib.functions.length || lib.blockSpecs.size) project.libraries.set(name, lib);
        }
        editor.updateLibraryList(); editor.selectLibrary(core.moduleName);
        editor.unsavedEdits = true;
        status('Saved P2 blocks organized by function; your existing definitions are preserved.');
        return true;
    }
    async function ensure(editor) {
        const profile = typeof MicroBlocksJSProfile === 'object' ? MicroBlocksJSProfile : null;
        if (!profile?.auto_load_target_blocks) return;
        const project = editor.project;
        if (organizeLegacy(editor, profile)) return;
        // A saved subset is intentional. Do not repopulate removed libraries,
        // or replace saved/custom definitions just because the editor updated.
        if (profile.target_library_modules.some(name => project.libraryNamed(name))) return announceReady(editor,profile);
        if (pending.has(project)) return pending.get(project);
        const operation = (async () => {
            const names = new Set(project.allFunctions().map(fn => fn.functionName));
            if (profile.function_names.some(name => names.has(name))) {
                status('Existing P2 function definitions preserved. Use Load target blocks to update them explicitly.');
                return;
            }
            const response = await fetch(profile.bundle + '?v=' + profile.target_library_sha256);
            if (!response.ok) throw Error('Could not load P2 target libraries (' + response.status + ')');
            const data = await response.text();
            const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(data));
            const sha = Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
            if (sha !== profile.target_library_sha256) throw Error('P2 target libraries do not match this editor build');
            // A file opening while the library is fetched owns the new project.
            if (editor.project !== project || profile.target_library_modules.some(name => project.libraryNamed(name))) return;
            const dirty = editor.unsavedEdits;
            await editor.importLibraryFromString(data, profile.bundle);
            if (!profile.target_library_modules.every(name => project.libraryNamed(name))) throw Error('P2 target libraries could not be imported');
            for (const name of profile.target_library_modules) project.libraryNamed(name).path = 'P2/' + name;
            editor.selectLibrary(profile.target_library_modules[0]);
            editor.unsavedEdits = dirty;
            announceReady(editor,profile);
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
        const openLibrary = MB_Editor.prototype.openLibraryFile;
        MB_Editor.prototype.openLibraryFile = async function (path, ...args) {
            if (path === MicroBlocksJSProfile.bundle && this.project.libraryNamed(MicroBlocksJSProfile.legacy_target_library_module)) {
                organizeLegacy(this, MicroBlocksJSProfile);
                if (this.project.libraryNamed(MicroBlocksJSProfile.legacy_target_library_module)) {
                    throw Error('Custom P2 library layout preserved. Export it before replacing target libraries.');
                }
            }
            const result=await openLibrary.call(this, path, ...args);
            announceReady(this,MicroBlocksJSProfile);
            return result;
        };
    }
    root.MicroBlocksTargetBlocks = Object.freeze({ensure});
})(globalThis);
