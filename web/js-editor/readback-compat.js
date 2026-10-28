// SPDX-License-Identifier: MPL-2.0
// Linux-profile adaptation; pinned upstream engine files stay unchanged.
(function (root) {
    'use strict';
    const installed = new WeakSet();
    function install(Decompiler, CodeManager, Scripts, editor) {
        if (typeof Decompiler !== 'function' || typeof CodeManager !== 'function' ||
            typeof Scripts !== 'function' || typeof editor !== 'function') {
            throw Error('Upstream readback hooks changed; review the Linux adapter');
        }
        if (installed.has(CodeManager)) return;
        const addHat = Decompiler.prototype.addHatBlock;
        const evaluate = CodeManager.prototype.evalOnBoard;
        if (typeof addHat !== 'function' || typeof evaluate !== 'function' ||
            typeof CodeManager.prototype.syncScripts !== 'function' || typeof editor !== 'function') {
            throw Error('Upstream readback hooks changed; review the Linux adapter');
        }
        Decompiler.prototype.addHatBlock = function (id, kind, node) {
            const result = addHat.call(this, id, kind, node);
            if (kind === 2 && result?.selector === 'return' && result.next == null &&
                result.args?.length === 1 && result.args[0]?.isReporter === true) {
                return result.args[0];
            }
            return result;
        };
        CodeManager.prototype.evalOnBoard = async function (block, showBytes) {
            const current = editor();
            const inPane = () => block?.parent instanceof Scripts && block.parent.children.includes(block);
            const active = () => editor() === current && current?.codeManager === this && current.project === this.project && inPane();
            if (active() && this.lookupChunkID(block) == null) {
                if (!(await current.saveBeforeRun()) || !active()) return;
                if (this.lookupChunkID(block) == null) await this.syncScripts();
                if (!active()) return;
            }
            return evaluate.call(this, block, showBytes);
        };
        installed.add(CodeManager);
    }
    const api = Object.freeze({install});
    root.MicroBlocksReadback = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
})(globalThis);
