#!/usr/bin/env python3
"""Normal portal startup, current P2 palette and JavaScript-only publication."""
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
            page.add_init_script('''window.serialRequests=0;
                if(navigator.serial) navigator.serial.requestPort=async()=>{
                    window.serialRequests++; throw Error('Hardware access forbidden in UI test');
                };''')
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
            p2_checks = {}
            for target in ['propeller2','waveshare','esp32p4','xrp-rp2350','raspberry-pi5','microduck','unoq','fruit-jam']:
                page.select_option('#board',target); page.locator('#open-editor').click()
                page.locator('#ide').wait_for(state='attached')
                page.wait_for_function('(target) => document.getElementById("ide").getAttribute("src")==="js-preview/"+target+"/index.html"',arg=target)
                current = editor()
                assert '/js-preview/'+target+'/' in current.url
                assert current.evaluate('typeof MB_Compiler') == 'function'
                assert page.locator('#full-editor').get_attribute('href') == 'js-preview/'+target+'/index.html'
                if target == 'propeller2':
                    current.wait_for_function('() => !!MB_editor.project.libraryNamed("P2 Hardware")')
                    library = current.get_by_text('P2 Hardware',exact=True)
                    assert library.is_visible()
                    library.click()
                    def p2_palette():
                        return current.evaluate('''() => ({
                            runtime:MicroBlocksJSProfile.function_names,
                            functions:MB_editor.project.allFunctions().map(f=>f.functionName),
                            palette:MB_editor.palette.contents.allChildren().map(b=>b.selector).filter(Boolean)
                        })''')
                    palette = p2_palette()
                    expected = json.loads((a.site/'js-preview/propeller2/target-library-source.json').read_text())['function_names']
                    assert palette['runtime'] == palette['functions'] == expected
                    for selector in ['p2ServoAngle','p2MeasureDutyPercent','p2CountWindowMS','[p2:p2CogStart]']:
                        assert selector in palette['palette'], (selector,palette['palette'])
                    assert current.evaluate('window.serialRequests') == 0
                    page.screenshot(path=str(a.output/'p2-current-blocks.png'))
                    print('P2 fresh startup: current runtime and visible palette verified',flush=True)
                    # Answer only the human's confirmation, as in the target
                    # cancellation check above; exercise real editor methods.
                    current.evaluate('window.visibilityConfirm=MB_editor.confirm; MB_editor.confirm=async()=>true')
                    awaitable_new = 'async () => { await MB_editor.newProject(); }'
                    current.evaluate(awaitable_new)
                    assert p2_palette()['functions'] == expected
                    print('P2 New: target library restored',flush=True)
                    project = "projectName 'Keep P2 work'\nmodule 'main'\nscript 40 60 (+ 20 22)\n"
                    current.evaluate('text => MB_editor.openProjectFromString(text,"Keep P2 work.ubp")',project)
                    assert p2_palette()['functions'] == expected
                    assert current.evaluate('MB_editor.project.main.scripts.length') == 1
                    print('P2 Open: existing script preserved',flush=True)
                    saved = project + "module 'P2 Hardware' Output\nversion 99 0\nto p2KeptCustom { return 123 }\n"
                    current.evaluate('''text => Promise.race([
                        MB_editor.openProjectFromString(text,"Custom P2.ubp"),
                        new Promise((_,reject)=>setTimeout(()=>reject(Error(document.body.innerText.slice(-5000))),15000))
                    ])''',saved)
                    assert current.evaluate('MB_editor.project.allFunctions().map(f=>f.functionName)') == ['p2KeptCustom']
                    print('P2 existing custom library preserved',flush=True)
                    # Keep accepting the P2 frame's human confirmation when
                    # switching away from this intentionally edited project.
                    p2_checks = {'automatic_functions':len(expected),'visible_palette':True,
                        'new_project':True,'opened_scripts_preserved':True,'existing_library_preserved':True,
                        'serial_requests':current.evaluate('window.serialRequests')}
                    current.evaluate('MB_editor.unsavedEdits=false')
                targets.append(target)
            assert not errors, errors
            assert not sockets, sockets
            assert not any('gp_wasm' in url for url in requests)
            assert page.locator('a[href*="legacy/"]').count() == 0
            removed = ['legacy/index.html','editor/propeller2/microblocks.html','preview/editor/raspberry-pi5/microblocks.html']
            for path in removed:
                assert page.request.get(f'http://127.0.0.1:{server.server_port}/'+path).status == 404
            # Direct P2 entry also uses the ordinary startup path, with no import call.
            direct = browser.new_page()
            direct.goto(f'http://127.0.0.1:{server.server_port}/js-preview/propeller2/')
            direct.wait_for_function('typeof MB_editor === "object" && !!MB_editor.project.libraryNamed("P2 Hardware")')
            assert direct.get_by_text('P2 Hardware',exact=True).is_visible()
            p2_checks['direct_entry'] = True
            result = {'default_editor':'javascript','targets':targets,'default_gp_loaded':False,
                'actual_js_compiler_loaded':True,'unsaved_switch_cancelled':True,'legacy_gp_loaded':False,
                'removed_gp_urls':removed,'p2':p2_checks,
                'automatic_sockets':sockets,'page_errors':errors,'physical_hardware':False}
            (a.output/'portal.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(result)); browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
