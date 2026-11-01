#!/usr/bin/env python3
"""Real browser WebSocket + compiler + owned native VM, never physical evidence."""
# SPDX-License-Identifier: MIT
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import select
import socket
import subprocess
import sys
import tempfile
import threading
from playwright.sync_api import sync_playwright


def browser_test(url, output, executable=None):
    errors = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch(executable_path=executable, headless=True, chromium_sandbox=True)
        context = browser.new_context(viewport={'width':390,'height':844}, is_mobile=True, has_touch=True)
        page = context.new_page()
        page.on('pageerror', lambda e:errors.append(str(e)))
        page.goto(url + 'mobile/index.html')
        page.wait_for_function('typeof world!=="undefined" && world && MicroBlocksIPhone.gestures')
        page.locator('[data-ide="app-preloader"]').wait_for(state='hidden')
        assert page.evaluate('MicroBlocksBrowser.runtime') == 'board'
        assert not page.evaluate('!!window.webkit?.messageHandlers?.microblocks')
        # A genuine browser supplies its own Origin. A second, opaque origin
        # must be refused by the existing bridge rather than relaxing its rule.
        class ForeignPage(BaseHTTPRequestHandler):
            def do_GET(self):
                self.send_response(200);self.end_headers();self.wfile.write(b'<!doctype html><title>Foreign origin fixture</title>')
            def log_message(self,*args):pass
        fixture=ThreadingHTTPServer(('127.0.0.1',0),ForeignPage)
        threading.Thread(target=fixture.serve_forever,daemon=True).start()
        try:
            foreign = context.new_page()
            foreign.goto(f'http://127.0.0.1:{fixture.server_port}/')
            cdp=context.new_cdp_session(foreign);statuses=[];socket_errors=[]
            cdp.send('Network.enable')
            cdp.on('Network.webSocketHandshakeResponseReceived',lambda e:statuses.append(e['response']['status']))
            cdp.on('Network.webSocketFrameError',lambda e:socket_errors.append(e['errorMessage']))
            rejected = foreign.evaluate('''url => new Promise(resolve => {
                const ws=new WebSocket(url.replace('http:','ws:')+'ws/vm');
                ws.onopen=()=>{ws.close();resolve(false)};ws.onerror=()=>resolve(true);
            })''', url)
            assert rejected and (403 in statuses or any('403' in e for e in socket_errors)), (statuses,socket_errors)
            foreign.close()
        finally:fixture.shutdown()
        page.evaluate('''() => { window.actualResults=[];
            const show=MB_editor.showResult.bind(MB_editor);
            MB_editor.showResult=(id,value)=>{actualResults.push(value);show(id,value)};
        }''')
        for attempt in range(2):
            page.get_by_role('button', name='Connect board', exact=True).click()
            assert page.locator('#iphone-address').input_value() == '127.0.0.1'
            assert page.locator('#iphone-address').get_attribute('readonly') is not None
            page.locator('#iphone-open').click()
            page.wait_for_function('MB_connection.connectedToBoard() && MB_connection.vmVersion===417')
            page.wait_for_function('!document.querySelector(".iphone-connect-sheet").open')
            if attempt == 0:
                page.evaluate('''async () => {
                    await MB_editor.openProjectFromString("projectName 'Browser VM'\\nmodule 'main'\\nscript 40 60 (+ 20 22)\\n",'Browser VM.ubp');
                    const block=MB_editor.scripts.children.find(b=>b instanceof ReporterBlockMorph);
                    window.actualCode=new MB_Compiler(null).compiledBytesFor(block);
                    while(actualCode.length%4) actualCode.push(0);
                    window.actualCRC=MB_editor.codeManager.computeCRC(actualCode);
                    if(!await MB_editor.codeManager.storeChunkOnBoard(0,[2,...actualCode],actualCRC)) throw Error('CRC upload failed');
                }''')
            else:
                page.evaluate('MB_editor.codeManager.lastCRC=null; MB_connection.sendMsg("getChunkCRCMsg",0)')
                page.wait_for_function('MB_editor.codeManager.lastCRC!==null')
                assert page.evaluate('JSON.stringify(Array.from(MB_editor.codeManager.lastCRC))===JSON.stringify(Array.from(actualCRC))')
            count=page.evaluate('actualResults.length')
            page.evaluate('MB_connection.sendMsg("startChunkMsg",0)')
            page.wait_for_function('n=>actualResults.length>n', arg=count)
            assert page.evaluate('actualResults.at(-1)') == 42
            page.evaluate('async () => {await MB_connection.sendMsg("stopAllMsg"); await MB_connection.sendQueue; MB_connection.disconnect()}')
            page.wait_for_timeout(200)
        page.screenshot(path=str(output/'real-vm-workspace.png'))
        assert not errors, errors
        report={'environment':'desktop Chromium and native SmallVM over loopback', 'browser':browser.version,
                'real_browser_websocket':True,'actual_compiler':True,'vm_version':417,'result':42,
                'crc_upload_readback':True,'stop_reconnect':True,'foreign_origin_rejected':True,
                'native_ios_bridge':False,'physical_board':False,'physical_iphone':False,'page_errors':errors}
        (output/'real-vm.json').write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps(report))
        browser.close()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--linux-source',type=Path);p.add_argument('--binary',type=Path)
    p.add_argument('--editor',type=Path);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--browser');p.add_argument('--url')
    args=p.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    if args.url:
        assert args.url.startswith('http://127.0.0.1:')
        browser_test(args.url,args.output,args.browser);return
    if sys.platform!='linux' or os.geteuid()==0:raise RuntimeError('Requires unprivileged Linux')
    with tempfile.TemporaryDirectory(prefix='mobile-web-vm-') as temp:
        with socket.socket() as free:free.bind(('127.0.0.1',0));port=free.getsockname()[1]
        child=subprocess.Popen([sys.executable,str(args.linux_source/'linux/arm64/session.py'),
            '--binary',str(args.binary.resolve()),'--editor',str(args.editor.resolve()),
            '--data',str(Path(temp)/'data'),'--port',str(port)],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            if not select.select([child.stdout],[],[],20)[0]:raise RuntimeError('VM session readiness deadline')
            line=child.stdout.readline()
            if not line:raise RuntimeError(child.stderr.read())
            assert json.loads(line)['state']=='ready'
            browser_test(f'http://127.0.0.1:{port}/',args.output,args.browser)
        finally:
            if child.poll() is None:child.terminate()
            child.communicate(timeout=15)
            if child.returncode:raise RuntimeError('VM supervisor did not exit cleanly')


if __name__=='__main__':main()
