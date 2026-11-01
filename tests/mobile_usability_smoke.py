#!/usr/bin/env python3
"""Real editor locale, palette and pinch rendering regressions. No device claim."""
# SPDX-License-Identifier: MIT
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from mobile_web_smoke import QuietHandler
from mobile_touch_smoke import Touch, SIZES, FIXTURE, script_state

LIBRARY = """module 'A library with a long descriptive name for a small screen' Output
spec ' ' '[test:longBlock]' 'A deliberately long block with several inputs _ and _ and _' 'str str str' 'first' 'second' 'third'
"""


def exercise(page, touch, output, size):
    width, height = size
    page.wait_for_function('() => typeof world !== "undefined" && world && MicroBlocksIPhone.gestures')
    page.locator('[data-ide="app-preloader"]').wait_for(state='hidden')
    page.evaluate('text => MB_editor.openProjectFromString(text, "Locale example.ubp")', FIXTURE)
    page.evaluate('MB_editor.setBlockScalePercent(100)')
    before = script_state(page)
    locales = []
    for code, autonym, caption, save in [('fr', 'Français', 'Langue', 'Enregistrer le projet'),
                                        ('de', 'Deutsch', 'Sprache', 'Projekt speichern'),
                                        ('es', 'Castellano', 'Idioma', 'Guardar proyecto'),
                                        ('en', 'English', 'Language', 'Save project'),
                                        ('fr', 'Français', 'Langue', 'Enregistrer le projet')]:
        if page.locator('#iphone-menu-panel').is_hidden():
            page.locator('#iphone-menu').click()
        page.locator('#iphone-original-menus .--language').click()
        page.locator('[data-ide="menu-container"]').get_by_text(autonym, exact=True).click()
        page.wait_for_function('(code) => GetText.currentLocale === code && document.documentElement.lang === code', arg=code)
        page.wait_for_timeout(200)
        assert page.locator('#iphone-original-menus .--language').get_attribute('aria-label') == caption
        assert page.locator('#iphone-save').inner_text() == save
        assert page.evaluate('JSON.parse(localStorage["user-prefs"]).locale') == code
        assert script_state(page) == before, 'Locale changes must preserve source and positions'
        palette = page.evaluate('''() => MB_editor.palette.contents.children.filter(b=>b instanceof BlockMorph).map(b=>b.blockSpec)''')
        locales.append({'locale': code, 'language_caption': caption, 'palette': palette[:5]})
    assert locales[0]['palette'] != locales[3]['palette'], locales
    page.screenshot(path=str(output / f'{width}x{height}-french-menu.png'))
    # A real reload must apply the existing persisted preference to new chrome.
    page.reload()
    page.wait_for_function('() => typeof MicroBlocksIPhone !== "undefined" && MicroBlocksIPhone.gestures && document.documentElement.lang === "fr"')
    page.locator('[data-ide="app-preloader"]').wait_for(state='hidden')
    page.locator('#iphone-menu').click()
    assert page.locator('#iphone-save').inner_text() == 'Enregistrer le projet'
    page.locator('#iphone-menu').click()
    page.evaluate('text => MB_editor.importLibraryFromString(text, "long-name.ubl")', LIBRARY)
    page.locator('#iphone-blocks').click()
    name = page.locator('.category-button').filter(has_text='A library with a long descriptive name for a small screen')
    name.scroll_into_view_if_needed()
    name.click()
    labels = page.locator('.workspace__left .category-button l-, .libraries__add-button l-').evaluate_all('''els => els.map(e=>({
        text:e.innerText, overflow:getComputedStyle(e).textOverflow, scroll:e.scrollWidth, width:e.clientWidth,
        height:e.clientHeight, scrollHeight:e.scrollHeight}))''')
    assert labels and all(x['overflow'] != 'ellipsis' and x['scroll'] <= x['width'] + 1 and x['scrollHeight'] <= x['height'] + 1 for x in labels), labels
    grip = page.locator('#iphone-palette-resize')
    assert grip.bounding_box()['width'] >= 44
    old = page.evaluate('MB_editor.paletteWidth')
    r = grip.bounding_box()
    touch.drag((r['x']+22, r['y']+r['height']*.5), (r['x']+72, r['y']+r['height']*.5))
    new = page.evaluate('MB_editor.paletteWidth')
    assert new > old + 35, (old, new)
    page.locator('#iphone-palette-wide').click()
    assert abs(page.evaluate('MB_editor.paletteWidth') - (page.locator('.workspace__canvas-wrapper').bounding_box()['width'] - 44)) < 2
    grip.focus()
    grip.press('Home')
    assert page.evaluate('MB_editor.paletteWidth') == 90
    grip.press('End')
    # A wide landscape palette can fit the entire block. Narrow it deliberately
    # to verify access to overflow rather than demanding an unnecessary bar.
    grip.press('Home')
    # Long blocks remain reachable with the stock horizontal palette scroll.
    scroll = page.evaluate('''() => {const f=MB_editor.palette; f.adjustScrollBars();
        const before=f.contents.left(); f.scrollX(-10000); f.adjustScrollBars();
        return {before,after:f.contents.left(),bar:f.hBar.isVisible};}''')
    assert scroll['bar'] and scroll['after'] < scroll['before'], scroll
    page.screenshot(path=str(output / f'{width}x{height}-palette-overflow.png'))
    page.locator('#iphone-palette-wide').click()
    page.locator('#iphone-blocks').click()
    # Load an internal test fixture through the editor's undo/rebuild path.
    # Opening a file here correctly asks to save the imported library, which
    # leaves an unattended evaluate() awaiting the user's answer indefinitely.
    page.evaluate('text => MB_editor.restoreUndoState(text)', FIXTURE)
    page.evaluate('MB_editor.setBlockScalePercent(100)')
    # Keep a real block close to the pinch anchor in wide landscape as well.
    # Otherwise a correct zoom can move every block offscreen, making a blank
    # workspace indistinguishable from a cleared bitmap in pixel sampling.
    page.evaluate('x => MB_editor.scripts.topBlocks()[0].setPosition(MB_editor.scripts.position().add(new Point(x,60)))', width*.52)
    before = script_state(page)
    # Instrument the actual renderer, not a simulated camera. An unchanged
    # bitmap must never be reset. Palette rebuilds happen only at gesture end.
    page.evaluate('''() => {
        window.renderEvidence={dimensionWrites:0,layouts:0,frames:[]};
        new MutationObserver(items=>renderEvidence.dimensionWrites+=items.length).observe(world.worldCanvas,
            {attributes:true,attributeFilter:['width','height']});
        const layout=MB_editor.relayoutBlocks.bind(MB_editor);
        MB_editor.relayoutBlocks=(...args)=>{renderEvidence.layouts++;return layout(...args)};
        const f=MB_editor.scriptsFrame;f.scrollX(100000);f.scrollY(100000);f.adjustScrollBars();
    }''')
    rect = page.locator('#canvas').bounding_box()
    center = (width*.58, rect['y']+min(150, rect['height']*.5))
    touch.send('touchStart', [(center[0]-50, center[1]), (center[0]+50, center[1])])
    anchor = page.evaluate('''c=>({x:c[0]/ZOOM-MB_editor.scripts.left(),y:(c[1]-canvas.getBoundingClientRect().y)/ZOOM-MB_editor.scripts.top()})''', center)
    for i in range(1, 25):
        distance = 100 + i*2
        touch.send('touchMove', [(center[0]-distance/2-i*.25, center[1]-i*.2), (center[0]+distance/2-i*.25, center[1]-i*.2)])
        frame = page.evaluate('''() => {
            const c=world.worldCanvas,p=c.getContext('2d').getImageData(0,0,c.width,c.height).data;
            let colors=new Set();for(let i=0;i<p.length;i+=64)colors.add([p[i],p[i+1],p[i+2],p[i+3]].join(','));
            return {zoom:ZOOM,colors:colors.size,layouts:renderEvidence.layouts,x:MB_editor.scripts.left(),y:MB_editor.scripts.top()};}''')
        assert frame['colors'] > 5, frame
        assert frame['layouts'] == 0, frame
        expected = {'x': (center[0]-i*.25)/frame['zoom']-frame['x'],
                    'y': (center[1]-i*.2-rect['y'])/frame['zoom']-frame['y']}
        assert abs(anchor['x']-expected['x']) < 1.5 and abs(anchor['y']-expected['y']) < 1.5, (anchor, expected)
        page.evaluate('frame=>renderEvidence.frames.push(frame)', frame)
    touch.send('touchEnd', [])
    evidence = page.evaluate('renderEvidence')
    assert evidence['layouts'] == 1 and evidence['dimensionWrites'] == 0, evidence
    assert abs(page.evaluate('ZOOM') - 1.48) < .001
    assert script_state(page) == before
    page.screenshot(path=str(output / f'{width}x{height}-pinch.png'))
    return {'size': size, 'locales': locales, 'reload_locale': 'fr', 'labels': labels, 'palette_drag': [old, new],
            'horizontal_palette': scroll, 'continuous_pinch': evidence}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--editor', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--browser')
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(args.editor)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results, errors = [], []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(executable_path=args.browser, headless=True, chromium_sandbox=True)
            for size in SIZES:
                context = browser.new_context(viewport=dict(zip(('width', 'height'), size)), is_mobile=True, has_touch=True)
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
                try:
                    results.append(exercise(page, Touch(page, context), args.output, size))
                except Exception:
                    print(json.dumps({'page_errors':errors, 'body':page.locator('body').inner_text()[-1800:]}), flush=True)
                    page.screenshot(path=str(args.output / 'failure.png'))
                    raise
                assert not errors, errors
                context.close()
                print(f'PASS usability {size}', flush=True)
            (args.output / 'usability.json').write_text(json.dumps({'environment':'Chromium mobile emulation',
                'physical_iphone':False, 'sizes':results, 'page_errors':errors}, indent=2, ensure_ascii=False)+'\n', encoding='utf-8')
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
