#!/usr/bin/env python3
"""Physical P2 worker objects/GC and main-cog pin-service acceptance.

Replaces the disposable test project. P0 drives only its wired high-impedance
P1 receiver. Stop/reset/edit checks release main-owned pin state.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import struct
import time
from pathlib import Path
from p2_serial import P2SerialVM, primitive

TEXT='worker retained λ'


def test(args):
    report=dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        scope='physical worker heap references, main-cog object services and routed pin ownership',
        result='FAIL',checks={})
    compiled=json.loads(args.program.read_text(encoding='utf-8'))
    variables=compiled['variables'];scripts=compiled['scripts']
    functions={c['name']:c['id'] for c in compiled['chunks'] if c['name']}
    vm=None
    try:
        vm=P2SerialVM(args.port,args.usb_serial,'edge32')
        report.update(identity=vm.identity,version=vm.version)
        def wait(predicate,after=None,seconds=10):
            first=len(vm.events) if after is None else after;deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                for e in vm.events[first:]:
                    if predicate(e):return e
                vm.pump()
            raise TimeoutError('Missing object-service response')
        vm.wait=wait
        def ping():
            first=len(vm.events);vm.short(26,97);wait(lambda e:e[:2]==(26,97),first)
        def run(index):
            first=len(vm.events);vm.short(3,index)
            body=wait(lambda e:e[:2]==(18,index),first)[2]
            if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
            if body[0]==2:return body[1:].decode('utf-8')
            if body[0]==3:return bool(body[1])
            return body
        def value(name):
            index=variables[name];first=len(vm.events);vm.short(7,index)
            body=wait(lambda e:e[:2]==(21,index),first)[2]
            if body[0]==1:return int.from_bytes(body[1:5],'little',signed=True)
            if body[0]==2:return body[1:].decode('utf-8')
            if body[0]==3:return bool(body[1])
            return body
        def set_value(name,value):
            if isinstance(value,bool):body=bytes([3,value])
            elif isinstance(value,int):body=b'\x01'+struct.pack('<i',value)
            else:body=b'\x02'+value.encode('utf-8')
            raw=body+b'\xfe';vm.send(bytes([251,8,variables[name]])+len(raw).to_bytes(2,'little')+raw)
        def start(index):
            first=len(vm.events);vm.short(3,index)
            wait(lambda e:e[:2] in ((17,index),(18,index)),first,30)
        def until(predicate,seconds=30,reject_errors=False):
            deadline=time.monotonic()+seconds
            while time.monotonic()<deadline:
                if predicate():return
                if reject_errors:
                    errors=[(e[1],e[2].hex()) for e in vm.events if e[0]==19]
                    if errors:raise RuntimeError('Unexpected worker/main errors: '+str(errors))
                vm.pump()
            raise TimeoutError('Worker object phase did not finish')
        vm.short(14,1);vm.short(10,1);vm.short(15);ping()
        for name,index in variables.items():
            raw=name.encode()+b'\xfe';vm.send(bytes([251,29,index])+len(raw).to_bytes(2,'little')+raw)
        ping()
        for c in compiled['chunks']:
            raw=bytes(c['bytes']);vm.upload(c['id'],raw+b'\0'*(-len(raw)%4),c['kind'])
        queries={200:('p2RuntimeRevision',()),201:('p2CogStart',('workerForeach',2)),
            202:('p2CogRunning',(2,)),203:('p2CogRunning',(3,)),204:('p2CogStackOK',(2,)),
            205:('p2CogStackOK',(3,)),206:('p2CogError',(2,)),207:('p2CogError',(3,)),
            208:('p2CogStart',('workerPinService',2)),209:('p2LocalPinDIR',(0,)),
            210:('p2PinModeHex',(0,)),211:('p2Configure',(1,'count rises','Schmitt','0','0',False,0)),
            212:('p2PinReadHex',(1,)),213:('p2CogStart',('workerPending',2)),
            214:('p2CogStart',('workerPending',3)),215:('p2CogStart',('workerOOM',2)),
            216:('p2CogStart',('workerBadByte',2)),217:('p2CogStop',(2,)),
            218:('p2CogStackUsed',(2,)),219:('p2CogStackUsed',(3,)),
            221:('p2CogStart',('workerTiming',2)),222:('p2CogStart',('workerReturnHeap',2))}
        for i,(name,params) in queries.items():vm.upload(i,primitive(name,params),2)
        revision=run(200); assert revision>=3
        report['checks']['extension_revision']=revision
        start(scripts[0]);set_value('SharedText',TEXT);ping();start(scripts[1])
        assert value('StartedA') is True and value('StartedB') is True
        until(lambda:value('CapturedA')==1 and value('CapturedB')==1)
        assert value('CogA')==2 and value('CogB')==3
        # These objects now survive through worker locals, not their source globals.
        set_value('SharedText',0);set_value('SharedBytes',0);set_value('Gate',True);ping()
        phase=len(vm.events);vm.short(3,functions['mainObjectPressure'])
        until(lambda:value('DoneA')==1 and value('DoneB')==1 and value('DoneMain')==1,60,True)
        ping()
        assert value('Errors')==0
        assert value('CountA')==1000 and value('CountB')==1000
        assert run(scripts[2])==3000
        assert run(scripts[3])==1002
        assert run(scripts[4])==255 and run(scripts[5])==128
        assert value('TextA')==TEXT and value('TextB')==TEXT
        gc_events=[e for e in vm.events[phase:] if b'GC took' in e[2]]
        assert len(gc_events)>=5,len(gc_events)
        first=wait(lambda e:e[:2]==(18,functions['objectWorkerA']),phase)[2]
        second=wait(lambda e:e[:2]==(18,functions['objectWorkerB']),phase)[2]
        assert first[0]==4 and TEXT.encode() in first
        assert second==b'\x02'+TEXT.encode()
        report['checks']['worker_objects_survive_gc_and_resize']=dict(cogs=[2,3],iterations=[1000,1000],
            atomic_list_total=3000,final_list_length=1002,gc_events=len(gc_events),retained_text=TEXT,
            byte_values=[255,128],deferred_returns=['list','string'],errors=0)
        print('Worker object roots, resizing and atomic list total PASS',flush=True)
        assert run(201) is True
        until(lambda:run(202) is False)
        assert run(206)==0
        assert [run(scripts[i]) for i in [2,6,7]]==[15,3,1360]
        report['checks']['foreach_list_unicode_and_bytearray']=[15,3,1360]
        print('Worker foreach and Unicode character allocation PASS',flush=True)
        assert run(221) is True
        until(lambda:run(202) is False)
        timer_ms=value('TimerElapsed');clock_ms=value('ClockElapsed')
        assert 25<=timer_ms<1000 and 0<=clock_ms-timer_ms<=10,(timer_ms,clock_ms)
        report['checks']['worker_wait_timer_and_millis_since']=dict(timer_ms=timer_ms,millis_since=clock_ms)

        for index,error in [(215,10),(216,19)]:
            assert run(index) is True;until(lambda:run(202) is False)
            assert run(206)==error,(index,run(206))
            ping()
        # A valid allocation/foreach after OOM proves the main allocator root was unwound.
        assert run(201) is True;until(lambda:run(202) is False);assert run(206)==0
        report['checks']['isolated_oom_and_invalid_byte_errors']=dict(errors=[10,19],recovery=True)

        vm.short(15);ping()
        assert run(211) is True and run(208) is True
        until(lambda:value('PulseProgress')>3)
        assert value('CogA')==2 and value('WorkerDIR') is False
        assert run(209) is True
        count=int(run(212),16);time.sleep(.05);new_count=int(run(212),16)
        assert new_count>count,(count,new_count)
        vm.short(6);ping()
        assert run(202) is False and run(209) is False and run(210)=='00000000'
        report['checks']['worker_pin_requests_keep_main_dir_ownership']=dict(worker_cog=2,
            worker_dir=False,main_dir_while_running=True,count_before=count,count_after=new_count,
            stop_all_releases_main_dir=True)
        print('Worker pin service ownership and stop-all PASS',flush=True)

        assert run(213) is True and run(214) is True
        vm.short(6);ping();assert run(202) is False and run(203) is False
        assert run(213) is True and run(214) is True
        vm.upload(220,primitive('p2RuntimeRevision'),2)
        assert run(202) is False and run(203) is False
        assert run(213) is True and run(214) is True
        vm.short(15);ping();assert run(202) is False and run(203) is False
        report['checks']['pending_request_stop_edit_reset']=True
        for _ in range(10):
            assert run(222) is True
            vm.short(15);ping()
            boundary=len(vm.events)
            assert run(202) is False
            start(scripts[0]);assert run(scripts[3])==2
            assert not any(e[:2]==(18,functions['workerReturnHeap']) for e in vm.events[boundary:])
        report['checks']['rapid_object_return_reset_cycles']=10
        assert run(204) is True and run(205) is True
        report['checks']['native_stack_guards']=dict(intact=True,cog2_bytes=run(218),cog3_bytes=run(219),capacity_bytes=8192)
        report['result']='PASS'
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        if vm:
            report['error_events']=[dict(index=i,body=b.hex()) for k,i,b in vm.events if k==19]
            report['last_events']=[dict(kind=k,index=i,body=b.hex()) for k,i,b in vm.events[-20:]]
        raise
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
