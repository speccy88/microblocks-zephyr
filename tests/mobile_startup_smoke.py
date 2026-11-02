#!/usr/bin/env python3
"""Hold real profile loading to exercise the phone's cold-start interaction gate."""
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
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--browser')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(a.editor)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=a.browser,headless=True,chromium_sandbox=True)
            page=browser.new_page(viewport={'width':430,'height':932},is_mobile=True,has_touch=True)
            held,errors=[],[]
            page.on('pageerror',lambda error:errors.append(str(error)))
            page.route('**/iphone-boards.json',lambda route:held.append(route))
            for cycle in range(3):
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html',wait_until='domcontentloaded')
                menu=page.locator('#iphone-menu');menu.wait_for(state='attached')
                assert menu.is_disabled(), 'Visible chrome must wait for the real editor'
                assert page.locator('.iphone-toolbar').get_attribute('aria-busy')=='true'
                # Request ownership is deterministic; no arbitrary startup sleep.
                for _ in range(100):
                    if held: break
                    page.wait_for_timeout(20)
                assert len(held)==1
                held.pop().fulfill(status=200,content_type='application/json',body=(a.editor/'iphone-boards.json').read_text())
                page.wait_for_function('() => typeof MicroBlocksIPhone!=="undefined" && MicroBlocksIPhone.gestures && !document.getElementById("iphone-menu").disabled')
                assert page.locator('.iphone-toolbar').get_attribute('aria-busy')=='false'
                assert page.locator('[data-ide="app-preloader"]').is_hidden()
                menu.click();assert page.get_by_role('button',name='Project',exact=True).is_visible()
                menu.click();assert page.locator('#iphone-menu-panel').is_hidden()
            assert not errors,errors
            report={'cycles':3,'held_profile_loading':True,'actions_disabled_until_ready':True,
                'first_ready_menu_tap':True,'physical_iphone':False,'page_errors':errors}
            (a.output/'startup.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8');print(json.dumps(report))
            browser.close()
    finally: server.shutdown()


if __name__=='__main__':main()
