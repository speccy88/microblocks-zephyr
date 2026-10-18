#!/usr/bin/env python3
"""Bounded physical ES8311/I2S validation; two quiet 200ms notes, no hearing claim.

One initially vacant chunk is owned and removed; original CRCs stay unchanged.
Explicit and global Stop are tested with volume zero. Disconnect the GUI first.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time
import urllib.request
from test_wireless_vm import VM, primitive

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host',required=True)
    parser.add_argument('--evidence',required=True,type=Path)
    parser.add_argument('--firmware-sha256',required=True)
    parser.add_argument('--silent',action='store_true',help='Validate DMA with zero PCM volume before coordinating an audible check')
    args=parser.parse_args()
    report=dict(result='FAIL',started_utc=datetime.now(timezone.utc).isoformat(),
        firmware_sha256=args.firmware_sha256,
        scope='Physical codec I2C readback and I2S DMA software evidence; audible output and waveform capture unverified',
        checks={})
    vm=None;owned=False;chunk=250;original={}
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
        return {'arguments':arguments,'error_code':error}
    def status():return json.loads(run('audioStatus'))
    def wait_idle():
        deadline=time.monotonic()+2
        while run('audioBusy'):
            assert time.monotonic()<deadline,'Audio did not become idle'
        value=status()
        assert value['busy']==0 and value['amp']==0 and value['mute']&0x60==0x60,value
        assert value['error']==0 and value['free_blocks']==4,value
        return value
    def memory():
        opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        with opener.open('http://'+args.host+'/api/memory',timeout=8) as response:return json.load(response)
    try:
        vm=VM(args.host);original=crcs()
        assert chunk not in original,'Audio test chunk occupied'
        owned=True
        report['original_crc32']={str(k):f'{v:08x}' for k,v in original.items()}
        initial=status();assert initial['id']=='8311'
        report['checks']['initial_status']=initial
        before=memory();report['checks']['memory_before']=before
        invalid=[([49,200,10],18),([4001,200,10],18),([440,0,10],18),
                 ([440,5001,10],18),([440,200,-1],18),([440,200,101],18),
                 ([False,200,10],13),([440,200],28)]
        report['checks']['invalid_inputs']=[run('audioTone',fields,error) for fields,error in invalid]
        assert status()['starts']==initial['starts'],'Invalid input started hardware'
        notes=[]
        volume=0 if args.silent else 10
        for hz in [440,660]:
            assert run('audioTone',[hz,200,volume]) is False
            # An unrelated hardware reporter must execute while DMA is active.
            rtc=run('rtcText');assert rtc.startswith('20'),rtc
            final=wait_idle()
            assert final['format']==12 and final['clock']==63 and final['dac_osr']==16 and final['gain']==191,final
            assert final['queued_frames']==4800 and final['completed_frames']==4800 and final['blocks']==19,final
            assert 150<=final['elapsed_ms']<=500,final
            notes.append(dict(frequency_hz=hz,duration_ms=200,volume=volume,status=final,concurrent_rtc=rtc))
        report['checks']['quiet_notes']=notes
        for stop in ['explicit','global']:
            assert run('audioTone',[440,1000,0]) is False
            active=status();assert active['busy']==1,active
            run('audioTone',[660,100,0],error=27)
            began=time.monotonic()
            if stop=='explicit':assert run('audioStop') is False
            else:vm.short(6,0)
            final=wait_idle()
            assert final['completed_frames']==0,final
            report['checks'][stop+'_stop']=dict(status=final,host_stop_seconds=round(time.monotonic()-began,3))
        report['checks']['temperature_milli_c']=run('temperatureMilliC')
        after=memory();report['checks']['memory_after']=after
        report['checks']['settled_allocator_loss_bytes']={pool:before[pool]['free_bytes']-after[pool]['free_bytes'] for pool in ['libc_malloc','kernel_heap']}
        assert after['uptime_ms']>before['uptime_ms'],'Board reset during audio'
        assert all(value<=1024 for value in report['checks']['settled_allocator_loss_bytes'].values())
        report['result']='PASS'
    except Exception as exc:
        report['error']=type(exc).__name__+': '+str(exc)
    finally:
        if vm and owned:
            try:
                run('audioStop')
                index=len(vm.events);vm.short(2,chunk);vm.short(26,99)
                vm.wait(lambda e:e[:2]==(26,99),after=index)
                assert crcs()==original
                report['original_program_preserved']=True
            except Exception as exc:
                report['result']='FAIL';report['cleanup_error']=type(exc).__name__+': '+str(exc)
        if vm:vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(report,indent=2))
    return 0 if report['result']=='PASS' else 1

if __name__=='__main__':raise SystemExit(main())
