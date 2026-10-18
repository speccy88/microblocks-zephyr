#!/usr/bin/env python3
"""Repeatable physical HTTP/VM soak; preserves all original program chunks.

Requires websocket-client 1.9.0. Disconnect the graphical VM controller first.
Keep --checkpoint outside Git: it contains the board's existing bytecode.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import gzip
import hashlib
import json
from pathlib import Path
import time
import traceback
import urllib.parse
import urllib.request

from test_wireless_vm import VM, op, primitive, words

REPORTER = 252
STREAM = 253
FIRST_VAR = 124
SECOND_VAR = 125


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--host', required=True)
    parser.add_argument('--manifest', type=Path, required=True)
    parser.add_argument('--evidence', type=Path, required=True)
    parser.add_argument('--checkpoint', type=Path, required=True)
    parser.add_argument('--minutes', type=float, default=1)
    parser.add_argument('--interval', type=float, default=30)
    parser.add_argument('--full-audit-every', type=int, default=10)
    parser.add_argument('--outputs',type=int,default=50)
    parser.add_argument('--minimum-cycles',type=int,default=1)
    parser.add_argument('--minimum-full-audits',type=int,default=1)
    parser.add_argument('--rtc-reports',type=int,default=1)
    parser.add_argument('--arithmetic-runs',type=int,default=1)
    parser.add_argument('--stop-file',type=Path,help='Presence requests an orderly stop/cleanup')
    parser.add_argument('--firmware-sha256',help='Hash of the app-only image verified at flash time')
    parser.add_argument('--require-rtc-utc',action='store_true',help='Require RTC text to remain within5 seconds of host UTC')
    args = parser.parse_args()
    if args.minutes <= 0 or args.interval <= 0 or args.full_audit_every < 1:
        parser.error('Duration, interval and audit frequency must be positive')
    if not 1<=args.outputs<=500 or min(args.minimum_cycles,args.minimum_full_audits,args.rtc_reports,args.arithmetic_runs)<1:
        parser.error('Use1..500 outputs and positive check counts')
    assets = json.loads(args.manifest.read_text())['assets']
    report = {'result':'RUNNING','started_utc':datetime.now(timezone.utc).isoformat(),
        'host':args.host,'duration_target_seconds':args.minutes*60,'interval_seconds':args.interval,
        'scope':'Physical unchanged firmware; HTTP content and binary VM workload. Browser fresh loads are recorded separately.',
        'cycles':[], 'memory':[], 'asset_audits':[], 'original_program_crc32':{},
        'criteria':{'minimum_cycles':args.minimum_cycles,'minimum_full_asset_audits':args.minimum_full_audits,'outputs_per_cycle':args.outputs,
            'no_reboot':True,'minimum_allocator_free_bytes':2048,'maximum_settled_residual_bytes':1024}}
    report['firmware_sha256']=args.firmware_sha256
    report['asset_manifest_sha256']=hashlib.sha256(args.manifest.read_bytes()).hexdigest()
    report['require_rtc_utc']=args.require_rtc_utc
    vm = None
    original = None
    owned = False
    start = time.monotonic()
    stop_file=args.stop_file or args.evidence.with_suffix('.stop')
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def save():
        args.evidence.parent.mkdir(parents=True,exist_ok=True)
        args.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')

    def http_json(path):
        with opener.open('http://'+args.host+path,timeout=60) as response:
            return json.load(response)

    def sample(phase):
        probe_started=time.monotonic()
        # The pinned single HTTP service may finish a large flash asset before
        # dispatching this API request. Keep the independent VM heartbeat alive.
        with ThreadPoolExecutor(max_workers=1) as probes:
            pending=probes.submit(http_json,'/api/memory')
            while not pending.done():
                if vm:vm.pump()
                else:time.sleep(.02)
            value=pending.result()
        value['http_response_seconds']=round(time.monotonic()-probe_started,3)
        value.update(elapsed_seconds=round(time.monotonic()-start,3),phase=phase,
            utc=datetime.now(timezone.utc).isoformat())
        previous = report['memory'][-1] if report['memory'] else None
        if previous:
            delta=(value['uptime_ms']-previous['uptime_ms']) & 0xffffffff
            assert delta < 120000, 'Board uptime reset or stalled probe interval'
        for pool in ['libc_malloc','kernel_heap']:
            assert value[pool]['result']==0
            assert value[pool]['free_bytes']>=2048, 'Allocator floor breached: '+pool
        report['memory'].append(value)
        return value

    def all_crcs():
        index=len(vm.events);vm.short(38,1)
        body=vm.wait(lambda e:e[0]==39,seconds=8,after=index)[2]
        assert len(body)%5==0
        return {body[i]:int.from_bytes(body[i+1:i+5],'little') for i in range(0,len(body),5)}

    def check_original():
        current=all_crcs()
        assert all(current.get(k)==v for k,v in original.items()), 'Original program changed'
        assert set(current)<=set(original)|{REPORTER,STREAM}, 'Unexpected external program change'

    def audit_asset(asset):
        own_opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
        url='http://'+args.host+urllib.parse.quote(asset['path'],safe='/')
        with own_opener.open(url,timeout=60) as response:
            encoded=response.read()
            assert response.headers.get('Content-Encoding','')==asset['encoding']
            assert response.headers.get_content_type()==asset['content_type']
            assert "connect-src 'self' ws://"+args.host in response.headers.get('Content-Security-Policy','')
            assert response.headers.get('Cross-Origin-Opener-Policy')=='same-origin'
            raw=gzip.decompress(encoded) if asset['encoding']=='gzip' else encoded
            assert hashlib.sha256(raw).hexdigest()==asset['sha256'], asset['path']
        return len(raw)

    try:
        report['initial_status']=http_json('/api/status')
        baseline=sample('initial-settled')
        vm=VM(args.host)
        original=all_crcs()
        assert REPORTER not in original and STREAM not in original, 'Test chunk IDs are occupied'
        # Read all code and variable names without deleting/resetting anything.
        index=len(vm.events);vm.short(13,1);vm.short(9,0);vm.short(26,96)
        vm.wait(lambda e:e[:2]==(26,96),seconds=10,after=index)
        checkpoint=[{'type':k,'id':i,'body_hex':b.hex()} for k,i,b in vm.events[index:] if k in (32,29)]
        assert {e['id'] for e in checkpoint if e['type']==32}==set(original)
        assert all(e['id'] not in (FIRST_VAR,SECOND_VAR) for e in checkpoint if e['type']==29), 'Test variable IDs are named'
        args.checkpoint.parent.mkdir(parents=True,exist_ok=True)
        args.checkpoint.write_text(json.dumps({'crc32':{str(k):f'{v:08x}' for k,v in original.items()},'records':checkpoint},indent=2)+'\n',encoding='utf-8')
        report['original_program_crc32']={str(k):f'{v:08x}' for k,v in original.items()}
        reporter=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
        tagged_count=2*args.outputs-1
        stream=words([op(2,1),op(7,FIRST_VAR),op(3,tagged_count&255),(tagged_count>>8)&65535,op(7,SECOND_VAR),op(6,SECOND_VAR),
            op(2,3),op(8,FIRST_VAR),op(6,FIRST_VAR),op(78,1),op(26,-5),0])
        owned=True
        vm.upload(STREAM,stream)
        cycle=0
        with ThreadPoolExecutor(max_workers=4) as pool:
            while time.monotonic()-start<args.minutes*60:
                if stop_file.exists():raise RuntimeError('Stopped by coordinator; evidence retained and owned chunks cleaned')
                cycle_start=time.monotonic()
                full=(cycle%args.full_audit_every)==0
                subset=assets if full else [a for a in assets if a['path'] in ['/emModule.js','/menus.js','/unoq-network.js','/gettext.js']]
                report['phase']='full-asset-audit' if full else 'workload'
                save()
                futures=[pool.submit(audit_asset,a) for a in subset]
                vm.upload(REPORTER,primitive('rtcText'),kind=2)
                rtc_offsets=[]
                for _ in range(args.rtc_reports):
                    text=vm.run_reporter(REPORTER)
                    assert isinstance(text,str) and text, 'RTC string reporter failed'
                    if args.require_rtc_utc:
                        clock=datetime.strptime(text,'%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
                        offset=abs((clock-datetime.now(timezone.utc)).total_seconds())
                        assert offset<5, 'RTC differs from host UTC by5 seconds or more'
                        rtc_offsets.append(offset)
                vm.upload(REPORTER,reporter,kind=2)
                assert [vm.run_reporter(REPORTER) for _ in range(args.arithmetic_runs)]==[12]*args.arithmetic_runs
                edited=bytearray(reporter);edited[5]=17
                vm.upload(REPORTER,edited,kind=2)
                assert vm.run_reporter(REPORTER)==13
                index=len(vm.events);vm.short(3,STREAM)
                vm.wait(lambda e:e[:2]==(17,STREAM),seconds=25,after=index)
                values=[int(e[2][1:]) for e in vm.events[index:] if e[:2]==(20,254)]
                assert values==list(range(1,args.outputs+1)), 'Numeric output order/count differs'
                report['phase']='active-memory-probe'
                save()
                sample('active-cycle-'+str(cycle+1))
                while not all(f.done() for f in futures):
                    vm.pump()
                total=sum(f.result() for f in futures)
                if full:report['asset_audits'].append({'cycle':cycle+1,'assets':len(subset),'uncompressed_bytes':total,'result':'PASS'})
                check_original()
                vm.close();vm=None
                time.sleep(.2)
                reconnect_start=time.monotonic()
                vm=VM(args.host)
                assert vm.run_reporter(REPORTER)==13
                reconnect=time.monotonic()-reconnect_start
                assert reconnect<5, 'Reconnect exceeded 5 seconds'
                cycle+=1
                report['cycles'].append({'cycle':cycle,'elapsed_seconds':round(time.monotonic()-start,3),
                    'rtc_string_reports':args.rtc_reports,'arithmetic_runs':args.arithmetic_runs,'edit_result':13,'ordered_outputs':len(values),
                    'maximum_rtc_host_offset_seconds':round(max(rtc_offsets),3) if rtc_offsets else None,
                    'reconnect_seconds':round(reconnect,3),'original_crcs_unchanged':True,
                    'seconds':round(time.monotonic()-cycle_start,3)})
                report['phase']='interval'
                save()
                print(json.dumps(report['cycles'][-1]),flush=True)
                while time.monotonic()-cycle_start<args.interval and time.monotonic()-start<args.minutes*60:
                    vm.pump()
        assert cycle>=args.minimum_cycles, 'Minimum complete cycle count not met'
        assert len(report['asset_audits'])>=args.minimum_full_audits, 'Minimum full asset audit count not met'
        report['result']='PASS'
    except Exception as exc:
        report.update(result='FAIL',error=type(exc).__name__+': '+str(exc),
            failed_phase=report.get('phase'),traceback=traceback.format_exc())
    finally:
        report['workload_seconds']=round(time.monotonic()-start,3)
        try:
            if owned:
                cleanup_error=None
                for attempt in range(3):
                    try:
                        if vm is None:vm=VM(args.host)
                        index=len(vm.events)
                        vm.short(4,STREAM);vm.short(2,REPORTER);vm.short(2,STREAM);vm.short(26,95)
                        vm.wait(lambda e:e[:2]==(26,95),seconds=5,after=index)
                        assert all_crcs()==original, 'Original chunk set differs after cleanup'
                        report['original_program_restored']=True
                        cleanup_error=None
                        break
                    except Exception as exc:
                        cleanup_error=exc
                        if vm:
                            try:vm.close()
                            except Exception:pass
                            vm=None
                        time.sleep(.5)
                if cleanup_error:raise cleanup_error
            if vm:vm.close();vm=None
            time.sleep(3)
            final=sample('final-settled')
            residual={p:baseline[p]['free_bytes']-final[p]['free_bytes'] for p in ['libc_malloc','kernel_heap']}
            report['settled_free_space_loss_bytes']=residual
            assert all(v<=1024 for v in residual.values()), 'Settled heap residual exceeds 1KiB'
            report['final_status']=http_json('/api/status')
            if 'websocket' in report['initial_status'] and 'websocket' in report['final_status']:
                first=report['initial_status']['websocket'];last=report['final_status']['websocket']
                delta={k:last[k]-first[k] for k in ['sessions','rx_errors','tx_errors','queue_timeouts']}
                report['websocket_diagnostic_delta']=delta
                assert not any(delta[k] for k in ['rx_errors','tx_errors','queue_timeouts']), 'WebSocket error counter increased'
            if 'assets' in report['initial_status'] and 'assets' in report['final_status']:
                first=report['initial_status']['assets'];last=report['final_status']['assets']
                report['asset_diagnostic_delta']={k:last[k]-first[k] for k in ['completed','aborted']}
                assert report['asset_diagnostic_delta']['aborted']==0, 'HTTP asset transfer was aborted'
            report['minimum_free_bytes']={p:min(s[p]['free_bytes'] for s in report['memory']) for p in ['libc_malloc','kernel_heap']}
        except Exception as exc:
            report.update(result='FAIL',cleanup_or_final_error=type(exc).__name__+': '+str(exc))
        if vm:vm.close()
        report['finished_utc']=datetime.now(timezone.utc).isoformat()
        report['phase']='finished'
        save()
        print(json.dumps({k:v for k,v in report.items() if k not in ['cycles','memory']},indent=2),flush=True)
    if report['result']!='PASS':raise SystemExit(1)


if __name__=='__main__':main()
