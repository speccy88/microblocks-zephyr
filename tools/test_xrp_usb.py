#!/usr/bin/env python3
"""Identified XRP physical USB acceptance; arithmetic and read-only inputs.

Baseline requires an empty installed VM and uses only vacant test chunks.
No motor, servo, PWM, RGB, Wi-Fi join or firmware update operation is sent.
Reset is performed separately with the known SWD probe, never through a
generic serial reset helper. The original MicroPython image is backed up first.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import time
from xrp_serial import XRPSerialVM
from test_wireless_vm import op,words,primitive
from test_generic_io import code_call

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True);parser.add_argument('--usb-serial',required=True)
    parser.add_argument('--phase',choices=('baseline','after-reset','inputs','cleanup'),required=True)
    parser.add_argument('--expected',type=Path);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();vm=None
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),phase=args.phase,checks={},
        motor_power='operator reported off; never enabled',motor_or_servo_commands_sent=False,
        physical_movement_validation=False,credentials_supplied=False)
    try:
        vm=XRPSerialVM(args.port,args.usb_serial);report['identity']=vm.identity
        report['version']=vm.version.lstrip('\x02')
        def sync(n):
            start=len(vm.events);vm.short(26,n);vm.wait(lambda e:e[:2]==(26,n),after=start)
        def run(code):vm.upload(234,code,2);return vm.run_reporter(234)
        sync(91);report['checks']['ping']=True
        if args.phase=='baseline':
            before=vm.all_crcs();assert not before,'Preserve existing VM code: expected a fresh empty image'
            report['checks']['code_crcs_before']=before
            reporter=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
            crcs={230:vm.upload(230,reporter,2)}
            assert [vm.run_reporter(230) for _ in range(10)]==[12]*10
            report['checks']['arithmetic_runs']=10
            edited=bytearray(reporter);edited[5]=17
            vm.upload(230,edited,2);assert vm.run_reporter(230)==13
            crcs[230]=vm.upload(230,reporter,2);report['checks']['live_edit_result']=13
            stream=words([op(2,1),op(7,0),op(3,99),0,op(7,1),op(6,1),op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
            crcs[231]=vm.upload(231,stream)
            start=len(vm.events);vm.short(3,231);vm.wait(lambda e:e[:2]==(17,231),seconds=20,after=start)
            outputs=[int(e[2][1:]) for e in vm.events[start:] if e[:2]==(20,254)]
            assert outputs==list(range(1,51));report['checks']['ordered_outputs']=outputs
            large=words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0])
            crcs[232]=vm.upload(232,large,fragmented=True)
            start=len(vm.events);vm.short(3,232);vm.wait(lambda e:e[:2]==(17,232),after=start)
            assert vm.variable(2)==42;report['checks']['fragmented_upload_bytes']=len(large)+7
            vm.send(bytes([251,32,7,100,0,1]));time.sleep(.35);sync(94)
            report['checks']['partial_frame_timeout_recovery']=True
            loop=words([op(9),op(2,3),op(8,5),op(22,-3)])
            vm.upload(233,loop);start=len(vm.events);vm.short(3,233)
            vm.wait(lambda e:e[:2]==(16,233),after=start);time.sleep(.1)
            vm.short(4,233);value=vm.variable(5);time.sleep(.15)
            assert value>0 and vm.variable(5)==value
            vm.short(2,233);sync(95);report['checks']['stop_and_variable_inspection']=True
            report['checks']['io_capabilities']=json.loads(run(primitive('ioCapabilities')))
            vm.short(2,234);sync(96)
            vm.close();vm=XRPSerialVM(args.port,args.usb_serial)
            assert vm.run_reporter(230)==12;report['checks']['reconnect_arithmetic']=12
            end=time.monotonic()+6
            while time.monotonic()<end:vm.pump()
            assert vm.all_crcs()==crcs
            report['checks']['code_crc32']={str(k):f'{v:08x}' for k,v in crcs.items()}
            report['checks']['snapshot_debounce_wait_seconds']=6
        elif args.phase=='after-reset':
            if not args.expected:raise ValueError('--expected baseline evidence required')
            expected=json.loads(args.expected.read_text())['checks']['code_crc32']
            actual={str(k):f'{v:08x}' for k,v in vm.all_crcs().items()}
            assert actual==expected,(actual,expected)
            assert vm.run_reporter(230)==12
            report['checks'].update(retained_crc32=actual,reboot_arithmetic=12)
        elif args.phase=='inputs':
            assert 234 not in vm.all_crcs(),'Temporary input-test chunk occupied'
            outcomes={}
            report['checks']['read_only_inputs']=outcomes
            calls={'imu_family_id':code_call(96,[0x6b,0x0f]),
                   **{'adc_gpio_'+str(p):code_call(86,[p]) for p in range(40,47)},
                   'user_button_level':code_call(88,[36,'up'])}
            for name,code in calls.items():
                try:
                    value=run(code)
                    if name=='imu_family_id':assert value==0x6c,value
                    elif name.startswith('adc_'):assert type(value)==int and 0<=value<=1023,value
                    else:assert type(value)==bool,value
                    outcomes[name]=dict(result='PASS',value=value)
                except Exception as exc:outcomes[name]=dict(result='FAIL',error=type(exc).__name__+': '+str(exc))
                args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
            for i,(a,b) in enumerate(((30,31),(24,25),(22,23),(2,3)),1):
                try:
                    run(code_call(37,[i,a,b,True],name='start',namespace=15));time.sleep(.05)
                    count=run(code_call(37,[i],name='count',namespace=15))
                    run(code_call(37,[i],name='stop',namespace=15))
                    outcomes['encoder_api_'+str(i)]=dict(result='PASS',count=count,motion_driven=False,edge_accuracy_validated=False)
                except Exception as exc:outcomes['encoder_api_'+str(i)]=dict(result='FAIL',error=type(exc).__name__+': '+str(exc))
            try:
                assert run(code_call(37,[1],name='captureStart')) is True;time.sleep(.035)
                count=run(code_call(37,name='captureCount'));assert 0<=count<=4
                run(code_call(37,name='captureEnd',command=True))
                outcomes['bounded_echo_capture_without_trigger']=dict(result='PASS',edges=count,distance_validated=False)
            except Exception as exc:outcomes['bounded_echo_capture_without_trigger']=dict(result='FAIL',error=type(exc).__name__+': '+str(exc))
            vm.short(2,234);sync(97);report['checks']['read_only_inputs']=outcomes
            assert all(x['result']=='PASS' for x in outcomes.values()),'One or more input checks failed'
        else:
            if not args.expected:raise ValueError('--expected baseline evidence required for cleanup')
            expected=json.loads(args.expected.read_text())['checks']['code_crc32']
            crcs=vm.all_crcs()
            assert {str(k):f'{v:08x}' for k,v in crcs.items()}==expected,'Unexpected code; never clear changed or unknown chunks'
            for chunk in crcs:vm.short(4,chunk);vm.short(2,chunk)
            sync(98);assert vm.all_crcs()=={}
            end=time.monotonic()+6
            while time.monotonic()<end:vm.pump()
            report['checks']['test_chunks_removed']=True
            report['checks']['code_crcs_after']={}
        report['result']='PASS'
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
        raise
    finally:
        if vm:vm.close()
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf8',newline='\n')
        print(json.dumps(report,indent=2))

if __name__=='__main__':main()
