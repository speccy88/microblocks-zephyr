#!/usr/bin/env python3
"""Physical scalar cog acceptance; replaces the P2 test project, never firmware.

Compile tests/fixtures/propeller2/cogs-scalars.ubp with the pinned JS compiler
first. The exact FTDI serial and module are mandatory. No GPIO action is used.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import datetime
import json
import time
from pathlib import Path
from p2_serial import P2SerialVM, primitive


def test(port, usb_serial, board, program, evidence):
    report = dict(tested_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                  scope='physical scalar workers and shared HUB variables; no GPIO or firmware loading',
                  checks={}, result='FAIL')
    compiled = json.loads(program.read_text(encoding='utf-8'))
    functions = {c['name']: c['id'] for c in compiled['chunks'] if c['name']}
    variables = compiled['variables']
    scripts = compiled['scripts']
    vm = None
    try:
        vm = P2SerialVM(port, usb_serial, board)
        report.update(identity=vm.identity, version=vm.version)

        def wait(predicate, seconds=5, after=None):
            first = len(vm.events) if after is None else after
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                for event in vm.events[first:]:
                    if predicate(event): return event
                vm.pump()
            raise TimeoutError('Expected cog test response was not received')
        vm.wait = wait  # worker rejection errors are inspected explicitly below

        def ping():
            start = len(vm.events); vm.short(26, 97)
            wait(lambda e:e[:2] == (26, 97), after=start)

        def value(name):
            index = variables[name]; start = len(vm.events); vm.short(7, index)
            body = wait(lambda e:e[:2] == (21, index), after=start)[2]
            if body[0] == 1: return int.from_bytes(body[1:5], 'little', signed=True)
            if body[0] == 3: return bool(body[1])
            raise RuntimeError('Expected scalar value: '+name)

        def start_script(index):
            first = len(vm.events); vm.short(3, index)
            wait(lambda e:e[:2] in ((17, index),(18, index)), seconds=20, after=first)

        def run(index):
            first = len(vm.events); vm.short(3, index)
            body = wait(lambda e:e[:2] == (18, index), after=first)[2]
            if body[0] == 1: return int.from_bytes(body[1:5], 'little', signed=True)
            if body[0] == 3: return bool(body[1])
            return body[1:].decode()

        vm.short(14, 1); vm.short(10, 1); vm.short(15); ping()
        for name, index in variables.items():
            raw = name.encode(); size = len(raw)+1
            vm.send(bytes([251,29,index,size & 255,size >> 8])+raw+b'\xfe')
        ping()
        for chunk in compiled['chunks']:
            raw = bytes(chunk['bytes']); raw += b'\0'*(-len(raw)%4)
            vm.upload(chunk['id'], raw, chunk['kind'])
        queries = {
            120:('p2RuntimeRevision',()), 121:('p2CogRunning',(2,)), 122:('p2CogRunning',(3,)),
            123:('p2CogError',(2,)), 124:('p2CogError',(3,)),
            125:('p2CogStackOK',(2,)), 126:('p2CogStackOK',(3,)),
            127:('p2CogStackUsed',(2,)), 128:('p2CogStackUsed',(3,)),
            129:('p2CogStart',('workerForbidden',2)), 130:('p2CogStop',(2,)),
            131:('p2CogStop',(3,)), 132:('p2CogStart',('workerExactA',0)),
            133:('p2CogStart',('workerExactA',1)), 134:('p2CogStart',('missingFunction',4)),
            135:('p2SharedRead',('Total',)),
            136:('p2CogStart',('workerContinuousA',2)),
        }
        for index,(name,args) in queries.items(): vm.upload(index, primitive(name,args),2)
        revision = run(120)
        assert revision >= 1
        report['checks']['extension_revision'] = revision
        assert run(132) is False and run(133) is False and run(134) is False
        report['checks']['main_rx_cogs_and_unknown_function_rejected'] = True

        start_script(scripts[0])
        assert value('StartedA') is True and value('StartedB') is True
        assert value('CoreA') == 2 and value('CoreB') == 3
        before = [value('ProgressA'),value('ProgressB')]
        time.sleep(.15); ping(); start_script(scripts[2])
        after = [value('ProgressA'),value('ProgressB')]
        assert all(b>a for a,b in zip(before,after)), (before,after)
        assert value('MainTick') == 1 and run(121) is True and run(122) is True
        assert run(136) is False
        report['checks']['distinct_physical_cogs_and_concurrent_progress'] = dict(cogs=[2,3],before=before,after=after,main_tick=1)
        print('Distinct cogs and concurrent progress PASS',flush=True)

        gc_start = len(vm.events)
        start_script(functions['mainGC'])
        ping()
        gc_events = [e for e in vm.events[gc_start:] if b'GC took' in e[2]]
        assert gc_events, 'GC was not observed'
        assert run(scripts[3]) == 32 and run(scripts[4]) == 42
        after_gc = [value('ProgressA'),value('ProgressB')]
        assert all(b>a for a,b in zip(after,after_gc))
        report['checks']['main_list_gc_with_live_scalar_workers'] = dict(gc_events=len(gc_events),list_length=32,first_item=42,progress=after_gc)

        previous = after_gc
        vm.close(); vm = None
        vm = P2SerialVM(port, usb_serial, board); vm.wait = wait
        resumed = [value('ProgressA'),value('ProgressB')]
        assert all(b>a for a,b in zip(previous,resumed))
        report['checks']['serial_reconnect_preserves_running_workers'] = True

        assert run(130) is True
        stopped_a = value('ProgressA'); b_first = value('ProgressB')
        time.sleep(.1)
        assert value('ProgressA') == stopped_a and value('ProgressB') > b_first
        assert run(131) is True
        report['checks']['independent_stop'] = True

        vm.short(15); ping()
        start_script(scripts[1])
        vm.short(3,scripts[5])
        deadline = time.monotonic()+30
        while time.monotonic()<deadline:
            if value('DoneA') == 1 and value('DoneB') == 1 and value('DoneMain') == 1: break
            time.sleep(.02)
        assert value('Total') == 15000, value('Total')
        assert run(135) == 15000
        assert value('CoreA') == 2 and value('CoreB') == 3
        report['checks']['exact_atomic_shared_increments'] = dict(cogs=[0,2,3],iterations_per_cog=5000,total=15000,methods=['standard change-variable opcode','named P2 atomic add'])
        print('Exact shared increments PASS: 15000',flush=True)

        assert run(125) is True and run(126) is True
        report['checks']['native_stack_guards_and_usage'] = dict(guards_intact=True,cog2_bytes=run(127),cog3_bytes=run(128),capacity_bytes=8192)
        negative_start = len(vm.events)
        assert run(129) is True
        deadline=time.monotonic()+2
        while time.monotonic()<deadline: vm.pump()
        assert run(123) == 27
        errors=[(e[1],e[2].hex()) for e in vm.events[negative_start:] if e[0]==19]
        assert any(index==functions['workerForbidden'] and body.startswith('1b') for index,body in errors),errors
        report['checks']['worker_management_rejected'] = dict(error=27,events=errors)

        start_script(scripts[0]); assert run(121) is True and run(122) is True
        vm.short(6); ping()
        assert run(121) is False and run(122) is False
        report['checks']['stop_all_stops_workers'] = True
        start_script(scripts[0]); assert run(121) is True and run(122) is True
        vm.short(15); ping()
        assert run(121) is False and run(122) is False
        assert value('Total') == 0 and value('ProgressA') == 0 and value('ProgressB') == 0
        report['checks']['soft_reset_stops_workers_and_clears_variables'] = True
        start_script(scripts[0]); assert run(121) is True and run(122) is True
        vm.upload(140,primitive('p2RuntimeRevision'),2) # live edit must stop all workers first
        assert run(121) is False and run(122) is False
        report['checks']['live_code_edit_stops_workers'] = True
        assert run(125) is True and run(126) is True
        report['result']='PASS'
    except Exception as error:
        report['error']=type(error).__name__+': '+str(error)
        if vm: report['last_events']=[dict(kind=k,index=i,body=b.hex()) for k,i,b in vm.events[-16:]]
        raise
    finally:
        if vm:
            try: vm.short(6)
            finally: vm.close()
        evidence.parent.mkdir(parents=True,exist_ok=True)
        evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
        print(json.dumps(report,indent=2),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port',required=True);parser.add_argument('--usb-serial',required=True)
    parser.add_argument('--board',choices=['eval','edge','edge32'],required=True)
    parser.add_argument('--program',type=Path,required=True);parser.add_argument('--evidence',type=Path,required=True)
    args=parser.parse_args();test(args.port,args.usb_serial,args.board,args.program,args.evidence)
