// SPDX-License-Identifier: MPL-2.0
// Linux primitive alias for the separate open LAN Pi touch package.
MicroBlocksIPhone.installCompiler(MB_Compiler);
(() => {
    const init = MB_Compiler.prototype.initPrimsets;
    MB_Compiler.prototype.initPrimsets = function () {
        init.call(this);
        if (this.primsets.has('linux') || this.primsets.get('io') !== 3) throw Error('Review changed Pi primitive table');
        this.primsets.set('linux', 3);
    };
})();
