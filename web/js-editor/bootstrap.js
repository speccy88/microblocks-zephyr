// SPDX-License-Identifier: MPL-2.0
// Loaded after the pristine engine and before the upstream window.onload.
MicroBlocksLinux.install(MB_Compiler, MB_CommPort, location, WebSocket, MicroBlocksJSProfile.primitive_sets, MicroBlocksJSProfile.function_names);
const boardProfileRuntime = MicroBlocksJSProfile.kind === 'serial' ? MicroBlocksBoardTransport.install(
    MB_CommPort, MB_Connection, MicroBlocksJSProfile, navigator.serial, () => MB_editor,
    message => window.dispatchEvent(new CustomEvent('microblocks-target-status', {detail: message}))) : null;
const linuxTarget = MicroBlocksTarget.install(MB_CommPort, MicroBlocksJSProfile.id, location);
MicroBlocksTarget.protectFirmware(typeof MB_Firmware === 'undefined' ? null : MB_Firmware, MicroBlocksJSProfile.id);
MicroBlocksLegacySlots.install(MB_Specs, SyntaxElementMorph, MicroBitDisplaySlotMorph, ArgMorph, Color, Point, MenuMorph);
MicroBlocksLegacyLoops.install(MB_Compiler);
MicroBlocksReadback.install(MB_Decompiler, MB_CodeManager, ScriptsMorph, () => MB_editor,{primitiveSets:MicroBlocksJSProfile.primitive_sets});
MicroBlocksReadback.protectRead(MB_Connection,MB_CodeManager,()=>MB_connection,()=>MB_editor);
MicroBlocksReadbackLibraries.install(MB_Decompiler,MicroBlocksReadbackLibraryMap);
window.addEventListener('DOMContentLoaded', () => {
    const panel = document.createElement('div');
    panel.setAttribute('role', 'status');
    panel.style.cssText = 'position:fixed;bottom:0;right:0;z-index:99999;background:#fff5cc;color:#222;padding:6px;font:13px sans-serif';
    const label = document.createElement('span');
    label.textContent = linuxTarget.name + (linuxTarget.placeholder ? ' — experimental placeholder, offline editing only. ' : ' — experimental JS editor. ');
    const button = document.createElement('button');
    button.textContent = linuxTarget.kind === 'serial' ? 'Connect target USB' : 'Connect local VM';
    button.disabled = !MicroBlocksTarget.canConnect(linuxTarget, location);
    if (!linuxTarget.placeholder && button.disabled) label.textContent += linuxTarget.kind === 'serial' ? 'Use desktop Chrome or Edge on HTTPS or loopback for USB. ' : 'Open the Pi-hosted editor through a local SSH tunnel to connect. ';
    button.onclick = async () => {
        try {
            if (MB_connection.port) MB_connection.disconnect();
            await MB_connection.connect(linuxTarget.kind === 'serial' ? 'serial' : 'linux-loopback');
            label.textContent = linuxTarget.kind === 'serial' ? 'Waiting for the selected USB board identity. ' : 'Connecting to local VM. ';
        } catch (error) { label.textContent = error.message + ' '; }
    };
    const close = document.createElement('button');
    close.textContent = 'Close local link';
    close.onclick = () => { MB_connection.disconnect(); label.textContent = 'Local link closed. '; };
    panel.append(label, button, close);
    if (MicroBlocksJSProfile.secure_websocket) {
        const endpoint=document.createElement('input');endpoint.type='url';endpoint.placeholder='wss://board.local/ws/vm';endpoint.setAttribute('aria-label','Trusted P4 secure WebSocket address');
        const network=document.createElement('button');network.textContent='Connect P4 WSS';
        network.onclick=async()=>{try{const url=MicroBlocksBoardTransport.secureEndpoint(endpoint.value);await MB_connection.connect('board-wss',url);label.textContent='Waiting for secure P4 readiness and identity. ';}catch(error){label.textContent=error.message;}};
        panel.append(endpoint,network);
    }
    window.addEventListener('microblocks-target-status', event => {label.textContent = String(event.detail).slice(0,512) + ' ';});
    const library = MicroBlocksJSProfile.bundle || (MicroBlocksJSProfile.id === 'microduck' ? 'Libraries/MicroDuck Linux.ubl' : null);
    if (library) {
        const load = document.createElement('button');
        load.textContent = 'Load target blocks';
        load.onclick = async () => {
            try {await MB_Files.initialize();await MB_editor.openLibraryFile(library);label.textContent = linuxTarget.name + ' target libraries loaded. ';}
            catch (error) {label.textContent = error.message + ' ';}
        };
        panel.append(load);
    }
    if (MicroBlocksJSProfile.id === 'microduck') {
        const starter=document.createElement('button');starter.textContent='Load starter lab (includes SIMULATION)';
        starter.onclick=async()=>{try{await MB_Files.initialize();await MB_editor.openLibraryFile('Libraries/MicroDuck Starter Lab.ubl');label.textContent='Simple sensors and advanced libraries loaded together. Action practice is SIMULATION ONLY. ';}catch(error){label.textContent=error.message;}};
        panel.append(starter);
    }
    document.body.append(panel);
    if (MicroBlocksJSProfile.id === 'esp32p4') {
        try {MicroBlocksP4UI.attach(MB_Connection,MB_connection,boardProfileRuntime);}
        catch (error) {label.textContent = 'P4 services unavailable: ' + error.message;}
    }
});
