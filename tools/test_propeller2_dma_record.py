#!/usr/bin/env python3
"""Disposable EC32MB DMA/pretrigger test, one driver per wired pair."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import hashlib
import json
import struct
import time
from pathlib import Path
from p2_serial import P2SerialVM,primitive


def decode(body):
    if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
    if body[0]==2:return body[1:].decode()
    if body[0]==3:return bool(body[1])
    assert body[0]==5 and int.from_bytes(body[1:3],'little')==body[3],body.hex()
    return body[4:]


def pattern(data,unit=1):
    bits=[(b>>n)&1 for b in data for n in range(8)];period=31*unit
    phases=[p for p in range(period) if all(v==int((i+p)%period<15*unit) for i,v in enumerate(bits[:period*2]))]
    assert len(phases)==1,(phases,data[:20].hex())
    assert all(v==int((i+phases[0])%period<15*unit) for i,v in enumerate(bits)),('pattern discontinuity',phases[0])
    return dict(bytes=len(data),bits=len(bits),phase=phases[0],period_bits=period,
        sha256=hashlib.sha256(data).hexdigest(),all_bits_match=True)


def test(args):
    report=dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),result='FAIL',checks={},
        scope='internal pin/ADC streamer WRFAST ring and page-granular pretrigger records',
        external_converter_tested=False,absolute_clock_or_analog_accuracy_tested=False,
        sustained_full_clock_host_transport_tested=False,sample_accurate_edge_trigger_tested=False,usb_tested=False)
    vm=None
    try:
        p=json.loads(args.program.read_text(encoding='utf-8'))
        vm=P2SerialVM(args.port,args.usb_serial,'edge32');report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(10,1);vm.short(15)
        for name,index in p['variables'].items():
            raw=name.encode()+b'\xfe';vm.send(bytes([251,29,index])+len(raw).to_bytes(2,'little')+raw)
        for c in p['chunks']:
            raw=bytes(c['bytes']);vm.upload(c['id'],raw+b'\0'*(-len(raw)%4),c['kind'])
        scripts=dict(zip(['source','native','stream','finite','recent','info','read','density','state','running',
            'complete','has_data','available','rate','stop','vector'],p['scripts']))
        functions={c['name']:c['id'] for c in p['chunks'] if c['name']}
        queries={200:('p2RuntimeRevision',()),201:('p2ClockHz',()),202:('digitalWrite',(4,False)),
            203:('digitalWrite',(4,True)),204:('p2CogStop',(3,)),205:('p2CogStart',('dmaHeartbeat',3)),
            206:('p2CogStart',('dmaConsumer',3)),207:('p2PinRelease',(1,)),208:('p2PinRelease',(5,)),
            209:('p2CogStop',(2,)),210:('p2LocalPinDIR',(1,)),211:('p2LocalPinDIR',(5,)),
            212:('p2CogStackOK',(2,)),213:('p2CogStackOK',(3,)),214:('p2PinAck',(1,)),
            215:('p2PinReadHex',(1,)),216:('p2DMACapture',(1,'Schmitt',0,7,2)),
            217:('p2DMACapture',(63,'Schmitt',0,2,2)),218:('p2DMACapture',(1,'DAC 990R 3V',0,2,2)),
            219:('p2DMARecord',(1,'Schmitt',0,2,2,2,1,True,1000)),
            221:('p2PinRelease',(0,)),222:('p2PinRelease',(4,)),
            223:('p2BitDensity',('bad',)),224:('p2DMACapture',(1,'Schmitt',16,2,2))}
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
        def info(field):return helper('info',Field=field)
        def value(name):
            index=p['variables'][name];first=len(vm.events);vm.short(7,index)
            return decode(vm.wait(lambda e:e[:2]==(21,index),after=first)[2])
        def until(condition,seconds=15):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if condition():return
                errors=[(e[1],e[2].hex()) for e in vm.events if e[0]==19]
                if errors:raise RuntimeError('VM error '+str(errors[-3:]))
                vm.pump()
            raise TimeoutError('DMA phase')
        def read():return helper('read',ReadCount=24)
        def drain():
            data=b''
            while info('available'):data+=read()
            return data
        def release():
            for q in [207,208,221,222]:run(q)
        def source(unit):assert helper('source',Unit=unit) is True
        def native(power=0,pages=0,circuit='Schmitt'):
            assert helper('native',Pin=1,Circuit=circuit,Power=power,Pages=pages,Cog=2) is True
        assert run(200)>=8 and run(201)==180000000;report['extension_revision']=run(200)
        assert run(scripts['vector'])==406250 and run(223) is False
        for query in [216,217,218,219,224]:assert run(query) is False
        assert helper('stream',Pin=1,Circuit='Schmitt',Maximum=0,Cog=2) is False
        assert helper('stream',Maximum=5493) is False
        assert helper('finite',Power=0,Words=129) is False
        report['checks']['density_vector_and_invalid_arguments']=dict(vector_ones=13,vector_bits=32,ppm=406250)

        source(8);finite=[]
        for words in [128,256,768]:
            assert helper('finite',Pin=1,Circuit='Schmitt',Power=0,Words=words,Cog=2) is True
            until(lambda:info('state')!=1)
            assert run(scripts['complete']) is True and run(scripts['running']) is False
            assert info('emitted')==words and info('page words')==128
            assert info('buffer guards') is True and info('cog')==2 and run(210) is False
            if words>128:
                assert info('maximum gap clocks')<=4608
                assert abs(info('elapsed clocks')-info('expected clocks'))<=512
            result=pattern(drain(),8);result.update(words=words,state='complete')
            finite.append(result)
        native();until(lambda:info('state')!=1);assert info('state')==4 and info('available')==768
        result=pattern(drain(),8);assert info('buffer guards') is True
        report['checks']['full_clock_finite_and_overflow']=dict(sample_hz=180000000,finite=finite,
            overflow=result,retained_overflow_words=768,buffer_guards=True)
        release();print('Full-clock DMA finite records and retained overflow PASS',flush=True)

        source(8192);native(13)
        assert info('DMA')==1 and info('sample clocks')==8192 and info('state')==1
        assert run(214) is False and run(215) is False and run(216) is False
        setvars(Progress=0);assert run(205) is True
        data=b'';deadline=time.monotonic()+20
        while len(data)<1400*4 and time.monotonic()<deadline:
            data+=read();assert info('state')==1
        assert len(data)>=5600
        setvars(Done=False);first=len(vm.events);vm.short(3,functions['dmaGarbage'])
        until(lambda:value('Done') is True)
        gc=sum(b'GC took' in e[2] for e in vm.events[first:]);assert gc>0
        assert value('Progress')>0 and value('Core')==3 and info('state')==1
        assert run(204) is True and run(scripts['stop']) is True
        emitted=info('emitted');available=info('available');assert len(data)//4+available==emitted
        data+=drain();result=pattern(data)
        assert info('buffer guards') is True and info('wraps')>0
        assert info('maximum gap clocks')<=33554944
        error=((info('elapsed clocks')-info('expected clocks')+(1<<29))&0x3fffffff)-(1<<29)
        assert abs(error)<=512,error
        result.update(sample_clocks=8192,gc_events=gc,worker_progress=value('Progress'),emitted_words=emitted,
            wraps=info('wraps'),maximum_gap_clocks=info('maximum gap clocks'),elapsed_error_clocks=error)
        report['checks']['continuous_divided_ring_host_gc']=result;release()

        source(8192);setvars(Consumed=0,Progress=0,StopConsumer=False,ConsumerStopped=False,LastDensity=0);native(13)
        assert run(206) is True
        setvars(Done=False);vm.short(3,functions['dmaGarbage']);until(lambda:value('Done') is True)
        until(lambda:value('Consumed')>=1400,20)
        setvars(StopConsumer=True);until(lambda:value('ConsumerStopped') is True)
        assert run(204) is True and run(scripts['stop']) is True
        consumed=value('Consumed');available=info('available');emitted=info('emitted')
        assert consumed+available==emitted and emitted>1024
        density=value('LastDensity');assert 450000<density<520000,density
        report['checks']['worker_density_consumption_gc']=dict(cog=value('Core'),consumed_words=consumed,
            buffered_words=available,emitted_words=emitted,density_ppm=density,exact_accounting=True)
        release();print('Continuous DMA wrap, GC, worker byte arrays and density PASS',flush=True)

        # Friendly maximum-rate rounding is downward to a power-of-two clock divisor.
        source(16384)
        assert helper('stream',Pin=1,Circuit='Schmitt',Maximum=20000,Cog=2) is True
        assert info('sample clocks')==16384 and run(scripts['rate'])==10986
        assert run(scripts['running']) is True;run(scripts['stop']);release()

        records=[]
        for high in [True,False]:
            source(8)
            run(202 if high else 203)
            assert helper('recent',Pin=1,Circuit='Schmitt',Maximum=180000000,History=256,After=256,
                Cog=2,Trigger=5,High=high,Timeout=5000) is True
            assert info('state')==7 and run(scripts['state'])=='armed pretrigger'
            assert run(scripts['running']) is True and run(scripts['has_data']) is False
            assert read() is False and run(210) is False and run(211) is False
            until(lambda:info('history discarded words')>=1024)
            run(203 if high else 202)
            until(lambda:info('state')!=1 and info('state')!=7)
            assert run(scripts['complete']) is True and info('available')==512 and info('trigger word')==256
            emitted=info('emitted');discarded=info('history discarded words')
            assert emitted-discarded==512 and discarded>0,(emitted,discarded)
            result=pattern(drain(),8);result.update(trigger_high=high,trigger_word=256,
                history_discarded_words=discarded,emitted_words=emitted)
            assert info('buffer guards') is True;records.append(result);release()
        report['checks']['pretrigger_history_chronological_both_levels']=records
        source(8);run(202)
        assert helper('recent',Pin=1,Circuit='Schmitt',Maximum=180000000,History=256,After=256,
            Cog=2,Trigger=5,High=True,Timeout=250) is True
        until(lambda:info('state') not in [1,7]);assert info('state')==5
        assert info('trigger word')==-1 and info('available')==256
        result=pattern(drain(),8);report['checks']['pretrigger_timeout_retains_history']=result
        release();print('Pretrigger many-wrap history, both levels and timeout PASS',flush=True)

        # Raw ADC bits are averaged only after a finite full-clock DMA record.
        densities={}
        for circuit in ['ADC ground','ADC VIO']:
            native(0,2,circuit);until(lambda:info('state')!=1)
            assert info('state')==2
            density=run(scripts['density']);assert isinstance(density,int)
            densities[circuit]=density;release()
        assert densities['ADC VIO']>densities['ADC ground']+200000,densities
        transfer=[]
        for level in [32,96,160,224]:
            # Project edit is safe here: no acquisition is active.
            vm.upload(230,primitive('p2DAC8',(0,level,'DAC 990R 3V')),2);assert run(230) is True
            time.sleep(.02);native(0,2,'ADC 1x');until(lambda:info('state')!=1)
            density=run(scripts['density']);transfer.append(dict(dac_code=level,density_ppm=density));release()
        assert all(b['density_ppm']>a['density_ppm'] for a,b in zip(transfer,transfer[1:])),transfer
        report['checks']['adc_full_clock_bit_density_response']=dict(references_ppm=densities,transfer=transfer,
            absolute_accuracy=False,enob=False)

        cancellations=[]
        for action in ['data release','trigger release','cog stop','stop-all','code edit']:
            source(8);run(202)
            assert helper('recent',Pin=1,Circuit='Schmitt',Maximum=180000000,History=256,After=256,
                Cog=2,Trigger=5,High=True,Timeout=5000) is True
            if action=='data release':run(207)
            elif action=='trigger release':run(208)
            elif action=='cog stop':assert run(209) is True
            elif action=='stop-all':vm.short(6)
            else:vm.upload(240,primitive('p2RuntimeRevision'),2)
            until(lambda:info('state') not in [1,7]);assert info('state')==3,(action,info('state'))
            assert info('buffer guards') is True;cancellations.append(action);release()
        code=primitive('p2ClockHz');code+=b'\0'*(1012-len(code));vm.upload(231,code,2,fragmented=True)
        assert run(231)==180000000
        for token in range(20):
            first=len(vm.events);vm.short(26,token);vm.wait(lambda e:e[:2]==(26,token),after=first)
        assert run(212) is True and run(213) is True
        report['checks']['fifo_return_hub_transport_and_lifecycle']=dict(cancellation=cancellations,
            buffer_and_stack_guards=True,pings=20,fragmented_code_bytes=1012,matching_crc=True)
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
