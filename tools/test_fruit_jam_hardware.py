#!/usr/bin/env python3
"""Focused physical Fruit Jam USB SmallVM and SHT4x acceptance.

Uses only the positively identified Fruit Jam CDC. Replaces test VM chunks;
does not flash or reset firmware. SHT4x uses no-heater commands at 0x44 only.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
import time
from fruit_jam_serial import SerialVM
from test_wireless_vm import op, words, primitive
from test_generic_io import code_call


def crc8(data):
    crc = 255
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = ((crc<<1)^0x31)&255 if crc&128 else (crc<<1)&255
    return crc


def read_six_code():
    # Keep the exact read destination in variable 20; report its six items in
    # separate messages without issuing six destructive sensor reads.
    ops = [op(9),op(5),10,op(7,20),op(3,137),0,op(6,20),op(37,2),
           (4<<10)+10,op(35),op(127),0]
    return words(ops)+struct.pack('<I',0x40000023)+bytes(8)+struct.pack('<I',36)+b'i2cRead\0'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM8')
    parser.add_argument('--phase',choices=['baseline','after-reboot','sensor'],required=True)
    parser.add_argument('--expected',type=Path)
    parser.add_argument('--evidence',type=Path,required=True)
    args = parser.parse_args()
    report = dict(result='FAIL',phase=args.phase,
        started_utc=datetime.now(timezone.utc).isoformat(),checks={},
        firmware_elf_sha256='ccc4b9cbf583a35fe52da15dea90ce9cfbbd0ef05375ff26a4679d76214d14ce')
    vm = None
    def sync(index):
        start=len(vm.events);vm.short(26,index)
        return vm.wait(lambda e:e[:2]==(26,index),after=start)
    def run(code,chunk=249):
        vm.upload(chunk,code,2)
        return vm.run_reporter(chunk)
    def named(name,values=()):
        return run(code_call(37,values,name=name))
    try:
        vm = SerialVM(args.port)
        report['usb_identity']=vm.identity
        assert vm.identity['serial']=='E46570978F1E5A34','Unexpected Fruit Jam USB serial'
        sync(91);report['checks']['ping']=True
        start=len(vm.events);vm.short(12)
        version=vm.wait(lambda e:e[0]==22,after=start)[2]
        report['checks']['version']=version[1:].decode()
        assert '417' in report['checks']['version'] and 'Fruit Jam RP2350B' in report['checks']['version']
        if args.phase=='baseline':
            vm.short(14,1);vm.short(15,0);sync(92)
            reporter=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
            crcs={0:vm.upload(0,reporter,2)}
            assert [vm.run_reporter(0) for _ in range(10)]==[12]*10
            report['checks']['arithmetic_runs']=10
            edited=bytearray(reporter);edited[5]=17
            vm.upload(0,edited,2);assert vm.run_reporter(0)==13
            vm.upload(0,reporter,2);report['checks']['live_edit_result']=13
            stream=words([op(2,1),op(7,0),op(3,99),0,op(7,1),op(6,1),
                op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
            crcs[3]=vm.upload(3,stream)
            start=len(vm.events);vm.short(3,3)
            vm.wait(lambda e:e[:2]==(17,3),seconds=20,after=start)
            outputs=[int(e[2][1:]) for e in vm.events[start:] if e[:2]==(20,254)]
            assert outputs==list(range(1,51)),outputs
            report['checks']['ordered_outputs']=outputs
            large=words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0])
            crcs[2]=vm.upload(2,large,fragmented=True)
            start=len(vm.events);vm.short(3,2)
            vm.wait(lambda e:e[:2]==(17,2),after=start)
            report['checks']['fragmented_upload_bytes']=len(large)+7
            vm.send(bytes([251,32,7,100,0,1]));time.sleep(.35);sync(94)
            report['checks']['partial_frame_timeout_recovery']=True
            loop=words([op(9),op(2,3),op(8,5),op(22,-3)])
            vm.upload(5,loop);start=len(vm.events);vm.short(3,5)
            vm.wait(lambda e:e[:2]==(16,5),after=start);time.sleep(.1)
            vm.short(4,5);value=vm.variable(5);time.sleep(.15)
            assert value>0 and vm.variable(5)==value
            vm.short(2,5);sync(95)
            report['checks']['stop_and_variable_inspection']=True
            startup=words([op(9),op(2,85),op(7,9),0])
            crcs[4]=vm.upload(4,startup,4)
            for chunk,crc in crcs.items():assert vm.crc(chunk)==crc
            report['checks']['code_crc32']={str(k):f'{v:08x}' for k,v in crcs.items()}
            report['checks']['io_capabilities']=json.loads(run(primitive('ioCapabilities')))
            report['checks']['buttons_pressed']=[run(primitive('buttonPressed',[n])) for n in (1,2,3)]
            vm.short(2,249);sync(96)
            vm.close();vm=None;time.sleep(.2)
            vm=SerialVM(args.port);assert vm.run_reporter(0)==12
            report['checks']['reconnect_arithmetic']=True
            deadline=time.monotonic()+7
            while time.monotonic()<deadline:vm.pump()
            for chunk,crc in crcs.items():assert vm.crc(chunk)==crc
            report['checks']['snapshot_debounce_wait_seconds']=7
        elif args.phase=='after-reboot':
            if not args.expected:raise ValueError('--expected baseline report is required')
            expected=json.loads(args.expected.read_text(encoding='utf-8'))['checks']['code_crc32']
            actual={k:f'{vm.crc(int(k)):08x}' for k in expected}
            assert actual==expected,(actual,expected)
            assert vm.run_reporter(0)==12
            assert vm.variable(9)==42
            report['checks'].update(code_crc32=actual,reboot_arithmetic=12,startup_variable_9=42)
        else:
            # Some I2C controllers cannot issue a zero-length address probe.
            # A documented command plus CRC-checked response is authoritative.
            report['checks']['zero_length_address_probe']=named('i2cExists',[68])
            report['checks']['capabilities_after_probe']=json.loads(run(primitive('ioCapabilities')))
            def read_six():
                assert run(read_six_code(),248)==6
                raw=bytes(run(words([op(9),op(6,20),op(2,2*n+1),op(81,2),op(35),op(127)]))
                          for n in range(1,7))
                assert crc8(raw[:2])==raw[2] and crc8(raw[3:5])==raw[5],raw.hex()
                return raw
            named('i2cWrite',[68,0x89]);time.sleep(.01)
            raw=read_six()
            report['checks']['known_address_0x44_present']=True
            report['checks']['serial_number']={'raw_hex':raw.hex(),
                'serial_hex':(raw[:2]+raw[3:5]).hex(),'both_crcs_valid':True}
            samples=[]
            for _ in range(3):
                named('i2cWrite',[68,0xfd]);time.sleep(.02)
                raw=read_six();t=int.from_bytes(raw[:2],'big');h=int.from_bytes(raw[3:5],'big')
                temperature=-45+175*t/65535
                humidity=max(0,min(100,-6+125*h/65535))
                assert -40<=temperature<=125 and 0<=humidity<=100
                samples.append(dict(raw_hex=raw.hex(),temperature_c=round(temperature,4),
                    humidity_percent=round(humidity,4),temperature_crc=True,humidity_crc=True))
                time.sleep(.15)
            report['checks']['samples']=samples
            report['checks']['exact_variant']='SHT4x protocol-compatible; SHT40 versus SHT41 not identified'
            report['checks']['heater_used']=False
            vm.short(2,248);vm.short(2,249);sync(99)
        report['result']='PASS'
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm:
            report['transport_counters']=dict(sent=vm.sent_bytes,received=vm.received_bytes)
            vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1


if __name__=='__main__':raise SystemExit(main())
