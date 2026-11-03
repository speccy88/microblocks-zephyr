#!/usr/bin/env python3
"""Native SINC streams, bit bursts and GETSCP rings on disposable EC32MB.

Uses only P0->P1 data, P2->P3 clock, P6->P7 analog, one driver per pair.
No USB or external converter/power circuit; no absolute accuracy/ENOB claim.
Preload all queries: live code uploads intentionally cancel native jobs.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import statistics
import struct
import time
from pathlib import Path
from p2_serial import P2SerialVM, primitive


def decode(body):
    if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
    if body[0]==2:return body[1:].decode()
    if body[0]==3:return bool(body[1])
    count=int.from_bytes(body[1:3],'little');sent=body[3]
    assert count==sent,('VM preview truncated; choose smaller read batch',count,sent)
    if body[0]==5:return body[4:]
    assert body[0]==4 and all(body[4+5*i]==1 for i in range(sent)),body.hex()
    return [int.from_bytes(body[5+5*i:9+5*i],'little',signed=True) for i in range(sent)]


def test(args):
    report=dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='native SINC consumers, finite contiguous bit bursts and GETSCP rings',
        result='FAIL',checks={},external_converter_tested=False,
        absolute_accuracy_or_enob_tested=False,usb_tested=False)
    vm=None
    try:
        p=json.loads(args.program.read_text(encoding='utf-8'))
        vm=P2SerialVM(args.port,args.usb_serial,'edge32');report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(10,1);vm.short(15)
        for name,index in p['variables'].items():
            raw=name.encode()+b'\xfe';vm.send(bytes([251,29,index])+len(raw).to_bytes(2,'little')+raw)
        for c in p['chunks']:
            raw=bytes(c['bytes']);vm.upload(c['id'],raw+b'\0'*(-len(raw)%4),c['kind'])
        functions={c['name']:c['id'] for c in p['chunks'] if c['name']}
        scripts=dict(zip(['start','internal','external','bits','state','info','samples','bytes','scope','triggered_scope','circuit'],p['scripts']))
        queries={200:('p2RuntimeRevision',()),201:('p2CaptureStop',()),
            202:('p2CogStart',('consumeCapture',3)),203:('p2CogStop',(3,)),
            204:('p2CogStart',('consumeCapture',2)),205:('p2PinReadHex',(7,)),
            206:('p2PinWriteX',(7,'0')),207:('p2PinAck',(7,)),208:('p2LocalPinDIR',(7,)),
            209:('p2CogStackOK',(2,)),210:('p2CogStackOK',(3,)),
            211:('p2CaptureStart',(1,'SINC2',16,1,16,2,True,2,100)),
            212:('p2PadNamed',(1,'Schmitt',False,False)),213:('p2PinRelease',(7,)),
            214:('p2CogStop',(2,)),215:('p2CogStackUsed',(2,)),
            216:('p2DAC8',(6,16,'DAC 990R 3V')),217:('p2DAC8',(6,128,'DAC 990R 3V')),
            218:('p2DAC8',(6,240,'DAC 990R 3V')),
            219:('digitalWrite',(0,False)),220:('digitalWrite',(0,True)),
            221:('p2Frequency',(2,20000)),222:('digitalWrite',(2,False)),
            223:('p2Frequency',(2,1000000)),
            224:('p2SmartPinRaw',(0,'00000052','001f00b4','0000000f')),
            225:('p2PinRelease',(0,)),226:('p2PinRelease',(1,)),
            227:('p2PinRelease',(2,)),228:('p2PinRelease',(3,)),229:('p2PinRelease',(6,)),
            230:('p2DAC8',(0,16,'DAC 990R 3V')),231:('p2DAC8',(0,240,'DAC 990R 3V')),
            232:('p2DAC8',(2,128,'DAC 990R 3V')),
            233:('p2Scope',(1,0,24,40,'ADC 1x')),234:('p2Scope',(3,2,24,40,'ADC 1x')),
            235:('p2DAC8',(6,120,'DAC 990R 3V')),236:('p2DAC8',(6,136,'DAC 990R 3V')),
            237:('p2ScopeCapture',(0,10,18000,16,2,1,100)),
            241:('p2ScaleSample',(50000000,10000000,90000000,65535)),
            242:('p2ScaleSample',(0,10000000,90000000,65535)),
            243:('p2ScaleSample',(100000000,10000000,90000000,65535)),
            244:('p2ScaleSample',(10,20,20,1023))}
        for i,(name,values) in queries.items():vm.upload(i,primitive(name,values),2)
        def run(i):
            first=len(vm.events);vm.short(3,i)
            return decode(vm.wait(lambda e:e[:2]==(18,i),after=first,seconds=15)[2])
        def setvars(**values):
            for name,value in values.items():
                if isinstance(value,bool):body=bytes([3,value])
                elif isinstance(value,int):body=b'\x01'+struct.pack('<i',value)
                else:body=b'\x02'+value.encode()
                raw=body+b'\xfe';vm.send(bytes([251,8,p['variables'][name]])+len(raw).to_bytes(2,'little')+raw)
        def value(name):
            index=p['variables'][name];first=len(vm.events);vm.short(7,index)
            return decode(vm.wait(lambda e:e[:2]==(21,index),after=first)[2])
        def info(field):setvars(Field=field);return run(scripts['info'])
        def until(predicate,seconds=10):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if predicate():return
                vm.pump()
            raise TimeoutError('Capture phase timed out')
        def start(kind='SINC2',pin=7,period=1024,keep=64,count=32,external=False,cog=2):
            setvars(Pin=pin,Kind=kind,Period=period,Keep=keep,Count=count,Cog=cog,
                    External=external,B=2 if external else 0,Timeout=3000)
            assert run(scripts['start']) is True
        def samples():setvars(ReadCount=32);return run(scripts['samples'])
        def bitbytes():
            all_bytes=b'';setvars(ReadCount=24)
            while info('available'):all_bytes+=run(scripts['bytes'])
            return all_bytes
        def release_all():
            run(201)
            for i in [225,226,227,228,229,213]:run(i)
        assert run(200)>=5
        assert [run(i) for i in [241,242,243,244]]==[32767,0,65535,False]
        report['checks']['wide_integer_sample_scaling_and_clamps']=[32767,0,65535,False]
        release_all()

        transfer=[]
        for kind,period in [('SINC2',1024),('SINC3',256)]:
            levels=[]
            for query,level in [(216,16),(217,128),(218,240)]:
                assert run(query) is True
                start(kind=kind,period=period)
                until(lambda:info('state')!=1)
                assert info('state')==2
                scale=info('scale');data=samples();assert len(data)==32
                mean=statistics.mean(data)/scale
                raw=info('raw');assert raw==(3 if kind=='SINC2' else 5)+64*32,raw
                levels.append(dict(dac8=level,mean_ratio=mean,min=min(data),max=max(data),
                    raw_samples=raw,emitted=info('emitted'),wraps=info('wraps')))
                assert info('wraps')>0
                assert info('maximum gap clocks')<period+128
                assert info('cog')==2 and info('local DIR')==0
            assert all(b['mean_ratio']>a['mean_ratio'] for a,b in zip(levels,levels[1:])),levels
            transfer.append(dict(kind=kind,period_clocks=period,levels=levels))
        report['checks']['sinc_internal_dac_transfer_modulo_and_settling']=transfer
        release_all();print('Internal SINC2/SINC3 transfer and modular differences PASS',flush=True)
        references={};gain_signals=[]
        for circuit in ['ADC ground','ADC VIO']:
            setvars(Pin=7,Kind='SINC2',Period=1024,Keep=64,Count=16,Cog=2,Circuit=circuit)
            assert run(scripts['circuit']) is True
            until(lambda:info('state')!=1);assert info('state')==2
            references[circuit]=statistics.mean(samples())/info('scale')
        assert references['ADC VIO']-references['ADC ground']>.5,references
        for circuit in ['ADC 1x','ADC 3x','ADC 10x','ADC 30x','ADC 100x']:
            means=[]
            for query in [235,236]:
                assert run(query) is True
                setvars(Circuit=circuit);assert run(scripts['circuit']) is True
                until(lambda:info('state')!=1);assert info('state')==2
                scale=info('scale');data=samples()
                assert all(0<=v<=scale for v in data)
                means.append(statistics.mean(data)/scale)
            assert means[1]>means[0]+.02,(circuit,means)
            gain_signals.append(dict(circuit=circuit,dac_codes=[120,136],ratios=means))
        report['checks']['sinc_references_and_gain_pad_response']=dict(references=references,
            gain_responses=gain_signals,gain_accuracy_tested=False)
        release_all()

        external=[]
        for kind in ['SINC2','SINC3']:
            for high in [False,True]:
                run(220 if high else 219);assert run(221) is True
                start(kind=kind,pin=1,period=16,keep=1,count=32,external=True)
                until(lambda:info('state')!=1);assert info('state')==2
                data=samples();scale=info('scale')
                assert data==[scale if high else 0]*32,(kind,high,data)
                external.append(dict(kind=kind,input_high=high,scale=scale,values_exact=True))
                release_all()
        report['checks']['external_sinc_synthetic_exact_zero_and_full_scale']=external
        print('External SINC2/SINC3 exact bit counts PASS',flush=True)

        assert run(217) is True
        start(kind='SINC3',period=256,keep=16384,count=0)
        assert info('state')==1 and run(208) is True and info('local DIR')==0
        assert run(205) is False and run(206) is False and run(207) is False
        assert run(204) is False
        for invalid in [dict(Cog=0),dict(Cog=1),dict(Cog=2,Period=1)]:
            setvars(**invalid);assert run(scripts['start']) is False
            assert info('state')==1 and info('cog')==2
        setvars(Cog=2,Period=256,Scale=info('scale'));assert run(202) is True
        setvars(Cog=3);assert run(scripts['start']) is False
        assert info('state')==1 and info('cog')==2
        setvars(Cog=2)
        phase=len(vm.events);vm.short(3,functions['captureMainGC'])
        until(lambda:value('Done') is True,45)
        until(lambda:value('Consumed')>=32,15)
        assert value('Core')==3 and value('Progress')>0 and value('Errors')==0
        assert info('state')==1 and info('raw')>100000
        gc_events=sum(b'GC took' in e[2] for e in vm.events[phase:]);assert gc_events>0
        report['checks']['native_stream_during_gc_and_vm_worker']=dict(native_cog=2,consumer_cog=3,
            consumed=value('Consumed'),worker_progress=value('Progress'),gc_events=gc_events,
            raw_samples=info('raw'),max_gap_clocks=info('maximum gap clocks'),ack_and_writes_refused=True,
            worker_scaled_value=value('LastScaled'))
        assert run(203) is True and run(201) is True
        assert info('state')==3 and run(209) is True and run(210) is True
        report['checks']['native_stream_during_gc_and_vm_worker']['stopped_max_gap_clocks']=info('maximum gap clocks')
        release_all();print('Continuous SINC through GC and worker consumption PASS',flush=True)

        assert run(217) is True
        start(period=256,keep=1,count=0)
        until(lambda:info('state')!=1);assert info('state')==4
        assert info('available')==1023 and info('emitted')==1023
        data=samples();assert len(data)==32 and info('available')==991
        report['checks']['overflow_stops_without_overwriting']=dict(capacity=1023,state='buffer full',retained=1023)
        release_all()

        run(219);run(222)
        assert run(211) is True
        until(lambda:info('state')!=1);assert info('state')==5 and info('raw')==0
        start(pin=1,period=16,external=True,count=0)
        assert info('state')==1
        assert run(212) is True and info('state')==3
        start(pin=1,period=16,external=True,count=0)
        assert run(214) is True and info('state')==3
        start(pin=1,period=16,external=True,count=0)
        vm.short(6);assert info('state')==3
        start(pin=1,period=16,external=True,count=0)
        vm.upload(240,primitive('p2RuntimeRevision'),2)
        assert info('state')==3
        start(pin=1,period=16,external=True,count=0)
        vm.short(15);assert info('state')==3
        setvars(Pin=1,Kind='bits',Period=32,Keep=1,Count=16,Cog=2,External=True,B=2,Timeout=100)
        assert run(scripts['start']) is True
        until(lambda:info('state')!=1);assert info('state')==5 and info('available')==0
        report['checks']['timeout_reassignment_cog_stop_stop_all_code_edit_and_reset']=True
        release_all();print('Overflow, timeout and cancellation lifecycle PASS',flush=True)

        bursts=[]
        for count in [1,2,128,1023]:
            assert run(217) is True
            setvars(Pin=7,Count=count,Cog=2,External=False,B=0)
            assert run(scripts['bits']) is True
            assert info('state')==2,(count,info('state'),info('elapsed clocks'),info('expected clocks'))
            elapsed=info('elapsed clocks');expected=info('expected clocks')
            data=bitbytes();assert len(data)==count*4
            bursts.append(dict(words=count,elapsed_clocks=elapsed,expected_clocks=expected,bytes=len(data)))
            release_all()
        report['checks']['internal_bit_burst_native_timing']=bursts
        print('Internal contiguous bit-burst timing PASS',flush=True)

        assert run(223) is True and run(224) is True
        setvars(Pin=1,Count=512,Cog=2,External=True,B=2)
        assert run(scripts['bits']) is True
        until(lambda:info('state')!=1);assert info('state')==2
        data=bitbytes();assert len(data)==2048
        bits=[(byte>>bit)&1 for byte in data for bit in range(8)]
        phases=[phase for phase in range(31) if all(value==int((i+phase)%31<15) for i,value in enumerate(bits))]
        assert len(phases)==1,('31-bit source lost phase',phases,data[:32].hex())
        report['checks']['external_bit_burst_contiguity']=dict(words=512,bit_clock_hz=1000000,
            source_period_bits=31,high_bits=15,phase=phases[0],all_16384_bits_match=True)
        release_all();print('External 31-bit pattern continuity PASS',flush=True)
        run(220);assert run(223) is True
        setvars(Pin=1,Count=64,Cog=2,External=True,B=2)
        assert run(scripts['bits']) is True
        until(lambda:info('state')!=1);assert info('state')==2
        assert bitbytes()==bytes([255])*256
        report['checks']['all_bit_positions_preserved']=dict(words=64,bytes=256,value=255)
        release_all()
        scope_results=[]
        for triggered in [False,True]:
            assert run(230) is True and run(232) is True
            assert run(233) is True and run(234) is True
            setvars(ScopeBase=0,Channels=10,Usecs=100,Count=128,Cog=2,Trigger=1)
            assert run(scripts['triggered_scope' if triggered else 'scope']) is True
            if triggered:
                assert info('state')==1
                assert run(231) is True
            until(lambda:info('state')!=1);assert info('state')==2
            elapsed=info('elapsed clocks');expected=info('expected clocks')
            assert abs(elapsed-expected)<32,(elapsed,expected)
            data=bitbytes();assert len(data)==512
            assert data[0::4]==bytes(128) and data[2::4]==bytes(128)
            a=list(data[1::4]);b=list(data[3::4])
            assert max(a)-min(a)<24 and max(b)-min(b)<24,(a,b)
            assert abs(statistics.mean(b)-128)<16,statistics.mean(b)
            assert (statistics.mean(a)>180 if triggered else statistics.mean(a)<80),statistics.mean(a)
            scope_results.append(dict(triggered=triggered,channels=10,frame_count=128,
                interval_us=100,elapsed_clocks=elapsed,expected_clocks=expected,
                pin1_mean=statistics.mean(a),pin3_mean=statistics.mean(b),unused_bytes_zero=True))
            release_all()
        report['checks']['scope_pipe_selected_channels_and_hardware_trigger']=scope_results
        assert run(230) is True and run(232) is True
        assert run(233) is True and run(234) is True
        setvars(ScopeBase=0,Channels=10,Usecs=2000,Count=0,Cog=2,ReadCount=24)
        assert run(scripts['scope']) is True
        continuous=b'';changed=False;deadline=time.monotonic()+15
        while len(continuous)<1100*4 and time.monotonic()<deadline:
            continuous+=run(scripts['bytes'])
            if not changed and len(continuous)>=256*4:
                assert run(231) is True;changed=True
            assert info('state')==1
        assert len(continuous)>=1100*4
        assert min(continuous[1::4])<80 and max(continuous[1::4])>180
        setvars(Done=False);phase=len(vm.events);vm.short(3,functions['captureMainGC'])
        until(lambda:value('Done') is True,45)
        assert info('state')==1
        assert run(201) is True and info('state')==3
        emitted=info('emitted');remaining=info('available')
        assert len(continuous)//4+remaining==emitted,(len(continuous),remaining,emitted)
        assert abs(info('elapsed clocks')-info('expected clocks'))<32
        assert info('maximum gap clocks')<=360032
        report['checks']['continuous_scope_ring_wrap_gc_and_stop']=dict(frames=emitted,
            drained_frames=len(continuous)//4,buffered_frames=remaining,interval_us=2000,
            gc_events=sum(b'GC took' in e[2] for e in vm.events[phase:]),
            exact_frame_accounting=True,ring_wrapped=emitted>1024)
        release_all()
        assert run(230) is True and run(232) is True
        assert run(233) is True and run(234) is True
        setvars(Usecs=3,Count=0);assert run(scripts['scope']) is True
        until(lambda:info('state')!=1);assert info('state')==4
        assert info('available')==1023 and info('emitted')==1023
        report['checks']['scope_overflow_retains_buffer']=1023
        release_all()
        assert run(230) is True and run(232) is True
        assert run(233) is True and run(234) is True
        assert run(237) is True
        until(lambda:info('state')!=1);assert info('state')==5 and info('available')==0
        report['checks']['scope_trigger_timeout_without_event']=True
        release_all()
        print('SCOPE pipe bursts and hardware trigger PASS',flush=True)
        assert run(209) is True
        report['checks']['native_stack']=dict(guards_intact=True,high_water_bytes=run(215),capacity_bytes=8192)
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
