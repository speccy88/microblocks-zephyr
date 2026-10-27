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
package = types.ModuleType('head_service_tests')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
imu = importlib.import_module(package.__name__ + '.head_imu_simulator')
svc = importlib.import_module(package.__name__ + '.head_imu_service')
gateway = importlib.import_module(package.__name__ + '.gateway')
rpc = importlib.import_module(package.__name__ + '.protocol')


def request(name='capture', p=None):
    return {'jsonrpc': '2.0', 'id': 1, 'method': svc.PREFIX + name, 'params': p or {}, 'confirmed': False}


def select(handle, field, component=1):
    return {'handle': handle, 'field': field, 'component': component}


def source(path, uid=None):
    return {'version': 1, 'daemon': 'tofd', 'path': str(path), 'uid': os.geteuid() if uid is None else uid}


async def normal_gateway(directory, path, uid=None):
    directory.mkdir(mode=0o700)
    config = directory / 'head.json'
    config.write_text(json.dumps(source(path, uid)))
    config.chmod(0o600)
    service = gateway.Gateway({}, head_imu=svc.load_source(config))
    await service.start(directory / 'gateway.sock')
    return service


class HeadServiceConfig(unittest.TestCase):
    def test_config_is_explicit_closed_and_tofd_only(self):
        good = {'version': 1, 'daemon': 'tofd', 'path': '/run/tofd.sock', 'uid': 1000}
        self.assertEqual(svc.validate_source(good), good)
        for delta in [{'version': True}, {'daemon': 'robotd'}, {'uid': True}, {'uid': -1},
                      {'path': 'tofd.sock'}, {'path': '/run/\x00sock'}, {'path': '/'+'a'*104}, {'discover': True}]:
            with self.assertRaises(ValueError):
                svc.validate_source({**good, **delta})

    def test_read_only_methods_have_no_endpoint_or_mutation_parameters(self):
        for q in [request('enable'), request('capture', {'path': '/run/tofd.sock'}),
                  request('read', select('a'*32, 'quat', 5)), request('read', select('A'*32, 'seq')),
                  request('read', {**select('a'*32, 'gyro'), 'sample': 1}), {**request(), 'confirmed': 1}]:
            with self.assertRaises(rpc.RpcError):
                svc.validate(q)
        self.assertEqual(svc.validate(request()), ('capture', {}))

    def test_local_ipc_reports_transport_without_reclassifying_hardware(self):
        description, frame = imu.fixture('normal')
        value = imu.sample_reading({'description': description, 'frame': frame}, 'gyro', 1, svc.result)
        self.assertEqual((value['value'], value['origin']), (125, 'local_ipc'))
        self.assertNotIn('simulation', value)
        self.assertIs(value['physical_hardware_verified'], False)
        self.assertIs(value['physical_movement_enabled'], False)

    def test_editor_library_uses_normal_methods_and_separate_decoder(self):
        library = (ROOT / 'linux/microduck/Head_IMU.ubl').read_text()
        self.assertIn('[microduck:headImuReading]', library)
        self.assertIn('microduck.headImu.capture', library)
        self.assertIn('local_ipc', library)
        self.assertNotIn('microduck.headImuSim.', library)
        self.assertNotIn('microduckHeadImu', (ROOT / 'linux/microduck/Head_IMU_Simulation.ubl').read_text())


@unittest.skipUnless(sys.platform == 'linux', 'Linux verified private sockets required')
class HeadServiceUnix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='head-service-')
        self.base = Path(self.temp.name)
        self.fixture = await imu.HeadSimulator(self.base / 'fixture').start()
        self.normal = await normal_gateway(self.base / 'normal', self.fixture.directory / 'tofd.sock')

    async def asyncTearDown(self):
        await self.normal.stop()
        await self.fixture.stop()
        self.temp.cleanup()

    async def call(self, q=None):
        reader, writer = await rpc.connect_checked(self.base / 'normal/gateway.sock', os.geteuid(), rpc.MAX_REPLY, True)
        try:
            writer.write(rpc.encode(q or request(), rpc.MAX_REQUEST))
            await writer.drain()
            return await rpc.read_message(reader, rpc.MAX_REPLY)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_private_config_permissions_symlinks_duplicates_and_oversize(self):
        config = self.base / 'normal/head.json'
        config.chmod(0o644)
        with self.assertRaises(ValueError):
            svc.load_source(config)
        config.chmod(0o600)
        alias = config.with_name('alias.json')
        alias.symlink_to(config)
        with self.assertRaises(OSError):
            svc.load_source(alias)
        for raw in ('{"version":1,"version":1}', 'x'*8193):
            config.write_text(raw)
            with self.assertRaises((ValueError, rpc.RpcError)):
                svc.load_source(config)

    async def test_normal_gateway_all_nine_fields_one_subscription_and_no_simulation_claim(self):
        handle = (await self.call())['result']['handle']
        for field, (_, components) in imu.FIELDS.items():
            for component in range(1, components + 1):
                value = (await self.call(request('read', select(handle, field, component))))['result']
                self.assertEqual(value['status'], 'ok')
                self.assertEqual(value['origin'], 'local_ipc')
                self.assertNotIn('simulation', value)
                self.assertFalse(value['physical_hardware_verified'])
        self.assertEqual(self.fixture.subscriptions, 1)
        self.assertEqual(self.fixture.action_count, 0)

    async def test_wrong_source_uid_rejected_before_request_write(self):
        self.normal.head_imu.config['uid'] = os.geteuid() + 1
        self.assertIn('error', await self.call())
        self.assertEqual(self.fixture.subscriptions, 0)
        self.assertEqual(self.normal.head_imu.entries, {})

    async def test_capabilities_disabled_routes_and_protected_methods(self):
        caps = (await self.call({'jsonrpc':'2.0','id':1,'method':'microduck.capabilities','params':{}}))['result']
        self.assertTrue(caps['read_only_adapters']['head_imu']['configured'])
        self.assertEqual(set(caps['methods']), svc.METHODS)
        self.assertEqual(caps['allowed_mutations'], [])
        for method in ('robot.move','robot.enable','head_imu.stream','microduck.headImuSim.capture'):
            q = {'jsonrpc':'2.0','id':1,'method':method,'params':{}}
            self.assertIn('error', await self.call(q))
        saved = self.normal.head_imu
        try:
            self.normal.head_imu = None
            self.assertEqual((await self.call())['error']['code'], -32004)
        finally:
            self.normal.head_imu = saved

    async def test_absence_malformed_and_partial_are_not_defaults(self):
        for profile, status in [('wrong_owner','absent'),('refused','refused'),('waiting','waiting')]:
            self.fixture.profile = profile
            value = (await self.call())['result']
            self.assertEqual(value['status'], status)
            self.assertNotIn('handle', value)
        self.fixture.profile = 'malformed'
        self.assertIn('error', await self.call())
        self.fixture.profile = 'partial'
        handle = (await self.call())['result']['handle']
        self.assertEqual((await self.call(request('read', select(handle,'gyro'))))['result']['value'], 0)
        self.assertEqual((await self.call(request('read', select(handle,'accel'))))['result']['status'], 'not_reported')

    async def test_expiry_and_shutdown_clear_retained_state(self):
        clock = [10.0]
        store = self.normal.head_imu
        store.clock = lambda: clock[0]
        handle = (await self.call())['result']['handle']
        clock[0] = 15
        self.assertEqual((await self.call(request('read', select(handle,'seq'))))['result']['status'], 'expired_or_unknown')
        await self.call()
        self.assertTrue(store.entries)
        await self.normal.stop()
        self.assertEqual(store.entries, {})

    async def test_shutdown_cancels_actual_pending_subscription_and_releases_capacity(self):
        self.fixture.profile = 'waiting'
        pending = asyncio.create_task(self.call())
        for _ in range(100):
            if self.fixture.subscriptions:
                break
            await asyncio.sleep(.002)
        self.assertEqual(self.normal.head_imu.pending, 1)
        await self.normal.stop()
        await asyncio.gather(pending, return_exceptions=True)
        for _ in range(100):
            if not self.fixture.active:
                break
            await asyncio.sleep(.002)
        self.assertEqual(self.normal.head_imu.pending, 0)
        self.assertEqual(self.fixture.active, 0)

    async def test_actual_gateway_cli_with_separate_private_source_config(self):
        config = self.base / 'normal/gateway.json'
        config.write_text('{"version":1,"upstreams":{}}')
        config.chmod(0o600)
        p = await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/gateway.py'),
            '--socket',str(self.base/'normal/cli.sock'),'--config',str(config),
            '--head-imu-config',str(self.base/'normal/head.json'),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            line = await asyncio.wait_for(p.stdout.readline(), 3)
            self.assertIn(b'gateway ready', line)
            reader, writer = await rpc.connect_checked(self.base/'normal/cli.sock',os.geteuid(),rpc.MAX_REPLY,True)
            try:
                writer.write(rpc.encode(request(),rpc.MAX_REQUEST));await writer.drain()
                value = await rpc.read_message(reader,rpc.MAX_REPLY)
                self.assertEqual(value['result']['origin'],'local_ipc')
                self.assertEqual(value['result']['status'],'ok')
            finally:
                writer.close();await writer.wait_closed()
        finally:
            if p.returncode is None:
                p.terminate()
            _, error = await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode())




    async def test_user_fixture_cli_runs_normal_gateway_with_explicit_simulated_input(self):
        directory = self.base/'demo'
        p = await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/head_imu_gateway_fixture.py'),
            '--directory',str(directory),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            ready = json.loads(await asyncio.wait_for(p.stdout.readline(),3))
            self.assertTrue(ready['simulation'])
            self.assertTrue(ready['normal_gateway'])
            self.assertFalse(ready['physical_hardware_verified'])
            reader,writer = await rpc.connect_checked(Path(ready['gateway_socket']),os.geteuid(),rpc.MAX_REPLY,True)
            try:
                writer.write(rpc.encode(request(),rpc.MAX_REQUEST));await writer.drain()
                value = await rpc.read_message(reader,rpc.MAX_REPLY)
                self.assertEqual(value['result']['origin'],'local_ipc')
                self.assertEqual(value['result']['status'],'ok')
            finally:
                writer.close();await writer.wait_closed()
        finally:
            if p.returncode is None:
                p.terminate()
            _,error = await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode())
        self.assertFalse((directory/'normal/gateway.sock').exists())
        self.assertFalse((directory/'source/tofd.sock').exists())


SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL = os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform == 'linux' and struct.calcsize('P') == 8 and
                     (EXTERNAL or shutil.which('gcc') and (SOURCE / '.git').is_dir()), 'native LP64 compiler/source required')
class HeadServiceNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='head-service-native-')
        cls.base = Path(cls.temp.name)
        if EXTERNAL:
            cls.binary = Path(EXTERNAL)
        else:
            p = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE),
                                '--output', str(cls.base / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
            if p.returncode:
                raise AssertionError(p.stdout + p.stderr)
            cls.binary = cls.base / 'build/smallvm'
        spec = importlib.util.spec_from_file_location('head_service_vm_helpers', ROOT / 'tests/test_linux_microduck_vm.py')
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.service = await imu.HeadSimulator(self.work / 'sim').start()
        self.normal = await normal_gateway(self.work / 'normal', self.service.directory / 'tofd.sock')
        self.normal.head_imu.clock = lambda: 0.0
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

    async def typed(self, reply, primitive='headImuReading'):
        P, V = self.helpers.Program, self.helpers.Var
        await self.execute(P().call(primitive, (reply,)).op(7, 3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81, 2)) for i in range(1, 5)]

    async def test_normal_vm_all_fields_have_local_ipc_origin_and_one_subscription(self):
        capture = await self.typed(await self.call())
        self.assertEqual(capture[0], 'ok')
        description, frame = imu.fixture('normal')
        for field, (unit, components) in imu.FIELDS.items():
            for component in range(1, components+1):
                actual = await self.typed(await self.call('read',select(capture[1],field,component)))
                expected = imu.sample_reading({'description':description,'frame':frame},field,component,svc.result)
                self.assertEqual(actual,['ok',expected['value'],unit,'local_ipc'])
        self.assertEqual(self.service.subscriptions,1)
        self.assertEqual(self.service.action_count,0)

    async def test_native_service_and_simulation_envelopes_are_distinct(self):
        description, frame = imu.fixture('normal')
        state = {'description':description,'frame':frame}
        live = imu.sample_reading(state,'seq',1,svc.result)
        simulated = imu.sample_reading(state,'seq',1)
        def envelope(v):return json.dumps({'jsonrpc':'2.0','id':1,'result':v})
        self.assertNotEqual((await self.typed(envelope(simulated)))[0],'ok')
        self.assertNotEqual((await self.typed(envelope(live),'headImuSample'))[0],'ok')
        for bad in [{**live,'simulation':True},{**live,'simulation':False},
                    {**live,'physical_hardware_verified':True},{**live,'source':'robotd'},
                    {**live,'physical_movement_enabled':True},{**live,'origin':'physical'}]:
            self.assertNotEqual((await self.typed(envelope(bad)))[0],'ok')

    async def test_native_unavailable_is_not_extractable_and_release_expires(self):
        self.service.profile = 'partial'
        handle = (await self.typed(await self.call()))[1]
        self.assertEqual(await self.typed(await self.call('read',select(handle,'accel'))),['not_reported','','mm/s2','local_ipc'])
        await self.primitive('readingValue',(self.helpers.Var(3),),error=32)
        self.assertEqual(await self.typed(await self.call('read',select(handle,'gyro'))),['ok',0,'mrad/s','local_ipc'])
        await self.call('release',{'handle':handle})
        self.assertEqual((await self.typed(await self.call('read',select(handle,'seq'))))[:2],['expired_or_unknown',''])

    async def test_native_selector_bounds_reject_before_io(self):
        for p in [select('a'*32,'gyro',4),select('a'*32,'quat',5),select('A'*32,'seq'),
                  {**select('a'*32,'gyro'),'path':'/run/tofd.sock'}]:
            await self.primitive('begin',(svc.PREFIX+'read',json.dumps(p),False),error=32)
        self.assertEqual(self.service.subscriptions,0)

    async def test_native_adapter_disabled_is_explicit_error(self):
        saved = self.normal.head_imu
        try:
            self.normal.head_imu = None
            reply = await self.call()
            self.assertEqual(json.loads(reply)['error']['code'],-32004)
            self.assertEqual((await self.typed(reply))[0],'error')
        finally:
            self.normal.head_imu = saved
        self.assertEqual(self.service.subscriptions,0)

    async def test_native_local_ipc_counter_survives_moving_gc(self):
        P,V = self.helpers.Program,self.helpers.Var
        description,frame = imu.fixture('normal')
        reply = json.dumps({'jsonrpc':'2.0','id':1,'result':imu.sample_reading({'description':description,'frame':frame},'t_ns',1,svc.result)})
        await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0))
        events = self.runtime.wire.events;start = len(events)
        self.assertEqual((await self.typed(reply))[1],str(2**63+77))
        self.assertTrue(any(k==20 and i==255 and b'GC took' in b for k,i,b in events[start:]))
        self.assertEqual(await self.primitive('readingValue',(V(3),)),str(2**63+77))


if __name__ == '__main__':
    unittest.main(verbosity=2)
