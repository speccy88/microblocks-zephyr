// SPDX-License-Identifier: MPL-2.0
// Loaded after the pristine engine and before the upstream window.onload.
MicroBlocksLinux.install(MB_Compiler, MB_CommPort, location, WebSocket);
const linuxTarget = MicroBlocksTarget.install(MB_CommPort, MicroBlocksJSProfile.id, location);
MicroBlocksLegacySlots.install(MB_Specs, SyntaxElementMorph, MicroBitDisplaySlotMorph, ArgMorph, Color, Point, MenuMorph);
MicroBlocksReadback.install(MB_Decompiler, MB_CodeManager, ScriptsMorph, () => MB_editor);
window.addEventListener('DOMContentLoaded', () => {
    const panel = document.createElement('div');
    panel.setAttribute('role', 'status');
    panel.style.cssText = 'position:fixed;bottom:0;right:0;z-index:99999;background:#fff5cc;color:#222;padding:6px;font:13px sans-serif';
    const label = document.createElement('span');
    label.textContent = linuxTarget.name + (linuxTarget.placeholder ? ' — experimental placeholder, offline editing only. ' : ' — experimental JS editor. ');
    const button = document.createElement('button');
    button.textContent = 'Connect local VM';
    button.disabled = !MicroBlocksTarget.canConnect(linuxTarget, location);
    if (!linuxTarget.placeholder && button.disabled) label.textContent += 'Open the Pi-hosted editor through a local SSH tunnel to connect. ';
    button.onclick = async () => {
        try {
            if (MB_connection.port) MB_connection.disconnect();
            await MB_connection.connect('linux-loopback');
            label.textContent = 'Connecting to local VM. ';
        } catch (error) { label.textContent = error.message + ' '; }
    };
    const close = document.createElement('button');
    close.textContent = 'Close local link';
    close.onclick = () => { MB_connection.disconnect(); label.textContent = 'Local link closed. '; };
    panel.append(label, button, close);
    document.body.append(panel);
});
