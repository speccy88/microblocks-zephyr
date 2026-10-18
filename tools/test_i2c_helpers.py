#!/usr/bin/env python3
"""Bounded I2C helper acceptance: only known ES8311 ID reads, no bus scan.

No register-data writes or audible output. The write(false) prefixes are the
known immutable ID register addresses, sent only with atomic one-byte reads.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import struct
from test_wireless_vm import VM,op,words,primitive
from test_generic_io import code_call


def read_first(*,list_target):
    # Actual named i2cRead, then return item 1 from the same temporary object.
    ops=[op(9),op(2,49),op(5),0,op(37,2),0,op(19,1),op(2,3),op(5),0,op(81,2),op(35),op(127),0]
    payload=struct.pack('<III',41,3,1) if list_target else struct.pack('<II',0x60000013,0)
    ops[3]=len(ops)-3;ops[9]=len(ops)-9
    name_word=len(ops)+len(payload)//2
    ops[5]=(4<<10)+name_word-5
    name=b'i2cRead\0'
    return words(ops)+payload+struct.pack('<I',36)+name


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--firmware-sha256',required=True)
    parser.add_argument('--evidence',required=True,type=Path)
    parser.add_argument('--checkpoint',required=True,type=Path)
    args=parser.parse_args()
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),firmware_sha256=args.firmware_sha256,
        checks={},bus_scan=False,generic_register_data_writes=0,audio_emitted=False)
    vm=None;owned=False;chunk=249;original={}
    def crcs():
        start=len(vm.events);vm.short(38,1)
        data=vm.wait(lambda e:e[0]==39,seconds=8,after=start)[2]
        return {data[i]:int.from_bytes(data[i+1:i+5],'little') for i in range(0,len(data),5)}
    def run(code,error=None):
        vm.upload(chunk,code,2)
        if error is None:return vm.run_reporter(chunk)
        start=len(vm.events);vm.short(3,chunk)
        event=vm.wait(lambda e:e[0] in (18,19) and e[1]==chunk,after=start)
        assert event[0]==19 and event[2][0]==error,(error,event)
        return error
    def named(name,values=(),error=None):return run(code_call(37,values,name=name),error)
    def caps():return json.loads(run(primitive('ioCapabilities')))
    try:
        vm=VM(args.host);original=crcs();assert chunk not in original
        start=len(vm.events);vm.short(13,1);vm.short(9,0);vm.short(26,94)
        vm.wait(lambda e:e[:2]==(26,94),seconds=10,after=start)
        records=[dict(type=t,id=i,body_hex=b.hex()) for t,i,b in vm.events[start:] if t in (32,29)]
        assert {v['id'] for v in records if v['type']==32}==set(original)
        args.checkpoint.parent.mkdir(parents=True,exist_ok=True)
        args.checkpoint.write_text(json.dumps(dict(crc32={str(k):f'{v:08x}' for k,v in original.items()},records=records),indent=2)+'\n',encoding='utf-8',newline='\n')
        owned=True
        assert named('i2cExists',[24]) is True
        report['checks']['known_codec_present']=True
        assert named('i2cExists',[128]) is False and named('i2cExists',[True]) is False
        assert named('i2cRead',[24,b''])==0
        assert named('i2cWrite',[24,b'']) is False
        invalid=[('i2cWrite',[128,0],21),('i2cWrite',[24,256],23),
            ('i2cWrite',[24,bytes(33)],18),('i2cWrite',[24,True],36),
            ('i2cRead',[128,b''],21),('i2cRead',[24,True],36)]
        report['checks']['invalid_calls']=[dict(name=n,error=named(n,a,e)) for n,a,e in invalid]
        reads=[]
        for register,expected,list_target in [(253,131,False),(254,17,True)]:
            assert named('i2cWrite',[24,register,False]) is False
            assert caps()['i2c_pending']==1
            actual=run(read_first(list_target=list_target));assert actual==expected,(register,actual)
            assert caps()['i2c_pending']==0
            reads.append(dict(address=24,register=register,destination='List' if list_target else 'ByteArray',count=1,value=actual))
        report['checks']['atomic_known_id_reads']=reads
        assert named('i2cWrite',[24,253,False]) is False
        assert caps()['i2c_pending']==1
        vm.close();vm=VM(args.host)
        assert caps()['i2c_pending']==0
        report['checks']['new_controller_cancels_staged_write_without_flush']=True
        final=caps();assert final['spi_initialized']==final['pwm_initialized']==final['pwm_active']==0
        report['checks']['final_capabilities']=final
        report['checks']['rtc']=run(primitive('rtcText'))
        report['checks']['audio_status_read_only']=json.loads(run(primitive('audioStatus')))
        assert report['checks']['audio_status_read_only']['starts']==0
        report['result']='PASS'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm and owned:
            try:
                # A safe native ID read cancels any residual staged prefix.
                assert run(code_call(96,[24,253]))==131
                start=len(vm.events);vm.short(2,chunk);vm.short(26,99)
                vm.wait(lambda e:e[:2]==(26,99),after=start);assert crcs()==original
                report['original_crc32_preserved']={str(k):f'{v:08x}' for k,v in original.items()}
            except Exception as exc:report['result']='FAIL';report['cleanup_error']=str(exc)
        if vm:vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2));return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
