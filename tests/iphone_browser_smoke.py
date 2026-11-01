#!/usr/bin/env python3
"""Desktop Chromium mobile emulation; never evidence of native iPhone hardware."""
# SPDX-License-Identifier: MIT
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--browser')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(args.editor)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.browser, headless=True, chromium_sandbox=True)
            context = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2,
                                          is_mobile=True, has_touch=True)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
            page.wait_for_function('typeof world !== "undefined" && world && MB_editor.palette && MB_editor.scriptsFrame')
            page.wait_for_function('document.getElementById("iphone-board").options.length === 6')
            fixture = "projectName 'Phone example'\nmodule 'main'\nscript 40 60 (+ 20 22)\n"
            page.evaluate('(text) => MB_editor.openProjectFromString(text, "Phone example.ubp")', fixture)
            page.wait_for_timeout(300)
            size = page.locator('#canvas').bounding_box()
            assert size['width'] >= 380, size
            assert page.locator('.top-bar__controls-run').is_disabled()
            page.get_by_role('button', name='Connect board', exact=True).click()
            assert page.locator('#iphone-open').is_disabled(), 'Browser must not simulate native Wi-Fi'
            page.select_option('#iphone-board', 'p2')
            assert page.locator('#iphone-address').is_disabled()
            assert 'USB serial only' in page.locator('#iphone-board-note').inner_text()
            page.select_option('#iphone-board', 'p4')
            assert page.locator('#iphone-open').is_disabled()
            page.get_by_role('button', name='Close connection sheet', exact=True).click()
            # Trusted touch events exercise the real Morphic block drag path.
            def block():
                return page.evaluate('''() => {
                    const b=MB_editor.scriptsPane().children.find(b=>b instanceof BlockMorph);
                    const c=world.worldCanvas.getBoundingClientRect();
                    return {x:c.x+(b.center().x-world.left())*ZOOM,
                            y:c.y+(b.center().y-world.top())*ZOOM, left:b.left(),top:b.top()};
                }''')
            before = block()
            cdp = context.new_cdp_session(page)
            cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[{'x':before['x'],'y':before['y']}]})
            for step in range(1, 9):
                cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[{'x':before['x']+step*6,'y':before['y']+step*10}]})
                page.wait_for_timeout(30)
            cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
            page.wait_for_timeout(300)
            after = block()
            assert abs(before['top'] - after['top']) > 20, (before, after)
            page.screenshot(path=str(args.output / 'portrait.png'))
            page.get_by_role('button', name='Blocks', exact=True).click()
            assert page.locator('[data-ide="workspace-left"]').is_visible()
            assert page.evaluate('MB_editor.palette.isVisible')
            page.screenshot(path=str(args.output / 'portrait-blocks.png'))
            palette = page.evaluate('''() => {
                const b=MB_editor.palette.contents.children.find(b=>b instanceof BlockMorph);
                const c=world.worldCanvas.getBoundingClientRect();
                return {x:c.x+(b.center().x-world.left())*ZOOM,y:c.y+(b.center().y-world.top())*ZOOM};
            }''')
            cdp.send('Input.dispatchTouchEvent', {'type':'touchStart','touchPoints':[palette]})
            for step in range(1, 11):
                point = {'x':palette['x']+(315-palette['x'])*step/10, 'y':palette['y']+160*step/10}
                cdp.send('Input.dispatchTouchEvent', {'type':'touchMove','touchPoints':[point]})
                page.wait_for_timeout(30)
            cdp.send('Input.dispatchTouchEvent', {'type':'touchEnd','touchPoints':[]})
            page.wait_for_function('!document.body.classList.contains("iphone-blocks-visible")')
            assert page.evaluate('MB_editor.scriptsPane().children.filter(b=>b instanceof BlockMorph).length') == 2
            page.set_viewport_size({'width': 844, 'height': 390})
            page.wait_for_timeout(300)
            page.screenshot(path=str(args.output / 'landscape.png'))
            assert page.locator('#canvas').bounding_box()['width'] >= 700
            # Test the actual export hook and unsaved/cancel semantics against
            # a clearly synthetic native share-sheet response.
            page.evaluate('''() => {
                window.webkit={messageHandlers:{microblocks:{postMessage(e) {
                    window.exportFixture=e;
                    setTimeout(()=>MicroBlocksIPhone.receive({type:'exported',id:e.id,saved:false}),0);
                }}}};
                MB_editor.unsavedEdits=true;
                return MB_editor.saveProject();
            }''')
            assert page.evaluate('MB_editor.unsavedEdits')
            page.evaluate('''() => {
                webkit.messageHandlers.microblocks.postMessage=e=>{
                    window.exportFixture=e;
                    setTimeout(()=>MicroBlocksIPhone.receive({type:'exported',id:e.id,saved:true,name:e.name}),0);
                };
                return MB_editor.saveProject();
            }''')
            assert not page.evaluate('MB_editor.unsavedEdits')
            exported = page.evaluate('window.exportFixture.text')
            restored = page.evaluate('''text => {
                const project = new MB_Project(); project.loadFromString(text);
                const script = project.main.scripts[0][2];
                return {selector:script.selector, values:script.inputs().map(i=>i.evaluate())};
            }''', exported)
            assert restored == {'selector': '+', 'values': [20, 22]}, (exported, restored)
            assert not errors, errors
            report = {'browser': browser.version, 'environment': 'desktop Chromium with mobile emulation',
                      'physical_iphone': False, 'native_socket': False, 'engine_loaded': True,
                      'touch_drag': {'before': before, 'after': after}, 'usb_only_boundary': True,
                      'offline_connection_disabled': True, 'portrait_landscape': True,
                      'native_export_response': 'synthetic success and cancellation',
                      'project_roundtrip': True, 'page_errors': errors}
            (args.output / 'browser.json').write_text(json.dumps(report, indent=2) + '\n')
            print(json.dumps(report))
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
