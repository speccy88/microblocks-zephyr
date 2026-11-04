#!/usr/bin/env python3
"""P2 output/measurement helpers on P0-1/P2-3; installed firmware unchanged."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import struct
import time
from pathlib import Path
from p2_serial import P2SerialVM,primitive


def decode(body):
    if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
    if body[0]==2:return body[1:].decode()
    if body[0]==3:return bool(body[1])
    raise AssertionError(body.hex())


def test(args):
    report=dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),result='FAIL',checks={},
        scope='non-DMA PWM/servo signal, bounded readiness and internally timed measurements',
        firmware_loaded=False,hardware_reset=False,dma_exercised=False,usb_smart_pin_exercised=False,
        external_clock_exercised=False,servo_motion_tested=False,speaker_sound_tested=False,
        absolute_time_or_voltage_accuracy_tested=False)
    vm=None
    try:
        p=json.loads(args.program.read_text(encoding='utf-8'))
        vm=P2SerialVM(args.port,args.usb_serial,'edge32');report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(10,1);vm.short(15)
        for name,index in p['variables'].items():
            raw=name.encode()+b'\xfe';vm.send(bytes([251,29,index])+len(raw).to_bytes(2,'little')+raw)
        for c in p['chunks']:
            raw=bytes(c['bytes']);vm.upload(c['id'],raw+b'\0'*(-len(raw)%4),c['kind'])
        scripts=dict(zip(['pwm','servo','angle','wait','read','high','period','frequency','duty','percent',
            'count','timed','ticks','raw'],p['scripts']))
        functions={c['name']:c['id'] for c in p['chunks'] if c['name']}
        queries={200:('p2RuntimeRevision',()),201:('p2PinRelease',(0,)),202:('p2PinRelease',(1,)),
            203:('p2PinRelease',(2,)),204:('p2PinRelease',(3,)),205:('p2PadNamed',(1,'Schmitt',False,False)),
            206:('p2PinSample',(1,)),207:('p2LocalPinDIR',(0,)),208:('p2LocalPinDIR',(2,)),
            209:('p2CogStackOK',(3,)),210:('p2CogRunning',(3,)),211:('p2PinModeHex',(0,)),
            212:('p2PinModeHex',(1,)),213:('digitalWrite',(0,False)),214:('digitalWrite',(2,False)),
            215:('p2Configure',(1,'count rises','Schmitt',0,0,False,0)),216:('p2PinRead',(1,)),
            217:('p2Configure',(3,'count rises','Schmitt',0,0,False,0)),218:('p2PinRead',(3,)),
            219:('p2Configure',(3,'count rises','Schmitt',18000000,0,False,0)),
            221:('p2CogStart',('usabilityWorkerPWM',3)),222:('p2CogStart',('usabilityWorkerTimed',3)),
            223:('p2CogStart',('usabilityWorkerRead',3))}
        for index,(name,values) in queries.items():vm.upload(index,primitive(name,values),2)
        def run(index,seconds=15):
            first=len(vm.events);vm.short(3,index)
            return decode(vm.wait(lambda e:e[:2]==(18,index),after=first,seconds=seconds)[2])
        def setvars(**values):
            for name,value in values.items():
                if isinstance(value,bool):body=bytes([3,value])
                elif isinstance(value,int):body=b'\x01'+struct.pack('<i',value)
                else:body=b'\x02'+value.encode()
                raw=body+b'\xfe';vm.send(bytes([251,8,p['variables'][name]])+len(raw).to_bytes(2,'little')+raw)
        def helper(name,**values):setvars(**values);return run(scripts[name])
        def value(name):
            index=p['variables'][name];first=len(vm.events);vm.short(7,index)
            return decode(vm.wait(lambda e:e[:2]==(21,index),after=first)[2])
        def until(condition,seconds=5):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if condition():return
                errors=[(e[1],e[2].hex()) for e in vm.events if e[0]==19]
                if errors:raise RuntimeError('VM error '+str(errors[-3:]))
                vm.pump()
            raise TimeoutError('usability phase')
        def release():
            for query in [201,202,203,204]:run(query)
        assert run(200)>=8;report['extension_revision']=run(200)
        release();pwm=[]
        for percent in [0,25,50,75,100]:
            assert helper('pwm',Pin=0,Hz=1000,Percent=percent) is True
            if percent in [0,100]:
                assert run(205) is True;assert run(206)==(percent==100)
                pwm.append(dict(percent=percent,constant_high=percent==100));continue
            period=helper('period',Pin=1,Timeout=500)
            high=helper('high');duty=helper('duty');rounded=helper('percent');hz=helper('frequency')
            assert abs(period-1000)<=2 and abs(high-percent*10)<=2,(percent,period,high)
            assert abs(duty-percent*10)<=3 and abs(rounded-percent)<=1 and abs(hz-1000)<=1
            assert int(run(212),16)&0x40==0
            pwm.append(dict(percent=percent,period_us=period,high_us=high,duty_per_mille=duty,read_percent=rounded,hz=hz))
        report['checks']['pwm_percent_endpoints_and_measurements']=pwm;release()
        print('PWM percent, endpoints and unit measurements PASS',flush=True)

        servo=[]
        for pulse in [500,1000,1500,2000,2500]:
            assert helper('servo',Pin=0,Usecs=pulse) is True
            period=helper('period',Pin=1,Timeout=500);high=helper('high')
            assert abs(period-20000)<=2 and abs(high-pulse)<=2,(pulse,period,high)
            servo.append(dict(request_us=pulse,high_us=high,period_us=period))
        mapped=[]
        for angle,low,high in [(0,1000,2000),(90,1000,2000),(180,1000,2000),(45,600,2400)]:
            assert helper('angle',Pin=0,Angle=angle,Low=low,High=high) is True
            actual=helper('high',Pin=1,Timeout=500);expected=low+angle*(high-low)//180
            assert abs(actual-expected)<=2,(angle,actual,expected)
            mapped.append(dict(angle=angle,zero_us=low,full_us=high,expected_us=expected,actual_us=actual))
        report['checks']['servo_signal_and_endpoint_mapping']=dict(pulses=servo,mapped=mapped,motion_tested=False)
        release();print('Servo electrical pulse widths and mapping PASS',flush=True)

        assert helper('pwm',Pin=0,Hz=1000,Percent=25) is True;mode=run(211)
        invalid=[('pwm',dict(Pin=0,Hz=1000,Percent=-1)),('pwm',dict(Percent=101)),('pwm',dict(Percent=25,Hz=0)),
            ('pwm',dict(Pin=63,Hz=1000)),('servo',dict(Pin=0,Usecs=499)),('servo',dict(Usecs=2501)),
            ('angle',dict(Angle=-1,Low=1000,High=2000)),('angle',dict(Angle=181)),
            ('angle',dict(Angle=90,Low=500,High=500)),('angle',dict(Low=400,High=2400)),
            ('angle',dict(Low=600,High=2600)),('timed',dict(Pin=0,Hz=0,Window=100))]
        for name,values in invalid:
            assert helper(name,**values) is False,(name,values)
            assert run(211)==mode
        assert abs(helper('high',Pin=1,Timeout=500)-250)<=2
        report['checks']['invalid_output_keeps_previous_waveform']=dict(cases=len(invalid),high_us=250)
        release()

        readings=[]
        for frequency in [50,1234,25000]:
            assert helper('pwm',Pin=0,Hz=frequency,Percent=40) is True
            actual=helper('frequency',Pin=1,Timeout=1000)
            assert abs(actual-frequency)<=1,(frequency,actual)
            readings.append(dict(request_hz=frequency,measured_hz=actual))
        release();run(213)
        began=time.monotonic();timeout=helper('period',Pin=1,Timeout=30);elapsed=(time.monotonic()-began)*1000
        assert timeout is False and 20<=elapsed<300,elapsed
        assert helper('raw',Result='bad',Timeout=100) is False
        assert helper('wait',Pin=63,Timeout=100) is False
        assert helper('ticks',Ticks=-1) is False
        ticks=[]
        for n,expected in [(0,0),(180,1),(180000,1000),(900000000,5000000)]:
            actual=helper('ticks',Ticks=n);assert type(actual) is int and actual==expected
            ticks.append([n,actual])
        report['checks']['frequency_timeout_and_tick_conversion']=dict(frequencies=readings,timeout_result=False,
            timeout_requested_ms=30,host_elapsed_ms=round(elapsed,2),ticks_to_us=ticks)

        zero=helper('count',Pin=1,Window=50,Timeout=500)
        assert type(zero) is int and zero==0,zero
        assert helper('pwm',Pin=0,Hz=1000,Percent=50) is True
        count=helper('count',Pin=1,Window=100,Timeout=1000);assert abs(count-100)<=1,count
        before=run(212);assert helper('count',Window=100,Timeout=10) is False and run(212)==before
        report['checks']['count_windows_zero_and_signal']=dict(zero_count=zero,window_ms=100,count=count,
            invalid_timeout_preserves_mode=True)
        release();print('Bounded waits, frequency, counts and numeric-zero distinction PASS',flush=True)

        run(213);assert run(215) is True
        began=time.monotonic();assert helper('timed',Pin=0,Hz=2000,Window=100) is True
        elapsed=(time.monotonic()-began)*1000;count=run(216)
        assert 195<=count<=210 and run(207) is False and 90<=elapsed<400,(count,elapsed)
        report['checks']['timed_square_normal_release']=dict(hz=2000,requested_ms=100,count=count,
            host_elapsed_ms=round(elapsed,2),driver_released=True)
        release()

        setvars(Done=0,Outcome=False);assert run(221) is True;until(lambda:value('Done')==1)
        assert value('WorkerCog')==3 and value('WorkerDIR') is False and value('Outcome') is True
        duty=helper('duty',Pin=3,Timeout=500);assert abs(duty-400)<=3,duty
        release();run(214);assert run(217) is True
        setvars(Done=0,GCDone=False,Outcome=False);assert run(222) is True
        first=len(vm.events);vm.short(3,functions['usabilityGarbage'])
        until(lambda:value('GCDone') is True and value('Done')==2)
        gc=sum(b'GC took' in e[2] for e in vm.events[first:]);assert gc>0
        count=run(218);elapsed=value('Elapsed')
        assert 195<=count<=250 and 100<=elapsed<500 and run(208) is False,(count,elapsed)
        assert value('WorkerDIR') is False and value('Outcome') is True
        release();run(214);assert run(219) is True
        setvars(Done=0,Outcome=False);assert run(223) is True;until(lambda:value('Done')==3)
        assert type(value('Outcome')) is int and value('Outcome')==0
        assert run(209) is True
        report['checks']['worker_services_gc_and_ready_zero']=dict(cog=3,worker_dir=False,duty_per_mille=duty,
            gc_events=gc,timed_count=count,timed_elapsed_ms=elapsed,driver_released=True,ready_zero=0,stack_guards=True)
        release();vm.short(6)
        assert run(207) is False and run(208) is False and run(210) is False
        report['checks']['stop_all_outputs_and_worker_idle']=True
        report['result']='PASS'
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error);raise
    finally:
        if vm:
            try:vm.short(15)
            finally:vm.close()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True);p.add_argument('--usb-serial',required=True)
    p.add_argument('--program',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True)
    test(p.parse_args())
