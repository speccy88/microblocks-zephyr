// SPDX-License-Identifier: MPL-2.0
// Shared help adapter: the pinned engine's existing menu supplies the Help item.
(function (root) {
    'use strict';
    // Keep the large authored catalog out of the interactive VM/editor page.
    const entries = new Set(root.MicroBlocksBlockHelpIndex);
    const own = selector => entries.has(selector);
    const urlFor = selector => 'block-help.html?v=' + encodeURIComponent(root.MicroBlocksBlockHelpVersion) + '#' + encodeURIComponent(selector);
    const original = MB_Editor.prototype.helpURLFor;
    if (typeof original !== 'function') throw Error('Review changed block Help hook');
    MB_Editor.prototype.helpURLFor = function (selector) {
        if (own(selector)) return urlFor(selector);
        const upstream = original.call(this, selector);
        if (upstream) return upstream;
        // New/user-defined blocks have a clearly labelled authoring fallback.
        // Never place project source, input values or credentials in a URL.
        const project = this.project;
        const declared = project?.blockSpecs?.has(selector) || project?.main?.blockSpecs?.has(selector) ||
            Array.from(project?.libraries?.values() || []).some(lib => lib.blockSpecs?.has(selector));
        if (declared || project?.functionNamed(selector)) return urlFor(selector);
        return upstream;
    };
    root.MicroBlocksBlockHelp = Object.freeze({has: own});
})(globalThis);
