#!/usr/bin/env python3
"""Physical P2 loopback acceptance on P0-1, P2-3, P4-5, P6-7.

Replaces the disposable project. One driver per wired pair; release both
before reversal. No USB, external supply, calibrated voltage or scope claim.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import time
from pathlib import Path
from p2_serial import P2SerialVM, primitive

OPERATIONS = ['repository','DAC noise','DAC random dither','DAC PWM dither',
    'pulse','transition','NCO frequency','NCO duty','PWM triangle','PWM sawtooth','PWM SMPS',
    'quadrature','register up','register up down','count rises','count highs','state ticks','high ticks',
    'event ticks','period ticks','period highs','window ticks','window highs','window periods',
    'ADC sample','ADC external','ADC scope','sync transmit','sync receive','async transmit','async receive']
PADS = ['logic','logic A feedback','logic B feedback','Schmitt','Schmitt A feedback','Schmitt B feedback',
    'compare A B','compare A B feedback','ADC ground','ADC VIO','ADC floating','ADC 1x','ADC 3x',
    'ADC 10x','ADC 30x','ADC 100x','DAC 990R 3V','DAC 600R 2V','DAC 124R 3V','DAC 75R 2V',
    'level A','level A feedback negative','level B feedback positive','level B feedback negative']


def test(args):
    report = dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='physical EC32MB wired-pair transfers/ratios; register configuration recorded separately',
        wiring=[[0,1],[2,3],[4,5],[6,7]], checks={}, result='FAIL',
        absolute_voltage_or_clock_accuracy=False, usb_mode_tested=False)
    vm = None
    try:
        vm=P2SerialVM(args.port,args.usb_serial,args.board)
        report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(15)
        def call(name,*values):
            vm.upload(220,primitive(name,values),2)
            return vm.run_reporter(220)
        def release(*pins):
            for pin in pins: assert call('p2PinRelease',pin) is True
        def setup(pin,mode,x=0,y=0,pad='Schmitt',drive=False,b=0):
            assert call('p2Configure',pin,mode,pad,f'{x:08x}',f'{y:08x}',drive,b) is True,(pin,mode)
        def z(pin): return int(call('p2PinReadHex',pin),16)
        revision=call('p2RuntimeRevision')
        assert revision >= 2
        report['extension_revision']=revision
        release(*range(8))
        levels=[]
        for even in range(0,8,2):
            for driver,receiver in [(even,even+1),(even+1,even)]:
                release(driver,receiver)
                assert call('p2PadNamed',receiver,'Schmitt',False,False) is True
                for high in [False,True,False,True]:
                    assert call('p2PadNamed',driver,'logic',True,high) is True
                    actual=call('p2PinSample',receiver);assert actual is high,(driver,receiver,high,actual)
                levels.append([driver,receiver])
                release(driver,receiver)
        report['checks']['gpio_both_directions_all_pairs']=dict(directions=levels,levels=[0,1,0,1])
        print('GPIO both directions PASS',flush=True)

        call('digitalWrite',0,False) # establish idle low before counting
        setup(1,'count rises')
        assert call('p2Pulse',0,100,100,100) is True
        counted=z(1); assert counted==100,counted
        assert call('p2PinReady',0) is True
        release(0,1)
        call('digitalWrite',0,False)
        setup(1,'count rises')
        assert call('p2Transition',0,100,200) is True
        counted=z(1); assert counted==100,counted
        report['checks']['finite_pulse_and_transition_count']=dict(pulse_rises=100,transition_rises=100,transitions=200)
        release(0,1)
        print('Finite pulse and transition counts PASS',flush=True)

        setup(1,'period ticks',10)
        assert call('p2Frequency',0,1000) is True
        period=z(1);assert abs(period-1800000)<1000,period
        before=call('p2PinModeHex',1);peek=call('p2PinPeekHex',1)
        assert call('p2PinModeHex',1)==before
        setup(1,'high ticks'); high=z(1);assert abs(high-90000)<1000,high
        report['checks']['nco_period_and_high_timing']=dict(hz=1000,periods=10,clock_ticks=period,high_ticks=high,quiet_read_hex=peek,mode_retained=True)
        release(0,1)

        pwm=[]
        for triangle in [False,True]:
            assert call('p2PWM',2,1000,250,triangle) is True
            setup(3,'period ticks',1);period=z(3)
            setup(3,'high ticks');high=z(3)
            ratio=high/period
            assert abs(period-180000)<1500,(triangle,period)
            assert abs(ratio-.25)<.01,(triangle,period,high,ratio)
            pwm.append(dict(triangle=triangle,period_ticks=period,high_ticks=high,duty_ratio=ratio))
            release(2,3)
        report['checks']['pwm_sawtooth_and_triangle_ratios']=pwm
        print('NCO timing and PWM ratios PASS',flush=True)

        assert call('p2UART',4,115200,True) is True
        assert call('p2UART',5,115200,False) is True
        assert call('p2UARTRead',5)==-1
        sent=[0,1,85,170,127,128,254,255];received=[]
        for byte in sent:
            assert call('p2UARTWrite',4,byte) is True
            received.append(call('p2UARTRead',5))
        assert received==sent,received
        assert call('p2UARTRead',5)==-1
        report['checks']['uart_8n1_115200']=dict(sent=sent,received=received,no_data_result=-1)
        release(4,5)
        print('UART byte transfers PASS',flush=True)

        # Two driven pairs supply A and B to a quadrature receiver on P1.
        release(0,1,2,3)
        call('digitalWrite',0,False);call('digitalWrite',2,False)
        assert call('p2PadNamed',3,'Schmitt',False,False) is True
        setup(1,'quadrature',b=2)
        for _ in range(5):
            call('digitalWrite',0,True);call('digitalWrite',2,True)
            call('digitalWrite',0,False);call('digitalWrite',2,False)
        forward=z(1);signed_forward=forward if forward<0x80000000 else forward-0x100000000
        assert abs(signed_forward)==20,signed_forward
        for _ in range(5):
            call('digitalWrite',2,True);call('digitalWrite',0,True)
            call('digitalWrite',2,False);call('digitalWrite',0,False)
        assert z(1)==0
        report['checks']['quadrature_two_pairs']=dict(a_pin=1,b_pin=3,b_offset=2,forward=signed_forward,reverse_returns_to=0)
        release(0,1,2,3)
        print('Quadrature forward/reverse PASS',flush=True)

        # One data pair and one clock pair: TX0->RX1, clock2->clock3.
        serial=[]
        for word in [0x00,0x55,0xaa,0xff]:
            release(0,1,2,3)
            call('digitalWrite',2,False)
            setup(0,'sync transmit',39,word,pad='logic',drive=True,b=2)
            setup(1,'sync receive',39,0,b=2)
            assert call('p2Transition',2,100,16) is True
            received=(z(1)>>24)&255
            assert received==word,(word,received)
            serial.append(received)
        release(0,1,2,3)
        report['checks']['synchronous_serial_two_pairs']=dict(data=[0,1],clock=[2,3],bits=8,received=serial)
        print('Synchronous serial words PASS',flush=True)

        transfer=[]
        for level in [16,64,128,192,240]:
            assert call('p2DAC8',6,level,'DAC 990R 3V') is True
            time.sleep(.01)
            # This calibrates internal ground/VIO and samples high-impedance 1x.
            measured=call('analogRead',7)
            transfer.append(dict(dac8=level,adc10=measured))
        values=[r['adc10'] for r in transfer]
        assert all(b>a for a,b in zip(values,values[1:])),transfer
        assert all(abs(r['adc10']/1023-r['dac8']/255)<.04 for r in transfer),transfer
        report['checks']['dac8_to_calibrated_adc1x_transfer']=dict(pad='990R 3V',samples=transfer,monotonic=True,absolute_accuracy_tested=False)
        release(6,7)
        print('DAC to ADC monotonic transfer PASS',flush=True)

        configured=[]
        for mode in OPERATIONS:
            pad='DAC 990R 3V' if mode.startswith('DAC ') else ('ADC 1x' if mode.startswith('ADC ') else 'Schmitt')
            setup(0,mode,32,0,pad=pad,drive=False)
            configured.append(dict(mode=mode,wrpin=call('p2PinModeHex',0)))
            release(0)
        for pad in PADS:
            assert call('p2PadNamed',0,pad,False,False) is True
            release(0)
        assert call('p2PadRaw',0,'1fff',False,False) is True
        assert call('p2PadRaw',0,'2000',False,False) is False
        assert call('p2Configure',0,'USB','logic','0','0',False,0) is False
        assert call('p2PadNamed',40,'logic',False,False) is False
        assert call('p2Configure',39,'count rises','logic','0','0',False,1) is False
        setup(0,'repository',0x12345678)
        assert call('p2PinReadHex',0)=='12345678'
        assert call('p2Configure',0,'repository','logic',42,0,False,0) is True
        assert call('p2PinReadHex',0)=='0000002a'
        report['checks']['configuration_only']=dict(named_operations=configured,pad_presets=PADS,raw_pad_13_bits=True,invalid_and_reserved_rejected=True,repository_roundtrip='12345678',signal_validation_claim=False)
        vm.short(6)
        assert call('p2PinModeHex',0)=='00000000'
        report['checks']['stop_all_clears_tracked_mode']=True
        setup(0,'repository',42)
        vm.short(15)
        assert call('p2PinModeHex',0)=='00000000'
        report['checks']['soft_reset_clears_tracked_mode']=True
        report['result']='PASS'
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        raise
    finally:
        if vm:
            try: vm.short(15) # releases hardware as well as test tasks
            finally:vm.close()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--port',required=True);p.add_argument('--usb-serial',required=True)
    p.add_argument('--board',choices=['edge32'],required=True)
    p.add_argument('--evidence',type=Path,required=True)
    test(p.parse_args())
