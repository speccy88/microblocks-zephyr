#!/usr/bin/env python3
"""Disposable EC32MB serial/logic test: one driver per P0/1, P2/3, P4/5 pair."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import struct
import time
from pathlib import Path
from p2_serial import P2SerialVM, primitive


def decode(body):
    if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
    if body[0]==2:return body[1:].decode()
    if body[0]==3:return bool(body[1])
    assert body[0]==4 and int.from_bytes(body[1:3],'little')==body[3],body.hex()
    result=[];pos=4
    for _ in range(body[3]):
        assert body[pos]==2,body.hex()
        size=body[pos+1];result.append(body[pos+2:pos+2+size].decode());pos+=2+size
    return result


def test(args):
    report=dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        result='FAIL',scope='checked word serial and input Boolean routing',checks={},
        external_serial_peripheral_tested=False,absolute_baud_accuracy_tested=False,usb_tested=False)
    vm=None
    try:
        p=json.loads(args.program.read_text(encoding='utf-8'))
        vm=P2SerialVM(args.port,args.usb_serial,'edge32');report.update(identity=vm.identity,version=vm.version)
        vm.short(14,1);vm.short(10,1);vm.short(15)
        for name,index in p['variables'].items():
            raw=name.encode()+b'\xfe';vm.send(bytes([251,29,index])+len(raw).to_bytes(2,'little')+raw)
        for c in p['chunks']:
            raw=bytes(c['bytes']);vm.upload(c['id'],raw+b'\0'*(-len(raw)%4),c['kind'])
        scripts=dict(zip(['async_tx','async_rx','sync_tx','sync_rx','send','read','busy','logic','truth','busy_probe','continuous'],p['scripts']))
        vm.upload(221,primitive('p2CogStart',('workerSerialProbe',3)),2)
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
        def received_word(pin):
            deadline=time.monotonic()+2
            while time.monotonic()<deadline:
                word=helper('read',Pin=pin)
                if word is not False:return word
            raise TimeoutError('Serial receive word did not complete')
        def value(name):
            index=p['variables'][name];first=len(vm.events);vm.short(7,index)
            return decode(vm.wait(lambda e:e[:2]==(21,index),after=first)[2])
        def release(*pins):
            for pin in pins:assert call('p2PinRelease',pin) is True
        report['extension_revision']=call('p2RuntimeRevision');assert report['extension_revision']>=6
        release(*range(8))

        asynchronous=[]
        for bits in [1,7,8,9,16,31,32]:
            for inverted in [False,True]:
                baud=921600 if bits in [9,32] else 115200
                assert helper('async_tx',Pin=4,Baud=baud,Bits=bits,Inverted=inverted) is True
                assert helper('async_rx',Pin=5) is True
                assert helper('read',Pin=5) is False
                words=[0,1,((1<<bits)-1),0xa581c37e&((1<<bits)-1)]
                received=[]
                for word in words:
                    assert helper('send',Pin=4,Word=f'{word:08x}') is True
                    actual=received_word(5);assert actual==f'{word:08x}',(bits,inverted,word,actual)
                    received.append(actual)
                assert helper('read',Pin=5) is False
                asynchronous.append(dict(bits=bits,inverted=inverted,baud=baud,received=received))
                release(4,5)
        report['checks']['async_width_polarity_and_fractional_baud']=asynchronous
        assert helper('async_tx',Pin=4,Baud=3000,Bits=32,Inverted=False) is True
        setvars(Word='80000001');assert run(scripts['busy_probe']) is True
        assert value('BusyStart') is True and value('BusyEnd') is False
        report['checks']['async_busy_until_stop_bit_complete']=True
        release(4,5)
        durations=[]
        for inverted in [False,True]:
            for baud in [921600,1234567]:
                assert helper('async_tx',Pin=4,Baud=baud,Bits=32,Inverted=inverted) is True
                assert call('p2PadNamed',5,'Schmitt',False,False) is True
                assert call('p2PinSample',5)==(not inverted)
                # Measure the 33 start/data bit periods independently of RX:
                # normal TX low becomes high through A inversion, inverted TX
                # is already physically high during an all-zero payload.
                mode='00060022' if inverted else '80060022'
                assert call('p2SmartPinRaw',5,mode,'0','0') is True
                assert helper('send',Pin=4,Word='00000000') is True
                ticks=int(call('p2PinReadHex',5),16)
                expected=(180000000*64//baud)/64*33
                assert abs(ticks-expected)<=6,(baud,inverted,ticks,expected)
                durations.append(dict(baud=baud,inverted=inverted,idle_high=not inverted,
                    measured_start_data_clocks=ticks,expected_quantized_clocks=expected))
                release(4,5)
        report['checks']['independent_idle_polarity_and_fractional_bit_timing']=durations
        print('Async 1..32-bit, polarity, fractional baud and busy PASS',flush=True)

        synchronous=[]
        for bits in [1,8,9,16,31,32]:
            for falling in [False,True]:
                for at_edge in [False,True]:
                    msb=not at_edge;word=0x819ac35e&((1<<bits)-1)
                    call('digitalWrite',2,False);assert call('p2PadNamed',3,'Schmitt',False,False) is True
                    assert helper('sync_rx',Pin=1,Bits=bits,B=2,Falling=falling,AtEdge=at_edge,MSB=msb) is True
                    assert helper('sync_tx',Pin=0,Word=f'{word:08x}',Continuous=False) is True
                    assert call('p2Transition',2,250,bits*2) is True
                    actual=received_word(1);assert actual==f'{word:08x}',(bits,falling,at_edge,msb,word,actual)
                    synchronous.append(dict(bits=bits,falling=falling,sample_at_edge=at_edge,msb_first=msb,received=actual))
                    release(0,1,2,3)
        report['checks']['sync_width_clock_sample_and_bit_order']=synchronous
        crossed=[]
        for bits in [8,32]:
            for tx_msb in [False,True]:
                word=0x819ac35e&((1<<bits)-1)
                call('digitalWrite',2,False);assert call('p2PadNamed',3,'Schmitt',False,False) is True
                assert helper('sync_rx',Pin=1,Bits=bits,B=2,Falling=False,AtEdge=True,MSB=not tx_msb) is True
                assert helper('sync_tx',Pin=0,Word=f'{word:08x}',Continuous=False,MSB=tx_msb) is True
                assert call('p2Transition',2,250,bits*2) is True
                actual=received_word(1);expected=int(f'{word:0{bits}b}'[::-1],2)
                assert actual==f'{expected:08x}',(bits,tx_msb,word,actual,expected)
                crossed.append(dict(bits=bits,transmit_msb=tx_msb,receive_msb=not tx_msb,received=actual))
                release(0,1,2,3)
        report['checks']['crossed_bit_order_independent_wire_reversal']=crossed
        call('digitalWrite',2,False)
        assert helper('sync_tx',Pin=0,Bits=8,B=2,Falling=False,Word='a5',Continuous=True,MSB=False) is True
        assert call('p2PinWriteY',0,'5a') is True
        assert helper('send',Pin=0,Word='3c') is False
        release(0,2)
        report['checks']['raw_y_updates_typed_tx_buffer_ownership']=True
        for falling in [False,True]:
            call('digitalWrite',2,False);assert call('p2PadNamed',3,'Schmitt',False,False) is True
            assert helper('sync_rx',Pin=1,Bits=8,B=2,Falling=falling,AtEdge=True,MSB=False) is True
            assert helper('sync_tx',Pin=0,Word='a5',Continuous=True) is True
            result=run(scripts['continuous']);assert result==['000000a5','0000005a','0000003c'],(falling,result)
            release(0,1,2,3)
        report['checks']['continuous_sync_reset_priming_and_three_words_both_edges']=True
        print('Sync widths, edges, sample positions, bit order and priming PASS',flush=True)

        logic=[]
        assert call('p2PadNamed',3,'Schmitt',False,False) is True
        for operation in ['pass A','A AND B','A OR B','A XOR B']:
            for inv_a in [False,True]:
                for inv_b in [False,True]:
                    assert helper('logic',Pin=1,Logic=operation,B=2,Ainv=inv_a,Binv=inv_b) is True
                    for a in [False,True]:
                        for b in [False,True]:
                            aa=a!=inv_a;bb=b!=inv_b
                            expected={'pass A':aa,'A AND B':aa and bb,'A OR B':aa or bb,'A XOR B':aa!=bb}[operation]
                            actual=helper('truth',AV=a,BV=b);assert actual==expected,(operation,inv_a,inv_b,a,b,actual)
                    assert call('p2LocalPinDIR',1) is False
                    logic.append(dict(operation=operation,invert_a=inv_a,invert_b=inv_b,truth_table_pass=True))
        report['checks']['routed_boolean_logic_all_inversions']=dict(configurations=logic,input_cases=64,receiver_dir=False)
        release(*range(6))
        print('Routed pass/AND/OR/XOR with both inversions PASS',flush=True)

        assert helper('async_rx',Pin=5,Baud=115200,Bits=16,Inverted=False) is True
        assert call('p2PinWriteX',5,'061a0007') is True
        assert helper('read',Pin=5) is False
        invalid=[('p2AsyncWords',(4,0,8,True,False)),('p2AsyncWords',(4,115200,33,True,False)),
            ('p2SyncTransmitWords',(0,8,'100',2,False,False,False)),
            ('p2SyncReceiveWords',(1,8,4,False,True,False)),
            ('p2LogicInput',(1,'A AND B',-3,False,2,False))]
        for name,values in invalid:assert call(name,*values) is False,(name,values)
        release(*range(6))
        call('digitalWrite',0,True);call('digitalWrite',2,False)
        assert call('p2PadNamed',3,'Schmitt',False,False) is True
        setvars(Done=False);assert run(221) is True
        deadline=time.monotonic()+10
        while value('Done') is not True:
            if time.monotonic()>deadline:raise TimeoutError('worker serial service')
            vm.pump()
        assert value('Core')==3 and value('Errors')==0
        assert call('p2CogStackOK',3) is True
        report['checks']['worker_main_owned_word_and_logic_services']=dict(cog=3,errors=0,worker_dir=False,stack_guards=True)
        report['checks']['raw_x_invalidation_and_invalid_arguments']=True
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
