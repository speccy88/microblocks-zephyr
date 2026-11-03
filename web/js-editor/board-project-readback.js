// SPDX-License-Identifier: MPL-2.0
// Keep connected-board project recovery separate from New/download behavior.
(function (root) {
    'use strict';
    const installed = new WeakSet();
    function install(Editor, connection) {
        if (installed.has(Editor)) return;
        const proto = Editor?.prototype;
        if (typeof connection !== 'function' ||
                ['openFromBoard', 'openProjectFromBoard', 'withBoardTurn'].some(name => typeof proto?.[name] !== 'function')) {
            throw Error('Review changed board project readback hooks');
        }
        const armRead = proto.openFromBoard;
        proto.openFromBoard = async function (...args) {
            const link = connection();
            // The upstream disconnected action arms a read for the next board.
            // Its clearProject() also clears a connected board: never take that
            // path when a live board is the source we are trying to recover.
            if (!link?.isConnected()) return armRead.apply(this, args);
            if (!Number.isInteger(link.vmVersion) || link.vmVersion <= 0) {
                throw Error('Wait for the board identity before reading its project');
            }
            const port = link.port;
            return this.withBoardTurn(async () => {
                if (connection() !== link || link.port !== port || !link.isConnected() ||
                        !Number.isInteger(link.vmVersion) || link.vmVersion <= 0) {
                    throw Error('Board connection changed before project readback');
                }
                this.readFromBoard = false;
                // The existing reader owns confirmation, decompilation and
                // project replacement, with the transport's read-only guard.
                return this.openProjectFromBoard();
            });
        };
        installed.add(Editor);
    }
    const api = Object.freeze({install});
    root.MicroBlocksBoardProjectReadback = api;
    if (typeof module === 'object' && module.exports) module.exports = api;
    if (typeof MB_Editor === 'function' && typeof MB_connection === 'object') {
        install(MB_Editor, () => MB_connection);
    }
})(globalThis);
