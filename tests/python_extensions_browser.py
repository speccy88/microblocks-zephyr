#!/usr/bin/env python3
"""Actual visible domain blocks and an actual VM; no fabricated RPC/VM replies."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]


def run(url,output,browser_path,physical_pi=False):
    if not url.startswith('http://127.0.0.1:'):raise ValueError('Use the existing exact-port SSH loopback forward')
    output.mkdir(parents=True,exist_ok=True);errors=[]
    with sync_playwright() as pw:
        browser=pw.chromium.launch(executable_path=browser_path,headless=True,chromium_sandbox=True)
        context=browser.new_context(viewport={'width':1440,'height':1000})
        page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
        try:
            page.goto(url)
            page.wait_for_function('() => typeof MB_editor!=="undefined"&&MB_editor.scripts&&typeof MicroBlocksPythonBlocks!=="undefined"')
            page.locator('[data-ide="app-preloader"]').wait_for(state='hidden')
            assert not page.evaluate('MB_editor.project.hasUserCode()'),'empty editor must stay empty'
            print('PASS empty editor and Python palette loaded',flush=True)
            page.get_by_role('button',name='Connect local VM',exact=True).click()
            page.wait_for_function('() => MB_connection.connectedToBoard()&&MB_connection.vmVersion===417')
            # Acknowledge the real upstream 421-vs-417 notice. Do not falsify
            # the VM version or silently install firmware to dismiss it.
            page.get_by_text('Ok',exact=True).click()
            print('PASS real VM 417 connection and version notice',flush=True)
            page.evaluate('''() => {window.sqlValues={};window.sqlReads=0;window.actualResults=[];
                const handle=MB_connection.handleMessage.bind(MB_connection);
                MB_connection.handleMessage=m=>{if(m[1]===21)sqlValues[m[2]]={value:MB_connection.returnedValue(m),read:++sqlReads};return handle(m)};
                const show=MB_editor.showResult.bind(MB_editor);MB_editor.showResult=(id,v)=>{actualResults.push(v);show(id,v)};}''')
            source=(ROOT/'linux/extensions/examples/sqlite.ubp').read_text()
            page.evaluate('text=>{window.sqliteOpen=MB_editor.openProjectFromString(text,"SQLite readings.ubp");window.sqliteOpened=false;sqliteOpen.then(()=>{sqliteOpened=true});}',source)
            for _ in range(100):
                if page.evaluate('sqliteOpened'):break
                if page.get_by_text('Discard current project?',exact=True).is_visible():page.get_by_role('button',name='Yes',exact=True).click()
                page.wait_for_timeout(100)
            assert page.evaluate('sqliteOpened'),'normal project replacement must complete'
            print('PASS ordinary SQLite project opened',flush=True)
            page.evaluate('''() => {MB_editor.setBlockScalePercent(80);MB_editor.selectCategory('cat;Data');
                window.domainBlocks=MB_editor.palette.contents.children.filter(b=>b instanceof BlockMorph&&MicroBlocksPythonBlocks.selectors.includes(b.selector));
                MB_editor.updateProject();window.sqlScript=MB_editor.project.allScripts()[0];
                window.sqlInsert=sqlScript.allBlocks().find(b=>b.selector==='sqliteExecute'&&b.inputs()[0].evaluate().startsWith('INSERT'));}''')
            assert page.evaluate('domainBlocks.some(b=>b.selector==="sqliteQuery")&&domainBlocks.some(b=>b.selector==="httpGet")&&domainBlocks.some(b=>b.selector==="mqttPublish")')
            assert page.evaluate('!sqlScript.allBlocks().some(b=>/python|microduck|Begin|Release/.test(b.selector))')
            def read(name):
                old=page.evaluate('sqlReads');index=page.evaluate('n=>MB_editor.project.indexForVar(n)',name)
                page.evaluate('i=>MB_editor.codeManager.getVar(i)',index)
                page.wait_for_function('p=>sqlValues[p[0]]?.read>p[1]',arg=[index,old])
                return page.evaluate('i=>sqlValues[i].value',index)
            page.locator('.top-bar__controls-run').click()
            # The desktop control is normal IDE UI, compiling, uploading and
            # starting the user's saved project through the real connection.
            for _ in range(80):
                count=read('SQLCount')
                if type(count) is int and count>=1:break
                page.wait_for_timeout(50)
            else:raise AssertionError('SQLCount did not arrive from actual VM')
            first=count;heartbeat=read('Heartbeat');assert heartbeat>0
            print('PASS Start control, real SQL and independent heartbeat',flush=True)
            page.wait_for_function('() => !MB_editor.runningChunks.has(sqlScript)')
            # Edit the actual normal list input, then evaluate the actual stack.
            point=page.evaluate('''() => {const input=sqlInsert.inputs()[1].inputs()[1],r=canvas.getBoundingClientRect();
                return [r.x+input.center().x*ZOOM,r.y+input.center().y*ZOOM];}''')
            page.mouse.click(*point);page.keyboard.press('Control+A');page.keyboard.type('22600');page.keyboard.press('Enter')
            assert page.evaluate('Number(sqlInsert.inputs()[1].inputs()[1].evaluate())')==22600
            point=page.evaluate('''() => {const r=canvas.getBoundingClientRect();return [r.x+(sqlScript.left()+30)*ZOOM,r.y+(sqlScript.top()+15)*ZOOM];}''')
            page.mouse.click(*point)
            for _ in range(80):
                count=read('SQLCount')
                if count==first+1:break
                page.wait_for_timeout(50)
            else:raise AssertionError('Edited domain-block program did not execute')
            assert read('Heartbeat')>heartbeat
            assert read('SQLLatestValue')==22600,'the edited value must return from SQL, not only appear in the block'
            print('PASS real edited parameter returned from SQL',flush=True)
            rows=read('SQLRows');assert rows,'actual result must exist'
            page.screenshot(path=str(output/'pi-sqlite-blocks.png'))
            await_stop='async () => {await MB_editor.stopAll();await MB_connection.sendQueue;}'
            page.evaluate(await_stop)
            print('PASS normal stop completed',flush=True)
            before=page.evaluate('actualResults.length')
            point=page.evaluate('''() => {const input=sqlInsert.inputs()[0],r=canvas.getBoundingClientRect();return [r.x+input.center().x*ZOOM,r.y+input.center().y*ZOOM];}''')
            page.mouse.click(*point);page.keyboard.press('Control+A');page.keyboard.type('INSERT INTO missing_table VALUES (?,?)');page.keyboard.press('Enter')
            point=page.evaluate('''() => {const r=canvas.getBoundingClientRect();return [r.x+(sqlScript.left()+30)*ZOOM,r.y+(sqlScript.top()+15)*ZOOM];}''')
            page.mouse.click(*point)
            page.wait_for_function('n=>actualResults.slice(n).some(v=>String(v).includes("no such table"))',arg=before)
            page.screenshot(path=str(output/'sql-error-message.png'))
            page.evaluate('MB_connection.disconnect()')
            assert not errors,errors
            report={'status':'PASS','actual_js_compiler':True,'actual_smallvm':417,'actual_python_sqlite':True,
                'physical_pi':physical_pi,'physical_iphone':False,'domain_palette':page.evaluate('domainBlocks.map(b=>b.selector)'),
                'user_script_has_no_rpc':True,'normal_run_control':True,'edited_parameter':22600,'row_count_before':first,'row_count_after':count,
                'sql_value_verified':22600,'real_input_edit_and_stack_click':True,'independent_task_progress':True,'domain_sql_error_has_actionable_message':True,'page_errors':errors}
            (output/'browser.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report))
        except BaseException:
            page.screenshot(path=str(output/'failure.png'))
            print(json.dumps({'errors':errors,'body':page.locator('body').inner_text()[-1000:],'results':page.evaluate('typeof actualResults!=="undefined"?actualResults:[]')}));raise
        finally:context.close();browser.close()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--url',required=True);p.add_argument('--output',required=True,type=Path);p.add_argument('--browser');p.add_argument('--physical-pi',action='store_true');a=p.parse_args()
    run(a.url,a.output,a.browser,a.physical_pi)
