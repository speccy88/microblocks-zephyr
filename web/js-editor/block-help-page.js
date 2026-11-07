// SPDX-License-Identifier: MPL-2.0
(function () {
    'use strict';
    const blocks = globalThis.MicroBlocksBlockHelpData.blocks;
    const main = document.getElementById('help');
    const element = (tag, text, parent = main) => {
        const node = document.createElement(tag);
        if (text !== undefined) node.textContent = text;
        parent.appendChild(node); return node;
    };
    function list(title, values) {
        if (!values.length) return;
        element('h2', title); const ul = element('ul');
        values.forEach(value => element('li', value, ul));
    }
    function render() {
        main.replaceChildren();
        document.title = 'MicroBlocks custom block help';
        let selector;
        try { selector = decodeURIComponent(location.hash.slice(1)); }
        catch (_) { selector = location.hash.slice(1); }
        if (!selector) {
            element('h1', 'Custom block reference');
            element('p', 'Choose a block, or right-click a block in the editor and choose help.');
            const input = element('input'); input.type = 'search'; input.placeholder = 'Search blocks or libraries'; input.setAttribute('aria-label', 'Search blocks or libraries');
            const ul = element('ul');
            const show = () => {
                ul.replaceChildren(); const query = input.value.toLowerCase();
                for (const [key, doc] of Object.entries(blocks)) {
                    if (!(key + ' ' + doc.label + ' ' + doc.modules.join(' ')).toLowerCase().includes(query)) continue;
                    const li = element('li', undefined, ul), a = element('a', doc.label, li);
                    a.href = '#' + encodeURIComponent(key);
                    element('small', ' — ' + doc.modules.join(', '), li);
                }
            };
            input.addEventListener('input', show); show(); return;
        }
        if (!Object.prototype.hasOwnProperty.call(blocks, selector)) {
            element('h1', 'Documentation not yet authored');
            element('code', selector);
            element('p', 'This is a user-defined or newly added block. Inspect its definition in the editor, or ask its library author for inputs, results, prerequisites and a worked example.');
            element('p', 'Do not infer hardware support or safe pin assignments from a block name. No program contents are sent to this page.');
            return;
        }
        const doc = blocks[selector];
        document.title = doc.label + ' • MicroBlocks help';
        element('h1', doc.label); element('code', selector);
        element('p', doc.modules.join(' · ')); element('p', doc.summary);
        element('p', 'This reference describes the bundled library. If you changed this block definition in your project, inspect that definition before using these examples.');
        list('Before you start', doc.prerequisites);
        list('Inputs', doc.inputs);
        element('h2', 'Result'); element('p', doc.returns);
        element('h2', 'Examples');
        element('p', 'Read these examples before recreating them in the editor. They do not run here.');
        for (const example of doc.examples) {
            element('h3', example.title); element('pre', example.code); element('p', example.explanation);
        }
        list('Notes and limitations', doc.notes); list('Canonical source', doc.sources);
    }
    addEventListener('hashchange', render); render();
})();
