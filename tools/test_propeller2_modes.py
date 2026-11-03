#!/usr/bin/env python3
"""Checked P2 library modes on disposable EC32MB project and wired pairs.

One driver per pair. No USB or power-converter circuit is attached/tested.
Synthetic external ADC data is digital; analog/clock accuracy is not measured.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import struct
import time
from pathlib import Path
from p2_serial import P2SerialVM, primitive

SCRIPTS = ['duty','feedback','noise','dac16','adc','scope','events','timeout',
           'periods','window','difference','external','capture','sample','sync_tx','sync_rx']


def test(args):
    report = dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='compiled P2 library helpers and wired-pair mode behavior',
        result='FAIL', checks={}, absolute_accuracy_tested=False,
        power_converter_tested=False, external_adc_converter_tested=False,
        contiguous_capture_tested=False, usb_mode_tested=False)
    vm = None
    try:
        compiled=json.loads(args.program.read_text(encoding='utf-8'))
        assert len(compiled['scripts'])==len(SCRIPTS)
        scripts=dict(zip(SCRIPTS,compiled['scripts']))
        vm=P2SerialVM(args.port,args.usb_serial,'edge32')
        report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(10,1);vm.short(15)
        for name,index in compiled['variables'].items():
            raw=name.encode()+b'\xfe'
            vm.send(bytes([251,29,index])+len(raw).to_bytes(2,'little')+raw)
        for c in compiled['chunks']:
            raw=bytes(c['bytes']);vm.upload(c['id'],raw+b'\0'*(-len(raw)%4),c['kind'])
        def call(name,*values):
            vm.upload(220,primitive(name,values),2)
            return vm.run_reporter(220)
        def helper(name,**values):
            for key,value in values.items():
                if isinstance(value,bool):body=bytes([3,value])
                elif isinstance(value,int):body=b'\x01'+struct.pack('<i',value)
                else:body=b'\x02'+value.encode()
                raw=body+b'\xfe'
                vm.send(bytes([251,8,compiled['variables'][key]])+len(raw).to_bytes(2,'little')+raw)
            return vm.run_reporter(scripts[name])
        def release(*pins):
            for pin in pins:assert call('p2PinRelease',pin) is True
        def setup(pin,mode,x=0,y=0,b=0):
            assert call('p2Configure',pin,mode,'Schmitt',x,y,False,b) is True
        def z(pin):return int(call('p2PinReadHex',pin),16)
        def value(name):
            index=compiled['variables'][name];first=len(vm.events);vm.short(7,index)
            event=vm.wait(lambda e:e[:2]==(21,index),after=first)
            body=event[2]
            if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
            if body[0]==3:return bool(body[1])
            return body

        def count_highs(pin,clocks=1800000):
            setup(pin,'count highs',clocks);return z(pin)
        report['extension_revision']=call('p2RuntimeRevision')
        assert report['extension_revision']>=4
        release(*range(8))

        ratios=[]
        for duty in [0,250,500,750,1000]:
            assert helper('duty',Pin=0,Value=duty,Period=100) is True
            high=count_highs(1);ratio=high/1800000
            assert abs(ratio-duty/1000)<.003,(duty,high)
            ratios.append(dict(duty_per_1000=duty,high_clocks=high,ratio=ratio))
            release(0,1)
        report['checks']['nco_duty_high_clock_ratios']=ratios
        print('NCO duty ratios PASS',flush=True)

        release(0,1,2,3,4,5)
        call('digitalWrite',0,False);call('digitalWrite',2,False)
        assert call('p2PadNamed',1,'Schmitt',False,False) is True
        assert call('p2PadNamed',3,'Schmitt',False,False) is True
        assert helper('feedback',Pin=4,Value=1000,Period=250,AOffset=-3,BOffset=-1) is True
        running=count_highs(5);assert abs(running/1800000-.25)<.01,running
        assert call('p2ConfigureInputs',4,'PWM SMPS','logic','ea600003','3a98',True,-3,-1) is True
        assert call('p2PinModeHex',4)=='57000054'
        assert count_highs(5)==450000
        call('digitalWrite',2,True)
        limited=count_highs(5);assert limited==0,limited
        call('digitalWrite',0,True);call('digitalWrite',2,False)
        inhibited=count_highs(5);assert inhibited==0,inhibited
        call('digitalWrite',0,False)
        resumed=count_highs(5);assert abs(resumed/1800000-.25)<.01,resumed
        report['checks']['feedback_pwm_digital_logic']=dict(output=4,receiver=5,
            voltage_input=1,current_input=3,running_high_clocks=running,
            current_limit_high_clocks=limited,voltage_inhibit_high_clocks=inhibited,
            resumed_high_clocks=resumed,power_converter_performance=False)
        release(0,1,2,3,4,5)
        print('Digital feedback PWM PASS',flush=True)

        gated=[]
        for mode in ['register up','register up down']:
            call('digitalWrite',0,False);call('digitalWrite',2,False)
            assert call('p2PadNamed',3,'Schmitt',False,False) is True
            setup(1,mode,b=2)
            assert call('p2Pulse',0,100,100,10) is True
            first=z(1)
            call('digitalWrite',2,True)
            assert call('p2Pulse',0,100,100,10) is True
            final=z(1)
            expected=0 if mode=='register up' else 0xfffffff6
            assert first==expected and final==(10 if mode=='register up' else 0),(mode,first,final)
            gated.append(dict(mode=mode,gate_low_hex=f'{first:08x}',gate_high_hex=f'{final:08x}'))
            release(0,1,2,3)
        call('digitalWrite',0,False);call('digitalWrite',2,False)
        assert call('p2PadNamed',3,'Schmitt',False,False) is True
        assert helper('difference',Pin=1,BOffset=2,Period=0,External=False) is True
        assert call('p2Pulse',0,100,100,12) is True
        assert call('p2Pulse',2,100,100,7) is True
        assert z(1)==5
        assert call('p2Duty',0,750,100) is True
        assert call('p2Duty',2,250,100) is True
        assert helper('difference',Pin=1,BOffset=2,Period=1800000,External=True) is True
        high_difference=z(1);assert abs(high_difference-900000)<2000,high_difference
        report['checks']['gated_and_difference_counters']=dict(gated=gated,difference=5,high_clock_difference=high_difference)
        release(0,1,2,3)
        print('Gated and difference counters PASS',flush=True)

        assert call('p2PWM',0,1000,250,False) is True
        measurements=[]
        for kind,result,quantity,expect in [('periods','clock ticks',10,1800000),
                ('periods','high clocks',10,450000),('window','clock ticks',1800000,1800000),
                ('window','high clocks',1800000,450000),('window','periods',1800000,10)]:
            assert helper(kind,Pin=1,Value=quantity,Period=quantity,Result=result,
                          Sensitivity='rise to rise',BOffset=0) is True
            actual=z(1)
            tolerance=1 if result=='periods' else (2000 if kind=='periods' else (45010 if result=='high clocks' else 180010))
            assert abs(actual-expect)<=tolerance,(kind,result,actual,expect)
            measurements.append(dict(kind=kind,result=result,value=actual))
        setup(1,'state ticks')
        state_ticks=z(1);assert min(abs(state_ticks-45000),abs(state_ticks-135000))<2000,state_ticks
        release(0,1)
        call('digitalWrite',0,False)
        assert helper('events',Pin=1,Value=20,Sensitivity='rise') is True
        assert call('p2Pulse',0,100,100,200) is True
        event_ticks=z(1);assert abs(event_ticks-720000)<2000,event_ticks
        release(0,1)
        call('digitalWrite',0,False)
        assert helper('timeout',Pin=1,Period=180000,Sensitivity='rise') is True
        assert call('p2PinReady',1) is True
        missing_ticks=z(1);assert missing_ticks>=180000,missing_ticks
        assert helper('timeout',Pin=1,Period=1800000,Sensitivity='rise') is True
        assert call('p2Frequency',0,1000) is True
        assert call('p2PinAck',1) is True
        assert call('p2PinReady',1) is False
        running_timeout=z(1);assert running_timeout<1800000,running_timeout
        call('digitalWrite',0,False)
        assert call('p2PinReady',1) is True
        stopped_timeout=z(1);assert stopped_timeout>=1800000,stopped_timeout
        report['checks']['timing_and_missing_event_timeout']=dict(measurements=measurements,
            twenty_rises_ticks=event_ticks,state_ticks=state_ticks,missing_event_ticks=missing_ticks,
            timeout_running_source_ticks=running_timeout,timeout_stopped_source_ticks=stopped_timeout)
        release(0,1)
        print('Period/window/event timing and timeout PASS',flush=True)

        transfers=[]
        for pwm in [False,True]:
            samples=[]
            for level in [4096,16384,32768,49152,61440]:
                assert helper('dac16',Pin=6,Value=level,Period=256,External=pwm,Circuit='DAC 990R 3V') is True
                measured=call('analogRead',7)
                samples.append(dict(level16=level,adc10=measured))
            assert all(b['adc10']>a['adc10'] for a,b in zip(samples,samples[1:])),samples
            assert all(abs(x['adc10']/1023-x['level16']/65535)<.04 for x in samples),samples
            transfers.append(dict(pwm_dither=pwm,samples=samples))
            release(6,7)
        assert helper('noise',Pin=6,Period=65536,Circuit='DAC 990R 3V') is True
        noise=[call('analogRead',7) for _ in range(5)]
        assert all(350<x<680 for x in noise),noise
        report['checks']['dac16_dither_and_noise']=dict(transfers=transfers,noise_adc10=noise,
            sixteen_bit_resolution_or_noise_spectrum_verified=False)
        release(6,7)
        print('DAC dither transfers and noise mean PASS',flush=True)

        external=[]
        for capture in [False,True]:
            for high in [False,True]:
                call('digitalWrite',0,high);call('digitalWrite',2,False)
                if capture:assert helper('capture',Pin=1,External=True,BOffset=2) is True
                else:assert helper('external',Pin=1,Value=4,BOffset=2) is True
                assert call('p2Transition',2,100,1024) is True
                actual=z(1);expect=(0xffffffff if capture else 16) if high else 0
                assert actual==expect,(capture,high,actual)
                external.append(dict(capture=capture,input_high=high,result_hex=f'{actual:08x}'))
                release(0,1,2,3)
        report['checks']['external_adc_synthetic_data_and_clock']=external
        print('Synthetic external ADC sample and latest bitstream PASS',flush=True)

        synchronous=[]
        for bits,word in [(1,1),(9,0x101),(16,0xa55a),(31,0x55555555),(32,0x80000001),(32,0xffffffff)]:
            call('digitalWrite',2,False)
            assert helper('sync_tx',Pin=0,Value=bits,Word=f'{word:08x}',BOffset=2) is True
            assert helper('sync_rx',Pin=1,Value=bits,BOffset=2) is True
            assert call('p2Transition',2,100,2*bits) is True
            received=(z(1)>>(32-bits))&((1<<bits)-1)
            assert received==word,(bits,word,received)
            synchronous.append(dict(bits=bits,sent_hex=f'{word:08x}',received_hex=f'{received:08x}'))
            release(0,1,2,3)
        report['checks']['synchronous_serial_word_widths']=synchronous
        print('Synchronous word widths 1-32 PASS',flush=True)

        assert helper('sample',Pin=7,Value=10,Circuit='ADC ground') is True
        ground=z(7)
        assert helper('sample',Pin=7,Value=10,Circuit='ADC VIO') is True
        vio=z(7);assert vio-ground>100,(ground,vio)
        internal=[]
        for level in [16,128,240]:
            assert call('p2DAC8',6,level,'DAC 990R 3V') is True
            assert helper('sample',Pin=7,Value=10,Circuit='ADC 1x') is True
            raw=z(7);ratio=(raw-ground)/(vio-ground)
            assert abs(ratio-level/255)<.04,(level,raw,ground,vio)
            internal.append(dict(dac8=level,raw=raw,normalized_ratio=ratio))
        report['checks']['typed_internal_adc_sampling']=dict(ground=ground,vio=vio,samples=internal)
        release(6,7)

        scopes=[]
        for filter_name in ['Tukey 68','Tukey 45','Hann 28']:
            assert call('p2DAC8',6,16,'DAC 990R 3V') is True
            assert helper('scope',Pin=7,Kind=filter_name,Value=24,Period=40,Circuit='ADC 1x') is True
            low=z(7);call('p2PinAck',7)
            assert call('p2DAC8',6,240,'DAC 990R 3V') is True
            triggered=call('p2PinReady',7);high=z(7)
            assert high-low>50 and triggered is True,(filter_name,low,high,triggered)
            scopes.append(dict(filter=filter_name,low=low,high=high,triggered=triggered))
            release(6,7)
        report['checks']['scope_dc_samples_and_hysteresis_trigger']=scopes
        print('Scope samples and triggers PASS',flush=True)

        call('digitalWrite',0,False)
        setup(1,'count highs',1800000)
        queries={230:('p2CogStart',('workerDutyService',2)),231:('p2LocalPinDIR',(0,)),
            232:('p2PinReadHex',(1,)),233:('p2CogStop',(2,)),234:('p2PinModeHex',(0,))}
        for index,(name,values) in queries.items():vm.upload(index,primitive(name,values),2)
        assert vm.run_reporter(230) is True
        deadline=time.monotonic()+5
        while value('Started') is not True and time.monotonic()<deadline:vm.pump()
        assert value('Started') is True and value('Cog')==2 and value('WorkerDIR') is False
        assert vm.run_reporter(231) is True
        high=int(vm.run_reporter(232),16);assert abs(high-450000)<2000,high
        assert vm.run_reporter(233) is True
        vm.short(6)
        assert vm.run_reporter(234)=='00000000'
        report['checks']['new_mode_worker_service_ownership']=dict(cog=2,worker_dir=False,
            main_dir=True,high_clocks=high,stop_all_mode='00000000')
        release(0,1)
        print('New mode worker ownership PASS',flush=True)

        configured=[]
        for kind,power in [('sample',9),('SINC2 accumulator',7),('SINC3 accumulator',7),('bitstream',5)]:
            assert helper('adc',Pin=7,Kind=kind,Period=power,External=False,Circuit='ADC 1x',BOffset=0) is True
            configured.append(dict(kind=kind,power=power,mode=call('p2PinModeHex',7)))
            release(7)
        invalid=[helper('duty',Pin=0,Value=1001,Period=100),
            helper('dac16',Pin=6,Value=32768,Period=257,External=True,Circuit='DAC 990R 3V'),
            helper('dac16',Pin=6,Value=65536,Period=256,External=False,Circuit='DAC 990R 3V'),
            helper('feedback',Pin=39,Value=1000,Period=250,AOffset=1,BOffset=0),
            helper('adc',Pin=7,Kind='SINC3 accumulator',Period=10,External=False,Circuit='ADC 1x',BOffset=0),
            helper('scope',Pin=7,Kind='Tukey 68',Value=64,Period=40,Circuit='ADC 1x'),
            helper('events',Pin=1,Value=0,Sensitivity='rise'),
            helper('window',Pin=1,Period=180000,Result='bad',Sensitivity='rise to rise',BOffset=0)]
        assert invalid==[False]*len(invalid),invalid
        report['checks']['configuration_only_and_invalid_arguments']=dict(adc_modes=configured,
            invalid_rejected=len(invalid),continuous_sinc_filter_processing_tested=False)
        report['result']='PASS'
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        raise
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
