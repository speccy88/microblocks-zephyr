#!/usr/bin/env python3
"""Short low-brightness onboard pixel test. Appearance needs human confirmation."""
# SPDX-License-Identifier: MPL-2.0
import argparse,json,time
from datetime import datetime,timezone
from pathlib import Path
from fruit_jam_serial import SerialVM
from test_wireless_vm import primitive

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM8')
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--firmware-elf-sha256',default='aa748a7e23712c63c8c270ac4c743b51425577b15bb6fb5fc84327bacfad7c75')
    parser.add_argument('--duration-ms',type=int,default=220)
    args=parser.parse_args()
    if not 100<=args.duration_ms<=1500:raise ValueError('Duration must be 100..1500 ms')
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
        firmware_elf_sha256=args.firmware_elf_sha256,
        checks={},visual_confirmation=False,external_sensor_access=False,audio_emitted=False)
    vm=None;chunk=None;occupied=None
    def run(name,values=()):
        vm.upload(chunk,primitive(name,values),2)
        return vm.run_reporter(chunk)
    try:
        vm=SerialVM(args.port)
        assert vm.identity['serial']=='E46570978F1E5A34'
        report['usb_identity']=vm.identity
        occupied=vm.all_crcs()
        chunk=next((n for n in range(254,-1,-1) if n not in occupied),None)
        if chunk is None:raise RuntimeError('No unused VM chunk for pixel test')
        assert run('pixelsOff') is False
        sequence=[]
        for index in range(1,6):
            assert run('pixel',[index,8,0,0]) is False
            sequence.append(dict(pixel=index,rgb=[8,0,0],duration_ms=args.duration_ms))
            time.sleep(args.duration_ms/1000)
            assert run('pixelsOff') is False
        for rgb in ([0,8,0],[0,0,8]):
            assert run('pixel',[1,*rgb]) is False
            sequence.append(dict(pixel=1,rgb=rgb,duration_ms=args.duration_ms))
            time.sleep(args.duration_ms/1000)
            assert run('pixelsOff') is False
        report['checks']['command_sequence']=sequence
        report['checks']['final_off_command']=True
        report['result']='PASS'
        report['scope']='Physical device accepted/completed commands; emitted light/colors need human observation'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm:
            try:
                if chunk is not None:
                    run('pixelsOff');vm.short(2,chunk)
                    start=len(vm.events);vm.short(26,97)
                    vm.wait(lambda e:e[:2]==(26,97),after=start)
                if occupied is not None:
                    assert vm.all_crcs()==occupied,'Cleanup changed existing VM code'
                    report['checks']['original_code_retained']=True
            except Exception as exc:
                report['cleanup_error']=type(exc).__name__+': '+str(exc)
                report['result']='FAIL'
            finally:vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
