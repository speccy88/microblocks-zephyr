#!/usr/bin/env python3
"""Actual JavaScript-first entry, target switching and legacy GP regression."""
# SPDX-License-Identifier: MIT
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from mobile_web_smoke import QuietHandler


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--browser')
    a = p.parse_args(); a.output.mkdir(parents=True,exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(a.site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=a.browser,headless=True,chromium_sandbox=True)
            page = browser.new_page(viewport={'width':1280,'height':900})
            errors, requests, sockets = [], [], []
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.on('request',lambda request:requests.append(request.url))
            page.on('websocket',lambda socket:sockets.append(socket.url))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            def editor():
                frame = page.frame_locator('#ide')
                frame.locator('[data-ide="app-preloader"]').wait_for(state='hidden',timeout=60000)
                current = next(f for f in page.frames if '/js-preview/' in f.url)
                current.wait_for_function('() => typeof world === "object" && world && MB_editor.scripts && typeof portalSaveBeforeLeaving === "function"')
                return current
            current = editor()
            assert '/js-preview/fruit-jam/' in current.url
            assert not any('gp_wasm' in url for url in requests), requests
            assert not sockets, sockets
            page.screenshot(path=str(a.output/'javascript-default.png'))
            # Use a real edited project; intercept only the human's answer.
            source = "projectName 'Keep my work'\nmodule 'main'\nscript 40 60 (+ 20 22)\n"
            current.evaluate('text => MB_editor.restoreUndoState(text)',source)
            before = current.evaluate('() => {MB_editor.updateProject(); MB_editor.unsavedEdits=true; return MB_editor.project.codeString()}')
            current.evaluate('''() => {window.savedConfirm=MB_editor.confirm; MB_editor.confirm=async()=>false;}''')
            page.select_option('#board','propeller2'); page.locator('#open-editor').click()
            page.wait_for_function('() => document.getElementById("portal-status").textContent === "Editor switch cancelled."')
            assert page.locator('#board').input_value() == 'fruit-jam'
            assert current.evaluate('MB_editor.project.codeString()') == before
            current.evaluate('MB_editor.confirm=window.savedConfirm; MB_editor.unsavedEdits=false')
            targets = []
            for target in ['propeller2','waveshare','esp32p4','xrp-rp2350','raspberry-pi5','microduck','unoq','fruit-jam']:
                page.select_option('#board',target); page.locator('#open-editor').click()
                page.locator('#ide').wait_for(state='attached')
                page.wait_for_function('(target) => document.getElementById("ide").getAttribute("src")==="js-preview/"+target+"/index.html"',arg=target)
                current = editor()
                assert '/js-preview/'+target+'/' in current.url
                assert current.evaluate('typeof MB_Compiler') == 'function'
                assert page.locator('#full-editor').get_attribute('href') == 'js-preview/'+target+'/index.html'
                targets.append(target)
            assert not errors, errors
            assert not sockets, sockets
            assert not any('gp_wasm' in url for url in requests)
            # Legacy remains deliberate, with its own original controller.
            legacy_requests = []
            legacy = browser.new_page()
            legacy.on('request',lambda request:legacy_requests.append(request.url))
            legacy.goto(f'http://127.0.0.1:{server.server_port}/legacy/index.html')
            legacy.frame_locator('#ide').locator('[data-ide="app-preloader"]').wait_for(state='hidden',timeout=60000)
            assert any('gp_wasm.js' in url for url in legacy_requests)
            assert any('/legacy/portal.js' in url for url in legacy_requests)
            assert '/editor/fruit-jam/' in legacy.locator('#ide').get_attribute('src') or legacy.locator('#ide').get_attribute('src').startswith('editor/fruit-jam/')
            legacy.screenshot(path=str(a.output/'legacy-gp.png'))
            result = {'default_editor':'javascript','targets':targets,'default_gp_loaded':False,
                'actual_js_compiler_loaded':True,'unsaved_switch_cancelled':True,'legacy_gp_loaded':True,
                'automatic_sockets':sockets,'page_errors':errors,'physical_hardware':False}
            (a.output/'portal.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result)); browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
