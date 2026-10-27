"""Actual VM and bounded tofd head-IMU reader with fictional Unix sensor data."""
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

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('depth_service_tests')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
wire = importlib.import_module(package.__name__ + '.sensor_simulator')
svc = importlib.import_module(package.__name__ + '.depth_service')
client = importlib.import_module(package.__name__ + '.client')
gateway = importlib.import_module(package.__name__ + '.gateway')
rpc = importlib.import_module(package.__name__ + '.protocol')


def request(name='capture',p=None):
    return {'jsonrpc':'2.0','id':1,'method':svc.PREFIX+name,'params':p or {},'confirmed':False}


def state():
    description,reports=wire.fixture('tof','normal')
    return {'description':description,'frame':svc.validate_frame(reports[0]['params'])}


def zone(handle,row=1,col=1,field='distance'):
    return {'handle':handle,'row':row,'col':col,'field':field}


def source(path,uid=None):
    return {'version':1,'daemon':'tofd','path':str(path),'uid':os.geteuid() if uid is None else uid}


async def normal_gateway(directory,path,uid=None):
    directory.mkdir(mode=0o700)
    config=directory/'depth.json';config.write_text(json.dumps(source(path,uid)));config.chmod(0o600)
    service=gateway.Gateway({},depth=svc.load_source(config))
    return await service.start(directory/'gateway.sock')


class DepthProtocol(unittest.TestCase):
    def test_closed_readonly_methods_and_selectors(self):
        for q in [request('capture',{'path':'/run/tofd.sock'}),request('zone',zone('A'*32)),
                  request('zone',zone('a'*32,row=0)),request('zone',zone('a'*32,col=True)),
                  request('zone',zone('a'*32,field='unsafe')),request('metadata',{'handle':'a'*32,'field':'unknown'}),
                  request('row',{'handle':'a'*32,'row':9}),{**request(),'confirmed':1}]:
            with self.assertRaises(rpc.RpcError):svc.validate(q)
        self.assertEqual(svc.validate(request()),('capture',{}))

    def test_source_status_classes_and_raw_diagnostics_are_distinct(self):
        s=state()
        for code,raw,expected in [(5,1,'ok'),(9,32767,'ok'),(255,0,'no_target'),(4,1000,'unusable'),(5,0,'unusable'),(9,-3,'unusable')]:
            s['frame']['status'][0]=code;s['frame']['distance_mm'][0]=raw
            value=svc.zone_reading(s,1,1,'distance')
            self.assertEqual(value['status'],expected)
            self.assertEqual(value['value'],raw if expected=='ok' else None)
            self.assertEqual(svc.zone_reading(s,1,1,'raw_status')['value'],code)
            self.assertEqual(svc.zone_reading(s,1,1,'raw_distance')['value'],raw)

    def test_full_geometry_i16_u8_and_u64_validation(self):
        good=state()['frame']
        for delta in [{'rows':True},{'cols':4},{'distance_mm':[1]*63},{'status':[5]*65},
                      {'distance_mm':[True]*64},{'distance_mm':[32768]*64},{'status':[-1]*64},
                      {'seq':2**64},{'at_us':True},{'t_ns':-1}]:
            with self.assertRaises(rpc.RpcError):svc.validate_frame({**good,**delta})

    def test_exact_metadata_missing_clocks_and_legacy_clock(self):
        s=state()
        for key in ('seq','at_us','t_ns'):
            s['frame'][key]=2**64-1
            self.assertEqual(svc.metadata_reading(s,key)['value'],str(2**64-1))
            s['frame'].pop(key)
            self.assertEqual(svc.metadata_reading(s,key)['status'],'not_reported')
            s['frame'][key]=0
            self.assertEqual(svc.metadata_reading(s,key)['value'],None if key=='t_ns' else '0')
        s['description'].pop('hz');self.assertEqual(svc.metadata_reading(s,'rate')['status'],'not_reported')
        s['description']['hz']=0;self.assertEqual(svc.metadata_reading(s,'rate')['value'],0)

    def test_immutable_copy_and_row_major_index(self):
        s=state();original=s['frame'];copied=svc.validate_frame(original)
        original['distance_mm'][63]=1
        self.assertEqual(copied['distance_mm'][63],1063)
        self.assertEqual(svc.zone_reading({'description':s['description'],'frame':copied},8,8,'distance')['value'],1063)

    def test_editor_blocks_are_normal_readonly_and_label_raw_diagnostics(self):
        library=(ROOT/'linux/microduck/Depth.ubl').read_text()
        for name in ('depthReading','depthRow','microduck.depth.capture','microduckDepthRawStatus','local_ipc'):self.assertIn(name,library)
        self.assertNotIn('microduck.sensorSim',library)
        self.assertNotIn('robot.move',library)
        self.assertIn('if (microduckReadingKnown depthFrame)',(ROOT/'linux/microduck/depth.ubp').read_text())

    def test_python_client_validator_admits_both_readonly_adapters_only(self):
        self.assertEqual(gateway.validate(request())[0],'microduck.depth.capture')
        self.assertEqual(gateway.validate({'jsonrpc':'2.0','id':1,'method':'microduck.headImu.capture','params':{}})[0],'microduck.headImu.capture')
        for method in ('tof.stream','robot.move','microduck.sensorSim.captureTof'):
            with self.assertRaises(rpc.RpcError):gateway.validate({'jsonrpc':'2.0','id':1,'method':method,'params':{}})


@unittest.skipUnless(sys.platform=='linux','Linux private Unix sockets required')
class DepthUnix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='depth-service-');self.base=Path(self.temp.name)
        self.fixture=await wire.SensorSimulator(self.base/'source').start()
        self.normal=await normal_gateway(self.base/'normal',self.fixture.directory/'tof.sock')
        self.client=client.Client(self.base/'normal/gateway.sock')

    async def asyncTearDown(self):
        await self.normal.stop();await self.fixture.stop();self.temp.cleanup()

    async def call(self,name='capture',p=None):return await self.client.call(svc.PREFIX+name,p)

    async def test_client_all64_zones_and8_rows_use_one_subscription(self):
        # Coherence is independent of elapsed query time; expiry has its own test.
        self.normal.depth.clock=lambda:0.0
        handle=(await self.call())['handle']
        for row in range(1,9):
            values=await self.call('row',{'handle':handle,'row':row})
            self.assertEqual(len(values['distance_mm']),8)
            for col in range(1,9):
                actual=await self.call('zone',zone(handle,row,col))
                self.assertEqual(actual,svc.zone_reading(state(),row,col,'distance'))
                self.assertNotIn('simulation',actual)
        self.assertEqual(self.fixture.subscriptions,1)
        self.assertEqual(self.fixture.action_count,0)

    async def test_metadata_seven_fields_are_coherent_and_no_io(self):
        handle=(await self.call())['handle']
        for field in svc.META_FIELDS:
            self.assertEqual(await self.call('metadata',{'handle':handle,'field':field}),svc.metadata_reading(state(),field))
        self.assertEqual(self.fixture.subscriptions,1)

    async def test_ragged_frames_bad_headers_and_missing_clocks(self):
        description,reports=wire.fixture('tof','normal')
        for delta in ({'rows':4},{'hz':True},{'sensor':'bad/name'}):
            with mock.patch.object(wire,'fixture',return_value=({**description,**delta},reports)):
                with self.assertRaises(rpc.RpcError):await self.call()
        broken=copy.deepcopy(reports);broken[0]['params']['status'].pop()
        with mock.patch.object(wire,'fixture',return_value=(description,broken)):
            with self.assertRaises(rpc.RpcError):await self.call()
        partial=copy.deepcopy(reports)
        for key in ('seq','at_us','t_ns'):partial[0]['params'].pop(key)
        with mock.patch.object(wire,'fixture',return_value=(description,partial)):
            handle=(await self.call())['handle']
        for field in ('seq','at_us','t_ns'):
            self.assertEqual((await self.call('metadata',{'handle':handle,'field':field}))['status'],'not_reported')

    async def test_refusal_absence_and_waiting_never_retain_handles(self):
        description,_=wire.fixture('tof','normal')
        for desc,status in [({**description,'accepted':False},'refused'),({**description,'sensor':None},'absent'),(description,'waiting')]:
            with mock.patch.object(wire,'fixture',return_value=(desc,[])):
                value=await self.call();self.assertEqual(value['status'],status);self.assertNotIn('handle',value)
        self.assertFalse(self.normal.depth.entries)

    async def test_uid_mismatch_disabled_and_protected_routes(self):
        self.normal.depth.config['uid']=os.geteuid()+1
        with self.assertRaises(rpc.RpcError):await self.call()
        self.assertEqual(self.fixture.subscriptions,0)
        for method in ('robot.enable','tof.stream','microduck.sensorSim.captureTof'):
            with self.assertRaises(rpc.RpcError):await self.client.call(method,{})
        saved=self.normal.depth;self.normal.depth=None
        try:
            with self.assertRaises(rpc.RpcError) as error:await self.call()
            self.assertEqual(error.exception.code,-32004)
        finally:self.normal.depth=saved

    async def test_capacity_release_expiry_and_clock_regression(self):
        clock=[10.0];self.normal.depth.clock=lambda:clock[0]
        handles=[(await self.call())['handle'] for _ in range(4)]
        self.assertEqual((await self.call())['status'],'busy')
        self.assertEqual((await self.call('release',{'handle':handles[0]}))['status'],'released')
        clock[0]=15
        self.assertEqual((await self.call('zone',zone(handles[1])))['status'],'expired_or_unknown')
        handle=(await self.call())['handle'];clock[0]=14
        self.assertEqual((await self.call('row',{'handle':handle,'row':1}))['status'],'expired_or_unknown')

    async def test_shutdown_cancels_actual_subscription_and_clears_state(self):
        desc,_=wire.fixture('tof','normal')
        with mock.patch.object(wire,'fixture',return_value=(desc,[])):
            pending=asyncio.create_task(self.call())
            for _ in range(100):
                if self.fixture.subscriptions:break
                await asyncio.sleep(.002)
            self.assertEqual(self.normal.depth.pending,1)
            await self.normal.stop();await asyncio.gather(pending,return_exceptions=True)
        for _ in range(100):
            if not self.fixture.active:break
            await asyncio.sleep(.002)
        self.assertEqual(self.fixture.active,0);self.assertEqual(self.normal.depth.pending,0);self.assertFalse(self.normal.depth.entries)

    async def test_actual_normal_gateway_cli_and_capabilities(self):
        config=self.base/'normal/gateway.json';config.write_text('{"version":1,"upstreams":{}}');config.chmod(0o600)
        p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/gateway.py'),'--socket',str(self.base/'normal/cli.sock'),'--config',str(config),'--depth-config',str(self.base/'normal/depth.json'),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            self.assertIn(b'gateway ready',await asyncio.wait_for(p.stdout.readline(),3))
            c=client.Client(self.base/'normal/cli.sock');caps=await c.call('microduck.capabilities')
            self.assertEqual(set(caps['methods']),svc.METHODS);self.assertEqual(caps['allowed_mutations'],[])
            self.assertTrue(caps['read_only_adapters']['depth']['configured'])
            self.assertEqual((await c.call(svc.PREFIX+'capture'))['status'],'ok')
        finally:
            if p.returncode is None:p.terminate()
            _,error=await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode())

    async def test_labelled_user_fixture_cli_and_shutdown(self):
        directory=self.base/'demo'
        p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/depth_gateway_fixture.py'),'--directory',str(directory),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            ready=json.loads(await asyncio.wait_for(p.stdout.readline(),3))
            self.assertTrue(ready['simulation']);self.assertTrue(ready['normal_gateway']);self.assertFalse(ready['physical_hardware_verified'])
            c=client.Client(ready['gateway_socket']);self.assertEqual((await c.call(svc.PREFIX+'capture'))['status'],'ok')
        finally:
            if p.returncode is None:p.terminate()
            _,error=await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode());self.assertFalse((directory/'normal/gateway.sock').exists())




SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL = os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform == 'linux' and struct.calcsize('P') == 8 and
                     (EXTERNAL or shutil.which('gcc') and (SOURCE / '.git').is_dir()), 'native LP64 compiler/source required')
class DepthNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='depth-service-native-')
        cls.base = Path(cls.temp.name)
        if EXTERNAL:
            cls.binary = Path(EXTERNAL)
        else:
            p = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE),
                                '--output', str(cls.base / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
            if p.returncode:
                raise AssertionError(p.stdout + p.stderr)
            cls.binary = cls.base / 'build/smallvm'
        spec = importlib.util.spec_from_file_location('depth_vm_helpers', ROOT / 'tests/test_linux_microduck_vm.py')
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.service = await wire.SensorSimulator(self.work / 'sim').start()
        self.normal = await normal_gateway(self.work / 'normal', self.service.directory / 'tof.sock')
        self.normal.depth.clock = lambda: 0.0
        data = self.work / 'programs'
        data.mkdir(mode=0o700)
        self.runtime = await asyncio.to_thread(self.helpers.Runtime, self.binary, data, self.work / 'normal/gateway.sock')

    async def asyncTearDown(self):
        await asyncio.to_thread(self.runtime.stop)
        log = self.runtime.log_path.read_text()
        self.assertEqual(self.runtime.process.returncode, 0, log)
        self.assertNotIn('AddressSanitizer', log)
        self.assertNotIn('runtime error:', log)
        await self.normal.stop()
        await self.service.stop()

    async def primitive(self, name, args=(), error=None, command=False):
        return await asyncio.to_thread(self.runtime.primitive, name, args, error, command)

    async def execute(self, p):
        return await asyncio.to_thread(self.runtime.execute, p.finish())

    async def call(self, name='capture', p=None):
        job = await self.primitive('begin', (svc.PREFIX + name, json.dumps(p or {}), False))
        deadline = asyncio.get_running_loop().time() + 4
        while await self.primitive('status', (job,)) == 'pending':
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        result = await self.primitive('result', (job,))
        await self.primitive('release', (job,), command=True)
        return result

    async def typed(self, reply, primitive='depthReading'):
        P, V = self.helpers.Program, self.helpers.Var
        await self.execute(P().call(primitive, (reply,)).op(7, 3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81, 2)) for i in range(1, 5)]

    async def row(self,reply,col):
        P,V=self.helpers.Program,self.helpers.Var
        await self.execute(P().call('depthRow',(reply,)).op(7,4).push(col).push(V(4)).op(81,2).op(7,3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81,2)) for i in range(1,5)]

    async def test_real_vm_all8_rows64_zones_and_metadata_one_capture(self):
        capture=await self.typed(await self.call());self.assertEqual(capture[0],'ok');handle=capture[1]
        for row in range(1,9):
            reply=await self.call('row',{'handle':handle,'row':row})
            for col in range(1,9):
                expected=svc.zone_reading(state(),row,col,'distance')
                self.assertEqual(await self.row(reply,col),[expected['status'],expected['value'] if expected['status']=='ok' else '','mm','local_ipc'])
        for field in svc.META_FIELDS:
            expected=svc.metadata_reading(state(),field)
            self.assertEqual(await self.typed(await self.call('metadata',{'handle':handle,'field':field})),['ok',expected['value'],expected['unit'],'local_ipc'])
        self.assertEqual(self.service.subscriptions,1)

    async def test_native_selector_bounds_reject_before_io(self):
        for name,p in [('row',{'handle':'a'*32,'row':9}),('zone',zone('a'*32,col=0)),
                       ('zone',zone('A'*32)),('zone',zone('a'*32,field='unknown')),
                       ('metadata',{'handle':'a'*32,'field':'unknown'}),('capture',{'path':'/run/tofd.sock'})]:
            await self.primitive('begin',(svc.PREFIX+name,json.dumps(p),False),error=32)
        self.assertEqual(self.service.subscriptions,0)

    async def test_native_strict_envelopes_units_types_ranges_and_kind(self):
        good=svc.zone_reading(state(),1,1,'distance')
        def envelope(v):return json.dumps({'jsonrpc':'2.0','id':1,'result':v})
        for delta in [{'value':True},{'value':999},{'raw_status':4},{'raw_distance_mm':0},
                      {'unit':'metres'},{'row':9},{'field':'raw'},{'kind':'head_imu_reading'},
                      {'simulation':True},{'physical_hardware_verified':True},{'source':'robotd'}]:
            self.assertNotEqual((await self.typed(envelope({**good,**delta})))[0],'ok')
        self.assertNotEqual((await self.typed(envelope(good),'headImuReading'))[0],'ok')
        P,V=self.helpers.Program,self.helpers.Var
        await self.execute(P().call('sensorSample',(envelope(good),'raw')).op(7,3).push(0))
        self.assertNotEqual(await self.execute(P().push(1).push(V(3)).op(81,2)),'ok')
        meta=svc.metadata_reading(state(),'seq')
        for value in (str(2**64),'01',True):
            self.assertNotEqual((await self.typed(envelope({**meta,'value':value})))[0],'ok')

    async def test_native_no_target_diagnostics_legacy_clock_and_release(self):
        handle=(await self.typed(await self.call()))[1]
        self.assertEqual(await self.typed(await self.call('zone',zone(handle,col=2))),['no_target','','mm','local_ipc'])
        await self.primitive('readingValue',(self.helpers.Var(3),),error=32)
        self.assertEqual(await self.typed(await self.call('zone',zone(handle,col=2,field='raw_status'))),['ok',255,'raw_status','local_ipc'])
        self.assertEqual(await self.typed(await self.call('zone',zone(handle,col=4,field='raw_distance'))),['ok',-3,'mm_raw','local_ipc'])
        meta=svc.metadata_reading(state(),'t_ns');reply=json.dumps({'jsonrpc':'2.0','id':1,'result':{**meta,'value':'0'}})
        self.assertEqual(await self.typed(reply),['not_reported','','ns','local_ipc'])
        await self.call('release',{'handle':handle})
        self.assertEqual((await self.row(await self.call('row',{'handle':handle,'row':1}),1))[0],'expired_or_unknown')

    async def test_nested_depth_rows_survive_actual_moving_gc(self):
        P,V=self.helpers.Program,self.helpers.Var;events=self.runtime.wire.events
        await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0));start=len(events)
        reply=json.dumps({'jsonrpc':'2.0','id':1,'result':svc.result('depth_row','ok',handle='a'*32,row=8,distance_mm=list(range(1000,1008)),raw_status=[5]*8)})
        self.assertEqual(await self.row(reply,8),['ok',1007,'mm','local_ipc'])
        self.assertTrue(any(k==20 and i==255 and b'GC took' in b for k,i,b in events[start:]))
        for col in range(1,9):
            await self.execute(P().push(col).push(V(4)).op(81,2).op(7,3).push(0))
            self.assertEqual(await self.primitive('readingValue',(V(3),)),999+col)

    async def test_disabled_adapter_returns_explicit_error_without_source_call(self):
        saved=self.normal.depth;self.normal.depth=None
        try:
            reply=await self.call();self.assertEqual(json.loads(reply)['error']['code'],-32004)
            self.assertEqual((await self.typed(reply))[0],'error')
        finally:self.normal.depth=saved
        self.assertEqual(self.service.subscriptions,0)


if __name__=='__main__':
    unittest.main(verbosity=2)
