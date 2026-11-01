#!/usr/bin/env python3
"""Trusted Chromium touch tests of the real editor; not physical iPhone evidence."""
# SPDX-License-Identifier: MIT
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from iphone_browser_smoke import QuietHandler

FIXTURE = "projectName 'Touch example'\nmodule 'main'\nscript 40 60 (+ 20 22)\nscript 950 1200 (+ 4 5)\n"
SIZES = [(375, 667), (667, 375), (390, 844), (844, 390), (430, 932), (932, 430)]
STACK_FIXTURE = "projectName 'Insert example'\nmodule 'main'\nscript 40 80 {\nwaitMillis 10\nwaitMillis 20\n}\n"


class Touch:
    def __init__(self, page, context):
        self.page = page
        self.cdp = context.new_cdp_session(page)

    def send(self, kind, points, ids=None):
        self.cdp.send('Input.dispatchTouchEvent', {'type': kind, 'touchPoints': [
            {'x': p[0], 'y': p[1], 'id': ids[i] if ids else i + 1} for i, p in enumerate(points)]})
        self.page.wait_for_timeout(25)

    def drag(self, start, end, cancel=False):
        self.send('touchStart', [start])
        for i in range(1, 11):
            self.send('touchMove', [(start[0] + (end[0] - start[0]) * i / 10,
                                     start[1] + (end[1] - start[1]) * i / 10)])
        self.send('touchCancel' if cancel else 'touchEnd', [])
        self.page.wait_for_timeout(100)

    def pinch(self, center, initial, final, shift=(0, 0), cancel=False):
        x, y = center
        self.send('touchStart', [(x - initial / 2, y), (x + initial / 2, y)])
        for i in range(1, 11):
            d = initial + (final - initial) * i / 10
            dx, dy = shift[0] * i / 10, shift[1] * i / 10
            self.send('touchMove', [(x + dx - d / 2, y + dy), (x + dx + d / 2, y + dy)])
        self.send('touchCancel' if cancel else 'touchEnd', [])
        self.page.wait_for_timeout(100)


def script_state(page):
    return page.evaluate('''() => {
        MB_editor.updateProject();
        return MB_editor.project.codeString();
    }''')


def block_flows(page, touch):
    """Use stock block objects and drop handlers, not a simulated editor."""
    page.evaluate('text => { MB_editor.removeAllScripts(); MB_editor.updateProject(); return MB_editor.openProjectFromString(text, "Touch example.ubp"); }', FIXTURE)
    page.evaluate('MB_editor.setBlockScalePercent(100)')
    page.wait_for_timeout(350)

    def reset_scroll():
        page.evaluate('''() => { const f=MB_editor.scriptsFrame;
            f.scrollX(100000); f.scrollY(100000); f.adjustScrollBars(); }''')

    def first_point():
        return page.evaluate('''() => {
            const b=MB_editor.scripts.children.find(b=>b instanceof BlockMorph && b.inputs()[0]?.evaluate()===20),r=canvas.getBoundingClientRect();
            return [r.x+(b.left()+5)*ZOOM,r.y+(b.top()+5)*ZOOM];
        }''')

    reset_scroll()
    before = script_state(page)
    page.locator('#iphone-hand').click()
    start = first_point()
    old = page.evaluate('MB_editor.scripts.left()')
    touch.drag(start, (start[0] - 25, start[1] - 25))
    assert page.evaluate('MB_editor.scripts.left()') < old - 20
    assert script_state(page) == before
    page.locator('#iphone-hand').click()
    reset_scroll()
    # A second finger before the grab becomes navigation, never a block click.
    start = first_point()
    touch.send('touchStart', [start])
    touch.send('touchStart', [start, (start[0] + 100, start[1])])
    touch.send('touchMove', [(start[0] - 15, start[1] - 15), (start[0] + 85, start[1] - 15)])
    touch.send('touchEnd', [])
    page.wait_for_timeout(400)
    assert script_state(page) == before
    assert page.evaluate('world.hand.children.length') == 0
    assert not page.evaluate('!!world.activeMenu')
    reset_scroll()
    # Secondary lift during an actual grab must leave the primary drag alive.
    start = first_point()
    moved = (start[0] + 32, start[1] + 32)
    touch.send('touchStart', [start])
    touch.send('touchMove', [moved])
    assert page.evaluate('world.hand.children.length') == 1
    touch.send('touchStart', [moved, (moved[0] + 80, moved[1])])
    # CDP touchEnd lists the lifted identifiers, not the remaining fingers.
    touch.send('touchEnd', [(moved[0] + 80, moved[1])], ids=[2])
    assert page.evaluate('world.hand.children.length') == 1
    touch.send('touchMove', [(moved[0] + 10, moved[1] + 10)])
    touch.send('touchCancel', [])
    assert page.evaluate('world.hand.children.length') == 0
    assert page.evaluate('MB_editor.scripts.topBlocks().length') == 2
    assert not page.evaluate('document.body.classList.contains("--is-dragging")')
    # Inserting a palette block keeps one top-level stack. It must still close
    # the palette, unlike the previous script-count-based heuristic.
    page.evaluate('text => { MB_editor.removeAllScripts(); MB_editor.updateProject(); return MB_editor.openProjectFromString(text, "Insert example.ubp"); }', STACK_FIXTURE)
    page.locator('#iphone-blocks').click()
    page.wait_for_timeout(100)
    palette = page.evaluate('''() => {
        const f=MB_editor.palette,r=canvas.getBoundingClientRect();
        for(let y=f.top()+90;y<f.bottom()-20;y+=5) {
            for(let x=f.right()-24;x>f.left()+20;x-=10) {
                const hit=world.topMorphAt(new Point(x,y));
                if(hit===f || hit===f.contents) return {x:r.x+x*ZOOM,y:r.y+y*ZOOM,top:f.contents.top()};
            }
        }
        throw new Error('No blank palette space to scroll');
    }''')
    touch.drag((palette['x'], palette['y']), (palette['x'], palette['y'] - 65))
    assert page.evaluate('MB_editor.palette.contents.top()') < palette['top'] - 20, (palette, page.evaluate('({top:MB_editor.palette.contents.top(),height:MB_editor.palette.contents.height(),frame:MB_editor.palette.height()})'))
    assert page.evaluate('MB_editor.palette.isVisible'), 'Scrolling must leave the palette open'
    drop = page.evaluate('''() => {
        const f=MB_editor.palette,b=f.contents.children.find(b=>b instanceof BlockMorph && b.selector==='waitMillis');
        f.scrollY(f.top()+35-b.top());
        const r=canvas.getBoundingClientRect(),target=MB_editor.scripts.topBlocks()[0];
        return {start:[r.x+(b.left()+5)*ZOOM,r.y+(b.top()+5)*ZOOM],
            end:[r.x+(target.left()+5)*ZOOM,r.y+(target.bottom()+5)*ZOOM]};
    }''')
    touch.drag(drop['start'], drop['end'])
    page.wait_for_function('!MB_editor.palette.isVisible')
    assert page.evaluate('MB_editor.scripts.topBlocks().length') == 1
    assert page.evaluate('MB_editor.scripts.topBlocks()[0].blockSequence().length') == 3
    text = script_state(page)
    assert text.count('waitMillis') == 3, text
    return {'hand_over_block': True, 'secondary_before_grab': True, 'secondary_during_grab': True,
            'cancelled_grab_retained': True, 'palette_scroll': True, 'stack_insertion': True,
            'insertion_collapses_palette': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--editor', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--browser')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietHandler, directory=str(args.editor)))
    threading.Thread(target=server.serve_forever, daemon=True).start()
    results, errors = [], []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(executable_path=args.browser, headless=True, chromium_sandbox=True)
            for index, (width, height) in enumerate(SIZES):
                context = browser.new_context(viewport={'width': width, 'height': height},
                                              device_scale_factor=2, is_mobile=True, has_touch=True)
                page = context.new_page()
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
                page.wait_for_function('typeof world !== "undefined" && world && MicroBlocksIPhone.gestures')
                page.evaluate('text => MB_editor.openProjectFromString(text, "Touch example.ubp")', FIXTURE)
                page.evaluate('MB_editor.setBlockScalePercent(100)')
                page.wait_for_timeout(400)
                touch = Touch(page, context)
                rect = page.locator('#canvas').bounding_box()
                assert rect['width'] == width and rect['height'] >= height - 49, rect
                targets = page.locator('.iphone-toolbar button').evaluate_all('els => els.map(e=>({label:e.ariaLabel,x:e.getBoundingClientRect().x,w:e.getBoundingClientRect().width,h:e.getBoundingClientRect().height}))')
                assert len(targets) == 6 and all(t['w'] >= 44 and t['h'] >= 44 and t['x'] >= 0 and t['x']+t['w'] <= width for t in targets), targets
                # Open/close every kind of chrome repeatedly, including short landscape.
                for _ in range(3):
                    page.locator('#iphone-menu').click()
                    assert page.get_by_role('button', name='Project', exact=True).is_visible()
                    labels = page.locator('#iphone-original-menus button').evaluate_all('els=>els.map(e=>getComputedStyle(e,"::after").content)')
                    assert all(any(name in label for label in labels) for name in ['Project', 'Settings', 'Language', 'Graph']), labels
                    panel = page.locator('#iphone-menu-panel').bounding_box()
                    assert panel['x'] >= 0 and panel['y'] + panel['height'] <= height, panel
                    page.get_by_role('button', name='Project', exact=True).click()
                    popup = page.locator('[data-ide="menu-container"] .menu')
                    popup.wait_for(state='visible')
                    bounds = popup.bounding_box()
                    assert bounds['x'] >= 0 and bounds['y'] >= 0 and bounds['x']+bounds['width'] <= width and bounds['y']+bounds['height'] <= height, bounds
                    assert all(h >= 44 for h in popup.locator('button').evaluate_all('els=>els.map(e=>e.getBoundingClientRect().height)'))
                    page.locator('#iphone-menu').click()
                    assert page.locator('#iphone-menu-panel').is_hidden()
                    assert not page.evaluate('!!Menus.current()')
                    page.locator('#iphone-blocks').click()
                    assert page.evaluate('MB_editor.palette.isVisible')
                    page.locator('#iphone-blocks').click()
                    assert not page.evaluate('MB_editor.palette.isVisible')
                    page.locator('#iphone-view').click()
                    assert page.locator('.scripts-pane-controls').is_visible()
                    tools = page.locator('.scripts-pane-controls').bounding_box()
                    assert tools['x'] >= 0, tools
                    page.locator('#iphone-view').click()
                    page.locator('#iphone-menu').click()
                    page.get_by_role('button', name='Hide controls', exact=True).click()
                    assert page.locator('.iphone-toolbar').is_hidden()
                    full = page.locator('#canvas').bounding_box()
                    assert full['height'] >= height - 1, full
                    page.get_by_role('button', name='Show controls', exact=True).click()
                    assert page.locator('.iphone-toolbar').is_visible()
                # Sheet repeatedly restores the hidden Morphic keyboard delegate.
                for _ in range(2):
                    page.get_by_role('button', name='Connect board', exact=True).click()
                    assert page.evaluate('GP.delegateKeyboardEvents')
                    assert page.locator('#iphone-open').is_disabled()
                    page.get_by_role('button', name='Close connection sheet', exact=True).click()
                    page.wait_for_function('!GP.delegateKeyboardEvents')
                before = script_state(page)
                page.evaluate('''() => {
                    window.viewSyncs = 0;
                    const sync = MB_editor.codeManager.syncScripts.bind(MB_editor.codeManager);
                    MB_editor.codeManager.syncScripts = (...args) => { window.viewSyncs++; return sync(...args); };
                }''')
                # A blank-space pan moves content, preserving all project coordinates.
                blank = (width * .75, rect['y'] + rect['height'] * .45)
                old = page.evaluate('({x:MB_editor.scripts.left(),y:MB_editor.scripts.top()})')
                touch.drag(blank, (blank[0] - 65, blank[1] - 65))
                new = page.evaluate('({x:MB_editor.scripts.left(),y:MB_editor.scripts.top()})')
                assert abs(old['x'] - new['x']) > 50 and abs(old['y'] - new['y']) > 50, (old, new)
                assert script_state(page) == before
                # Zoom about the midpoint, with simultaneous pan. The exact anchor
                # must remain under the translated midpoint (away from scroll bounds).
                center = (width / 2, rect['y'] + min(150, rect['height'] / 2))
                anchor = page.evaluate('''c => {
                    const r=canvas.getBoundingClientRect();
                    return {x:(c[0]-r.x)/ZOOM-MB_editor.scripts.left(),y:(c[1]-r.y)/ZOOM-MB_editor.scripts.top()};
                }''', center)
                touch.pinch(center, 100, 150, shift=(-12, -8))
                assert page.evaluate('ZOOM') == 1.5
                anchor_after = page.evaluate('''c => {
                    const r=canvas.getBoundingClientRect();
                    return {x:(c[0]-r.x)/ZOOM-MB_editor.scripts.left(),y:(c[1]-r.y)/ZOOM-MB_editor.scripts.top()};
                }''', (center[0] - 12, center[1] - 8))
                assert abs(anchor['x'] - anchor_after['x']) < 1.5 and abs(anchor['y'] - anchor_after['y']) < 1.5, (anchor, anchor_after)
                assert script_state(page) == before
                touch.pinch(center, 25, 260)
                assert page.evaluate('ZOOM') == 2.5
                touch.pinch(center, 260, 25)
                assert page.evaluate('ZOOM') == .5
                touch.pinch(center, 100, 200, cancel=True)
                assert page.evaluate('ZOOM') == 1
                # Lifting one pinch finger continues as a pan, without a jump
                # back into block editing or a change to the zoom.
                touch.send('touchStart', [(center[0]-50, center[1]), (center[0]+50, center[1])])
                touch.send('touchMove', [(center[0]-60, center[1]-10), (center[0]+40, center[1]-10)])
                touch.send('touchEnd', [(center[0]+40, center[1]-10)], ids=[2])
                touch.send('touchMove', [(center[0]-70, center[1]-20)])
                touch.send('touchEnd', [])
                assert page.evaluate('ZOOM') == 1
                assert script_state(page) == before
                assert page.evaluate('window.viewSyncs') == 0
                # A cancelled navigation must not strand the next block grab.
                page.evaluate('''() => {
                    const f=MB_editor.scriptsFrame;
                    f.scrollX(100000); f.scrollY(100000); f.adjustScrollBars();
                }''')
                drags = []
                for scale in [50, 100, 150, 250]:
                    page.evaluate('s => MB_editor.setBlockScalePercent(s)', scale)
                    page.evaluate('''() => {
                        const f=MB_editor.scriptsFrame;
                        f.scrollX(100000); f.scrollY(100000);
                        // Keep the measurement away from stock edge auto-scroll
                        // in the shortest landscape at the largest block size.
                        const b=MB_editor.scripts.children.find(b=>b instanceof BlockMorph && b.inputs()[0]?.evaluate()===20);
                        b.setPosition(MB_editor.scripts.position().add(new Point(40,20)));
                    }''')
                    b = page.evaluate('''() => {
                        const b=MB_editor.scripts.children.find(b=>b instanceof BlockMorph && b.inputs()[0]?.evaluate()===20),r=canvas.getBoundingClientRect();
                        return {x:r.x+(b.left()+5)*ZOOM,y:r.y+(b.top()+5)*ZOOM,top:b.top()-MB_editor.scripts.top()};
                    }''')
                    dy = 32
                    touch.drag((b['x'], b['y']), (b['x'] + 16, b['y'] + dy))
                    after = page.evaluate('''() => { const b=MB_editor.scripts.children.find(b=>b instanceof BlockMorph && b.inputs()[0]?.evaluate()===20);
                        return b.top()-MB_editor.scripts.top(); }''')
                    # Stock reporters deliberately sit 10 scene units above
                    # the pointer while held; the touch begins 5 units inside.
                    assert abs((after - b['top']) - (dy / (scale / 100) - 5)) < 2, (scale, b, after)
                    drags.append({'scale': scale, 'scene_delta': after - b['top']})
                page.wait_for_timeout(350)
                # Only navigation is counted here: drag edits legitimately sync.
                page.evaluate('window.viewSyncs=0')
                for scale in [100, 50, 250, 100]:
                    page.evaluate('s=>MB_editor.setBlockScalePercent(s)', scale)
                page.wait_for_timeout(300)
                assert page.evaluate('window.viewSyncs') == 0
                flows = block_flows(page, touch) if index < 2 else None
                assert not errors, errors
                page.screenshot(path=str(args.output / f'{width}x{height}.png'))
                if index == 0:
                    page.locator('#iphone-menu').click()
                    page.screenshot(path=str(args.output / 'menu.png'))
                    page.get_by_role('button', name='Hide controls', exact=True).click()
                    page.screenshot(path=str(args.output / 'focus.png'))
                    page.get_by_role('button', name='Show controls', exact=True).click()
                    page.locator('#iphone-blocks').click()
                    page.screenshot(path=str(args.output / 'palette.png'))
                results.append({'size': [width, height], 'canvas': rect, 'targets': targets,
                                'menu_focus_palette_cycles': 3, 'connection_cycles': 2,
                                'blank_pan': True, 'pinch_anchor': True, 'zoom_limits': [50, 250],
                                'cancel_recovery': True, 'pinch_to_single_pan': True, 'coordinate_drags': drags,
                                'view_syncs': 0, 'additional_block_flows': flows})
                context.close()
                print(f'PASS {width}x{height}', flush=True)
            report = {'environment': 'desktop Chromium mobile emulation', 'browser': browser.version,
                      'physical_iphone': False, 'native_socket': False, 'sizes': results, 'page_errors': errors}
            (args.output / 'touch.json').write_text(json.dumps(report, indent=2) + '\n', newline='\n')
            print(json.dumps(report))
            browser.close()
    finally:
        server.shutdown()


if __name__ == '__main__':
    main()
