#!/usr/bin/env python3
"""Real JS SFC editor and optional real SmallVM/WebSocket lifecycle evidence."""
# SPDX-License-Identifier: MPL-2.0
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from mobile_web_smoke import QuietHandler
from mobile_touch_smoke import Touch

ROOT=Path(__file__).resolve().parents[1]
SOURCE=(ROOT/'tests/fixtures/sfc_native/and-2.ubp').read_text()


def ready(page):
    page.wait_for_function('() => typeof world!=="undefined"&&world&&typeof MicroBlocksSFC!=="undefined"&&MB_editor.scripts')
    page.locator('[data-ide="app-preloader"]').wait_for(state='hidden')


def load(page):
    page.evaluate('text=>MB_editor.openProjectFromString(text,"SFC example.ubp")',SOURCE)
    page.evaluate('''() => {MB_editor.setBlockScalePercent(70);MB_editor.updateProject();MicroBlocksSFC.preflight(MB_editor.codeManager);
        window.sfcChart=MB_editor.project.allScripts()[0];window.sfcSequence=sfcChart.allBlocks().find(b=>b.selector==='sfcSequence');
        window.sfcSteps=sfcChart.allBlocks().filter(b=>b.selector==='sfcStep');}''')


def exercise(page,context,output,size,mobile):
    ready(page);load(page)
    original=page.evaluate('MB_editor.project.codeString()')
    assert page.evaluate('sfcSteps.length')==4
    # Actual loaded blocks have two native command cavities and shared-variable
    # menus, rather than a picture or a separate graph canvas.
    assert page.evaluate('sfcSteps.every(b=>b.inputs()[1] instanceof CommandSlotMorph&&b.inputs()[2] instanceof CommandSlotMorph)')
    menu=page.evaluate('Object.keys(sfcSteps[0].inputs()[0].sfcSharedVarsMenu())')
    assert 'Source' in menu and 'Gate' in menu,menu
    assert page.evaluate('sfcSteps[0].inputs()[0].evaluate()')=='Source'
    page.screenshot(path=str(output/f'{size[0]}x{size[1]}-sfc.png'))
    point=page.evaluate('''() => {const slot=sfcSteps[0].inputs()[0],r=canvas.getBoundingClientRect();
        return [r.x+(slot.right()-3)*ZOOM,r.y+slot.center().y*ZOOM];}''')
    (page.touchscreen.tap if mobile else page.mouse.click)(*point)
    page.locator('[data-ide="menu-container"]').get_by_text('Choice1',exact=True).click()
    page.wait_for_function('sfcSteps[0].inputs()[0].evaluate()==="Choice1"')
    # Seed a known history around this edit; timer-based autosave may also have
    # recorded an intermediate generated module while the menu was open.
    page.evaluate('''async source=>{MB_editor.updateProject();MicroBlocksSFC.preflight(MB_editor.codeManager);
        MB_editor.undoStack=[source];MB_editor.redoStack=[];MB_editor.storeUndoState();await MB_editor.undo();}''',original)
    assert page.evaluate('MB_editor.project.allScripts()[0].allBlocks().find(b=>b.selector==="sfcStep").inputs()[0].evaluate()')=='Source'
    page.evaluate('MB_editor.redo()')
    assert page.evaluate('MB_editor.project.allScripts()[0].allBlocks().find(b=>b.selector==="sfcStep").inputs()[0].evaluate()')=='Choice1'
    page.evaluate('MB_editor.undo()')
    # The normal source rebuild/undo path keeps the native flow and generated
    # implementation canonical; compilation never replaces editable blocks.
    page.evaluate('text=>MB_editor.restoreUndoState(text)',original)
    assert page.evaluate('MB_editor.updateProject();MicroBlocksSFC.preflight(MB_editor.codeManager);MB_editor.project.codeString()')==original
    page.evaluate('''() => {MB_editor.selectCategory('cat;Control');window.sfcPalette=MB_editor.palette.contents.children.filter(b=>b instanceof BlockMorph&&b.selector.startsWith('sfc'));}''')
    assert page.evaluate('sfcPalette.length')==7
    # Expand a real copied palette block, using its native expander event path.
    counts=page.evaluate('''() => {const spec=MicroBlocksSFC.specs.find(s=>s[1]==='sfcAnd');const b=MB_Specs.blockForSpec(spec,'Control');
        b.isTemplate=false;const counts=[b.inputs().length];for(let i=0;i<5;i++){
          b.expander.mouseClickLeft(new Point(b.expander.right()-1,b.expander.center().y));counts.push(b.inputs().length);}
        return counts;}''')
    assert counts==[2,3,4,5,6,5],counts # at the limit only the contract arrow remains
    if mobile:
        touch=Touch(page,context)
        rect=page.locator('#canvas').bounding_box();center=(size[0]*.6,rect['y']+min(130,rect['height']*.5))
        before=page.evaluate('MB_editor.updateProject();MB_editor.project.codeString()')
        touch.pinch(center,100,130,shift=(-15,-10))
        touch.pinch(center,130,100)
        assert page.evaluate('MB_editor.updateProject();MB_editor.project.codeString()')==before
    return {'size':size,'mobile':mobile,'native_steps':4,'shared_variable_menu':True,'source_roundtrip':True,
            'native_palette_blocks':7,'expansion_counts':counts,'dropdown_selection_undo_redo':True,'pinch_preserves_source':mobile}


def real_vm(page,output):
    ready(page)
    page.get_by_role('button',name='Connect board',exact=True).click();page.locator('#iphone-open').click()
    page.wait_for_function('MB_connection.connectedToBoard()&&MB_connection.vmVersion===417')
    page.wait_for_function('!document.querySelector(".iphone-connect-sheet").open')
    load(page)
    page.evaluate('''() => {window.sfcValues={};window.sfcReads=0;const handle=MB_connection.handleMessage.bind(MB_connection);
        MB_connection.handleMessage=m=>{if(m[1]===21){sfcValues[m[2]]={value:MB_connection.returnedValue(m),read:++sfcReads};}return handle(m);};}''')
    def set_value(name,value):page.evaluate('p=>MB_editor.codeManager.setVar(MB_editor.project.indexForVar(p[0]),p[1])',[name,value])
    def read(name):
        old=page.evaluate('sfcReads');index=page.evaluate('n=>MB_editor.project.indexForVar(n)',name)
        page.evaluate('i=>MB_editor.codeManager.getVar(i)',index)
        page.wait_for_function('p=>sfcValues[p[0]]?.read>p[1]',arg=[index,old])
        return page.evaluate('i=>sfcValues[i].value',index)
    page.evaluate('MB_editor.codeManager.syncAndStartAll()')
    page.wait_for_function('sfcSteps.find(b=>b.inputs()[0].evaluate()==="Source").sfcActive===true')
    set_value('Gate',True)
    page.wait_for_function('sfcSteps.filter(b=>["B1","B2"].includes(b.inputs()[0].evaluate())).every(b=>b.sfcActive===true)')
    assert read('PeerSeen') is True
    page.screenshot(path=str(output/'real-vm-parallel-active.png'))
    set_value('Join',True)
    page.wait_for_function('sfcSteps.find(b=>b.inputs()[0].evaluate()==="After").sfcActive===true')
    owner=page.evaluate('MB_editor.codeManager.lookupChunkID(sfcChart)')
    page.evaluate('id=>MB_editor.codeManager.stopRunningChunk(id)',owner)
    page.wait_for_function('sfcSteps.every(b=>b.sfcActive!==true)')
    for name in ['Source','B1','B2','After']:assert read(name) is False
    assert read('_sfc1_status')==-3
    heartbeat=read('Heartbeat');page.wait_for_timeout(100);assert read('Heartbeat')>heartbeat
    # Edit an action after its hidden function has already been downloaded.
    # A source/CRC assertion alone cannot prove the VM received the new worker.
    page.evaluate('''async () => {const b=sfcSteps.find(b=>b.inputs()[0].evaluate()==='B2');
        b.inputs()[1].nestedBlock().inputs()[1].setContents(3);MB_editor.updateProject();
        await MB_editor.codeManager.syncScripts();}''')
    for name in ['Gate','Join','Done']:set_value(name,False)
    page.evaluate('id=>MB_editor.codeManager.runChunk(id)',owner)
    page.wait_for_function('sfcSteps.find(b=>b.inputs()[0].evaluate()==="Source").sfcActive===true')
    assert read('SourceEntry')==2
    set_value('Gate',True)
    page.wait_for_function('sfcSteps.filter(b=>["B1","B2"].includes(b.inputs()[0].evaluate())).every(b=>b.sfcActive===true)')
    assert read('B2Entry')==4,'VM must run the edited setup, not the previous hidden worker'
    page.evaluate('MB_connection.disconnect()')
    page.wait_for_function('sfcSteps.every(b=>b.sfcActive!==true)')
    return {'actual_compiler':True,'actual_VM':417,'browser_WebSocket':True,'live_parallel_step_colors':True,
        'owner_stop_clears_public_flags':True,'independent_task_continues':True,'reentry':True,'edited_worker_uploaded_and_executed':True,'disconnect_clears_live':True,
        'physical_iphone':False,'physical_board':False}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',type=Path);p.add_argument('--url');p.add_argument('--output',required=True,type=Path);p.add_argument('--browser');a=p.parse_args()
    a.output.mkdir(parents=True,exist_ok=True);server=None;errors=[];records=[]
    if not a.url:
        server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(a.site)))
        threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=a.browser,headless=True,chromium_sandbox=True)
            if a.url:
                assert a.url.startswith('http://127.0.0.1:')
                context=browser.new_context(viewport={'width':390,'height':844},is_mobile=True,has_touch=True)
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)));page.goto(a.url+'mobile/index.html')
                records.append(real_vm(page,a.output));context.close()
            else:
                for size,mobile in [((1280,900),False),((375,667),True),((667,375),True),((430,932),True),((932,430),True)]:
                    context=browser.new_context(viewport=dict(zip(('width','height'),size)),is_mobile=mobile,has_touch=mobile)
                    page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                    page.goto(f'http://127.0.0.1:{server.server_port}/'+('mobile/index.html' if mobile else 'js-preview/waveshare/index.html'))
                    try:records.append(exercise(page,context,a.output,size,mobile))
                    except BaseException:
                        page.screenshot(path=str(a.output/'failure.png'));print(json.dumps({'errors':errors,'body':page.locator('body').inner_text()[-1000:]}));raise
                    context.close();print('PASS SFC editor',size,flush=True)
            assert not errors,errors
            (a.output/'sfc-browser.json').write_text(json.dumps({'status':'PASS','records':records,'page_errors':errors,'physical_iphone':False},indent=2)+'\n')
            browser.close()
    finally:
        if server:server.shutdown()


if __name__=='__main__':main()
