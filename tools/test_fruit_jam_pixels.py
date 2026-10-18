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
    args=parser.parse_args()
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
        firmware_elf_sha256='aa748a7e23712c63c8c270ac4c743b51425577b15bb6fb5fc84327bacfad7c75',
        checks={},visual_confirmation=False,external_sensor_access=False,audio_emitted=False)
    vm=None
    def run(name,values=()):
        vm.upload(250,primitive(name,values),2)
        return vm.run_reporter(250)
    try:
        vm=SerialVM(args.port)
        assert vm.identity['serial']=='E46570978F1E5A34'
        report['usb_identity']=vm.identity
        assert run('pixelsOff') is False
        sequence=[]
        for index in range(1,6):
            assert run('pixel',[index,8,0,0]) is False
            sequence.append(dict(pixel=index,rgb=[8,0,0],duration_ms=220))
            time.sleep(.22)
            assert run('pixelsOff') is False
        for rgb in ([0,8,0],[0,0,8]):
            assert run('pixel',[1,*rgb]) is False
            sequence.append(dict(pixel=1,rgb=rgb,duration_ms=220))
            time.sleep(.22)
            assert run('pixelsOff') is False
        report['checks']['command_sequence']=sequence
        report['checks']['final_off_command']=True
        report['result']='PASS'
        report['scope']='Physical device accepted/completed commands; emitted light/colors need human observation'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm:
            try:
                run('pixelsOff');vm.short(2,250)
            except Exception as exc:report['cleanup_error']=str(exc)
            vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
