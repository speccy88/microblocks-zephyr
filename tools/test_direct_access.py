#!/usr/bin/env python3
"""Verify direct binary programming, reconnect and powered reset persistence.

Owns only one initially vacant chunk; never changes saved Wi-Fi settings.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.error
import urllib.request
import websocket
from test_wireless_vm import VM

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--evidence',required=True,type=Path)
    parser.add_argument('--firmware-sha256',required=True)
    parser.add_argument('--reboot-port',required=True)
    args=parser.parse_args()
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
        firmware_sha256=args.firmware_sha256,checks={})
    vm=None;owned=False;chunk=251;original={}
    def crcs():
        index=len(vm.events);vm.short(38,1)
        data=vm.wait(lambda e:e[0]==39,seconds=8,after=index)[2]
        return {data[i]:int.from_bytes(data[i+1:i+5],'little') for i in range(0,len(data),5)}
    try:
        vm=VM(args.host)
        report['checks']['ready_received_without_sending_credentials']=True
        original=crcs();assert chunk not in original
        reporter=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
        owned=True;vm.upload(chunk,reporter,2);assert vm.run_reporter(chunk)==12
        edited=bytearray(reporter);edited[5]=17
        vm.upload(chunk,edited,2);assert vm.run_reporter(chunk)==13
        vm.close();vm=None;time.sleep(.2)
        vm=VM(args.host);assert vm.run_reporter(chunk)==13
        report['checks']['program_edit_and_reconnect_result']=13
        index=len(vm.events);vm.short(2,chunk);vm.short(26,97)
        vm.wait(lambda e:e[:2]==(26,97),after=index)
        assert crcs()==original;owned=False
        # Same-origin rules remain; malformed bodies must not save credentials.
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        statuses={}
        for label,origin in [('same_origin','http://'+args.host),('foreign_origin','http://example.invalid')]:
            req=urllib.request.Request('http://'+args.host+'/api/wifi',data=b'no-newline',
                headers={'Origin':origin,'Content-Type':'text/plain'},method='POST')
            try:
                with opener.open(req,timeout=5) as response:code=response.status
            except urllib.error.HTTPError as exc:code=exc.code
            statuses[label]=code
        assert statuses=={'same_origin':400,'foreign_origin':403},statuses
        report['checks']['wifi_malformed_post_rejected_without_save']=statuses
        vm.close();vm=None
        try:
            bad=websocket.create_connection('ws://'+args.host+'/ws/vm',origin='http://example.invalid',timeout=4,http_no_proxy=['*'])
        except (websocket.WebSocketException,OSError):report['checks']['foreign_websocket_origin_rejected']=True
        else:
            # Zephyr may send HTTP 101 before its setup callback rejects the
            # session. A successful upgrade alone is not VM-controller access.
            try:foreign_reply=bad.recv()
            except (websocket.WebSocketException,OSError):foreign_reply=None
            finally:bad.close()
            assert foreign_reply!='ready','Foreign origin obtained VM controller access'
            report['checks']['foreign_websocket_origin_rejected']=True
        time.sleep(3)
        import serial
        from esptool.reset import HardReset
        port=serial.Serial(port=None,baudrate=115200,timeout=.1)
        port.dtr=False;port.rts=False;port.port=args.reboot_port;port.open()
        try:HardReset(port,uses_usb=True).reset()
        finally:port.close()
        deadline=time.monotonic()+45
        while True:
            try:vm=VM(args.host);break
            except Exception:
                if time.monotonic()>deadline:raise
                time.sleep(.5)
        assert crcs()==original
        report['checks']['powered_reset_reconnect_without_credentials']=True
        report['original_program_crc32_preserved']={str(k):f'{v:08x}' for k,v in original.items()}
        report['result']='PASS'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if owned:
            try:
                if vm is None:vm=VM(args.host)
                vm.short(2,chunk);index=len(vm.events);vm.short(26,99)
                vm.wait(lambda e:e[:2]==(26,99),after=index)
                assert crcs()==original
            except Exception as exc:report.update(result='FAIL',cleanup_error=str(exc))
        if vm:vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
