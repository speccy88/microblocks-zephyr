#!/usr/bin/env python3
"""Bounded physical native Wi-Fi/VM checks; preserves every existing code chunk.

Only the positively identified Fruit Jam USB port and its verified network IP
are used. No flash, vault read, coprocessor reset, sensor or audible/light test.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,json,struct,time,urllib.request
from datetime import datetime,timezone
from pathlib import Path
import websocket
from fruit_jam_serial import SerialVM
from fruit_jam_wifi import encode_request
from test_wireless_vm import VM,op,words

class NetworkVM(VM):
    all_crcs=SerialVM.all_crcs
    def send(self,data):self.ws.send_binary(data)

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--host',required=True);p.add_argument('--port',default='COM8');p.add_argument('--evidence',required=True,type=Path);a=p.parse_args()
    report={'result':'FAIL','started_utc':datetime.now(timezone.utc).isoformat(),'host':a.host,'checks':{},'credentials_read':False,'coprocessor_reset':False,'hardware_outputs':False}
    vm=None;before=None;owned=[]
    try:
        usb=SerialVM(a.port)
        try:
            assert usb.identity['serial']=='E46570978F1E5A34';report['usb_identity']=usb.identity
            before=usb.all_crcs();assert before.get(0)==0x297d191b and usb.run_reporter(0)==12
            owned=[n for n in range(254,0,-1) if n not in before][:4];assert len(owned)==4
        finally:usb.close()
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://'+a.host+'/api/status',timeout=8) as response:status=json.load(response)
        assert status['board']=='Adafruit Fruit Jam' and status['airlift']['mac']=='58:e6:c5:f5:a3:58' and status['airlift']['ip']==a.host
        report['checks']['initial_http_status']=status
        report['phase']='websocket_connect'
        vm=NetworkVM(a.host);report['checks']['websocket_ready']=True
        report['phase']='read_program_crcs'
        assert vm.all_crcs()==before
        reporter=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
        r,stream_chunk,large_chunk,loop_chunk=owned
        vm.upload(r,reporter,2);assert [vm.run_reporter(r) for _ in range(10)]==[12]*10
        report['checks']['arithmetic_runs']=10
        report['phase']='live_edit'
        edited=bytearray(reporter);edited[5]=17;vm.upload(r,edited,2);assert vm.run_reporter(r)==13;vm.upload(r,reporter,2)
        report['checks']['live_edit_result']=13
        stream=words([op(2,1),op(7,0),op(3,99),0,op(7,1),op(6,1),op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
        vm.upload(stream_chunk,stream);start=len(vm.events);vm.short(3,stream_chunk)
        vm.wait(lambda e:e[:2]==(17,stream_chunk),seconds=20,after=start)
        outputs=[int(e[2][1:]) for e in vm.events[start:] if e[:2]==(20,254)]
        assert outputs==list(range(1,51));report['checks']['ordered_outputs']=50
        large=words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0]);vm.upload(large_chunk,large,fragmented=True)
        start=len(vm.events);vm.short(3,large_chunk);vm.wait(lambda e:e[:2]==(17,large_chunk),after=start)
        report['checks']['fragmented_upload_bytes']=len(large)+7
        loop=words([op(9),op(2,3),op(8,5),op(22,-3)]);vm.upload(loop_chunk,loop)
        start=len(vm.events);vm.short(3,loop_chunk);vm.wait(lambda e:e[:2]==(16,loop_chunk),after=start);time.sleep(.1)
        vm.short(4,loop_chunk);value=vm.variable(5);time.sleep(.2);assert value>0 and vm.variable(5)==value
        report['checks']['stop_variable_inspection']=True
        # Deliberately fake fixture data. A network controller cannot submit
        # Wi-Fi credentials; this must be rejected before any NINA join.
        request_id=0x197001;packet=encode_request(2,request_id,bytearray(b'Unit'),bytearray(b'unit-key'))
        start=len(vm.events);vm.send(packet)
        answer=json.loads(vm.wait(lambda e:e[:2]==(205,0),after=start)[2]);assert answer['request']==request_id and not answer['accepted'] and answer['command_error']==-13
        assert answer['status']['generation']==status['airlift']['generation'];report['checks']['network_setup_rejected_before_join']=True
        try:
            other=NetworkVM(a.host)
        except websocket.WebSocketBadStatusException as exc:assert exc.status_code==503
        else:other.close();raise AssertionError('Second VM controller accepted')
        report['checks']['second_controller_rejected']=True
        vm.close();vm=None;time.sleep(.1)
        vm=NetworkVM(a.host);assert vm.run_reporter(r)==12
        report['checks']['websocket_reconnect']=True
        # Taking USB ownership must immediately preserve the program stream.
        usb=SerialVM(a.port)
        try:
            assert usb.run_reporter(0)==12
            assert {n:c for n,c in usb.all_crcs().items() if n not in owned}==before
        finally:usb.close()
        vm.close();vm=None;time.sleep(.1)
        vm=NetworkVM(a.host);assert vm.run_reporter(r)==12
        report['checks']['usb_priority_and_return_to_wifi']=True
        report['phase']='complete';report['result']='PASS'
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
        if vm:report['received_vm_events']=[{'kind':k,'index':n,'body_bytes':len(b)} for k,n,b in vm.events]
    finally:
        if vm:
            try:vm.close()
            except Exception:pass
        if before is not None:
            usb=None
            try:
                usb=SerialVM(a.port)
                for n in owned:usb.short(2,n)
                start=len(usb.events);usb.short(26,97);usb.wait(lambda e:e[:2]==(26,97),after=start)
                assert usb.all_crcs()==before and usb.run_reporter(0)==12
                report['checks']['cleanup_original_code_crc32']={str(n):f'{crc:08x}' for n,crc in before.items()}
                report['checks']['cleanup_usb_arithmetic']=12
            except Exception as exc:report['result']='FAIL';report['cleanup_error']=type(exc).__name__+': '+str(exc)
            finally:
                if usb:usb.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat();a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1
if __name__=='__main__':raise SystemExit(main())
