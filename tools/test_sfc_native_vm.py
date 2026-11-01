#!/usr/bin/env python3
"""Execute genuine GP-compiled SFC chunks in the real local SmallVM over PTY.

No browser, device port, board, socket gateway or external network is opened.
Only test controls use small official bytecode utilities; SFC code is uploaded
unchanged from the real compiler (zero padding to the wire's word alignment).
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import platform
import struct
import tempfile
import time


def run(binary, compiled, output):
    assert platform.system() == 'Linux'
    assert not output.exists(), 'Inspect existing evidence before a new run'
    root = Path(__file__).resolve().parents[1]
    spec = importlib.util.spec_from_file_location('sfc_real_vm_tools', root/'tests/test_linux_microduck_vm.py')
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    report = json.loads(compiled.read_text())
    assert report['status'] == 'PASS' and report['result']['save_load_equal']
    result = report['result']
    indices = result['variables']
    receipt = {'status':'RUNNING', 'real_VM':True,'real_GP_compiler':True,
               'hardware_access':False,'browser_access':False,
               'binary_sha256':hashlib.sha256(binary.read_bytes()).hexdigest(),
               'compiler_report_sha256':hashlib.sha256(compiled.read_bytes()).hexdigest(),
               'checks':[], 'snapshots':[]}
    runtime = None
    def check(name, predicate):
        assert predicate, name
        receipt['checks'].append(name)
    with tempfile.TemporaryDirectory(prefix='sfc-native-real-vm-') as temporary:
        data = Path(temporary)/'data';data.mkdir(mode=0o700)
        try:
            runtime = support.Runtime(binary,data,None)
            vm = runtime.wire
            checksums = {}
            for c in result['chunks']:
                code = bytes(c['bytes']);code += b'\0'*(-len(code)%4)
                checksums[c['id']] = vm.upload(c['id'],code,c['kind'])
            receipt['uploaded_chunks'] = [{'id':c['id'],'bytes':len(c['bytes']),'padding':-len(c['bytes'])%4} for c in result['chunks']]
            def get(name):
                start=len(vm.events);vm.short(7,indices[name])
                value=vm.wait(lambda e:e[:2]==(21,indices[name]),start)[2]
                if value[0]==1:return struct.unpack('<i',value[1:5])[0]
                if value[0]==3:return bool(value[1])
                raise AssertionError('Unexpected variable result '+value.hex())
            def set_value(name,value):
                code=support.Program().push(value).op(7,indices[name]).push(True).finish()
                assert runtime.execute(code,chunk=254) is True
            def until(predicate):
                deadline=time.monotonic()+3
                while time.monotonic()<deadline:
                    if predicate():return
                    vm.pump(.005)
                raise TimeoutError('Native SFC state did not arrive')
            def snapshot(label):
                item={'label':label,**{name:get(name) for name in indices}}
                receipt['snapshots'].append(item);return item
            check('real compiler preserved native when-started chunk types',all(c['kind']==4 for c in result['chunks']))
            vm.short(5,1) # native editor's 64-bit-object start-all/green-flag command
            until(lambda:get('Step1') is True and get('Heartbeat')>=3)
            if 'empty-loop' not in compiled.name:until(lambda:get('Loops1')>=3)
            first=snapshot('waiting-first-transition')
            check('setup executes once while waiting',first['Entries1']==1 and first['Entries2']==0 and first['Completed']==0)
            check('only current step is active',first['Step1'] is True and first['Step2'] is False)
            old_heartbeat=first['Heartbeat'];vm.pump(.025)
            check('unrelated task progresses while transition waits',get('Heartbeat')>old_heartbeat)
            set_value('Transition1',1)
            old_loop=get('Loops1') if 'Loops1' in indices else None
            old_heartbeat=get('Heartbeat');vm.pump(.025)
            check('numeric one is not Boolean true',get('Step1') is True and get('Entries2')==0 and get('Heartbeat')>old_heartbeat)
            if 'empty-loop' not in compiled.name:check('loop repeats during wait',get('Loops1')>old_loop)
            set_value('Transition1',True)
            until(lambda:get('Step2') is True and get('Loops2')>=3)
            second=snapshot('waiting-second-transition')
            check('live shared variable wakes the transition',second['Step1'] is False and second['Step2'] is True and second['Entries2']==1)
            check('transition is not auto-consumed',second['Transition1'] is True)
            set_value('Transition2',True)
            until(lambda:get('Completed')==1)
            done=snapshot('sequence-complete')
            check('normal transition clears step flags',done['Step1'] is False and done['Step2'] is False)
            def loop_counts():return tuple(get(n) for n in ['Loops1','Loops2'] if n in indices)
            loops=loop_counts()
            vm.short(3,128);until(lambda:get('Completed')==2)
            check('already-true transitions still execute setup once',get('Entries1')==2 and get('Entries2')==2)
            check('already-true transitions skip loop',loops==loop_counts())
            set_value('Transition1',False);set_value('Transition2',False)
            vm.short(3,128);until(lambda:get('Step1') is True)
            vm.short(4,128);vm.ping()
            stop=snapshot('explicit-task-stop')
            vm.pump(.02)
            check('controlled stop prevents handoff',get('Completed')==2 and get('Entries2')==2)
            check('documented stop flag remains until restart',stop['Step1'] is True)
            old_heartbeat=get('Heartbeat');vm.pump(.02)
            check('stopping the sequence preserves independent task',get('Heartbeat')>old_heartbeat)
            set_value('Transition1',True);set_value('Transition2',True)
            vm.short(3,128);until(lambda:get('Completed')==3)
            check('restart resets flags and reenters setup',get('Step1') is False and get('Step2') is False and get('Entries1')==4 and get('Entries2')==3)
            vm.short(4,129);vm.ping()
            runtime.stop();runtime=None
            text=(data/'runtime.log').read_text()
            check('no sanitizer diagnostics',not any(t in text for t in ['AddressSanitizer','runtime error:','LeakSanitizer']))
            runtime=support.Runtime(binary,data,None);vm=runtime.wire
            check('compiled chunks survive process restart',all(vm.crc(i)==crc for i,crc in checksums.items()))
            # Reopened persisted source has the same behavior; startup values
            # are VM defaults, proving a fresh reread rather than stale arguments.
            until(lambda:get('Step1') is True)
            check('reopened native program waits on fresh variable',get('Entries1')==1 and get('Completed')==0)
            vm.short(4,128);vm.ping()
            receipt['status']='PASS'
        except BaseException as error:
            receipt.update(status='FAIL',error=type(error).__name__+': '+str(error))
            raise
        finally:
            if runtime:runtime.stop()
            if (data/'runtime.log').exists():receipt['last_runtime_log']=(data/'runtime.log').read_text()
            output.write_text(json.dumps(receipt,indent=2)+'\n')
    return receipt


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary',type=Path,required=True)
    parser.add_argument('--compiled',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=run(args.binary.resolve(),args.compiled.resolve(),args.output.resolve())
    print(json.dumps({'status':result['status'],'checks':len(result['checks'])}))
