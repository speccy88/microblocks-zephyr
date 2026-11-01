"""Coherent depth and bounded observed gamepad state; fixed fake services only."""
# SPDX-License-Identifier: MIT
import asyncio
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
package=types.ModuleType('snapshot_lab_services');package.__path__=[str(ROOT/'linux/microduck')];sys.modules[package.__name__]=package
wire=importlib.import_module(package.__name__+'.sensor_simulator')
snap=importlib.import_module(package.__name__+'.sensor_snapshots')
rpc=importlib.import_module(package.__name__+'.protocol')


def request(name,params=None):
    return {'jsonrpc':'2.0','id':1,'method':wire.PREFIX+name,'params':{} if params is None else params,'confirmed':False}


class SnapshotProtocol(unittest.TestCase):
    def test_exact_tokens_rows_codes_and_empty_capture_params(self):
        handle='a'*32
        for name,params in [('captureTof',{}),('capturePad',{}),('depthRow',{'handle':handle,'row':8}),('padAxis',{'handle':handle,'code':65535}),('release',{'handle':handle})]:
            self.assertEqual(snap.validate(request(name,params)),(name,params))
        for name,params in [('captureTof',{'extra':1}),('depthRow',{'handle':handle,'row':0}),('depthRow',{'handle':handle,'row':True}),('padButton',{'handle':handle,'code':65536}),('release',{'handle':'A'*32}),('release',{'handle':handle,'row':1}),('release',{'handle':'a'*31})]:
            with self.assertRaises(rpc.RpcError):snap.validate(request(name,params))
    def test_library_preserves_legacy_blocks_and_checks_capture_before_example_reads(self):
        library=(ROOT/'linux/microduck/Sensor_Simulation.ubl').read_text();example=(ROOT/'linux/microduck/sensor-simulation.ubp').read_text()
        for name in ('microduckSimDepthZone','microduckSimPadAxis','microduckSimPadButton','microduckSimDepthCapture','microduckSimDepthRow','microduckSimPadCapture','microduckSimPadAxisState','microduckSimPadPosition','microduckSimPadButtonState','microduckSimSnapshotRelease'):self.assertIn(name,library)
        self.assertIn('if (microduckReadingKnown depthCapture)',example);self.assertIn('if (microduckReadingKnown padCapture)',example)
        self.assertNotIn('robot.move',library+example)


class PadObservedState(unittest.TestCase):
    def setUp(self):
        _,self.reports=wire.fixture('pad','normal');self.window=snap.PadWindow();self.window.apply(self.reports[0]['params'])
    def frame(self,seq=None,events=None,**patch):
        frame=copy.deepcopy(self.reports[1]['params'])
        if seq is not None:frame['seq']=seq
        if events is not None:frame['events']=events
        return {**frame,**patch}
    def test_attachment_values_are_unobserved_and_not_fresh_held_state(self):
        state=self.window.snapshot();self.assertEqual(state['buttons'][304]['status'],'unobserved');self.assertIsNone(state['axes'][0]['value'])
    def test_button_and_axis_hold_across_empty_frame_then_release(self):
        self.window.apply(self.frame());self.window.apply(self.reports[2]['params']);state=self.window.snapshot()
        self.assertEqual(state['axes'][0]['value'],1583);self.assertEqual(state['buttons'][304]['value'],2);self.assertEqual(state['frames'],2)
        self.assertEqual(state['buttons'][304]['event_seq'],str(self.reports[1]['params']['seq']))
        self.window.apply(self.frame(seq=self.window.seq+1,events=[{'kind':1,'code':304,'value':0,'name':'BTN_SOUTH'}]))
        self.assertEqual(self.window.snapshot()['buttons'][304]['value'],0)
    def test_loss_invalidates_all_until_a_later_clean_event_for_each_control(self):
        self.window.apply(self.frame());seq=self.window.seq
        self.window.apply(self.frame(seq=seq+1,socket_dropped=1));self.assertIsNone(self.window.snapshot()['buttons'][304]['value'])
        self.window.apply(self.frame(seq=seq+2,events=[{'kind':3,'code':0,'value':0,'name':'ABS_X'}]))
        state=self.window.snapshot();self.assertEqual(state['axes'][0]['value'],0);self.assertEqual(state['buttons'][304]['status'],'dropped')
    def test_gap_regression_and_reattachment_cannot_reuse_old_state(self):
        self.window.apply(self.frame());seq=self.window.seq;at=self.window.at_us
        self.window.apply(self.frame(seq=seq-1,at_us=1));self.assertEqual(self.window.seq,seq);self.assertEqual(self.window.at_us,at)
        self.assertIsNone(self.window.snapshot()['axes'][0]['value'])
        self.window.apply(self.frame(seq=seq+2));self.assertEqual(self.window.snapshot()['buttons'][304]['status'],'dropped')
        self.window.apply(self.reports[0]['params']);self.assertEqual(self.window.snapshot()['buttons'][304]['status'],'unobserved')
    def test_detach_and_imu_do_not_make_controls_known(self):
        self.window.apply(self.frame());self.window.apply({'report':'imu','samples':[]});self.assertEqual(self.window.frames,1)
        self.window.apply({'report':'detached','why':'SIMULATION'});self.assertEqual(self.window.snapshot()['status'],'detached')
        with self.assertRaises(rpc.RpcError):self.window.apply(self.frame())
    def test_malformed_and_out_of_range_events_are_rejected(self):
        for patch in ({'seq':True},{'after_drop':1},{'since_us':2**63},{'events':[{'kind':3,'code':0,'value':40000,'name':'ABS_X'}]},{'events':[{'kind':1,'code':999,'value':1,'name':'UNKNOWN'}]}):
            with self.assertRaises(rpc.RpcError):self.window.apply(self.frame(**patch))


@unittest.skipUnless(sys.platform=='linux','Linux private streams required')
class SnapshotUnixBackend(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='snapshots-');self.base=Path(self.temporary.name)
        self.service=await wire.SensorSimulator(self.base/'sim').start();self.store=self.service.gateway.snapshots
    async def asyncTearDown(self):await self.service.stop();self.temporary.cleanup()
    async def call(self,name,params=None):
        reader,writer=await rpc.connect_checked(self.service.directory/'gateway.sock',os.geteuid(),16384,True)
        try:
            writer.write(rpc.encode(request(name,params),16384));await writer.drain();reply=await rpc.read_message(reader,16384)
            self.assertNotIn('error',reply);return reply['result']
        finally:writer.close();await writer.wait_closed()
    async def test_all_eight_rows_reuse_one_immutable_frame_without_subscriptions(self):
        original=wire.fixture;calls=0
        def changing(service,profile):
            nonlocal calls
            description,reports=original(service,profile)
            if service=='tof':
                calls+=1;reports[0]['params']['distance_mm']=[100*calls+i for i in range(64)];reports[0]['params']['seq']=calls
            return description,reports
        with mock.patch.object(wire,'fixture',side_effect=changing),mock.patch.object(rpc.Upstream,'call',side_effect=AssertionError('ordinary upstream forbidden')):
            first=await self.call('captureTof');second=await self.call('captureTof');self.assertNotEqual(first['handle'],second['handle'])
            for row in range(1,9):
                result=await self.call('depthRow',{'handle':first['handle'],'row':row})
                self.assertEqual(result['seq'],'1');self.assertEqual(result['distance_mm'],list(range(100+(row-1)*8,100+row*8)))
            self.assertEqual(calls,2);self.assertEqual(self.service.subscriptions,2)
    async def test_capacity_release_expiry_and_wrong_kind_are_explicit(self):
        clock=[0.0];self.store.clock=lambda:clock[0]
        captures=[await self.call('captureTof') for _ in range(4)]
        self.assertEqual((await self.call('captureTof'))['status'],'busy')
        token=captures[0]['handle'];self.assertEqual((await self.call('padAxis',{'handle':token,'code':0}))['status'],'wrong_kind')
        self.assertEqual((await self.call('release',{'handle':token}))['status'],'released')
        self.assertEqual((await self.call('release',{'handle':token}))['status'],'not_retained')
        clock[0]=5
        self.assertEqual((await self.call('depthRow',{'handle':captures[1]['handle'],'row':1}))['status'],'expired_or_unknown')
        self.assertEqual(len(self.store.entries),0)
    async def test_inflight_reservations_and_cancellation_release_slots(self):
        gate=asyncio.Event()
        async def blocked(directory,kind):await gate.wait();return snap.result(kind+'_capture','waiting'),None
        with mock.patch.object(snap,'capture',side_effect=blocked):
            tasks=[asyncio.create_task(self.store.acquire('pad')) for _ in range(4)]
            await asyncio.sleep(0);self.assertEqual(self.store.pending,4)
            self.assertEqual((await self.store.acquire('tof'))['status'],'busy')
            for task in tasks:task.cancel()
            await asyncio.gather(*tasks,return_exceptions=True)
        self.assertEqual(self.store.pending,0);self.assertEqual(len(self.store.entries),0)
    async def test_pad_snapshot_has_held_state_without_new_subscriptions(self):
        capture=await self.call('capturePad');handle=capture['handle'];self.assertEqual(capture['frames'],2)
        axis=await self.call('padAxis',{'handle':handle,'code':0});button=await self.call('padButton',{'handle':handle,'code':304})
        self.assertEqual(axis['value'],1583);self.assertIs(button['value'],True);self.assertNotEqual(button['event_seq'],button['seq'])
        self.assertEqual(self.service.subscriptions,1)
        self.assertEqual((await self.call('padAxis',{'handle':handle,'code':1}))['status'],'unsupported')
        self.assertEqual((await self.call('depthRow',{'handle':handle,'row':1}))['status'],'wrong_kind')
    async def test_absence_and_clock_regression_do_not_retain_handles(self):
        self.service.profile='absent'
        self.assertEqual((await self.call('captureTof'))['status'],'absent')
        self.assertEqual((await self.call('capturePad'))['status'],'waiting');self.assertEqual(len(self.store.entries),0)
        self.service.profile='normal';clock=[10.0];self.store.clock=lambda:clock[0]
        capture=await self.call('captureTof');clock[0]=9.0
        self.assertEqual((await self.call('depthRow',{'handle':capture['handle'],'row':1}))['status'],'expired_or_unknown')


SOURCE=Path(os.environ.get('SMALLVM_UPSTREAM',ROOT.parent/'smallvm-linux-upstream'));EXTERNAL=os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform=='linux' and struct.calcsize('P')==8 and (EXTERNAL or shutil.which('gcc') and (SOURCE/'.git').is_dir()),'native LP64 compiler/source required')
class SnapshotNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='snapshot-native-tests-');cls.base=Path(cls.temporary.name)
        if EXTERNAL:cls.binary=Path(EXTERNAL)
        else:
            p=subprocess.run([sys.executable,str(ROOT/'linux/arm64/build.py'),'--upstream',str(SOURCE),'--output',str(cls.base/'build'),'--sanitize'],capture_output=True,text=True,timeout=120)
            if p.returncode:raise AssertionError(p.stdout+p.stderr)
            cls.binary=cls.base/'build/smallvm'
        spec=importlib.util.spec_from_file_location('snapshot_vm_helpers',ROOT/'tests/test_linux_microduck_vm.py');cls.helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.helpers)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    async def asyncSetUp(self):
        self.work=Path(tempfile.mkdtemp(dir=self.base));self.service=await wire.SensorSimulator(self.work/'sim').start();self.runtime=None
    async def asyncTearDown(self):
        if self.runtime:
            await asyncio.to_thread(self.runtime.stop);log=self.runtime.log_path.read_text();self.assertEqual(self.runtime.process.returncode,0,log);self.assertNotIn('AddressSanitizer',log);self.assertNotIn('runtime error:',log)
        await self.service.stop()
    async def start_vm(self):
        data=self.work/'programs';data.mkdir(mode=0o700);self.runtime=await asyncio.to_thread(self.helpers.Runtime,self.binary,data,self.service.directory/'gateway.sock')
    async def primitive(self,name,args=(),error=None,command=False):return await asyncio.to_thread(self.runtime.primitive,name,args,error,command)
    async def execute(self,program,error=None):return await asyncio.to_thread(self.runtime.execute,program.finish(),error)
    async def call(self,name,params=None):
        job=await self.primitive('begin',(wire.PREFIX+name,json.dumps(params or {}),False));deadline=asyncio.get_running_loop().time()+4
        while await self.primitive('status',(job,))=='pending':self.assertLess(asyncio.get_running_loop().time(),deadline);await asyncio.sleep(.005)
        reply=await self.primitive('result',(job,));await self.primitive('release',(job,),command=True);return reply
    async def reading(self,reply,selector='raw'):
        P,V=self.helpers.Program,self.helpers.Var
        await self.execute(P().call('sensorSample',(reply,selector)).op(7,3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81,2)) for i in range(1,5)]
    async def row(self,reply,column):
        P,V=self.helpers.Program,self.helpers.Var
        await self.execute(P().call('sensorRow',(reply,)).op(7,4).push(column).push(V(4)).op(81,2).op(7,3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81,2)) for i in range(1,5)]
    async def test_real_vm_coherent_rows_and_typed_zone_states(self):
        await self.start_vm();capture=await self.call('captureTof');reading=await self.reading(capture,'capture');self.assertEqual(reading[0],'ok');handle=reading[1]
        for row in range(1,9):
            reply=await self.call('depthRow',{'handle':handle,'row':row})
            self.assertEqual(await self.row(reply,8),['ok',1000+row*8-1,'mm','simulation'])
        first=await self.call('depthRow',{'handle':handle,'row':1})
        self.assertEqual((await self.row(first,2))[0],'no_target');self.assertEqual((await self.row(first,3))[0],'unusable');self.assertEqual((await self.row(first,4))[0],'unusable')
        self.assertEqual(self.service.subscriptions,1)
        await self.call('release',{'handle':handle})
        self.assertEqual((await self.row(await self.call('depthRow',{'handle':handle,'row':1}),1))[0],'expired_or_unknown')
    async def test_real_vm_held_gamepad_raw_boolean_and_declared_span_position(self):
        await self.start_vm();capture=json.loads(await self.call('capturePad'))['result'];handle=capture['handle']
        axis=await self.call('padAxis',{'handle':handle,'code':0});button=await self.call('padButton',{'handle':handle,'code':304})
        self.assertEqual(await self.reading(axis),['ok',1583,'raw','simulation']);self.assertEqual(await self.reading(axis,'position'),['ok',524,'permille','simulation'])
        self.assertEqual(await self.reading(button),['ok',True,'boolean','simulation']);self.assertEqual(capture['frames'],2)
        self.assertEqual(self.service.subscriptions,1)
    async def test_native_snapshot_selector_bounds_refuse_before_io(self):
        await self.start_vm()
        for name,params in [('capturePad',{'extra':1}),('depthRow',{'handle':'a'*32,'row':9}),('padAxis',{'handle':'a'*32,'code':True}),('release',{'handle':'g'*32}),('release',{'handle':'a'*31})]:
            await self.primitive('begin',(wire.PREFIX+name,json.dumps(params),False),error=32)
        self.assertEqual(self.service.subscriptions,0)
    async def test_typed_unknown_overflow_boolean_and_span_extremes(self):
        await self.start_vm()
        def envelope(**patch):return json.dumps({'jsonrpc':'2.0','id':1,'result':{'simulation':True,'physical_movement_enabled':False,'kind':'axis_state','status':'ok','unit':'raw','value':0,'min':-2**31,'max':2**31-1,**patch}})
        self.assertEqual((await self.reading(envelope(value=2**31-1)))[0],'out_of_range')
        self.assertEqual(await self.reading(envelope(value=2**31-1),'position'),['ok',1000,'permille','simulation'])
        self.assertEqual(await self.reading(envelope(value=-2**31),'position'),['ok',0,'permille','simulation'])
        for patch in ({'value':True},{'value':None},{'simulation':False},{'physical_movement_enabled':True},{'min':None},{'min':0,'max':0},{'min':1,'max':10,'value':0}):self.assertNotEqual((await self.reading(envelope(**patch)))[0],'ok')
        depth={'source':'tofd','unit':'mm','raw_distance_mm':1000,'raw_status':5,'value':1000}
        self.assertEqual(await self.reading(envelope(**depth)),['ok',1000,'mm','simulation'])
        for patch in ({'value':0,'raw_distance_mm':0},{'raw_status':4},{'raw_distance_mm':999},{'value':-1}):
            self.assertEqual((await self.reading(envelope(**{**depth,**patch})))[0],'invalid')
        self.assertEqual((await self.reading(envelope(status='unobserved',value=None)))[0],'unobserved')
        await self.primitive('readingValue',(self.helpers.Var(3),),error=32)
        self.service.profile='absent';self.assertEqual((await self.reading(await self.call('captureTof'),'capture'))[0],'absent')
    async def test_nested_row_records_survive_actual_moving_gc(self):
        await self.start_vm();P,V=self.helpers.Program,self.helpers.Var;events=self.runtime.wire.events;start=len(events)
        await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0))
        self.assertFalse(any(k==20 and i==255 and b'GC took' in body for k,i,body in events[start:]))
        start=len(events)
        reply=json.dumps({'jsonrpc':'2.0','id':1,'result':snap.result('depth_row','ok',handle='a'*32,row=1,distance_mm=list(range(1000,1008)),raw_status=[5]*8)})
        self.assertEqual(await self.row(reply,8),['ok',1007,'mm','simulation'])
        self.assertTrue(any(k==20 and i==255 and b'GC took' in body for k,i,body in events[start:]))
        for column in range(1,9):
            await self.execute(P().push(column).push(V(4)).op(81,2).op(7,3).push(0))
            self.assertEqual(await self.primitive('readingValue',(V(3),)),999+column)


if __name__=='__main__':unittest.main(verbosity=2)
