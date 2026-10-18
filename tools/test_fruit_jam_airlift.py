#!/usr/bin/env python3
"""Explicit factory AirLift identification over the verified Fruit Jam CDC.

No Wi-Fi credentials, scan, firmware upload or I2C access. Reset22 is used only
with --reset-before-first-query; it also resets the idle audio codec.
Two unused VM chunks are selected and removed; existing chunks are retained.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse, json, re, time
from datetime import datetime, timezone
from pathlib import Path
from fruit_jam_serial import SerialVM
from test_wireless_vm import primitive

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',default='COM8')
    parser.add_argument('--firmware-elf-sha256',required=True)
    parser.add_argument('--reset-before-first-query',action='store_true')
    parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args()
    if not re.fullmatch('[0-9a-f]{64}',args.firmware_elf_sha256):raise ValueError('Expected ELF SHA256')
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
        firmware_elf_sha256=args.firmware_elf_sha256,checks={},
        network_credentials_sent=False,coprocessor_flashed=False,external_sensor_access=False)
    vm=None; owned_chunks=[]; before=None
    arithmetic=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
    def run(name):
        vm.upload(diagnostic_chunk,primitive(name),2)
        return vm.run_reporter(diagnostic_chunk)
    try:
        vm=SerialVM(args.port)
        report['usb_identity']=vm.identity
        assert vm.identity['serial']=='E46570978F1E5A34','Unexpected Fruit Jam USB serial'
        before=vm.all_crcs()
        free=[n for n in range(254,-1,-1) if n not in before]
        if len(free)<2:raise RuntimeError('Need two unused VM chunks for the diagnostic')
        diagnostic_chunk,arithmetic_chunk=free[:2]
        owned_chunks=free[:2]
        report['temporary_chunks']=owned_chunks
        report['checks']['initial_status']=json.loads(run('airliftStatus'))
        results=[]
        for n in range(3):
            initial=json.loads(run('airliftStatus'))
            generation=initial['generation']+1
            command='airliftResetAndIdentify' if n==0 and args.reset_before_first_query else 'airliftIdentify'
            run(command)
            deadline=time.monotonic()+12
            while time.monotonic()<deadline:
                status=json.loads(run('airliftStatus'))
                if status['generation']==generation and status['state'] in (3,4):break
                time.sleep(.15)
            else:raise TimeoutError('Bounded AirLift diagnostic did not complete')
            results.append(status)
            vm.upload(arithmetic_chunk,arithmetic,2)
            assert vm.run_reporter(arithmetic_chunk)==12,'USB VM stopped responding during AirLift test'
            if status['state']!=3:break
        report['checks']['identification_runs']=results
        report['checks']['arithmetic_after_queries']=12
        after={n:crc for n,crc in vm.all_crcs().items() if n not in owned_chunks}
        assert after==before,'Existing VM code changed'
        report['checks']['retained_code_crc32']={str(n):f'{crc:08x}' for n,crc in after.items()}
        assert len(results)==3 and all(item['state']==3 and item['error']==0 and item['queries']==3 for item in results),results
        assert len({item['version'] for item in results})==1
        assert all(re.fullmatch(r'(?:[0-9a-f]{2}:){5}[0-9a-f]{2}',item['mac']) for item in results)
        assert len({item['mac'] for item in results})==1
        assert all(item['mac'] not in ('00:00:00:00:00:00','ff:ff:ff:ff:ff:ff') for item in results)
        assert all(item['coprocessor_flashed'] is False for item in results)
        vm.close();vm=None
        vm=SerialVM(args.port)
        assert vm.identity['serial']=='E46570978F1E5A34'
        assert vm.run_reporter(arithmetic_chunk)==12
        report['checks']['reconnect_arithmetic']=12
        report['result']='PASS'
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm:
            try:
                for chunk in owned_chunks:vm.short(2,chunk)
                start=len(vm.events);vm.short(26,97)
                vm.wait(lambda e:e[:2]==(26,97),after=start)
                if before is not None:assert vm.all_crcs()==before,'Cleanup changed existing code'
            except Exception as exc:
                report['cleanup_error']=type(exc).__name__+': '+str(exc)
                report['result']='FAIL'
            vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
