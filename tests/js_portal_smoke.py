#!/usr/bin/env python3
"""Direct editor tabs, current P2 palette and JavaScript-only publication."""
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
    p.add_argument('--site', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--browser')
    a = p.parse_args()
    a.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(a.site)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    errors, requests, sockets = [], [], []
    base = f'http://127.0.0.1:{server.server_port}/'
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=a.browser, headless=True, chromium_sandbox=True)
            context = browser.new_context(viewport={'width':1280, 'height':900})
            context.add_init_script("""window.serialRequests=0;
                if(navigator.serial)navigator.serial.requestPort=async()=>{
                    window.serialRequests++;throw Error('Hardware forbidden in UI test');
                };""")
            context.on('page', lambda page: page.on('pageerror', lambda error: errors.append(str(error))))
            context.on('request', lambda request: requests.append(request.url))
            context.on('page', lambda page: page.on('websocket', lambda socket: sockets.append(socket.url)))
            launcher = context.new_page()
            launcher.goto(base)
            choices = ['fruit-jam','waveshare','esp32p4','propeller2','xrp-rp2350','raspberry-pi5','microduck','unoq']
            assert launcher.locator('.board-choice').count() == len(choices)
            assert launcher.locator('iframe, select, .intro, .connections, .projects-note, footer').count() == 0
            assert not any('/engine/' in url or 'gp_wasm' in url for url in requests)
            for target in choices:
                link = launcher.locator(f'[data-board="{target}"]')
                assert link.is_visible()
                assert link.get_attribute('href') == f'js-preview/{target}/index.html'
                assert link.get_attribute('target') == '_blank'
                assert 'noopener' in link.get_attribute('rel')
                assert link.bounding_box()['y'] + link.bounding_box()['height'] < 900
            catalog = json.loads((a.site/'installation-catalog.json').read_text(encoding='utf-8'))
            assert launcher.locator('.board-card').count() == launcher.locator('.board-install').count() == 8
            for width in [320,390,1280]:
                launcher.set_viewport_size({'width':width,'height':900})
                assert launcher.evaluate('() => document.documentElement.scrollWidth<=innerWidth')
                for card in launcher.locator('.board-card').all():
                    editor = card.locator('.board-choice').bounding_box()
                    install = card.locator('.board-install').bounding_box()
                    assert abs(editor['y']-install['y']) < 1
                    assert 0 <= install['x']-(editor['x']+editor['width']) <= 16
                    assert editor['height'] >= 44 and install['height'] >= 44
                    assert editor['x'] >= 0 and install['x']+install['width'] <= width
                if width == 390:
                    launcher.screenshot(path=str(a.output/'paired-mobile.png'),full_page=True)
            launcher.screenshot(path=str(a.output/'board-choices.png'))
            launcher.locator('[data-board="propeller2"]').focus()
            launcher.keyboard.press('Tab')
            assert launcher.evaluate('() => document.activeElement.dataset.install') == 'propeller2'
            assert launcher.evaluate('() => getComputedStyle(document.activeElement).outlineStyle') == 'solid'

            def open_install(target):
                with context.expect_page() as popup:
                    launcher.locator(f'[data-install="{target}"]').click()
                install = popup.value
                install.wait_for_load_state('domcontentloaded')
                assert install.evaluate('window.opener===null')
                assert install.evaluate('window.serialRequests') == 0
                return install

            installation_checks = []
            for board in catalog['boards']:
                target = board['id']
                action = launcher.locator(f'[data-install="{target}"]')
                assert action.is_visible() and action.get_attribute('target') == '_blank'
                assert 'noopener' in action.get_attribute('rel')
                install = open_install(target)
                assert f'/install/{target}/index.html' in install.url
                if board['mode'] == 'browser':
                    assert target == 'propeller2'
                    assert install.locator('#install').is_disabled()
                else:
                    assert install.locator('h1').inner_text() == 'Install SmallVM: '+board['name']
                    release = install.locator('.release-status')
                    assert release.get_attribute('data-release-kind') == board['release']['kind']
                    assert release.locator('.release-link').get_attribute('href') == board['release']['url']
                    assert install.locator('script,iframe').count() == 0
                    install.set_viewport_size({'width':390,'height':844})
                    assert install.evaluate('() => document.documentElement.scrollWidth<=innerWidth')
                    if target in ['raspberry-pi5','microduck']:
                        install.screenshot(path=str(a.output/('guide-'+target+'.png')),full_page=True)
                installation_checks.append({'target':target,'mode':board['mode'],'separate_tab':True})
                install.close()

            def open_target(target):
                with context.expect_page() as popup:
                    launcher.locator(f'[data-board="{target}"]').click()
                page = popup.value
                page.wait_for_url('**/js-preview/'+target+'/index.html', wait_until='load', timeout=60000)
                try:
                    page.wait_for_function('''() => {
                        try { return typeof MB_editor==="object" && !!MB_editor.scripts && typeof world==="object" && !!world; }
                        catch (_) { return false; } // globals can still be in their initialization phase
                    }''', timeout=60000)
                except Exception:
                    print(json.dumps({'startup_failed_target':target,'url':page.url,'page_errors':errors}))
                    raise
                page.locator('[data-ide="app-preloader"]').wait_for(state='hidden', timeout=60000)
                assert f'/js-preview/{target}/' in page.url
                assert page.evaluate('window.opener === null')
                assert page.locator('img[src="img/microblocks-ide-logo.svg"], img[src="img/logo-preloader.svg"]').count() == 0
                assert page.locator('.editor-wordmark').is_visible()
                assert page.evaluate('window.serialRequests') == 0
                return page

            visited, p2_checks = [], {}
            for target in ['propeller2', *[name for name in choices if name != 'propeller2']]:
                page = open_target(target)
                assert page.evaluate('typeof MB_Compiler') == 'function'
                if target == 'propeller2':
                    installer = page.locator('#p2-install-vm')
                    assert installer.is_visible() and installer.get_attribute('target') == '_blank'
                    assert installer.get_attribute('href') == '../../install/propeller2/index.html'
                    receipt = json.loads((a.site/'js-preview/propeller2/target-library-source.json').read_text())
                    page.wait_for_function('!!MB_editor.project.libraryNamed("P2 Core")')
                    for name in receipt['modules']:
                        assert page.get_by_text(name, exact=True).is_visible()
                    assert page.get_by_text('P2 Hardware', exact=True).count() == 0
                    expected = receipt['function_names']
                    state = page.evaluate("""() => ({
                        runtime:MicroBlocksJSProfile.function_names,
                        functions:MB_editor.project.allFunctions().map(f=>f.functionName),
                        palette:[]
                    })""")
                    assert state['runtime'] == state['functions'] == expected
                    for module, selector in [('P2 Servo','p2ServoAngle'),('P2 Measurements','p2MeasureDutyPercent'),('P2 Count Rises','p2CountWindowMS'),('P2 Cogs','[p2:p2CogStart]'),('P2 UART','[p2:p2UART]'),('P2 DAC','[p2:p2DAC8]'),('P2 Capture Control','p2CaptureRunning')]:
                        page.get_by_text(module,exact=True).click()
                        assert page.evaluate('selector => MB_editor.palette.contents.allChildren().some(b=>b.selector===selector)',selector)
                    page.get_by_text('P2 Core',exact=True).click()
                    page.screenshot(path=str(a.output/'p2-current-blocks.png'))
                    source = "projectName 'Keep P2 work'\\nmodule 'main'\\nscript 40 60 (+ 20 22)\\n".replace('\\n','\n')
                    page.evaluate('MB_editor.confirm=async()=>true')
                    page.evaluate('text => MB_editor.openProjectFromString(text,"Keep P2 work.ubp")', source)
                    before = page.evaluate('MB_editor.updateProject();MB_editor.unsavedEdits=true;MB_editor.project.codeString()')
                    install_tab = open_install('propeller2')
                    assert page.evaluate('MB_editor.updateProject();MB_editor.project.codeString()') == before
                    assert page.evaluate('MB_editor.unsavedEdits')
                    install_tab.close()
                    other = open_target('waveshare')
                    assert page.evaluate('MB_editor.updateProject();MB_editor.project.codeString()') == before
                    assert page.evaluate('MB_editor.unsavedEdits')
                    other.close()
                    page.evaluate('MB_editor.confirm=async()=>false')
                    page.evaluate('MB_editor.newProject()')
                    assert page.evaluate('MB_editor.project.main.scripts.length') == 1
                    page.evaluate('MB_editor.confirm=async()=>true')
                    page.evaluate('MB_editor.newProject()')
                    assert page.evaluate('MB_editor.project.allFunctions().map(f=>f.functionName)') == expected
                    page.evaluate('text => MB_editor.openProjectFromString(text,"Keep P2 work.ubp")', source)
                    assert page.evaluate('MB_editor.project.main.scripts.length') == 1
                    saved = source + "module 'P2 Hardware' Output\\nversion 99 0\\nto p2KeptCustom { return 123 }\\n".replace('\\n','\n')
                    page.evaluate('text => MB_editor.openProjectFromString(text,"Custom P2.ubp")', saved)
                    assert page.evaluate('MB_editor.project.allFunctions().map(f=>f.functionName)') == ['p2KeptCustom']
                    assert page.get_by_text('P2 Hardware',exact=True).count() == 0
                    assert page.get_by_text('P2 Core',exact=True).is_visible()
                    p2_checks = {'automatic_functions':len(expected), 'visible_palette':True,'modules':receipt['modules'],'no_duplicate_palette':True,
                        'new_project':True, 'opened_scripts_preserved':True,
                        'existing_library_preserved':True, 'cancelled_new_preserves_project':True,
                        'other_tab_preserves_unsaved_project':True, 'serial_requests':0}
                else:
                    assert page.locator('#p2-install-vm').count() == 0
                visited.append(target)
                page.close(run_before_unload=False)
            assert launcher.url == base
            assert launcher.locator('a[href*="legacy/"]').count() == 0
            removed = ['legacy/index.html','editor/propeller2/microblocks.html','preview/editor/raspberry-pi5/microblocks.html']
            for path in removed:
                assert launcher.request.get(base+path).status == 404
            assert not errors, errors
            assert not sockets, sockets
            assert not any('gp_wasm' in url for url in requests)
            result = {'default_editor':'javascript', 'targets':visited, 'eight_immediate_choices':True,
                'separate_editor_tabs':True, 'opener_isolated':True, 'no_embedded_editor':True,
                'intro_connection_project_sections_removed':True, 'rabbit_logo_removed':True,
                'p2':p2_checks, 'removed_gp_urls':removed, 'automatic_sockets':sockets,
                'page_errors':errors, 'p2_install_link_visible':True, 'installation_choices':installation_checks,
                'paired_at_widths':[320,390,1280], 'install_tab_preserves_unsaved_project':True, 'physical_hardware':False}
            (a.output/'portal.json').write_text(json.dumps(result,indent=2)+'\n', encoding='utf-8')
            print(json.dumps(result))
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
