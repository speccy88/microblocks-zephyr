#!/usr/bin/env python3
"""Real installer UI with a synthetic Web Serial provider; never hardware."""
# SPDX-License-Identifier: MIT
import argparse
from functools import partial
from http.server import ThreadingHTTPServer
import json
from pathlib import Path
import threading
from playwright.sync_api import sync_playwright
from mobile_web_smoke import QuietHandler

FAKE_SERIAL = r'''
window.p2Test={requests:0,resets:0,flash:false,bytes:0,closes:0};
class P2TestPort {
  constructor(){this.running=window.p2TestRunning||null;this.flash=false;this.hex='';}
  async open(options){
    this.opened=true;this.baud=options.baudRate;
    this.readable=new ReadableStream({start:controller=>{this.rx=controller;}});
    this.writable=new WritableStream({write:bytes=>this.write(bytes)});
  }
  async close(){this.opened=false;p2Test.closes++;}
  async setSignals(signals){if(signals.dataTerminalReady){p2Test.resets++;this.running=this.flash?'v405 Parallax P2 Edge 32MB':null;}}
  version(){const raw=new TextEncoder().encode(this.running),p=new Uint8Array(raw.length+6);p.set([251,22,0,raw.length+1,0,2]);p.set(raw,6);return p;}
  async write(bytes){
    if(window.p2TestSlow)await new Promise(r=>setTimeout(r,3));
    if(bytes[0]===250&&bytes[1]===12){if(this.running)this.rx.enqueue(this.version());return;}
    const s=new TextDecoder().decode(bytes);
    if(s.startsWith('> Prop_Chk')){this.rx.enqueue(new TextEncoder().encode('\r\nProp_Ver '+(window.p2TestROM||'G')+'\r\n'));return;}
    if(s.startsWith('> Prop_Hex')||s.startsWith('> Prop_Txt')){this.hex='';return;}
    this.hex+=s;
    p2Test.bytes+=(s.match(/\b[0-9a-f]{2}\b/g)||[]).length;
    if(s.endsWith('?')){
      const raw=Uint8Array.from(atob(this.hex.replace(/[>\s?]/g,'')),c=>c.charCodeAt(0)),v=new DataView(raw.buffer);let sum=0;
      for(let i=0;i<raw.length;i+=4)sum=(sum+v.getUint32(i,true))>>>0;
      if(sum!==0x706f7250)throw Error('Synthetic ROM rejected RAM checksum');
      this.rx.enqueue(new TextEncoder().encode('.'));this.running='v405 Parallax P2 Edge 32MB';
    }
    if(s==='~'){this.flash=true;p2Test.flash=true;this.running='v405 Parallax P2 Edge 32MB';}
  }
}
const p2TestPort=new P2TestPort();
Object.defineProperty(navigator,'serial',{configurable:true,value:{requestPort:async options=>{
  if(options.filters[0].usbVendorId!==0x0403)throw Error('P2 FTDI filter missing');
  p2Test.requests++;return p2TestPort;
}}});
'''


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--site',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--browser')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    server=ThreadingHTTPServer(('127.0.0.1',0),partial(QuietHandler,directory=str(a.site)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/install/propeller2/index.html'
    errors=[];results={}
    try:
        with sync_playwright() as pw:
            browser=pw.chromium.launch(executable_path=a.browser,headless=True,chromium_sandbox=True)
            def page_for(prefix=''):
                context=browser.new_context(viewport={'width':1100,'height':1100})
                context.add_init_script(prefix+FAKE_SERIAL)
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                page.goto(url);return page
            for mode in ['ram','flash']:
                page=page_for()
                assert page.evaluate('p2Test.requests')==0
                assert page.locator('#install').is_disabled()
                page.locator('#check').click();page.wait_for_function('() => document.getElementById("status").textContent.startsWith("No SmallVM response")')
                assert page.locator('#install').is_disabled()
                page.select_option('#module','edge32')
                page.locator('input[value="'+mode+'"]').check()
                assert page.locator('#install').is_disabled()
                page.locator('#acknowledge').check()
                assert page.locator('#install').is_enabled()
                page.screenshot(path=str(a.output/(mode+'-choice.png')))
                page.locator('#install').click()
                page.wait_for_function('() => document.getElementById("open-editor").hidden===false',timeout=30000)
                status=page.locator('#status').inner_text()
                assert ('flash boot' if mode=='flash' else 'ROM checksum') in status
                state=page.evaluate('p2Test');assert state['requests']==1
                assert state['flash']==(mode=='flash') and state['resets']==(2 if mode=='flash' else 1)
                results[mode]={'status':status,'requests':state['requests'],'resets':state['resets'],'synthetic_serial':True}
                page.screenshot(path=str(a.output/(mode+'-complete.png')));page.context.close()
            page=page_for('window.p2TestRunning="v405 Parallax P2 Edge 32MB";')
            page.locator('#check').click();page.wait_for_function('() => document.getElementById("status").textContent.includes("already running")')
            assert page.locator('#install').is_disabled() and page.evaluate('p2Test.resets')==0
            results['running_vm_preserved']=True;page.context.close()
            page=page_for('window.p2TestRunning="v417 Other Board";')
            page.locator('#check').click();page.wait_for_function('() => document.getElementById("status").textContent.includes("different MicroBlocks")')
            assert page.locator('#install').is_disabled() and page.evaluate('p2Test.resets')==0
            results['other_vm_refused']=True;page.context.close()
            page=page_for('window.p2TestSlow=true;')
            page.locator('#check').click();page.wait_for_function('() => document.getElementById("status").textContent.startsWith("No SmallVM response")')
            page.select_option('#module','edge32');page.locator('input[value="flash"]').check();page.locator('#acknowledge').check()
            page.locator('#install').click();page.wait_for_function('() => document.getElementById("progress").value>0')
            page.locator('#cancel').click();page.wait_for_function('() => document.getElementById("status").textContent.includes("cancelled")')
            assert not page.evaluate('p2Test.flash');results['cancel_before_flash_programming']=True;page.context.close()
            unsupported=browser.new_page(viewport={'width':390,'height':844})
            unsupported.add_init_script('Object.defineProperty(navigator,"serial",{value:undefined});')
            unsupported.goto(url);assert unsupported.locator('#check').is_disabled()
            assert 'Web Serial is unavailable' in unsupported.locator('#status').inner_text()
            assert unsupported.evaluate('document.documentElement.scrollWidth<=innerWidth')
            results['unsupported_browser_has_no_connection']=True
            assert not errors,errors
            report={'status':'PASS','browser':browser.version,'checks':results,'page_errors':errors,'physical_hardware':False,'web_serial_provider':'synthetic'}
            (a.output/'installer.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
            print(json.dumps(report));browser.close()
    finally:server.shutdown()


if __name__=='__main__':main()
