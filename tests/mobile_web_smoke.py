#!/usr/bin/env python3
"""Actual browser/mobile UI checks; desktop emulation, never physical evidence."""
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
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--site', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--browser')
    p.add_argument('--engine', choices=['chromium','webkit'], default='chromium')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(args.site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, requests = [], []
    try:
        with sync_playwright() as pw:
            options = {'headless':True}
            if args.engine == 'chromium': options.update(executable_path=args.browser, chromium_sandbox=True)
            browser = getattr(pw, args.engine).launch(**options)
            context = browser.new_context(viewport={'width': 390, 'height': 844}, device_scale_factor=2, is_mobile=True, has_touch=True)
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('request', lambda request: requests.append(request.url))
            page.goto(f'http://127.0.0.1:{server.server_port}/')
            page.get_by_role('link', name='Open touch editor', exact=True).wait_for()
            assert page.get_by_role('link',name='Open touch editor',exact=True).evaluate('e=>getComputedStyle(e).color') == 'rgb(255, 255, 255)'
            assert not page.locator('#ide').get_attribute('src')
            assert not any('/editor/' in url for url in requests), requests
            page.screenshot(path=str(args.output / 'mobile-offer.png'))
            page.get_by_role('link', name='Open touch editor', exact=True).click()
            page.wait_for_function('typeof world !== "undefined" && world && MicroBlocksIPhone.gestures')
            page.locator('[data-ide="app-preloader"]').wait_for(state='hidden')
            assert page.evaluate('MicroBlocksBrowser.runtime') == 'pages'
            assert not page.evaluate('!!window.webkit?.messageHandlers?.microblocks')
            assert all(url.startswith((f'http://127.0.0.1:{server.server_port}/','data:','blob:')) for url in requests), requests
            page.evaluate('text=>MB_editor.openProjectFromString(text,"Touch example.ubp")', "projectName 'Touch example'\nmodule 'main'\nscript 40 60 (+ 20 22)\n")
            page.wait_for_timeout(300)
            page.screenshot(path=str(args.output / 'mobile-workspace.png'))
            page.get_by_role('button', name='Menu', exact=True).click()
            assert page.get_by_role('link', name='Desktop editor', exact=True).is_visible()
            page.screenshot(path=str(args.output / 'mobile-menu.png'))
            # Cancellation must retain the actual edited project and layout.
            url = page.url
            project = page.evaluate('MB_editor.updateProject(); MB_editor.project.codeString()')
            page.evaluate('''async () => {
                const dirty=MB_editor.hasUnsavedEdits, confirm=MB_editor.confirm;
                MB_editor.hasUnsavedEdits=()=>true;MB_editor.confirm=async()=>false;
                try {await MicroBlocksLayout.leave('desktop');}
                finally {MB_editor.hasUnsavedEdits=dirty;MB_editor.confirm=confirm;}
            }''')
            assert page.url == url
            assert page.evaluate('MB_editor.updateProject(); MB_editor.project.codeString()') == project
            page.get_by_role('button', name='Menu', exact=True).click()
            page.get_by_role('button', name='Connect board', exact=True).click()
            assert page.locator('#iphone-open').is_disabled()
            assert 'Safari on iPhone' in page.locator('.iphone-limit').inner_text()
            page.locator('#iphone-address').fill('8.8.8.8')
            page.get_by_role('button', name='Open board website', exact=True).click()
            assert 'private IPv4' in page.locator('#iphone-sheet-status').inner_text()
            page.select_option('#iphone-board', 'p2')
            assert page.locator('#mobile-open-board').is_disabled()
            assert page.locator('#iphone-address').is_disabled()
            page.get_by_role('button', name='Close connection sheet', exact=True).click()
            page.wait_for_function('!GP.delegateKeyboardEvents')
            desktop = browser.new_context(viewport={'width':1280,'height':900})
            normal = desktop.new_page()
            normal.on('pageerror', lambda error: errors.append(str(error)))
            normal.goto(f'http://127.0.0.1:{server.server_port}/')
            normal.locator('#ide[src]').wait_for(state='attached')
            assert not normal.locator('#mobile-editor-offer').count()
            normal.frame_locator('#ide').locator('[data-ide="app-preloader"]').wait_for(state='hidden',timeout=60000)
            normal.locator('.editor-notes').get_by_role('link',name='Touch editor',exact=True).click()
            normal.wait_for_url('**/mobile/index.html*')
            normal.wait_for_function('typeof world!=="undefined" && world && MicroBlocksIPhone.gestures')
            desktop.close()
            # Explicit desktop on a phone persists and can be reversed by URL.
            override = browser.new_context(viewport={'width':375,'height':667},is_mobile=True,has_touch=True)
            phone = override.new_page()
            phone.goto(f'http://127.0.0.1:{server.server_port}/?layout=desktop&board=propeller2')
            phone.locator('#ide[src]').wait_for(state='attached')
            assert '/propeller2/' in phone.locator('#ide').get_attribute('src')
            assert phone.evaluate('localStorage.getItem(MicroBlocksLayout.key)') == 'desktop'
            phone.goto(f'http://127.0.0.1:{server.server_port}/')
            assert not phone.locator('#mobile-editor-offer').count()
            phone.goto(f'http://127.0.0.1:{server.server_port}/?layout=mobile')
            phone.wait_for_url('**/mobile/index.html*')
            override.close()
            assert not errors, errors
            report = {'environment': 'desktop '+args.engine+' mobile emulation', 'browser': browser.version,
                      'mobile_detection': True, 'gp_not_loaded_before_choice': True,
                      'actual_editor_loaded': True, 'ios_native_bridge_impersonated': False,
                      'pages_connection_disabled': True, 'private_board_navigation_validated': True,
                      'real_desktop_started':True,'desktop_and_touch_switch':True,'explicit_phone_override':True,
                      'cancelled_mode_switch_keeps_project':True,
                      'runtime_assets_local':True,'desktop_target_preserved':True,
                      'physical_iphone': False, 'physical_board': False, 'page_errors': errors}
            (args.output / 'browser.json').write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
            print(json.dumps(report))
            browser.close()
    except Exception:
        print('Browser errors:', errors)
        raise
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
