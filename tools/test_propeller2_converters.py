#!/usr/bin/env python3
"""Safe converter-pad/analog-comparator response on P6->P7 and feedback pairs.

One DAC driver per pair; receiver output disabled. Input response only does
not establish resistance, gain accuracy, linearity, hysteresis, or an SMPS.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
from pathlib import Path
from p2_serial import P2SerialVM, primitive


def test(args):
    report=dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        result='FAIL',scope='DAC pad transfers, ADC gain response and comparator feedback logic',checks={},
        absolute_accuracy_tested=False,source_resistance_tested=False,
        gain_accuracy_tested=False,feedback_output_tested=False,power_converter_tested=False)
    vm=None
    try:
        vm=P2SerialVM(args.port,args.usb_serial,'edge32');report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(15)
        def call(name,*values):
            vm.upload(220,primitive(name,values),2);return vm.run_reporter(220)
        def release(*pins):
            for pin in pins:assert call('p2PinRelease',pin) is True
        pads=[]
        for circuit in ['DAC 990R 3V','DAC 600R 2V','DAC 124R 3V','DAC 75R 2V']:
            samples=[]
            for level in [16,64,128,192,240]:
                assert call('p2DAC8',6,level,circuit) is True
                samples.append(dict(dac8=level,calibrated_adc10=call('analogRead',7)))
            assert all(b['calibrated_adc10']>a['calibrated_adc10'] for a,b in zip(samples,samples[1:])),samples
            pads.append(dict(circuit=circuit,samples=samples))
            release(6,7)
        report['checks']['dac_all_four_pad_monotonic_transfers']=pads
        print('Four DAC pad transfers PASS',flush=True)

        gains=[]
        for circuit in ['ADC 1x','ADC 3x','ADC 10x','ADC 30x','ADC 100x']:
            samples=[]
            for level in [0,16,64,120,127,128,129,136,192,255]:
                assert call('p2DAC8',6,level,'DAC 990R 3V') is True
                assert call('p2ADCSetup',7,'sample',9,False,circuit,0) is True
                value=int(call('p2PinReadHex',7),16)
                assert 0<=value<=1024
                samples.append(dict(dac8=level,raw_sample=value))
            values=[s['raw_sample'] for s in samples]
            assert max(values)-min(values)>200
            assert all(b>=a-4 for a,b in zip(values,values[1:])),samples
            gains.append(dict(circuit=circuit,samples=samples))
            release(6,7)
        report['checks']['adc_gain_input_response']=dict(source='990R 3V DAC',curves=gains,
            loading_and_clipping_included=True,nominal_gain_accuracy_established=False)
        print('Five ADC gain response curves PASS',flush=True)

        comparators=[]
        for circuit in ['level A','level A feedback negative','level B feedback positive','level B feedback negative']:
            samples=[]
            for threshold in [64,128,192]:
                assert call('p2LevelInput',7,threshold,circuit) is True
                assert call('p2LocalPinDIR',7) is False
                levels=[]
                for level in [threshold-32,threshold+32]:
                    assert call('p2DAC8',6,level,'DAC 990R 3V') is True
                    levels.append(call('p2PinSample',7))
                assert levels==[False,True],(circuit,threshold,levels)
                samples.append(dict(threshold8=threshold,source_codes=[threshold-32,threshold+32],states=levels))
            comparators.append(dict(circuit=circuit,samples=samples,receiver_dir=False))
            release(6,7)
        report['checks']['input_only_level_comparator_thresholds']=comparators
        print('Four comparator circuits, input-only thresholds PASS',flush=True)

        release(*range(6))
        for pin in [0,2]:assert call('p2DAC8',pin,32,'DAC 990R 3V') is True
        for pin in [1,3]:assert call('p2LevelInput',pin,64,'level A') is True
        assert call('p2FeedbackPWM',4,1000,250,-3,-1) is True
        def high_count():
            assert call('p2Configure',5,'count highs','Schmitt',1800000,0,False,0) is True
            return int(call('p2PinReadHex',5),16)
        running=high_count();assert abs(running-450000)<2000,running
        assert call('p2DAC8',2,96,'DAC 990R 3V') is True
        assert call('p2PinSample',3) is True
        limited=high_count();assert limited==0,limited
        assert call('p2DAC8',0,96,'DAC 990R 3V') is True
        assert call('p2DAC8',2,32,'DAC 990R 3V') is True
        inhibited=high_count();assert inhibited==0,inhibited
        assert call('p2DAC8',0,32,'DAC 990R 3V') is True
        resumed=high_count();assert abs(resumed-450000)<2000,resumed
        assert call('p2LocalPinDIR',1) is False and call('p2LocalPinDIR',3) is False
        report['checks']['analog_comparator_feedback_gating']=dict(dac_sources=[0,2],
            input_comparators=[1,3],threshold8=64,source_codes=[32,96],pwm_output=4,
            receiver=5,high_clock_window=1800000,running=running,current_limited=limited,
            voltage_inhibited=inhibited,resumed=resumed,converter_circuit=False)
        release(*range(8))
        assert call('p2LevelInput',7,256,'level A') is False
        assert call('p2LevelInput',7,128,'ADC 1x') is False
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
    p.add_argument('--evidence',type=Path,required=True)
    test(p.parse_args())
