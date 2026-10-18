#!/usr/bin/env python3
"""Prompted input-only Fruit Jam button acceptance; no patterns or audio.

After the user is ready, hold button 1 for about one second and release it;
repeat for buttons 2 and 3. Never press Reset during this test. The three
reporter chunks are unused slots, removed on exit. Other saved code is retained.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,json,re,time
from datetime import datetime,timezone
from pathlib import Path
from fruit_jam_serial import SerialVM
from test_wireless_vm import primitive

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM8')
    parser.add_argument('--seconds',type=int,default=120)
    parser.add_argument('--firmware-elf-sha256',required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    if not 15<=args.seconds<=180:raise ValueError('Use 15..180 seconds')
    if not re.fullmatch('[0-9a-f]{64}',args.firmware_elf_sha256):raise ValueError('Expected ELF SHA256')
    report=dict(result='FAIL',scope='Physical input-only press/release of three Fruit Jam buttons',
        started_utc=datetime.now(timezone.utc).isoformat(),firmware_elf_sha256=args.firmware_elf_sha256,
        GPIOs=[0,4,5],events=[],presses=[],checks={},outputs_driven=False,audio_emitted=False,
        coprocessor_reset=False,external_sensor_access=False)
    vm=None;owned=[];before=None
    try:
        vm=SerialVM(args.port)
        assert vm.identity['serial']=='E46570978F1E5A34','Unexpected Fruit Jam'
        report['usb_identity']=vm.identity
        before=vm.all_crcs()
        owned=[n for n in range(254,-1,-1) if n not in before][:3]
        if len(owned)!=3:raise RuntimeError('Need three unused reporter chunks')
        report['temporary_chunks']=owned
        for button,chunk in enumerate(owned,1):vm.upload(chunk,primitive('buttonPressed',[button]),2)
        started=time.monotonic();deadline=started+args.seconds
        previous=None;candidate=None;stable_count=0;stable=None
        initial_released=False;expected=1;pressed_since=None;final_released_since=None
        print(json.dumps({'state':'READY','instructions':'Hold button 1 for one second, release two seconds; then button 2, then button 3. Do not press Reset.'}),flush=True)
        while time.monotonic()<deadline:
            values=tuple(vm.run_reporter(chunk) for chunk in owned)
            assert all(type(value) is bool for value in values),'Expected three Boolean button replies'
            if values==candidate:stable_count+=1
            else:candidate=values;stable_count=1
            if stable_count>=2 and values!=stable:
                stable=values
                event={'elapsed_ms':round((time.monotonic()-started)*1000),'pressed':[i+1 for i,v in enumerate(values) if v]}
                report['events'].append(event);print(json.dumps(event),flush=True)
                if not initial_released:
                    if not any(values):initial_released=True;report['checks']['initially_released']=True
                elif expected<=3:
                    if pressed_since is None:
                        if any(values):
                            assert values==tuple(i==expected for i in range(1,4)),'Unexpected button order or simultaneous press'
                            pressed_since=time.monotonic()
                    elif not any(values):
                        duration=round((time.monotonic()-pressed_since)*1000)
                        assert duration>=250,'Hold each button longer so stable press/release is measured'
                        report['presses'].append({'button':expected,'stable_hold_ms':duration,'release_observed':True})
                        expected+=1;pressed_since=None
                        if expected==4:final_released_since=time.monotonic()
                    else:assert values==tuple(i==expected for i in range(1,4)),'Unexpected button changed during hold'
            if expected==4 and stable==(False,False,False) and time.monotonic()-final_released_since>=.25:
                report['checks']['finally_released']=True;break
            time.sleep(.05)
        assert initial_released and expected==4 and report['checks'].get('finally_released'),'Timed out before three isolated press/release pairs'
        assert [item['button'] for item in report['presses']]==[1,2,3]
        report['checks']['physical_press_release_order']=[1,2,3]
        report['result']='PASS'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm:
            try:
                for chunk in owned:vm.short(2,chunk)
                start=len(vm.events);vm.short(26,97);vm.wait(lambda e:e[:2]==(26,97),after=start)
                if before is not None:
                    assert vm.all_crcs()==before,'Existing code changed during button acceptance'
                    report['checks']['retained_code_crc32']={str(n):f'{crc:08x}' for n,crc in before.items()}
                if before and 0 in before and before[0]==0x297d191b:
                    assert vm.run_reporter(0)==12;report['checks']['arithmetic_after']=12
            except Exception as exc:
                report['cleanup_error']=type(exc).__name__+': '+str(exc);report['result']='FAIL'
            finally:vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2),flush=True)
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
