#!/usr/bin/env python3
"""Focused post-transfer Fruit Jam VM/USB regression without program changes."""
# SPDX-License-Identifier: MIT
import argparse,json,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
from fruit_jam_serial import SerialVM
from test_fruit_jam_network import NetworkVM
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',required=True);p.add_argument('--port',default='COM8')
p.add_argument('--firmware-elf-sha256',required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
r={'result':'FAIL','started_utc':datetime.now(timezone.utc).isoformat(),'firmware_elf_sha256':a.firmware_elf_sha256,
   'host':a.host,'checks':{},'credentials_read':False,'coprocessor_reset':False,'hardware_outputs':False,'program_uploads':False}
vm=None;usb=None
try:
    usb=SerialVM(a.port);assert usb.identity['serial']=='E46570978F1E5A34';r['usb_identity']=usb.identity
    before=usb.all_crcs();assert before=={0:0x297d191b} and usb.run_reporter(0)==12;usb.close();usb=None
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open('http://'+a.host+'/api/status',timeout=8) as response:status=json.load(response)
    assert status['airlift']['ip']==a.host and status['airlift']['connection']==3 and status['airlift']['mac']=='58:e6:c5:f5:a3:58'
    r['checks']['http_status']=status
    vm=NetworkVM(a.host);assert vm.all_crcs()==before and [vm.run_reporter(0) for _ in range(3)]==[12]*3
    r['checks']['websocket_arithmetic_runs']=3;vm.close();vm=None;time.sleep(.1)
    vm=NetworkVM(a.host);assert vm.run_reporter(0)==12;r['checks']['websocket_reconnect']=True
    usb=SerialVM(a.port);assert usb.all_crcs()==before and usb.run_reporter(0)==12;usb.close();usb=None
    r['checks']['usb_takeover']=True;vm.close();vm=None;time.sleep(.1)
    vm=NetworkVM(a.host);assert vm.all_crcs()==before and vm.run_reporter(0)==12
    r['checks']['return_to_websocket']=True;vm.close();vm=None
    usb=SerialVM(a.port);assert usb.all_crcs()==before and usb.run_reporter(0)==12
    r['checks']['final_code_crc32']={str(n):f'{c:08x}' for n,c in before.items()};r['checks']['final_usb_arithmetic']=12;r['result']='PASS'
except Exception as exc:r['error']=type(exc).__name__+': '+str(exc)
finally:
    if vm:vm.close()
    if usb:usb.close()
    r['finished_utc']=datetime.now(timezone.utc).isoformat();a.evidence.write_text(json.dumps(r,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(r,indent=2))
raise SystemExit(0 if r['result']=='PASS' else 1)
