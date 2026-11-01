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
package = types.ModuleType('head_imu_lab_services')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
imu = importlib.import_module(package.__name__ + '.head_imu_simulator')
rpc = importlib.import_module(package.__name__ + '.protocol')


def request(name, p=None):
    return {'jsonrpc': '2.0', 'id': 1, 'method': imu.PREFIX + name, 'params': p or {}, 'confirmed': False}


def state(profile='normal'):
    description, frame = imu.fixture(profile)
    return {'description': description, 'frame': imu.validate_frame(frame)}


def select(handle, field, component=1):
    return {'handle': handle, 'field': field, 'component': component}


class HeadImuProtocol(unittest.TestCase):
    def test_closed_read_only_methods_and_selectors(self):
        for bad in [request('unknown'), request('capture', {'endpoint': '/run/tofd.sock'}),
                    request('read', select('a' * 32, 'gyro', 4)), request('read', select('a' * 32, 'quat', 5)),
                    request('read', select('a' * 32, 'rate', True)), request('read', select('A' * 32, 'seq')),
                    request('read', {**select('a' * 32, 'gyro'), 'sample': 1}), {**request('capture'), 'confirmed': 1}]:
            with self.assertRaises(rpc.RpcError):
                imu.validate(bad)
        library = (ROOT / 'linux/microduck/Head_IMU_Simulation.ubl').read_text()
        self.assertIn('SIMULATION ONLY', library)
        self.assertNotIn('microduckSimRelay', library)
        self.assertNotIn('true)', (ROOT / 'linux/microduck/head-imu-simulation.ubp').read_text())

    def test_all_source_fields_and_units_without_transform(self):
        s = state()
        cases = [('gyro', 1, 125), ('gyro', 2, -500), ('gyro', 3, 0),
                 ('accel', 3, 9810), ('quat', 1, 1000000), ('quat', 4, 0),
                 ('temperature', 1, 23125), ('sensor', 1, 'BMI088'), ('rate', 1, 100)]
        for field, component, expected in cases:
            value = imu.sample_reading(s, field, component)
            self.assertEqual(value['value'], expected)
            self.assertEqual(value['unit'], imu.FIELDS[field][0])

    def test_finite_f32_shape_and_unsigned_clock_validation(self):
        for delta in [{'gyro': [0, True, 0]}, {'accel': [0, 0]}, {'quat': [0]*5},
                      {'temp_c': float('nan')}, {'temp_c': float('inf')}, {'temp_c': 3.5e38},
                      {'seq': -1}, {'at_us': True}, {'t_ns': 2**64}]:
            with self.assertRaises(rpc.RpcError):
                imu.validate_frame({**state()['frame'], **delta})
        self.assertFalse(imu.number(10**1000))
        self.assertFalse(imu.sensor_name('BMI088/secret'))
        self.assertFalse(imu.sensor_name('é'))
        self.assertTrue(imu.sensor_name('LSM6DSV16X-head_1'))

    def test_missing_and_zero_are_distinct_and_zero_quaternion_is_unusable(self):
        s = state('partial')
        self.assertEqual(imu.sample_reading(s, 'gyro', 1)['value'], 0)
        for field in ('accel', 'quat', 'temperature', 'seq', 'at_us', 't_ns'):
            self.assertEqual(imu.sample_reading(s, field, 1)['status'], 'not_reported')
        self.assertEqual(imu.sample_reading(state('zero_quat'), 'quat', 1)['status'], 'unusable')
        s['frame']['temp_c'] = 0
        self.assertEqual(imu.sample_reading(s, 'temperature', 1)['value'], 0)
        s['description'].pop('hz')
        self.assertEqual(imu.sample_reading(s, 'rate', 1)['status'], 'not_reported')
        s['description']['hz'] = 0
        self.assertEqual(imu.sample_reading(s, 'rate', 1)['value'], 0)

    def test_signed_rounding_and_explicit_fixed_point_overflow(self):
        s = state()
        for raw, expected in [(.0005, 1), (-.0005, -1), (0, 0)]:
            s['frame']['gyro'][0] = raw
            self.assertEqual(imu.sample_reading(s, 'gyro', 1)['value'], expected)
        for raw in (1073741.824, -1073741.825):
            s['frame']['gyro'][0] = raw
            value = imu.sample_reading(s, 'gyro', 1)
            self.assertEqual((value['status'], value['value']), ('out_of_range', None))
        s['frame']['quat'] = [2.0, 0.0, 0.0, 0.0]
        self.assertEqual(imu.sample_reading(s, 'quat', 1)['value'], 2000000)  # no invented normalization

    def test_exact_u64_sender_uptime_and_legacy_clock_semantics(self):
        s = state()
        for field in ('seq', 'at_us', 't_ns'):
            s['frame'][field] = 2**64 - 1
            self.assertEqual(imu.sample_reading(s, field, 1)['value'], str(2**64 - 1))
            s['frame'][field] = 0
            value = imu.sample_reading(s, field, 1)
            self.assertEqual(value['status'], 'not_reported' if field == 't_ns' else 'ok')
            self.assertEqual(value['value'], None if field == 't_ns' else '0')

    def test_validated_frame_copy_is_independent(self):
        frame = state()['frame']
        copied = imu.validate_frame(frame)
        frame['gyro'][0] = 99
        self.assertEqual(copied['gyro'][0], .125)


@unittest.skipUnless(sys.platform == 'linux', 'Linux verified private sockets required')
class HeadImuUnixBackend(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='head-imu-lab-')
        self.base = Path(self.temp.name)
        self.service = await imu.HeadSimulator(self.base / 'sim').start()
        self.robot_calls = []
        original = self.service.result
        def record(method, params):
            self.robot_calls.append(method)
            return original(method, params)
        self.service.result = record

    async def asyncTearDown(self):
        await self.service.stop()
        self.temp.cleanup()

    async def call(self, name='capture', p=None):
        reader, writer = await rpc.connect_checked(self.service.directory / 'gateway.sock', os.geteuid(), imu.wire.LINE_LIMIT, True)
        try:
            writer.write(rpc.encode(request(name, p), imu.wire.LINE_LIMIT))
            await writer.drain()
            return await rpc.read_message(reader, imu.wire.LINE_LIMIT)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_reusable_reader_first_request_has_no_hello_or_simulation_marker(self):
        status, captured = await imu.read_tofd_head(self.service.directory / 'tofd.sock', os.geteuid(), True)
        self.assertEqual(status, 'ok')
        self.assertEqual(captured, state())
        self.assertNotIn('simulation', captured)
        self.assertEqual(self.service.subscriptions, 1)  # fake accepts exact first method only
        with self.assertRaises(rpc.RpcError):
            await imu.read_tofd_head(self.service.directory / 'tofd.sock', os.geteuid() + 1, True)
        self.assertEqual(self.service.subscriptions, 1)  # UID rejected before write
        self.assertEqual(self.robot_calls, [])

    async def test_capture_all_components_has_one_subscription_and_no_renewal(self):
        capture = (await self.call())['result']
        for field, (unit, components) in imu.FIELDS.items():
            for component in range(1, components + 1):
                value = (await self.call('read', select(capture['handle'], field, component)))['result']
                self.assertEqual(value['value'], imu.sample_reading(state(), field, component)['value'])
                self.assertLessEqual(len(rpc.encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': value}, 8192)), 760)
        self.service.profile = 'malformed'
        self.assertEqual((await self.call('read', select(capture['handle'], 'gyro')))['result']['value'], 125)
        self.assertEqual(self.service.subscriptions, 1)

    async def test_availability_wrong_owner_and_empty_never_create_handles(self):
        for profile, status in [('absent', 'absent'), ('wrong_owner', 'absent'), ('refused', 'refused'),
                                ('waiting', 'waiting'), ('pre_ack_timeout', 'timeout'), ('empty', 'not_reported')]:
            self.service.profile = profile
            value = (await self.call())['result']
            self.assertEqual(value['status'], status, profile)
            self.assertNotIn('handle', value)
        self.service.profile = 'malformed'
        self.assertIn('error', await self.call())
        self.assertEqual(self.service.gateway.head.entries, {})
        self.assertEqual(self.robot_calls, [])  # no fallback robot call

    async def test_header_and_frame_fail_closed(self):
        good = imu.fixture('normal')
        for description in ({'accepted': 1}, {'accepted': True, 'sensor': 'bad/name'},
                            {'accepted': True, 'sensor': 'BMI088', 'hz': 256},
                            {'accepted': True, 'sensor': 'BMI088', 'hz': True}):
            with mock.patch.object(imu, 'fixture', return_value=(description, good[1])):
                self.assertIn('error', await self.call())
        with mock.patch.object(imu.wire, 'notification', side_effect=rpc.RpcError(-32011, 'wrong frame')):
            self.assertIn('error', await self.call())
        with mock.patch.object(imu, 'response_result', side_effect=rpc.RpcError(-32011, 'wrong id')):
            self.assertIn('error', await self.call())

    async def test_capacity_expiry_release_and_clock_regression(self):
        store, clock = self.service.gateway.head, [10.0]
        store.clock = lambda: clock[0]
        captures = [(await self.call())['result'] for _ in range(4)]
        self.assertEqual((await self.call())['result']['status'], 'busy')
        self.assertEqual((await self.call('release', {'handle': captures[0]['handle']}))['result']['status'], 'released')
        clock[0] = 15
        self.assertEqual((await self.call('read', select(captures[1]['handle'], 'seq')))['result']['status'], 'expired_or_unknown')
        new = (await self.call())['result']
        clock[0] = 14
        self.assertEqual((await self.call('read', select(new['handle'], 'seq')))['result']['status'], 'expired_or_unknown')

    async def test_inflight_cancellation_releases_reservations(self):
        store, gate = self.service.gateway.head, asyncio.Event()
        async def pending(*args):
            await gate.wait()
        with mock.patch.object(imu, 'read_tofd_head', side_effect=pending):
            tasks = [asyncio.create_task(store.acquire()) for _ in range(4)]
            await asyncio.sleep(.01)
            self.assertEqual(store.pending, 4)
            self.assertEqual((await store.acquire())['status'], 'busy')
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.assertEqual(store.pending, 0)

    async def test_actual_cli_and_failed_metadata_cleanup(self):
        p = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'linux/microduck/head_imu_simulator.py'),
                                                '--directory', str(self.base / 'cli'), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            meta = json.loads(await asyncio.wait_for(p.stdout.readline(), 3))
            self.assertTrue(meta['head_imu_simulation'])
            self.assertFalse(meta['physical_movement_enabled'])
        finally:
            if p.returncode is None:
                p.terminate()
            _, error = await asyncio.wait_for(p.communicate(), 3)
        self.assertEqual(p.returncode, 0, error.decode())
        failed = imu.HeadSimulator(self.base / 'failed')
        original = imu._fresh_file
        def fail_metadata(path, value):
            if path.name == 'head-imu-simulation.json':
                raise OSError('SIMULATION metadata refused')
            return original(path, value)
        with mock.patch.object(imu, '_fresh_file', side_effect=fail_metadata):
            with self.assertRaises(OSError):
                await failed.start()
        self.assertIsNone(failed.gateway)
        self.assertFalse((failed.directory / 'tofd.sock').exists())


SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL = os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform == 'linux' and struct.calcsize('P') == 8 and
                     (EXTERNAL or shutil.which('gcc') and (SOURCE / '.git').is_dir()), 'native LP64 compiler/source required')
class HeadImuNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='head-imu-native-')
        cls.base = Path(cls.temp.name)
        if EXTERNAL:
            cls.binary = Path(EXTERNAL)
        else:
            p = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE),
                                '--output', str(cls.base / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
            if p.returncode:
                raise AssertionError(p.stdout + p.stderr)
            cls.binary = cls.base / 'build/smallvm'
        spec = importlib.util.spec_from_file_location('head_imu_vm_helpers', ROOT / 'tests/test_linux_microduck_vm.py')
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.service = await imu.HeadSimulator(self.work / 'sim').start()
        self.service.gateway.head.clock = lambda: 0.0
        data = self.work / 'programs'
        data.mkdir(mode=0o700)
        self.runtime = await asyncio.to_thread(self.helpers.Runtime, self.binary, data, self.service.directory / 'gateway.sock')

    async def asyncTearDown(self):
        await asyncio.to_thread(self.runtime.stop)
        log = self.runtime.log_path.read_text()
        self.assertEqual(self.runtime.process.returncode, 0, log)
        self.assertNotIn('AddressSanitizer', log)
        self.assertNotIn('runtime error:', log)
        await self.service.stop()

    async def primitive(self, name, args=(), error=None, command=False):
        return await asyncio.to_thread(self.runtime.primitive, name, args, error, command)

    async def execute(self, p):
        return await asyncio.to_thread(self.runtime.execute, p.finish())

    async def call(self, name='capture', p=None):
        job = await self.primitive('begin', (imu.PREFIX + name, json.dumps(p or {}), False))
        deadline = asyncio.get_running_loop().time() + 4
        while await self.primitive('status', (job,)) == 'pending':
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        result = await self.primitive('result', (job,))
        await self.primitive('release', (job,), command=True)
        return result

    async def typed(self, reply, primitive='headImuSample'):
        P, V = self.helpers.Program, self.helpers.Var
        await self.execute(P().call(primitive, (reply,)).op(7, 3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81, 2)) for i in range(1, 5)]

    async def test_real_vm_all_nine_fields_all_components_exact_time_and_one_subscription(self):
        captured = await self.typed(await self.call())
        self.assertEqual(captured[0], 'ok')
        for field, (unit, components) in imu.FIELDS.items():
            for component in range(1, components + 1):
                actual = await self.typed(await self.call('read', select(captured[1], field, component)))
                self.assertEqual(actual, ['ok', imu.sample_reading(state(), field, component)['value'], unit, 'simulation'])
        self.assertEqual(self.service.subscriptions, 1)

    async def test_native_bounds_reject_before_io(self):
        for p in [select('a' * 32, 'gyro', 4), select('a' * 32, 'quat', 5), select('A' * 32, 'seq'),
                  select('a' * 32, 'unknown'), {**select('a' * 32, 'gyro'), 'sample': 1}]:
            await self.primitive('begin', (imu.PREFIX + 'read', json.dumps(p), False), error=32)
        self.assertEqual(self.service.subscriptions, 0)

    async def test_native_absence_timeout_partial_zero_and_unusable(self):
        for profile, status in [('absent', 'absent'), ('wrong_owner', 'absent'), ('refused', 'refused'),
                                ('waiting', 'waiting'), ('pre_ack_timeout', 'timeout'), ('empty', 'not_reported')]:
            self.service.profile = profile
            self.assertEqual(await self.typed(await self.call()), [status, '', 'snapshot', 'simulation'])
        for profile, field, expected in [('partial', 'gyro', ['ok', 0, 'mrad/s', 'simulation']),
                                         ('partial', 'accel', ['not_reported', '', 'mm/s2', 'simulation']),
                                         ('zero_quat', 'quat', ['unusable', '', 'ppm', 'simulation']),
                                         ('legacy_clock', 't_ns', ['not_reported', '', 'ns', 'simulation'])]:
            self.service.profile = profile
            handle = (await self.typed(await self.call()))[1]
            self.assertEqual(await self.typed(await self.call('read', select(handle, field))), expected)
            if expected[0] != 'ok':
                await self.primitive('readingValue', (self.helpers.Var(3),), error=32)
            await self.call('release', {'handle': handle})

    async def test_native_decoder_strict_types_units_ranges_and_cross_kind(self):
        def envelope(value):
            return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': value})
        good = imu.sample_reading(state(), 'seq', 1)
        gyro = imu.sample_reading(state(), 'gyro', 1)
        sensor = imu.sample_reading(state(), 'sensor', 1)
        rate = imu.sample_reading(state(), 'rate', 1)
        for bad in [{**good, 'value': str(2**64)}, {**good, 'value': '01'}, {**good, 'unit': 'us'},
                    {**good, 'component': 2}, {**good, 'kind': 'pad_imu_reading'}, {**gyro, 'value': True},
                    {**gyro, 'value': 2**30}, {**sensor, 'value': 'bad/name'}, {**sensor, 'value': 'é'},
                    {**sensor, 'value': 'x'*65}, {**rate, 'value': 256}, {**rate, 'value': True},
                    imu.result('head_imu_capture', 'ok', handle='A'*32)]:
            self.assertNotEqual((await self.typed(envelope(bad)))[0], 'ok')
        self.assertEqual((await self.typed(envelope({**good, 'value': str(2**64-1)})))[1], str(2**64-1))
        self.assertEqual((await self.typed(envelope({**sensor, 'value': 'x'*64})))[1], 'x'*64)
        self.assertNotEqual((await self.typed(envelope(good), 'imuSample'))[0], 'ok')

    async def test_native_release_expiry_and_legacy_zero_clock(self):
        handle = (await self.typed(await self.call()))[1]
        await self.call('release', {'handle': handle})
        self.assertEqual((await self.typed(await self.call('read', select(handle, 'seq'))))[:2], ['expired_or_unknown', ''])
        good = imu.sample_reading(state(), 't_ns', 1)
        reply = json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {**good, 'value': '0'}})
        self.assertEqual(await self.typed(reply), ['not_reported', '', 'ns', 'simulation'])

    async def test_native_text_allocation_survives_moving_gc(self):
        P, V = self.helpers.Program, self.helpers.Var
        events = self.runtime.wire.events
        await self.execute(P().call('newByteArray', (262080,), prim_set=1).op(19, 1).push(0))
        start = len(events)
        reply = json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': imu.sample_reading(state(), 'sensor', 1)})
        self.assertEqual((await self.typed(reply))[1], 'BMI088')
        self.assertTrue(any(k == 20 and i == 255 and b'GC took' in b for k, i, b in events[start:]))
        self.assertEqual(await self.primitive('readingValue', (V(3),)), 'BMI088')


if __name__ == '__main__':
    unittest.main(verbosity=2)
