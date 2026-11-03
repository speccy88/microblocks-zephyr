#!/usr/bin/env python3
"""Global filter ownership and external continuous-bit capture on paired EC32MB."""
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


def pattern(raw):
    bits=[(byte>>bit)&1 for byte in raw for bit in range(8)]
    phases=[p for p in range(31) if all(v==int((i+p)%31<15) for i,v in enumerate(bits[:62]))]
    assert len(phases)==1,('pattern phase',phases,raw[:24].hex())
    phase=phases[0]
    assert all(v==int((i+phase)%31<15) for i,v in enumerate(bits)),('noncontiguous bit pattern',phase)
    return dict(bytes=len(raw),bits=len(bits),phase=phase,sha256=hashlib.sha256(raw).hexdigest(),all_bits_match=True)


def test(args):
    report=dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),result='FAIL',checks={},
        scope='four global filter banks and native external continuous bit ring',
        internal_full_clock_continuous_tested=False,streamer_dma_tested=False,
        external_converter_tested=False,absolute_clock_or_analog_accuracy_tested=False,usb_tested=False)
    vm=None
    try:
        p=json.loads(args.program.read_text(encoding='utf-8'))
        vm=P2SerialVM(args.port,args.usb_serial,'edge32');report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(10,1);vm.short(15)
        for name,index in p['variables'].items():
            raw=name.encode()+b'\xfe';vm.send(bytes([251,29,index])+len(raw).to_bytes(2,'little')+raw)
        for c in p['chunks']:
            raw=bytes(c['bytes']);vm.upload(c['id'],raw+b'\0'*(-len(raw)%4),c['kind'])
        scripts=dict(zip(['configure','input','filter_info','routed','rises','debounce','generic','stream',
            'capture_info','read','stop','pulse','long','source'],p['scripts']))
        functions={c['name']:c['id'] for c in p['chunks'] if c['name']}
        queries={200:('p2RuntimeRevision',()),201:('p2ClockHz',()),202:('digitalWrite',(0,False)),
            203:('p2PinRelease',(1,)),204:('p2PinRelease',(3,)),205:('digitalWrite',(0,True)),
            206:('digitalWrite',(2,False)),207:('p2CogStop',(2,)),208:('p2CogStop',(3,)),
            209:('p2CogStart',('bitStreamHeartbeat',3)),210:('p2CogStart',('bitStreamConsumer',3)),
            211:('p2CogStart',('workerFilter',3)),212:('p2LocalPinDIR',(1,)),
            213:('p2CaptureStart',(1,'bits',32,1,0,2,False,0,100)),
            214:('p2CogStackOK',(2,)),215:('p2CogStackOK',(3,)),216:('p2PinAck',(1,)),
            217:('p2PinWriteX',(1,'0')),218:('p2PinReadHex',(1,)),
            219:('p2PinRelease',(0,)),221:('p2PinRelease',(2,))}
        for index,(name,values) in queries.items():vm.upload(index,primitive(name,values),2)
        def run(index,seconds=15):
            first=len(vm.events);vm.short(3,index)
            return decode(vm.wait(lambda e:e[:2]==(18,index),after=first,seconds=seconds)[2])
        def call(name,*values):vm.upload(220,primitive(name,values),2);return run(220)
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
        def until(condition,seconds=15):
            end=time.monotonic()+seconds
            while time.monotonic()<end:
                if condition():return
                errors=[(e[1],e[2].hex()) for e in vm.events if e[0]==19]
                if errors:raise RuntimeError('VM error '+str(errors[-3:]))
                vm.pump()
            raise TimeoutError('filter/capture phase')
        def fi(bank,field):return helper('filter_info',Bank=bank,Field=field)
        def info(field):return helper('capture_info',Field=field)
        def release():
            run(203);run(204);run(219);run(221)
        def read():return helper('read',ReadCount=24)
        def drain():
            data=b''
            while info('available'):data+=read()
            return data
        def source(hz=20000):assert helper('source',Frequency=hz) is True
        def start(timeout=1000):assert helper('stream',Pin=1,Cog=2,B=2,Timeout=timeout) is True
        assert run(200)>=7 and run(201)==180000000
        report['extension_revision']=run(200)

        defaults=[]
        for bank,(length,tap) in enumerate([(2,0),(3,5),(5,19),(8,22)]):
            assert fi(bank,'length')==length and fi(bank,'tap')==tap and fi(bank,'users')==0
            defaults.append(dict(bank=bank,length=length,tap=tap))
        report['checks']['documented_boot_filter_defaults']=defaults
        pulses=[]
        for bank,(length,tap) in enumerate([(2,10),(3,9),(5,8),(8,8)]):
            run(202);assert helper('configure',Bank=bank,Length=length,Tap=tap) is True
            assert helper('rises',Pin=1,Bank=bank,Window=0) is True
            assert fi(bank,'users')==1
            config=fi(bank,'configuration hex')
            assert helper('configure',Tap=tap+1) is False
            assert fi(bank,'configuration hex')==config
            assert helper('configure',Tap=tap) is True
            baseline=int(helper('pulse',High=2,Low=50,Count=1),16)
            narrow=int(helper('pulse',Count=100),16)
            broad=int(helper('pulse',High=40,Low=40,Count=100),16)
            assert narrow-baseline==0 and broad-narrow==100,(bank,baseline,narrow,broad)
            pulses.append(dict(bank=bank,length=length,tap=tap,narrow_high_us=2,
                long_high_us=40,narrow_rises=narrow-baseline,long_rises=broad-narrow,active_retime_refused=True))
            run(203)
        report['checks']['all_banks_and_lengths_pulse_rejection']=pulses
        print('Four filter banks/lengths reject narrow and count long pulses PASS',flush=True)

        assert helper('configure',Bank=0,Length=8,Tap=8) is True
        assert helper('input',Pin=1,Bank=0) is True and helper('input',Pin=3) is True
        assert fi(0,'users')==2 and helper('configure',Tap=9) is False
        run(203);assert fi(0,'users')==1 and helper('configure',Tap=9) is False
        run(204);assert helper('configure',Tap=9) is True
        assert call('p2SmartPinRaw',1,'0086001c','0','0') is True
        assert fi(0,'users')==1 and helper('configure',Tap=10) is False
        before=fi(0,'configuration hex');vm.short(6)
        assert fi(0,'users')==0 and fi(0,'configuration hex')==before
        assert helper('configure',Tap=10) is True
        report['checks']['shared_raw_consumer_and_stop_ownership']=True
        run(202);run(206);assert call('p2PadNamed',3,'Schmitt',False,False) is True
        assert helper('routed',Pin=1,Bank=2,AOffset=2,Ainv=True,B=0,Binv=False) is True
        time.sleep(.005);assert call('p2PinSample',1) is True
        call('digitalWrite',2,True)
        time.sleep(.005);assert call('p2PinSample',1) is False and run(212) is False
        report['checks']['routed_inverted_filtered_input']=dict(input_pin=1,source_pin=3,source_driver=2,
            a_offset=2,inverted=True,receiver_dir=False)
        release()
        run(202);assert helper('debounce',Pin=1,Bank=1,Usecs=1000) is True
        assert fi(1,'length')==8 and fi(1,'tap')==15
        run(203);assert helper('rises',Pin=1,Bank=1,Window=0) is True
        short=int(helper('pulse',High=200,Low=1,Count=1),16)
        long=int(run(scripts['long']),16);assert short==0 and long==1,(short,long)
        report['checks']['debounce_microsecond_helper']=dict(request_minimum_us=1000,length=8,tap=15,
            actual_minimum_clocks=7*32768,actual_maximum_clocks=8*32768,short_200us_rejected=True,long_5ms_counted=True)
        run(203)
        assert helper('configure',Bank=0,Length='8',Tap=8) is True
        stable=fi(0,'configuration hex')
        for values in [dict(Bank=4),dict(Bank=0,Length=4),dict(Length=8,Tap=32)]:
            assert helper('configure',**values) is False
        assert fi(0,'configuration hex')==stable
        assert call('p2FilterInput',63,0,0,False,0,False) is False
        assert helper('debounce',Pin=63,Bank=0,Usecs=1000) is False
        assert helper('generic',Pin=1,Operation='count rises',Circuit='Schmitt',X='0',Y='0',
            Drive=False,AOffset=0,B=0,Bank=0) is True
        assert fi(0,'users')==1
        code=primitive('p2ClockHz');code+=b'\0'*(1012-len(code))
        vm.upload(230,code,2,fragmented=True)
        for token in range(20):
            first=len(vm.events);vm.short(26,token)
            vm.wait(lambda e:e[:2]==(26,token),after=first)
        assert run(201)==180000000
        run(203);setvars(Done=0);assert run(211) is True
        until(lambda:value('Done')==1)
        assert value('Core')==3 and fi(3,'users')==1 and run(212) is False
        run(203)
        report['checks']['worker_requests_clock_and_binary_transport']=dict(cog=3,receiver_dir=False,
            clock_report_hz=180000000,pings=20,fragmented_code_bytes=1012,wire_packet_bytes=1019,matching_crc=True)
        release();print('Filter sharing, raw ownership, debounce, worker and IDE transport PASS',flush=True)

        source();start();assert info('continuous bits')==1 and info('local DIR')==0
        assert run(213) is False and info('state')==1
        assert run(216) is False and run(217) is False and run(218) is False
        setvars(Progress=0);assert run(209) is True
        all_bytes=b'';deadline=time.monotonic()+20
        while len(all_bytes)<1200*4 and time.monotonic()<deadline:
            all_bytes+=read();assert info('state')==1
        assert len(all_bytes)>=1200*4
        setvars(Done=False);first=len(vm.events);vm.short(3,functions['filterCaptureGC'])
        until(lambda:value('Done') is True)
        gc=sum(b'GC took' in e[2] for e in vm.events[first:]);assert gc>0
        assert value('Core')==3 and value('Progress')>0 and info('state')==1
        assert run(208) is True and run(scripts['stop']) is True
        emitted=info('emitted');buffered=info('available')
        if report['extension_revision']>=8:assert info('startup discarded words')==1
        assert len(all_bytes)//4+buffered==emitted
        all_bytes+=drain();check=pattern(all_bytes)
        assert info('maximum gap clocks')<=288128
        delta=((info('elapsed clocks')-(emitted-1)*288000+(1<<29))&0x3fffffff)-(1<<29)
        assert abs(delta)<=128,delta
        check.update(emitted_words=emitted,ring_wrapped=emitted>1024,gc_events=gc,worker_progress=value('Progress'),
            maximum_gap_clocks=info('maximum gap clocks'),elapsed_error_clocks=delta)
        report['checks']['external_continuous_pattern_ring_wrap_gc']=check
        release()

        source();setvars(Consumed=0,Progress=0,StopConsumer=False,ConsumerStopped=False);start();assert run(210) is True
        setvars(Done=False);vm.short(3,functions['filterCaptureGC'])
        until(lambda:value('Done') is True);until(lambda:value('Consumed')>=1200,20)
        setvars(StopConsumer=True);until(lambda:value('ConsumerStopped') is True)
        assert run(208) is True and run(scripts['stop']) is True
        consumed=value('Consumed');available=info('available');emitted=info('emitted')
        assert consumed+available==emitted and emitted>1024,(consumed,available,emitted)
        assert info('maximum gap clocks')<=288128
        report['checks']['worker_bytearray_consumption_and_gc']=dict(native_cog=2,consumer_cog=value('Core'),
            consumed_words=consumed,buffered_words=available,emitted_words=emitted,
            maximum_gap_clocks=info('maximum gap clocks'),exact_accounting=True)
        release();print('Continuous external raw ring wrap, pattern and GC/worker consumption PASS',flush=True)

        source(1000000);start()
        until(lambda:info('state')!=1);assert info('state')==4 and info('available')==1023
        assert info('emitted')==1023
        assert info('maximum gap clocks')<=5888
        assert abs(info('elapsed clocks')-1022*5760)<=128
        check=pattern(drain());check.update(bit_clock_hz=1000000,overflow_words_retained=1023)
        report['checks']['external_1mhz_overflow_retains_contiguous_data']=check
        release()
        source();run(205);start();until(lambda:info('available')>=32)
        assert run(scripts['stop']) is True;data=drain();assert len(data)>=128 and set(data)=={255}
        report['checks']['full_32_bit_all_ones_preserved']=dict(bytes=len(data),all_ff=True)
        release()
        if report['extension_revision']>=8:
            startups=[]
            for hz in [20000,62500,1000000,62500,20000,1000000]:
                source(hz);start();until(lambda:info('available')>=8)
                assert run(scripts['stop']) is True and info('startup discarded words')==1
                check=pattern(drain());check.update(bit_clock_hz=hz,startup_snapshots_discarded=1)
                startups.append(check);release()
            report['checks']['external_startup_snapshot_sync']=startups
        source();start(100);run(206)
        until(lambda:info('state')!=1);assert info('state')==5
        release()
        cancellations=[]
        for action in ['release','cog','stop-all','edit']:
            source();start()
            if action=='release':run(203)
            elif action=='cog':assert run(207) is True
            elif action=='stop-all':vm.short(6)
            else:vm.upload(240,primitive('p2RuntimeRevision'),2)
            until(lambda:info('state')!=1);assert info('state')==3,(action,info('state'))
            cancellations.append(action);release()
        assert run(214) is True and run(215) is True
        report['checks']['stream_timeout_and_lifecycle']=dict(missing_word_timeout=True,cancellation=cancellations,
            native_and_worker_stack_guards=True)
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
