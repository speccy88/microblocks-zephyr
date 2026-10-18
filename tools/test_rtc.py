#!/usr/bin/env python3
"""Physical UTC RTC acceptance, using one initially vacant VM chunk.

Sets the board RTC, tests invalid input and leap-day rollover, then leaves it
at the host's current UTC. Optional COM port reset tests powered retention.
Does not change the computer clock, Wi-Fi settings or credentials.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
from test_wireless_vm import VM, primitive


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--private',type=Path,required=True)
    parser.add_argument('--evidence',type=Path,required=True)
    parser.add_argument('--reboot-port')
    parser.add_argument('--firmware-sha256')
    args=parser.parse_args()
    private=json.loads(args.private.read_text())
    vm=None;owned=False;original={}
    report={'scope':'Real PCF85063A through the VM UTC setter; no battery/power-removal claim',
        'started_utc':datetime.now(timezone.utc).isoformat(),'checks':{},'result':'FAIL',
        'firmware_sha256':args.firmware_sha256}
    chunk=250
    def crcs():
        index=len(vm.events);vm.short(38,1)
        data=vm.wait(lambda e:e[0]==39,seconds=8,after=index)[2]
        return {data[i]:int.from_bytes(data[i+1:i+5],'little') for i in range(0,len(data),5)}
    def run(name,arguments=(),error=None):
        vm.upload(chunk,primitive(name,arguments),kind=2)
        if error is None:return vm.run_reporter(chunk)
        index=len(vm.events);vm.short(3,chunk)
        event=vm.wait(lambda e:e[0] in (18,19) and e[1]==chunk,after=index)
        assert event[0]==19 and event[2][0]==error, (name,arguments,event)
        return {'error_code':event[2][0]}
    def clock():
        text=run('rtcText')
        return datetime.strptime(text,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
    def set_current():
        now=datetime.now(timezone.utc)
        assert run('rtcSetUTC',[now.year,now.month,now.day,now.hour,now.minute,now.second]) is False
        actual=clock();offset=abs((actual-datetime.now(timezone.utc)).total_seconds())
        assert offset<2, 'RTC differs from host UTC by 2s or more'
        return {'readback_utc':actual.isoformat(),'absolute_host_offset_seconds':round(offset,3)}
    try:
        deadline=time.monotonic()+45
        while True:
            try:vm=VM(args.host,private['pair']);break
            except (OSError,TimeoutError):
                if time.monotonic()>deadline:raise
                time.sleep(1)
        original=crcs()
        assert chunk not in original, 'RTC test chunk is occupied'
        owned=True
        report['checks']['initial_rtc_text']=run('rtcText')
        valid=[2000,2,29,12,34,56]
        assert run('rtcSetUTC',valid) is False
        assert abs((clock()-datetime(2000,2,29,12,34,56,tzinfo=timezone.utc)).total_seconds())<=1
        report['checks']['year2000_leap_day']=True
        invalid=[([1999,1,1,0,0,0],18),([2100,1,1,0,0,0],18),
            ([2026,0,1,0,0,0],18),([2026,13,1,0,0,0],18),([2026,2,29,0,0,0],18),
            ([2026,4,31,0,0,0],18),([2026,1,0,0,0,0],18),([2026,1,32,0,0,0],18),
            ([2026,1,1,24,0,0],18),([2026,1,1,-1,0,0],18),([2026,1,1,0,60,0],18),
            ([2026,1,1,0,0,60],18),([False,1,1,0,0,0],13),([2026,1,1,0,0],28),
            ([2026,1,1,0,0,0,0],28)]
        rejected=[]
        before=clock();invalid_start=time.monotonic()
        for fields,error in invalid:
            run('rtcSetUTC',fields,error=error)
            rejected.append({'fields':fields,'error_code':error})
        after=clock()
        assert abs((after-before).total_seconds()-(time.monotonic()-invalid_start))<2
        report['checks']['invalid_inputs_rejected_without_clock_jump']=rejected
        assert run('rtcSetUTC',[2024,2,29,23,59,58]) is False
        rollover_start=time.monotonic();time.sleep(3.2)
        rolled=clock()
        expected=datetime(2024,2,29,23,59,58,tzinfo=timezone.utc)
        assert rolled.date().isoformat()=='2024-03-01'
        assert abs((rolled-expected).total_seconds()-(time.monotonic()-rollover_start))<2
        report['checks']['leap_day_rollover_utc']=rolled.isoformat()
        assert run('rtcSetUTC',[2099,12,31,12,0,0]) is False
        assert clock().year==2099
        report['checks']['year2099_readback']=True
        report['checks']['host_utc_set_and_readback']=set_current()
        first=clock();tick_start=time.monotonic();time.sleep(3.2);second=clock()
        delta=(second-first).total_seconds()
        assert 2<=delta<=5 and abs(delta-(time.monotonic()-tick_start))<2
        report['checks']['ticking_seconds']=delta
        if args.reboot_port:
            vm.short(2,chunk);index=len(vm.events);vm.short(26,98)
            vm.wait(lambda e:e[:2]==(26,98),after=index)
            assert crcs()==original
            time.sleep(4)
            vm.close();vm=None
            import serial
            from esptool.reset import HardReset
            port=serial.Serial(port=None,baudrate=115200,timeout=.1)
            port.dtr=False;port.rts=False;port.port=args.reboot_port;port.open()
            try:HardReset(port,uses_usb=True).reset()
            finally:port.close()
            deadline=time.monotonic()+45
            while True:
                try:vm=VM(args.host,private['pair']);break
                except Exception:
                    if time.monotonic()>deadline:raise
                    time.sleep(1)
            retained=clock()
            offset=abs((retained-datetime.now(timezone.utc)).total_seconds())
            assert offset<3
            report['checks']['powered_com_reset_retention']={'rtc_utc':retained.isoformat(),'host_offset_seconds':round(offset,3)}
        report['result']='PASS'
    except Exception as exc:
        report.update(result='FAIL',error=type(exc).__name__+': '+str(exc))
    finally:
        if owned:
            try:
                if vm is None:vm=VM(args.host,private['pair'])
                report['final_host_utc_restore']=set_current()
                index=len(vm.events);vm.short(2,chunk);vm.short(26,99)
                vm.wait(lambda e:e[:2]==(26,99),after=index)
                assert crcs()==original
                report['original_program_crc32_unchanged']={str(k):f'{v:08x}' for k,v in original.items()}
                time.sleep(4)
            except Exception as exc:report.update(result='FAIL',cleanup_error=type(exc).__name__+': '+str(exc))
        if vm:vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2))
    if report['result']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
