#!/usr/bin/env python3
"""Read-only onboard checks and argument rejection; never drives SPI/PWM outputs.

Only ES8311 immutable IDs are read. No generic register writes, valid external
transfers, pull changes, or tones. One vacant temporary chunk is restored away.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import struct
from test_wireless_vm import VM, op, words, primitive


def code_call(opcode, arguments=(), *, name=None, namespace=4, command=False):
    ops=[op(9)];literals=[]
    def literal(value):
        raw=value.encode()+b'\0' if isinstance(value,str) else value
        padded=raw+b'\0'*((-len(raw))%4)
        header=(len(padded)//4<<4)|(4 if isinstance(value,str) else 3)
        if isinstance(value,bytes):header|=((-len(value))%4)<<29
        offset_word=len(ops)+1;ops.extend([op(5),0]);literals.append((offset_word,struct.pack('<I',header)+padded))
    for value in arguments:
        if isinstance(value,(str,bytes)):literal(value)
        elif isinstance(value,bool):ops.append(op(2,4 if value else 0))
        elif -64<=value<=63:ops.append(op(2,2*value+1))
        else:
            tagged=2*value+1;ops.extend([op(3,tagged&255),(tagged>>8)&65535])
    if name is None:ops.append(op(opcode,len(arguments)))
    else:
        name_word=len(ops)+1;ops.extend([op(37,len(arguments)),0])
    if command:ops.append(op(2,0))
    ops.extend([op(35),op(127)])
    if len(ops)%2:ops.append(0)
    blob=bytearray(words(ops))
    for offset_word,data in literals:
        struct.pack_into('<H',blob,2*offset_word,len(blob)//2-offset_word);blob.extend(data)
    if name is not None:
        raw=name.encode()+b'\0';raw+=b'\0'*((-len(raw))%4)
        struct.pack_into('<H',blob,2*name_word,(namespace<<10)+(len(blob)//2-name_word))
        blob.extend(struct.pack('<I',(len(raw)//4<<4)|4)+raw)
    return bytes(blob)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--evidence',required=True,type=Path)
    parser.add_argument('--checkpoint',required=True,type=Path)
    parser.add_argument('--firmware-sha256',required=True)
    args=parser.parse_args()
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
        firmware_sha256=args.firmware_sha256,checks={},physical_external_outputs_tested=False,
        audio_emitted=False,generic_register_data_writes=0)
    vm=None;owned=False;chunk=249;original={}
    def crcs():
        start=len(vm.events);vm.short(38,1)
        data=vm.wait(lambda e:e[0]==39,seconds=8,after=start)[2]
        return {data[i]:int.from_bytes(data[i+1:i+5],'little') for i in range(0,len(data),5)}
    def run(code,error=None):
        vm.upload(chunk,code,2)
        if error is None:return vm.run_reporter(chunk)
        index=len(vm.events);vm.short(3,chunk)
        event=vm.wait(lambda e:e[0] in (18,19) and e[1]==chunk,after=index)
        assert event[0]==19 and event[2][0]==error,(error,event)
        return error
    def caps():return json.loads(run(primitive('ioCapabilities')))
    try:
        vm=VM(args.host);original=crcs();assert chunk not in original,'Temporary chunk occupied'
        index=len(vm.events);vm.short(13,1);vm.short(9,0);vm.short(26,94)
        vm.wait(lambda e:e[:2]==(26,94),seconds=10,after=index)
        records=[dict(type=t,id=i,body_hex=b.hex()) for t,i,b in vm.events[index:] if t in (32,29)]
        assert {v['id'] for v in records if v['type']==32}==set(original)
        args.checkpoint.parent.mkdir(parents=True,exist_ok=True)
        args.checkpoint.write_text(json.dumps(dict(crc32={str(k):f'{v:08x}' for k,v in original.items()},records=records),indent=2)+'\n',encoding='utf-8',newline='\n')
        owned=True;before=caps()
        assert before['analog_gpio']==[1,2] and before['digital_gpio']==[1,2,17]
        assert before['spi_initialized']==before['pwm_initialized']==before['pwm_active']==0,before
        report['checks']['initial_capabilities']=before
        ids=[run(code_call(96,[24,reg])) for reg in (253,254)]
        assert ids==[131,17],ids;report['checks']['es8311_read_only_ids']=ids
        assert run(code_call(84))==2 and run(code_call(85))==3
        report['checks']['native_pin_counts']={'analog':2,'digital':3}
        invalid=[(96,[-1,0],21),(96,[24,256],22),(96,[False,0],13),
            (95,[24,0,256],23),(95,[128,0,0],21),
            (97,[256],23),(97,[True],13),(97,[bytes(260)],18),
            (86,[2],57),(86,[False],13),(87,[0,10],57),(87,[2,True],13),
            (86,[],28),(87,[2],28),(95,[24,0],28),(96,[],28),(97,[],28),(98,[0],28)]
        report['checks']['invalid_native_calls']=[dict(opcode=o,error=run(code_call(o,a,command=o in (87,95,97)),e)) for o,a,e in invalid]
        assert run(code_call(97,[b''],command=True)) is False
        assert run(code_call(37,[b''],name='spiExchange')) is False
        assert run(code_call(37,[250000,3,0,'LSB'],name='spiSetup')) is False
        configured=caps();assert configured['spi_hz']==250000 and configured['spi_mode']==3 and configured['spi_lsb']==1
        assert configured['spi_initialized']==configured['pwm_initialized']==configured['pwm_active']==0
        assert run(code_call(37,[1000000],name='spiSetup')) is False
        after=caps();assert after['spi_hz']==1000000 and after['spi_mode']==after['spi_lsb']==0
        assert after['spi_initialized']==after['pwm_initialized']==after['pwm_active']==0,after
        report['checks']['configuration_and_empty_calls_never_initialize_outputs']=True
        report['checks']['final_capabilities']=after
        report['checks']['rtc']=run(primitive('rtcText'))
        report['checks']['temperature_milli_c']=run(primitive('temperatureMilliC'))
        report['checks']['humidity_milli_pct']=run(primitive('humidityMilliPct'))
        report['checks']['battery_raw']=run(primitive('batteryRaw'))
        report['checks']['audio_status_read_only']=json.loads(run(primitive('audioStatus')))
        assert report['checks']['audio_status_read_only']['starts']==0,'Unexpected audio playback'
        report['result']='PASS'
    except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm and owned:
            try:
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
