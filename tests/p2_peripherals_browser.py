#!/usr/bin/env python3
"""Actual editor UI acceptance; hardware access is forbidden in this test."""
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
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--site',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--browser')
    args=parser.parse_args();args.output.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(args.site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    errors=[]
    names=['P2 LEDs','P2 Displays','P2 Peripherals','P2 Storage','P2 Sensors','P2 Audio']
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=args.browser,headless=True,chromium_sandbox=True)
            context=browser.new_context(viewport={'width':1280,'height':960})
            context.add_init_script("""window.hardwareRequests=0;
                const forbidden=()=>{window.hardwareRequests++;throw Error('Hardware forbidden in UI test');};
                Object.defineProperty(navigator,'serial',{configurable:true,value:{requestPort:forbidden,getPorts:forbidden}});
                window.WebSocket=class {constructor(){forbidden();}};
            """)
            page=context.new_page();page.on('pageerror',lambda error:errors.append(str(error)))
            url=f'http://127.0.0.1:{server.server_port}/js-preview/propeller2/index.html'
            page.goto(url)
            page.wait_for_function('typeof MB_editor==="object" && !!MB_editor.project.libraryNamed("P2 Core")',timeout=60000)
            page.locator('[data-ide="app-preloader"]').wait_for(state='hidden',timeout=60000)
            assert page.evaluate('MB_editor.project.allFunctions().length')==79
            for name in names:
                assert page.locator('.libraries__list').get_by_text(name,exact=True).count()==0
            for name in names:
                page.locator('.libraries__add-button').click()
                navigation=page.locator('.navigation__list')
                navigation.get_by_text('P2',exact=True).click()
                assert set(names).issubset(set(navigation.locator('li').all_inner_texts()))
                navigation.get_by_text(name,exact=True).click()
                page.wait_for_function('document.querySelector(".__field_description")?.textContent.includes("extension-9")')
                page.get_by_role('button',name='Open',exact=True).click()
                page.wait_for_function('name=>!!MB_editor.project.libraryNamed(name)',arg=name)
                page.locator('.libraries__list').get_by_text(name,exact=True).wait_for(state='visible')
            selectors={'P2 LEDs':'p2LEDUpdate','P2 Displays':'p2EPDInit',
                       'P2 Peripherals':'p2PeripheralFirmware','P2 Storage':'p2FileRead',
                       'P2 Sensors':'p2DHT22Read','P2 Audio':'p2PlayWAV'}
            for name,selector in selectors.items():
                page.locator('.libraries__list').get_by_text(name,exact=True).click()
                assert page.evaluate('selector=>MB_editor.palette.contents.allChildren().some(b=>b.selector===selector)',selector),selector
            state=page.evaluate(r"""() => {
                MB_editor.updateProject();MB_editor.codeManager.assignFunctionIDs();
                const functions=MB_editor.project.allFunctions();
                return {names:functions.map(f=>f.functionName),
                    bytes:functions.map(f=>MB_editor.codeManager.compiledBytesFor(f).length),
                    libraries:Array.from(MB_editor.project.libraries.values(),l=>l.codeString(MB_editor.project)).join('\n')};
            }""")
            assert all(0<n<1000 for n in state['bytes'])
            page.locator('.libraries__list').get_by_text('P2 Audio',exact=True).click()
            page.screenshot(path=str(args.output/'optional-libraries.png'))

            # Actual editor project serialization and bytecode recompilation, without sending code.
            page.evaluate('MB_editor.confirm=async()=>true')
            def compile_edit(value):
                source="projectName 'Interactive P2 test'\nmodule 'main'\nscript 40 60 (+ 20 "+str(value)+")\n"+state['libraries']
                page.evaluate('source=>MB_editor.openProjectFromString(source,"Interactive P2.ubp")',source)
                return page.evaluate("""() => {
                    MB_editor.updateProject();MB_editor.codeManager.assignFunctionIDs();
                    const script=MB_editor.project.allScripts().find(b=>b&&!b.isFunctionDefinition());
                    return {bytes:Array.from(MB_editor.codeManager.compiledBytesFor(script)),
                        functions:MB_editor.project.allFunctions().map(f=>f.functionName),
                        source:MB_editor.project.codeString()};
                }""")
            before=compile_edit(22);after=compile_edit(23)
            assert before['bytes']!=after['bytes']
            assert before['functions']==after['functions']
            assert sorted(before['functions'])==sorted(state['names']),{
                'missing':sorted(set(state['names'])-set(before['functions'])),
                'added':sorted(set(before['functions'])-set(state['names']))}
            page.evaluate('source=>MB_editor.openProjectFromString(source,"Saved P2.ubp")',after['source'])
            assert sorted(page.evaluate('MB_editor.project.allFunctions().map(f=>f.functionName)'))==sorted(state['names'])
            visible=page.locator('.libraries__list').inner_text()
            for dependency in ['GPS (neo-7m)','Gas (BME680)','Inertial Sensors','WAV PCM']:
                assert dependency not in visible,dependency+' must remain implementation-only after reload'
            assert 'candidate extension 9' in page.locator('body > div[role="status"]').inner_text()

            # Reuse the shipped graph, testing only synthetic input and CSV conversion.
            page.locator('.--graph').click()
            assert page.locator('#graph-canvas').is_visible()
            page.evaluate("document.dispatchEvent(new CustomEvent('graph.clear'));for(const value of ['12 true -5','22 false -15','32 true -25'])document.dispatchEvent(new CustomEvent('graph.data',{detail:{value}}))")
            assert page.evaluate('Graph.dataTracks.slice(0,3).map(t=>t.at(-1))')==[32,100,-25]
            assert page.evaluate('Graph.csvData()')=='12, 100, -5\n22, 0, -15\n32, 100, -25\n'
            page.screenshot(path=str(args.output/'existing-graph.png'))
            assert page.evaluate('window.hardwareRequests')==0
            assert not errors,errors
            result={'physical_hardware':False,'hardware_requests':0,'page_errors':errors,
                    'automatic_functions':79,'optional_libraries_added_through_UI':names,
                    'optional_palette_selectors':selectors,'compiled_functions':len(state['names']),
                    'project_save_reload_preserves_functions':True,'source_edit_changes_bytecode':True,
                    'hidden_dependencies_preserved_after_reload':True,
                    'live_board_execution_verified':False,'existing_graph_synthetic_input_and_CSV':True}
            (args.output/'peripherals-browser.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
            print(json.dumps(result));browser.close()
    finally:
        server.shutdown()


if __name__=='__main__':main()
