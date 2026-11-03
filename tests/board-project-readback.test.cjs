// SPDX-License-Identifier: MPL-2.0
const test = require('node:test');
const assert = require('node:assert/strict');
const {install} = require('../web/js-editor/board-project-readback.js');

function fixture({connected = true, version = 405} = {}) {
    const events = [];
    const link = {port: {}, vmVersion: version, isConnected: () => connected};
    class Editor {
        async openFromBoard() {events.push('clear-project-and-arm'); return 'armed';}
        async openProjectFromBoard() {events.push('read-project'); return 'recovered';}
        async withBoardTurn(action) {events.push('board-turn'); return action();}
    }
    install(Editor, () => link);
    return {Editor, editor: new Editor(), link, events};
}

test('connected recovery reads the board without clearing it or arming reconnect', async () => {
    const {editor, events} = fixture();
    assert.equal(await editor.openFromBoard(), 'recovered');
    assert.deepEqual(events, ['board-turn', 'read-project']);
    assert.equal(editor.readFromBoard, false);
});

test('disconnected recovery retains the normal next-board workflow', async () => {
    const {editor, events} = fixture({connected: false});
    assert.equal(await editor.openFromBoard(), 'armed');
    assert.deepEqual(events, ['clear-project-and-arm']);
});

test('a live board with an unverified identity is never cleared', async () => {
    const {editor, events} = fixture({version: null});
    await assert.rejects(editor.openFromBoard(), /Wait for the board identity/);
    assert.deepEqual(events, []);
});

test('a port change while waiting for an existing transfer prevents a wrong-board read', async () => {
    const {editor, link, events} = fixture();
    let release;
    editor.withBoardTurn = action => new Promise(resolve => {release = () => resolve(action());});
    const pending = editor.openFromBoard();
    link.port = {};
    release();
    await assert.rejects(pending, /Board connection changed/);
    assert.deepEqual(events, []);
});

test('failed readback does not fall back to the destructive connected path', async () => {
    const {editor, events} = fixture();
    editor.openProjectFromBoard = async () => {throw Error('read failed');};
    await assert.rejects(editor.openFromBoard(), /read failed/);
    assert.deepEqual(events, ['board-turn']);
});

test('installation is idempotent and rejects changed upstream hooks', () => {
    const {Editor} = fixture();
    const wrapped = Editor.prototype.openFromBoard;
    install(Editor, () => null);
    assert.equal(Editor.prototype.openFromBoard, wrapped);
    assert.throws(() => install(class {}, () => null), /Review changed/);
});
