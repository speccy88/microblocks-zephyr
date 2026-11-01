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
package = types.ModuleType('gamepad_service_tests')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
wire = importlib.import_module(package.__name__ + '.sensor_simulator')
snap = importlib.import_module(package.__name__ + '.sensor_snapshots')
svc = importlib.import_module(package.__name__ + '.gamepad_service')
client = importlib.import_module(package.__name__ + '.client')
gateway = importlib.import_module(package.__name__ + '.gateway')
rpc = importlib.import_module(package.__name__ + '.protocol')


def request(name='capture',p=None):return {'jsonrpc':'2.0','id':1,'method':svc.PREFIX+name,'params':p or {},'confirmed':False}
def axis(handle,field='raw',code=0):return {'handle':handle,'code':code,'field':field}
def button(handle,field='pressed',code=304):return {'handle':handle,'code':code,'field':field}
def control(handle,kind='axis',index=1,field='code'):return {'handle':handle,'kind':kind,'index':index,'field':field}
def meta(handle,field='frames'):return {'handle':handle,'field':field}
def source(path,uid=None):return {'version':1,'daemon':'padd','path':str(path),'uid':os.geteuid() if uid is None else uid}


def state(reports=None):
    if reports is None:_,reports=wire.fixture('pad','normal')
    window=snap.PadWindow()
    for message in reports:
        report=copy.deepcopy(message['params'])
        if report.get('report')=='attached':report['device']=svc.validate_device(report['device'])
        window.apply(report)
    return {'device':copy.deepcopy(window.device),'observation':window.snapshot(),'window_end':'deadline'}


async def normal_gateway(directory,path,uid=None):
    directory.mkdir(mode=0o700);config=directory/'gamepad.json';config.write_text(json.dumps(source(path,uid)));config.chmod(0o600)
    return await gateway.Gateway({},gamepad=svc.load_source(config)).start(directory/'gateway.sock')


class GamepadProtocol(unittest.TestCase):
    def test_explicit_padd_config_and_closed_selectors(self):
        good={'version':1,'daemon':'padd','path':'/run/padd.sock','uid':1000};self.assertEqual(svc.validate_source(good),good)
        with self.assertRaises(ValueError):svc.validate_source({**good,'daemon':'tofd'})
        for q in [request('capture',{'path':'/dev/input/event0'}),request('axis',axis('a'*32,'pressed')),
                  request('button',button('a'*32,'raw')),request('control',control('a'*32,'button',1,'min')),
                  request('control',control('a'*32,index=65)),request('metadata',meta('a'*32,'node')),
                  request('release',{'handle':'A'*32}),{**request(),'confirmed':1}]:
            with self.assertRaises(rpc.RpcError):svc.validate(q)

    def test_cached_attachment_values_are_unobserved_but_descriptors_known(self):
        _,reports=wire.fixture('pad','normal');s=state(reports[:1])
        self.assertEqual(svc.reading(s,'axis',axis('a'*32))['status'],'unobserved')
        self.assertEqual(svc.reading(s,'button',button('a'*32))['status'],'unobserved')
        self.assertEqual(svc.reading(s,'control',control('a'*32))['value'],0)
        self.assertEqual(svc.reading(s,'metadata',meta('a'*32))['value'],0)
        self.assertEqual(svc.reading(s,'metadata',meta('a'*32,'observation_state'))['value'],'waiting')

    def test_held_values_survive_empty_frames_and_event_zero_is_known(self):
        s=state()
        self.assertEqual(svc.reading(s,'axis',axis('a'*32))['value'],1583)
        self.assertIs(svc.reading(s,'button',button('a'*32))['value'],True)
        self.assertEqual(svc.reading(s,'axis',axis('a'*32,'event_seq'))['value'],str(2**63+3))
        self.assertEqual(svc.reading(s,'metadata',meta('a'*32,'seq'))['value'],str(2**63+4))
        s['observation']['buttons'][304]['value']=0
        self.assertIs(svc.reading(s,'button',button('a'*32))['value'],False)

    def test_loss_and_sequence_gaps_require_later_clean_events_per_control(self):
        _,messages=wire.fixture('pad','normal');window=snap.PadWindow()
        for report in messages[:2]:window.apply(report['params'])
        dropped={**messages[2]['params'],'socket_dropped':1};window.apply(dropped)
        self.assertEqual(window.snapshot()['axes'][0]['status'],'dropped')
        clean={**dropped,'seq':dropped['seq']+1,'socket_dropped':0,'events':[{'kind':3,'code':0,'value':0,'name':'ABS_X'}]};window.apply(clean)
        self.assertEqual(window.snapshot()['axes'][0]['status'],'ok');self.assertEqual(window.snapshot()['buttons'][304]['status'],'dropped')
        window.apply({**clean,'seq':clean['seq']+2});self.assertEqual(window.snapshot()['axes'][0]['status'],'dropped')
        window.apply(messages[0]['params']);self.assertEqual(window.snapshot()['axes'][0]['status'],'unobserved')

    def test_exact_counter_kernel_time_and_signed_negative_interval(self):
        s=state();s['observation'].update(seq=str(2**64-1),at_us=str(2**64-1),since_us=str(-(2**63)))
        for field,value in [('seq',str(2**64-1)),('at_us',str(2**64-1)),('since_us',str(-(2**63)))]:
            self.assertEqual(svc.reading(s,'metadata',meta('a'*32,field))['value'],value)
        s['observation']['since_us']=None;self.assertEqual(svc.reading(s,'metadata',meta('a'*32,'since_us'))['status'],'not_reported')

    def test_raw_overflow_span_extremes_and_unsupported_controls(self):
        s=state();item=s['observation']['axes'][0];item.update(min=-(2**31),max=2**31-1)
        for raw,expected in [(-(2**31),0),(2**31-1,1000)]:
            item['value']=raw
            self.assertEqual(svc.reading(s,'axis',axis('a'*32,'position'))['value'],expected)
            self.assertEqual(svc.reading(s,'axis',axis('a'*32))['status'],'out_of_range')
        self.assertEqual(svc.reading(s,'axis',axis('a'*32,code=999))['status'],'unsupported')
        self.assertEqual(svc.reading(s,'control',control('a'*32,index=2))['status'],'unsupported')

    def test_utf8_descriptor_bounds_and_no_attached_value_surface(self):
        _,messages=wire.fixture('pad','normal');device=messages[0]['params']['device'];device['name']='é'*64
        self.assertEqual(svc.validate_device(device)['name'],'é'*64)
        for value in ('é'*65,'bad\x00name','\ud800'):
            with self.assertRaises(rpc.RpcError):svc.validate_device({**device,'name':value})
        for field in ('value','pressed','node','unique'):
            with self.assertRaises(rpc.RpcError):svc.validate(request('control',control('a'*32,field=field)))

    def test_editor_and_python_client_use_only_readonly_wrapper_methods(self):
        library=(ROOT/'linux/microduck/Gamepad.ubl').read_text();example=(ROOT/'linux/microduck/gamepad.ubp').read_text()
        for text in ('[microduck:gamepadReading]','local_ipc','microduckGamepadAxisCode','microduckGamepadObservationState'):self.assertIn(text,library)
        self.assertIn('microduckGamepadAxisCode padWindow 1',example);self.assertNotIn('robot.move',library+example)
        self.assertEqual(gateway.validate(request())[0],svc.PREFIX+'capture')
        with self.assertRaises(rpc.RpcError):gateway.validate({'jsonrpc':'2.0','id':1,'method':'pad.input','params':{}})


@unittest.skipUnless(sys.platform=='linux','Linux private Unix sockets required')
class GamepadUnix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='gamepad-service-');self.base=Path(self.temp.name)
        self.fixture=await wire.SensorSimulator(self.base/'source').start()
        self.normal=await normal_gateway(self.base/'normal',self.fixture.directory/'pad.sock')
        self.client=client.Client(self.base/'normal/gateway.sock')

    async def asyncTearDown(self):
        await self.normal.stop();await self.fixture.stop();self.temp.cleanup()

    async def call(self,name='capture',p=None):return await self.client.call(svc.PREFIX+name,p)

    async def test_one_subscription_supports_all_typed_queries_and_discovery(self):
        self.normal.gamepad.clock=lambda:0.0;handle=(await self.call())['handle'];s=state()
        groups=[('axis',axis(handle,field)) for field in svc.AXIS_FIELDS]+[('button',button(handle,field)) for field in svc.BUTTON_FIELDS]
        groups += [('control',control(handle,field=field)) for field in svc.CONTROL_FIELDS]+[('control',control(handle,'button',1,field)) for field in ('code','name')]
        groups += [('metadata',meta(handle,field)) for field in svc.META_FIELDS]
        for name,p in groups:self.assertEqual(await self.call(name,p),svc.reading(s,name,p))
        self.assertEqual(self.fixture.subscriptions,1);self.assertEqual(self.fixture.action_count,0)

    async def test_quiet_descriptor_capture_has_no_live_values(self):
        description,messages=wire.fixture('pad','normal')
        with mock.patch.object(wire,'fixture',return_value=(description,messages[:1])):
            capture=await self.call()
        self.assertEqual(capture['frames'],0);handle=capture['handle']
        self.assertEqual((await self.call('control',control(handle)))['value'],0)
        self.assertEqual((await self.call('axis',axis(handle)))['status'],'unobserved')
        self.assertEqual((await self.call('button',button(handle)))['status'],'unobserved')
        self.assertEqual((await self.call('metadata',meta(handle,'seq')))['status'],'not_reported')

    async def test_no_pad_imu_only_and_refusal_are_explicit_without_handles(self):
        for accepted,reports,status in [(False,[],'refused'),(True,[],'waiting'),(True,[{'jsonrpc':'2.0','method':'pad.report','params':{'report':'imu','samples':[]}}]*16,'event_limit')]:
            with mock.patch.object(wire,'fixture',return_value=({'accepted':accepted},reports)):
                value=await self.call();self.assertEqual(value['status'],status);self.assertNotIn('handle',value)

    async def test_detach_and_malformed_events_never_retain_old_state(self):
        description,messages=wire.fixture('pad','normal');detached={'jsonrpc':'2.0','method':'pad.report','params':{'report':'detached','why':'SIMULATION'}}
        with mock.patch.object(wire,'fixture',return_value=(description,messages+[detached])):
            self.assertEqual((await self.call())['status'],'detached')
        broken=copy.deepcopy(messages);broken[1]['params']['events'][0]['value']=True
        with mock.patch.object(wire,'fixture',return_value=(description,broken)):
            with self.assertRaises(rpc.RpcError):await self.call()
        self.assertFalse(self.normal.gamepad.entries)

    async def test_source_loss_is_unknown_until_a_clean_event_restores_each_control(self):
        description,messages=wire.fixture('pad','normal');messages[-1]['params']['after_drop']=True
        with mock.patch.object(wire,'fixture',return_value=(description,messages)):
            handle=(await self.call())['handle']
        self.assertEqual((await self.call('axis',axis(handle)))['status'],'dropped')
        self.assertEqual((await self.call('button',button(handle)))['status'],'dropped')
        self.assertEqual((await self.call('control',control(handle)))['status'],'ok')

    async def test_uid_before_write_and_disabled_protected_methods(self):
        self.normal.gamepad.config['uid']=os.geteuid()+1
        with self.assertRaises(rpc.RpcError):await self.call()
        self.assertEqual(self.fixture.subscriptions,0)
        for method in ('pad.input','pad.bind','robot.move','microduck.sensorSim.capturePad'):
            with self.assertRaises(rpc.RpcError):await self.client.call(method,{})
        saved=self.normal.gamepad;self.normal.gamepad=None
        try:
            with self.assertRaises(rpc.RpcError) as error:await self.call()
            self.assertEqual(error.exception.code,-32004)
        finally:self.normal.gamepad=saved

    async def test_capacity_release_ttl_and_clock_regression(self):
        clock=[10.0];self.normal.gamepad.clock=lambda:clock[0];handles=[(await self.call())['handle'] for _ in range(4)]
        self.assertEqual((await self.call())['status'],'busy')
        self.assertEqual((await self.call('release',{'handle':handles[0]}))['status'],'released')
        clock[0]=15;self.assertEqual((await self.call('axis',axis(handles[1])))['status'],'expired_or_unknown')
        handle=(await self.call())['handle'];clock[0]=14
        self.assertEqual((await self.call('metadata',meta(handle)))['status'],'expired_or_unknown')

    async def test_shutdown_cancels_pending_reader_and_clears_capacity(self):
        description,messages=wire.fixture('pad','normal')
        with mock.patch.object(wire,'fixture',return_value=(description,messages[:1])):
            pending=asyncio.create_task(self.call())
            for _ in range(100):
                if self.fixture.subscriptions:break
                await asyncio.sleep(.002)
            self.assertEqual(self.normal.gamepad.pending,1);await self.normal.stop();await asyncio.gather(pending,return_exceptions=True)
        for _ in range(100):
            if not self.fixture.active:break
            await asyncio.sleep(.002)
        self.assertEqual(self.fixture.active,0);self.assertEqual(self.normal.gamepad.pending,0);self.assertFalse(self.normal.gamepad.entries)

    async def test_actual_gateway_cli_and_private_config(self):
        config=self.base/'normal/gateway.json';config.write_text('{"version":1,"upstreams":{}}');config.chmod(0o600)
        private=self.base/'normal/gamepad.json';private.chmod(0o644)
        with self.assertRaises(ValueError):svc.load_source(private)
        private.chmod(0o600);alias=self.base/'normal/alias.json';alias.symlink_to(private)
        with self.assertRaises(OSError):svc.load_source(alias)
        p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/gateway.py'),'--socket',str(self.base/'normal/cli.sock'),'--config',str(config),'--gamepad-config',str(private),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            self.assertIn(b'gateway ready',await asyncio.wait_for(p.stdout.readline(),3));c=client.Client(self.base/'normal/cli.sock');caps=await c.call('microduck.capabilities')
            self.assertEqual(set(caps['methods']),svc.METHODS);self.assertEqual(caps['allowed_mutations'],[]);self.assertTrue(caps['read_only_adapters']['gamepad']['configured'])
            self.assertEqual((await c.call(svc.PREFIX+'capture'))['status'],'ok')
        finally:
            if p.returncode is None:p.terminate()
            _,error=await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode())

    async def test_labelled_fixture_cli_and_clean_shutdown(self):
        directory=self.base/'demo';p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/gamepad_gateway_fixture.py'),'--directory',str(directory),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            ready=json.loads(await asyncio.wait_for(p.stdout.readline(),3));self.assertTrue(ready['simulation']);self.assertTrue(ready['normal_gateway']);self.assertFalse(ready['physical_hardware_verified'])
            c=client.Client(ready['gateway_socket']);self.assertEqual((await c.call(svc.PREFIX+'capture'))['status'],'ok')
        finally:
            if p.returncode is None:p.terminate()
            _,error=await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode());self.assertFalse((directory/'normal/gateway.sock').exists())




SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL = os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform == 'linux' and struct.calcsize('P') == 8 and
                     (EXTERNAL or shutil.which('gcc') and (SOURCE / '.git').is_dir()), 'native LP64 compiler/source required')
class GamepadNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='gamepad-service-native-')
        cls.base = Path(cls.temp.name)
        if EXTERNAL:
            cls.binary = Path(EXTERNAL)
        else:
            p = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE),
                                '--output', str(cls.base / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
            if p.returncode:
                raise AssertionError(p.stdout + p.stderr)
            cls.binary = cls.base / 'build/smallvm'
        spec = importlib.util.spec_from_file_location('gamepad_vm_helpers', ROOT / 'tests/test_linux_microduck_vm.py')
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.service = await wire.SensorSimulator(self.work / 'sim').start()
        self.normal = await normal_gateway(self.work / 'normal', self.service.directory / 'pad.sock')
        self.normal.gamepad.clock = lambda: 0.0
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

    async def typed(self, reply, primitive='gamepadReading'):
        P, V = self.helpers.Program, self.helpers.Var
        await self.execute(P().call(primitive, (reply,)).op(7, 3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81, 2)) for i in range(1, 5)]

    async def test_real_vm_all_sections_and_discovery_use_one_subscription(self):
        capture=await self.typed(await self.call());self.assertEqual(capture[0],'ok');handle=capture[1];s=state()
        groups=[('axis',axis(handle,field)) for field in svc.AXIS_FIELDS]+[('button',button(handle,field)) for field in svc.BUTTON_FIELDS]
        groups += [('control',control(handle,field=field)) for field in svc.CONTROL_FIELDS]+[('control',control(handle,'button',1,field)) for field in ('code','name')]
        groups += [('metadata',meta(handle,field)) for field in svc.META_FIELDS]
        for name,p in groups:
            expected=svc.reading(s,name,p)
            self.assertEqual(await self.typed(await self.call(name,p)),['ok',expected['value'],expected['unit'],'local_ipc'])
        self.assertEqual(self.service.subscriptions,1);self.assertEqual(self.service.action_count,0)

    async def test_native_quiet_discovery_and_unobserved_extraction_refusal(self):
        description,messages=wire.fixture('pad','normal')
        with mock.patch.object(wire,'fixture',return_value=(description,messages[:1])):
            handle=(await self.typed(await self.call()))[1]
        self.assertEqual(await self.typed(await self.call('metadata',meta(handle))),['ok',0,'count','local_ipc'])
        self.assertEqual(await self.typed(await self.call('metadata',meta(handle,'observation_state'))),['ok','waiting','state','local_ipc'])
        self.assertEqual(await self.typed(await self.call('control',control(handle))),['ok',0,'code','local_ipc'])
        self.assertEqual(await self.typed(await self.call('button',button(handle))),['unobserved','','boolean','local_ipc'])
        await self.primitive('readingValue',(self.helpers.Var(3),),error=32)
        await self.call('release',{'handle':handle})
        self.assertEqual((await self.typed(await self.call('axis',axis(handle))))[0],'expired_or_unknown')

    async def test_native_loss_false_zero_and_exact_signed_unsigned_clocks(self):
        description,messages=wire.fixture('pad','normal');messages[1]['params']['seq']=2**64-1;messages[1]['params']['at_us']=2**64-1;messages[1]['params']['since_us']=-(2**63)
        messages[1]['params']['events'][0]['value']=0;messages[1]['params']['events'][1]['value']=0
        with mock.patch.object(wire,'fixture',return_value=(description,messages[:2])):
            handle=(await self.typed(await self.call()))[1]
        self.assertEqual(await self.typed(await self.call('axis',axis(handle))),['ok',0,'raw','local_ipc'])
        self.assertEqual(await self.typed(await self.call('button',button(handle))),['ok',False,'boolean','local_ipc'])
        for field,value in [('seq',str(2**64-1)),('at_us',str(2**64-1)),('since_us',str(-(2**63)))]:
            self.assertEqual((await self.typed(await self.call('metadata',meta(handle,field))))[1],value)
        await self.call('release',{'handle':handle})
        description,messages=wire.fixture('pad','normal');messages[-1]['params']['socket_dropped']=1
        with mock.patch.object(wire,'fixture',return_value=(description,messages)):
            dropped=(await self.typed(await self.call()))[1]
        self.assertEqual((await self.typed(await self.call('axis',axis(dropped))))[0],'dropped')
        await self.primitive('readingValue',(self.helpers.Var(3),),error=32)

    async def test_native_decoder_strict_markers_types_sources_and_counter_bounds(self):
        def envelope(value):return json.dumps({'jsonrpc':'2.0','id':1,'result':value})
        good=svc.reading(state(),'axis',axis('a'*32))
        for delta in [{'value':True},{'value':2**30},{'unit':'state'},{'section':'button'},
                      {'simulation':True},{'simulation':False},{'source':'tofd'},{'physical_hardware_verified':True},
                      {'kind':'head_imu_reading'},{'code':65536}]:
            self.assertNotEqual((await self.typed(envelope({**good,**delta})))[0],'ok')
        for primitive in ('headImuReading','depthReading'):
            self.assertNotEqual((await self.typed(envelope(good),primitive))[0],'ok')
        for field,values in [('seq',[str(2**64),'01',True]),('since_us',[str(-(2**63)-1),'-0','01'])]:
            base=svc.reading(state(),'metadata',meta('a'*32,field))
            for value in values:self.assertNotEqual((await self.typed(envelope({**base,'value':value})))[0],'ok')
        descriptor=svc.reading(state(),'control',control('a'*32))
        self.assertNotEqual((await self.typed(envelope({**descriptor,'field':'min','control_kind':'button','unit':'raw'})))[0],'ok')

    async def test_native_bounds_and_disabled_adapter_refuse_before_source_io(self):
        for name,p in [('axis',axis('a'*32,'pressed')),('button',button('a'*32,'raw')),
                       ('control',control('a'*32,'button',1,'min')),('control',control('a'*32,index=65)),
                       ('metadata',meta('a'*32,'node')),('capture',{'path':'/dev/input/event0'})]:
            await self.primitive('begin',(svc.PREFIX+name,json.dumps(p),False),error=32)
        saved=self.normal.gamepad;self.normal.gamepad=None
        try:
            reply=await self.call();self.assertEqual(json.loads(reply)['error']['code'],-32004)
            self.assertEqual((await self.typed(reply))[0],'error')
        finally:self.normal.gamepad=saved
        self.assertEqual(self.service.subscriptions,0)

    async def test_native_utf8_text_survives_actual_moving_gc(self):
        P,V=self.helpers.Program,self.helpers.Var;events=self.runtime.wire.events;s=state();s['device']['name']='é'*64
        reply=json.dumps({'jsonrpc':'2.0','id':1,'result':svc.reading(s,'metadata',meta('a'*32,'device_name'))})
        await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0));start=len(events)
        self.assertEqual((await self.typed(reply))[1],'é'*64)
        self.assertTrue(any(k==20 and i==255 and b'GC took' in b for k,i,b in events[start:]))
        self.assertEqual(await self.primitive('readingValue',(V(3),)),'é'*64)


if __name__=='__main__':
    unittest.main(verbosity=2)
