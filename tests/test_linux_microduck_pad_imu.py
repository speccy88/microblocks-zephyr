"""Coherent typed gamepad IMU snapshots against fixed fake Unix services."""
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
package = types.ModuleType('pad_imu_lab_services')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
imu = importlib.import_module(package.__name__ + '.pad_imu_simulator')
rpc = importlib.import_module(package.__name__ + '.protocol')


def request(name, p=None):
    return {'jsonrpc': '2.0', 'id': 1, 'method': imu.PREFIX + name, 'params': p or {}, 'confirmed': False}


def state(profile='normal'):
    _, reports = imu.fixture(profile)
    return {'device': imu.validate_device(reports[0]['device']), 'samples': imu.validate_batch(reports[1])}


def select(handle, field, sample=1, component=1):
    return {'handle': handle, 'field': field, 'sample': sample, 'component': component}


class PadImuProtocol(unittest.TestCase):
    def test_closed_read_only_methods_and_selectors(self):
        for bad in [request('unknown'), request('capturePad', {'endpoint': 'invalid'}),
                    request('read', select('a' * 32, 'accel_raw', component=4)),
                    request('read', select('a' * 32, 'sample_count', sample=2)),
                    request('read', select('A' * 32, 'seq')), request('read', select('a' * 32, 'gyro_raw', sample=True)),
                    {**request('capturePad'), 'confirmed': 1}]:
            with self.assertRaises(rpc.RpcError):
                imu.validate(bad)
        library = (ROOT / 'linux/microduck/Pad_IMU_Simulation.ubl').read_text()
        self.assertIn('SIMULATION ONLY', library)
        self.assertNotIn('microduckSimRelay', library)
        self.assertNotIn('true)', (ROOT / 'linux/microduck/pad-imu-simulation.ubp').read_text())

    def test_device_requires_reported_nonnegative_resolutions_not_assumptions(self):
        original = state()['device']
        for delta in [{'accel_per_g': -1}, {'gyro_per_dps': True}, {'accel_max': 2**31}, {'node': ''}]:
            with self.assertRaises(rpc.RpcError):
                imu.validate_device({**original, **delta})
        unknown = state('unscaled')
        self.assertEqual(imu.sample_reading(unknown, 'accel_mg', 1, 1)['status'], 'not_reported')
        self.assertEqual(imu.sample_reading(unknown, 'accel_raw', 1, 1)['value'], 0)
        self.assertEqual(imu.sample_reading(unknown, 'gyro_per_dps', 1, 1)['value'], 0)

    def test_batch_bounds_shape_loss_and_nonconsecutive_sequences(self):
        _, reports = imu.fixture('normal')
        good = reports[1]
        for samples in ([], good['samples'] * 11, [{'seq': True, 'at_us': 0, 'accel': [0]*3, 'gyro': [0]*3}]):
            with self.assertRaises(rpc.RpcError):
                imu.validate_batch({'samples': samples})
        self.assertIsNone(imu.validate_batch({**good, 'socket_dropped': 1}))
        bad = copy.deepcopy(good)
        bad['samples'][1]['seq'] += 1
        self.assertIsNone(imu.validate_batch(bad))
        bad = copy.deepcopy(good)
        bad['samples'][0]['gyro'][0] = 2**31
        with self.assertRaises(rpc.RpcError):
            imu.validate_batch(bad)

    def test_exact_scale_signed_rounding_zero_and_overflow(self):
        s = state()
        cases = [('accel_mg', 1, 0), ('accel_mg', 2, -1000), ('accel_mg', 3, 500),
                 ('gyro_mdps', 1, 1000), ('gyro_mdps', 2, 0), ('gyro_mdps', 3, -500)]
        for field, component, value in cases:
            self.assertEqual(imu.sample_reading(s, field, 1, component)['value'], value)
        s['device']['accel_per_g'] = 2000
        for raw, expected in [(1, 1), (-1, -1), (0, 0)]:
            s['samples'][0]['accel'][0] = raw
            self.assertEqual(imu.sample_reading(s, 'accel_mg', 1, 1)['value'], expected)
        s['samples'][0]['accel'][0] = -(2**31)
        self.assertEqual(imu.sample_reading(s, 'accel_raw', 1, 1)['status'], 'out_of_range')
        s['device']['accel_per_g'] = 1
        self.assertEqual(imu.sample_reading(s, 'accel_mg', 1, 1)['status'], 'out_of_range')

    def test_reported_limits_are_boolean_or_unknown(self):
        s = state()
        self.assertIs(imu.sample_reading(s, 'accel_at_limit', 1, 1)['value'], False)
        s['samples'][0]['accel'][0] = -s['device']['accel_max']
        self.assertIs(imu.sample_reading(s, 'accel_at_limit', 1, 1)['value'], True)
        s['device']['accel_max'] = 0
        self.assertEqual(imu.sample_reading(s, 'accel_at_limit', 1, 1)['status'], 'not_reported')

    def test_exact_u64_and_wall_clock_regression_preserve_order(self):
        s = state()
        s['samples'][0]['seq'] = 2**64 - 1
        self.assertEqual(imu.sample_reading(s, 'seq', 1, 1)['value'], str(2**64 - 1))
        _, reports = imu.fixture('normal')
        reports[1]['samples'][1]['at_us'] = 0
        samples = imu.validate_batch(reports[1])
        self.assertEqual(samples[1]['at_us'], 0)
        self.assertEqual([p['seq'] for p in samples], [2**63, 2**63 + 1, 2**63 + 2])

    def test_sample_range_metadata_and_validated_copies_are_independent(self):
        s = state()
        self.assertEqual(imu.sample_reading(s, 'sample_count', 1, 1)['value'], 3)
        self.assertEqual(imu.sample_reading(s, 'accel_raw', 4, 1)['status'], 'not_reported')
        _, reports = imu.fixture('normal')
        copied = imu.validate_batch(reports[1])
        reports[1]['samples'][0]['accel'][0] = 99
        self.assertEqual(copied[0]['accel'][0], 0)


@unittest.skipUnless(sys.platform == 'linux', 'Linux verified private sockets required')
class PadImuUnixBackend(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='pad-imu-lab-')
        self.base = Path(self.temp.name)
        self.service = await imu.ImuSimulator(self.base / 'sim').start()

    async def asyncTearDown(self):
        await self.service.stop()
        self.temp.cleanup()

    async def call(self, name='capturePad', p=None):
        reader, writer = await rpc.connect_checked(self.service.directory / 'gateway.sock', os.geteuid(), imu.wire.LINE_LIMIT, True)
        try:
            writer.write(rpc.encode(request(name, p), imu.wire.LINE_LIMIT))
            await writer.drain()
            return await rpc.read_message(reader, imu.wire.LINE_LIMIT)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_capture_whole_batch_and_all_queries_issue_one_subscription(self):
        capture = (await self.call())['result']
        self.assertEqual(capture['sample_count'], 3)
        self.assertEqual(self.service.subscriptions, 1)
        for field, (unit, components) in imu.FIELDS.items():
            value = (await self.call('read', select(capture['handle'], field)))['result']
            self.assertEqual(value['status'], 'ok', field)
            self.assertEqual(value['unit'], unit)
            self.assertLessEqual(len(rpc.encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': value}, 8192)), 760)
        self.service.imu_profile = 'dropped'
        self.assertEqual((await self.call('read', select(capture['handle'], 'accel_mg', 2, 3)))['result']['value'], 500)
        self.assertEqual(self.service.subscriptions, 1)

    async def test_availability_loss_and_malformed_profiles_never_create_handles(self):
        expected = {'dropped': 'dropped', 'no_imu': 'not_reported', 'waiting': 'waiting',
                    'detached': 'detached', 'refused': 'refused', 'bad_order': 'dropped'}
        for profile, status in expected.items():
            self.service.imu_profile = profile
            value = (await self.call())['result']
            self.assertEqual(value['status'], status)
            self.assertNotIn('handle', value)
        self.service.imu_profile = 'oversized'
        self.assertIn('error', await self.call())
        self.assertEqual(self.service.gateway.imu.entries, {})

    async def test_metadata_before_sample_and_independent_imu_lifecycle(self):
        _, reports = imu.fixture('normal')
        with mock.patch.object(imu, 'fixture', return_value=({'accepted': True}, [reports[1]])):
            self.assertIn('error', await self.call())
        notes = [reports[0], {'report': 'detached', 'why': 'SIMULATION pad node, not IMU'}, reports[1]]
        with mock.patch.object(imu, 'fixture', return_value=({'accepted': True}, notes)):
            self.assertEqual((await self.call())['result']['status'], 'ok')

    async def test_capacity_expiry_release_and_clock_regression(self):
        store = self.service.gateway.imu
        clock = [10.0]
        store.clock = lambda: clock[0]
        captures = [(await self.call())['result'] for _ in range(4)]
        self.assertEqual((await self.call())['result']['status'], 'busy')
        self.assertEqual((await self.call('release', {'handle': captures[0]['handle']}))['result']['status'], 'released')
        clock[0] = 15
        self.assertEqual((await self.call('read', select(captures[1]['handle'], 'seq')))['result']['status'], 'expired_or_unknown')
        new = (await self.call())['result']
        clock[0] = 14
        self.assertEqual((await self.call('read', select(new['handle'], 'seq')))['result']['status'], 'expired_or_unknown')

    async def test_inflight_reservations_and_cancellation_release_capacity(self):
        store = self.service.gateway.imu
        gate = asyncio.Event()
        async def pending(directory):
            await gate.wait()
        with mock.patch.object(imu, 'capture', side_effect=pending):
            tasks = [asyncio.create_task(store.acquire()) for _ in range(4)]
            await asyncio.sleep(.01)
            self.assertEqual(store.pending, 4)
            self.assertEqual((await store.acquire())['status'], 'busy')
            for t in tasks:
                t.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
        self.assertEqual(store.pending, 0)

    async def test_event_cap_and_unknown_scale_are_explicit(self):
        notes = [{'report': 'frame'}] * imu.wire.EVENTS
        with mock.patch.object(imu, 'fixture', return_value=({'accepted': True}, notes)):
            self.assertEqual((await self.call())['result']['status'], 'event_limit')
        self.service.imu_profile = 'unscaled'
        capture = (await self.call())['result']
        self.assertEqual((await self.call('read', select(capture['handle'], 'accel_mg')))['result']['status'], 'not_reported')
        self.assertEqual((await self.call('read', select(capture['handle'], 'accel_raw')))['result']['value'], 0)

    async def test_actual_cli_and_failed_metadata_cleanup(self):
        p = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'linux/microduck/pad_imu_simulator.py'),
                                                '--directory', str(self.base / 'cli'), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            meta = json.loads(await asyncio.wait_for(p.stdout.readline(), 3))
            self.assertTrue(meta['pad_imu_simulation'])
            self.assertFalse(meta['physical_movement_enabled'])
        finally:
            if p.returncode is None:
                p.terminate()
            _, error = await asyncio.wait_for(p.communicate(), 3)
        self.assertEqual(p.returncode, 0, error.decode())
        failed = imu.ImuSimulator(self.base / 'failed')
        original = imu.wire._fresh_file
        def fail_media(path, value):
            if path.name == 'pad-imu-simulation.json':
                raise OSError('SIMULATION metadata refused')
            return original(path, value)
        with mock.patch.object(imu.wire, '_fresh_file', side_effect=fail_media):
            with self.assertRaises(OSError):
                await failed.start()
        self.assertIsNone(failed.gateway)
        self.assertFalse((failed.directory / 'pad.sock').exists())


SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL = os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform == 'linux' and struct.calcsize('P') == 8 and
                     (EXTERNAL or shutil.which('gcc') and (SOURCE / '.git').is_dir()), 'native LP64 compiler/source required')
class PadImuNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='pad-imu-native-')
        cls.base = Path(cls.temp.name)
        if EXTERNAL:
            cls.binary = Path(EXTERNAL)
        else:
            p = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE),
                                '--output', str(cls.base / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
            if p.returncode:
                raise AssertionError(p.stdout + p.stderr)
            cls.binary = cls.base / 'build/smallvm'
        spec = importlib.util.spec_from_file_location('pad_imu_vm_helpers', ROOT / 'tests/test_linux_microduck_vm.py')
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.service = await imu.ImuSimulator(self.work / 'sim').start()
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

    async def call(self, name='capturePad', p=None):
        job = await self.primitive('begin', (imu.PREFIX + name, json.dumps(p or {}), False))
        deadline = asyncio.get_running_loop().time() + 4
        while await self.primitive('status', (job,)) == 'pending':
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        result = await self.primitive('result', (job,))
        await self.primitive('release', (job,), command=True)
        return result

    async def typed(self, reply):
        P, V = self.helpers.Program, self.helpers.Var
        await self.execute(P().call('imuSample', (reply,)).op(7, 3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81, 2)) for i in range(1, 5)]

    async def test_real_vm_coherent_batch_all_thirteen_fields_and_samples(self):
        self.service.gateway.imu.clock = lambda: 0.0
        captured = await self.typed(await self.call())
        self.assertEqual(captured[0], 'ok')
        handle = captured[1]
        s = state()
        for field, (unit, components) in imu.FIELDS.items():
            actual = await self.typed(await self.call('read', select(handle, field)))
            expected = imu.sample_reading(s, field, 1, 1)
            self.assertEqual(actual, ['ok', expected['value'], unit, 'simulation'], field)
        for sample in (1, 2, 3):
            value = await self.typed(await self.call('read', select(handle, 'seq', sample)))
            self.assertEqual(value[1], str(2**63 + sample - 1))
        self.assertEqual(self.service.subscriptions, 1)

    async def test_native_bounds_reject_before_io(self):
        for p in [select('a' * 32, 'gyro_raw', component=4), select('a' * 32, 'sample_count', sample=2),
                  select('A' * 32, 'seq'), select('a' * 32, 'unknown')]:
            await self.primitive('begin', (imu.PREFIX + 'read', json.dumps(p), False), error=32)
        self.assertEqual(self.service.subscriptions, 0)

    async def test_native_unknown_scale_reported_limit_and_numeric_overflow(self):
        self.service.imu_profile = 'unscaled'
        handle = (await self.typed(await self.call()))[1]
        self.assertEqual(await self.typed(await self.call('read', select(handle, 'accel_raw'))), ['ok', 0, 'raw', 'simulation'])
        self.assertEqual(await self.typed(await self.call('read', select(handle, 'accel_mg'))), ['not_reported', '', 'mg', 'simulation'])
        await self.primitive('readingValue', (self.helpers.Var(3),), error=32)
        normal = state()
        normal['samples'][0]['accel'][0] = -(2**31)
        reply = json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': imu.sample_reading(normal, 'accel_raw', 1, 1)})
        self.assertEqual(await self.typed(reply), ['out_of_range', '', 'raw', 'simulation'])
        reply = json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': imu.sample_reading(normal, 'accel_at_limit', 1, 1)})
        self.assertEqual(await self.typed(reply), ['ok', True, 'boolean', 'simulation'])

    async def test_native_lifecycle_unavailable_and_release(self):
        for profile, status in [('dropped', 'dropped'), ('no_imu', 'not_reported'), ('waiting', 'waiting'),
                                ('detached', 'detached'), ('refused', 'refused'), ('bad_order', 'dropped')]:
            self.service.imu_profile = profile
            self.assertEqual(await self.typed(await self.call()), [status, '', 'snapshot', 'simulation'])
        self.service.imu_profile = 'normal'
        handle = (await self.typed(await self.call()))[1]
        await self.call('release', {'handle': handle})
        self.assertEqual((await self.typed(await self.call('read', select(handle, 'seq'))))[:2], ['expired_or_unknown', ''])

    async def test_native_decoder_rejects_forged_shapes_units_types_and_counter_overflow(self):
        def envelope(value):
            return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': value})
        good = imu.sample_reading(state(), 'seq', 1, 1)
        for bad in [{**good, 'value': str(2**64)}, {**good, 'value': '01'}, {**good, 'unit': 'us'},
                    {**good, 'sample': 33}, {**good, 'component': 2}, {**good, 'kind': 'other'},
                    {**imu.sample_reading(state(), 'accel_raw', 1, 1), 'value': True},
                    imu.result('pad_imu_capture', 'ok', handle='a' * 32, sample_count=0)]:
            self.assertNotEqual((await self.typed(envelope(bad)))[0], 'ok')
        actual = await self.typed(envelope({**good, 'value': str(2**64 - 1)}))
        self.assertEqual(actual[1], str(2**64 - 1))

    async def test_native_reading_allocation_survives_moving_gc(self):
        P, V = self.helpers.Program, self.helpers.Var
        events = self.runtime.wire.events
        await self.execute(P().call('newByteArray', (262080,), prim_set=1).op(19, 1).push(0))
        start = len(events)
        reply = json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': imu.sample_reading(state(), 'seq', 1, 1)})
        self.assertEqual((await self.typed(reply))[1], str(2**63))
        self.assertTrue(any(k == 20 and i == 255 and b'GC took' in b for k, i, b in events[start:]))
        self.assertEqual(await self.primitive('readingValue', (V(3),)), str(2**63))


if __name__ == '__main__':
    unittest.main(verbosity=2)
