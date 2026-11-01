#!/usr/bin/env python3
"""Serve actual decompressed flash assets; no board/VM is simulated."""
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
    p.add_argument('--packages',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--browser')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True);results=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=a.browser,headless=True,chromium_sandbox=True)
        for name in ['rlcd','xrp','fruit-jam']:
            server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(a.packages/name/'http-root')))
            threading.Thread(target=server.serve_forever,daemon=True).start()
            context=browser.new_context(viewport={'width':375,'height':667},is_mobile=True,has_touch=True)
            page=context.new_page();errors=[];sockets=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.on('websocket',lambda ws:sockets.append(ws.url))
            try:
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                page.get_by_role('link',name='Open touch editor',exact=True).click()
                page.wait_for_function('typeof world!=="undefined" && world && MicroBlocksIPhone.gestures')
                page.locator('[data-ide="app-preloader"]').wait_for(state='hidden')
                assert page.evaluate('MicroBlocksBrowser.board')==name
                assert not sockets, sockets
                for retry in range(2):
                    page.get_by_role('button',name='Connect board',exact=True).click()
                    assert page.locator('#iphone-board').is_disabled()
                    assert page.locator('#iphone-open').is_enabled()
                    page.locator('#iphone-open').click()
                    page.wait_for_function('document.getElementById("iphone-sheet-status").textContent.includes("failed")')
                    assert page.locator('.iphone-connect-sheet').is_visible()
                    assert page.locator('#iphone-open').is_enabled()
                    assert page.locator('#iphone-sheet-status').is_visible()
                    page.get_by_role('button',name='Close connection sheet',exact=True).click()
                page.get_by_role('button',name='Menu',exact=True).click()
                target=page.get_by_role('link',name='Desktop editor',exact=True).get_attribute('href')
                assert target.endswith('/microblocks.html?layout=desktop'),target
                page.screenshot(path=str(a.output/(name+'-menu.png')))
                assert not errors,errors
                results.append({'board':name,'root_offer':True,'correct_board_profile':True,
                    'automatic_connections':0,'missing_socket_honest_error_and_retry':True,
                    'physical_board':False})
            finally:context.close();server.shutdown()
        browser.close()
    (a.output/'boards.json').write_text(json.dumps(results,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(results))


if __name__=='__main__':main()
