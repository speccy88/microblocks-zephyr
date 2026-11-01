"""Actual local motion lab and native VM jobs; every control frame is simulated."""
# SPDX-License-Identifier: MIT
import asyncio
import importlib
import importlib.util
import json
import math
import os
from pathlib import Path
import platform
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('motion_lab_services')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
motion = importlib.import_module(package.__name__ + '.motion_simulator')
gateway = importlib.import_module(package.__name__ + '.gateway')
rpc = importlib.import_module(package.__name__ + '.protocol')
PARAMS = {'vx_mm_s': 100, 'vy_mm_s': -50, 'vyaw_mrad_s': 250, 'duration_ms': 500}


def request(name, params=None, confirmed=False):
    return {'jsonrpc': '2.0', 'id': 1, 'method': motion.PREFIX + name,
            'params': {} if params is None else params, 'confirmed': confirmed}


class ManualClock:
    class Handle:
        def __init__(self, at, fn):
            self.at, self.fn, self.cancelled = at, fn, False
        def cancel(self):
            self.cancelled = True
    def __init__(self):
        self.now = 0.0
        self.handles = []
    def clock(self):
        return self.now
    def schedule(self, at, fn):
        handle = self.Handle(at, fn)
        self.handles.append(handle)
        return handle
    def fire(self, at):
        self.now = at
        due = [h for h in self.handles if not h.cancelled and h.at <= at]
        for handle in due:
            self.handles.remove(handle)
            handle.fn()


class MotionProtocol(unittest.TestCase):
    def test_exact_integer_params_and_local_method_envelope(self):
        self.assertEqual(motion.validate_motion(request('run', PARAMS, True)), (motion.PREFIX + 'run', PARAMS))
        for key, (lo, hi) in motion.BOUNDS.items():
            for value in [lo, hi]:
                motion.validate_motion(request('run', {**PARAMS, key: value}, True))
            for value in [lo - 1, hi + 1, True, 1.0, None, '1', float('inf')]:
                with self.subTest(key=key, value=value), self.assertRaises(rpc.RpcError):
                    motion.validate_motion(request('run', {**PARAMS, key: value}, True))
        for value in [{**PARAMS, 'extra': 0}, {k: v for k, v in PARAMS.items() if k != 'vx_mm_s'}]:
            with self.assertRaises(rpc.RpcError):
                motion.validate_motion(request('run', value, True))

    def test_notifications_are_exact_source_shapes_and_forbid_ids_or_other_methods(self):
        control = motion._ControlRecording()
        packet = {'jsonrpc': '2.0', 'method': 'robot.move', 'params': {'vx': .3, 'vy': -.3, 'vyaw': 1.5}}
        control.send(rpc.encode(packet, rpc.MAX_REQUEST))
        self.assertEqual(control.frames[0]['notification'], packet)
        for value in [{**packet, 'id': 1}, {**packet, 'method': 'robot.init'},
                      {**packet, 'params': {'vx': 0}}, {**packet, 'params': {**packet['params'], 'vx': True}},
                      {**packet, 'params': {**packet['params'], 'vx': .301}}]:
            with self.assertRaises(rpc.RpcError):
                control.send(rpc.encode(value, rpc.MAX_REQUEST))
        self.assertEqual(control.count, 1)

    def test_duplicates_nonfinite_batches_bad_ids_and_unknown_methods_are_refused(self):
        for raw in [b'{"jsonrpc":"2.0","id":1,"id":2}\n', b'{"v":NaN}\n', b'[]\n']:
            with self.assertRaises(rpc.RpcError):
                motion.validate_motion(rpc.decode(raw, rpc.MAX_REQUEST))
        for value in [request('unknown'), {**request('status'), 'id': True},
                      {**request('status'), 'id': 0}, {**request('status'), 'token': 'PRIVATE'},
                      request('status', {'duration_ms': 100}), request('run', PARAMS, 1)]:
            with self.assertRaises(rpc.RpcError):
                motion.validate_motion(value)

    def test_real_gateway_allowlist_still_rejects_motion_and_local_lab_methods(self):
        for method in ['robot.move', 'robot.stop', 'robot.head', *motion.METHODS]:
            with self.assertRaises(rpc.RpcError) as caught:
                gateway.validate({'jsonrpc': '2.0', 'id': 1, 'method': method, 'params': {}, 'confirmed': True})
            self.assertEqual(caught.exception.code, -32601)

    def test_separate_library_defaults_unconfirmed_and_example_only_reads_status(self):
        library = (ROOT / 'linux/microduck/Motion_Simulation.ubl').read_text()
        self.assertIn("module 'MicroDuck Motion Simulation'", library)
        self.assertIn("0 0 0 500 false", library)
        self.assertIn("microduck.motionSim.run", library)
        self.assertNotIn("'robot.move'", library)
        self.assertNotIn('[io:', library)
        example = (ROOT / 'linux/microduck/motion-simulation.ubp').read_text()
        self.assertIn('(microduckSimMotionStatus)', example)
        self.assertNotIn('(microduckSimMotionRun', example)

    def test_compact_rpc_summary_retains_gates_and_fits_native_reporter_bound(self):
        for value in [-300, -99, -1, 0, 1, 99, 300]:
            clock = ManualClock()
            model = motion.MotionSimulation(True, clock=clock.clock, schedule=clock.schedule)
            try:
                state = model.run({**PARAMS, 'vx_mm_s': value, 'vy_mm_s': value, 'duration_ms': 2000}, True)
                state['active_lease_id'] = motion.MAX_LEASES
                state['recorded_frames'] = motion.MAX_FRAMES
                reply = motion.MotionGateway._reply(state)
                self.assertTrue(reply['allow_motion_simulation'])
                self.assertFalse(reply['physical_movement_enabled'])
                self.assertNotIn('frame_history', reply)
                self.assertLessEqual(len(rpc.encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': reply}, rpc.MAX_REPLY)), 760)
            finally:
                model.close()


class MotionModel(unittest.TestCase):
    def model(self, allowed=True, **options):
        clock = ManualClock()
        model = motion.MotionSimulation(allowed, clock=clock.clock, schedule=clock.schedule, **options)
        self.addCleanup(model.close)
        return model, clock

    def test_construction_status_and_default_configuration_record_nothing(self):
        model, _ = self.model(False)
        before = model.snapshot()
        self.assertEqual(before['recorded_frames'], 0)
        self.assertFalse(before['physical_movement_enabled'])
        self.assertIsNone(before['applied_motion'])
        self.assertFalse(before['callback_pending'])
        with self.assertRaises(rpc.RpcError):
            model.run(PARAMS, True)
        self.assertEqual(model.snapshot()['lease_attempts'], 0)

    def test_confirmation_required_each_run_and_busy_does_not_queue(self):
        model, _ = self.model()
        for confirmed in [False, None, 1, 'true']:
            with self.assertRaises(rpc.RpcError):
                model.run(PARAMS, confirmed)
        self.assertEqual(model.snapshot()['recorded_frames'], 0)
        model.run(PARAMS, True)
        with self.assertRaises(rpc.RpcError) as caught:
            model.run({**PARAMS, 'vx_mm_s': -100}, True)
        self.assertEqual(caught.exception.code, -32006)
        self.assertEqual(model.snapshot()['recorded_frames'], 1)
        model.cancel()
        with self.assertRaises(rpc.RpcError):
            model.run(PARAMS, False)

    def test_units_direction_cadence_and_expiry_zero_without_extra_wire_fields(self):
        model, clock = self.model()
        state = model.run(PARAMS, True)
        packet = state['frame_history'][0]['notification']
        self.assertEqual(packet, {'jsonrpc': '2.0', 'method': 'robot.move', 'params': {'vx': .1, 'vy': -.05, 'vyaw': .25}})
        self.assertNotIn('id', packet)
        clock.fire(.1)
        clock.fire(.2)
        self.assertEqual(model.snapshot()['recorded_frames'], 3)
        clock.fire(.5)
        state = model.snapshot()
        self.assertEqual(state['phase'], 'expired')
        self.assertIsNone(state['active_lease_id'])
        self.assertFalse(state['callback_pending'])
        self.assertTrue(state['final_zero_attempted'])
        self.assertEqual(state['frame_history'][-1]['notification']['params'], {'vx': 0, 'vy': 0, 'vyaw': 0})

    def test_late_tick_ends_lease_without_catchup_or_replay(self):
        model, clock = self.model()
        model.run({**PARAMS, 'duration_ms': 2000}, True)
        clock.fire(.35)
        state = model.snapshot()
        self.assertEqual(state['phase'], 'stale_tick')
        self.assertEqual(state['recorded_frames'], 2)
        clock.fire(10)
        self.assertEqual(model.snapshot()['recorded_frames'], 2)

    def test_cancel_and_close_are_idempotent_and_clear_ownership(self):
        model, clock = self.model()
        model.cancel()
        self.assertEqual(model.snapshot()['recorded_frames'], 0)
        model.run(PARAMS, True)
        model.cancel()
        model.cancel()
        model.close()
        model.close()
        clock.fire(10)
        self.assertEqual(model.snapshot()['recorded_frames'], 2)
        with self.assertRaises(rpc.RpcError):
            model.run(PARAMS, True)

    def test_write_faults_preserve_not_sent_or_unknown_and_never_replay(self):
        for fault, outcome, frames in [('write-before', 'not_sent', 0), ('write-after', 'unknown', 1), ('drop', 'not_sent', 0)]:
            model, clock = self.model(fault=fault)
            with self.assertRaises(rpc.RpcError) as caught:
                model.run(PARAMS, True)
            self.assertEqual(caught.exception.outcome, outcome)
            self.assertEqual(model.snapshot()['recorded_frames'], frames)
            self.assertFalse(model.snapshot()['callback_pending'])
            self.assertIsNone(model.snapshot()['active_lease_id'])
            clock.fire(10)
            self.assertEqual(model.snapshot()['recorded_frames'], frames)
            with self.assertRaises(rpc.RpcError):
                model.run(PARAMS, True)

    def test_lease_history_and_frame_budgets_are_bounded(self):
        model, _ = self.model()
        for _ in range(motion.MAX_LEASES):
            model.run(PARAMS, True)
            model.cancel()
        self.assertEqual(model.snapshot()['lease_attempts'], motion.MAX_LEASES)
        self.assertEqual(len(model.snapshot()['frame_history']), motion.HISTORY)
        with self.assertRaises(rpc.RpcError):
            model.run(PARAMS, True)
        control = motion._ControlRecording()
        control.count = motion.MAX_FRAMES
        with self.assertRaises(rpc.RpcError):
            control.send(rpc.encode({'jsonrpc': '2.0', 'method': 'robot.move', 'params': {'vx': 0, 'vy': 0, 'vyaw': 0}}, rpc.MAX_REQUEST))
        self.assertEqual(len(control.frames), 0)

    def test_snapshot_is_detached_and_missing_clock_or_scheduler_cannot_leave_a_lease(self):
        model, clock = self.model()
        state = model.run(PARAMS, True)
        state['frame_history'][0]['notification']['params']['vx'] = 99
        self.assertEqual(model.snapshot()['frame_history'][0]['notification']['params']['vx'], .1)
        model.cancel()
        model._schedule = lambda *_: (_ for _ in ()).throw(RuntimeError('PRIVATE'))
        with self.assertRaises(rpc.RpcError):
            model.run(PARAMS, True)
        self.assertIsNone(model.snapshot()['active_lease_id'])
        self.assertFalse(model.snapshot()['callback_pending'])
        self.assertNotIn('PRIVATE', json.dumps(model.snapshot()))


@unittest.skipUnless(sys.platform == 'linux', 'private Linux Unix credentials required')
class MotionUnixBackend(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='microduck-motion-sockets-')
        self.base = Path(self.temporary.name)
        self.service = await motion.MotionSimulator(self.base / 'simulation', True).start()
    async def asyncTearDown(self):
        await self.service.stop()
        self.temporary.cleanup()
    async def call(self, value):
        reader, writer = await rpc.connect_checked(self.service.directory / 'gateway.sock', os.geteuid(), rpc.MAX_REPLY, True)
        try:
            writer.write(rpc.encode(value, rpc.MAX_REQUEST))
            await writer.drain()
            return await rpc.read_message(reader, rpc.MAX_REPLY)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_real_private_socket_status_run_cancel_never_calls_an_upstream(self):
        with mock.patch.object(rpc.Upstream, 'call', side_effect=AssertionError('Motion must never reach an upstream')):
            self.assertEqual((await self.call(request('status')))['result']['recorded_frames'], 0)
            state = (await self.call(request('run', PARAMS, True)))['result']
            self.assertTrue(state['simulation'])
            self.assertFalse(state['physical_movement_enabled'])
            self.assertEqual(state['recorded_frames'], 1)
            result = (await self.call(request('cancel')))['result']
            self.assertIsNone(result['active_lease_id'])
            self.assertEqual(result['last_notification']['params']['vx'], 0)

    async def test_denied_inputs_and_real_methods_never_record_or_forward(self):
        for value in [request('run', PARAMS, False), request('run', {**PARAMS, 'duration_ms': 3000}, True),
                      {'jsonrpc': '2.0', 'id': 1, 'method': 'robot.move', 'params': {'vx': .1}, 'confirmed': True},
                      {'jsonrpc': '2.0', 'id': 1, 'method': 'robot.init', 'params': {}, 'confirmed': True},
                      {'jsonrpc': '2.0', 'id': 1, 'method': 'robot.enable', 'params': {'on': True}, 'confirmed': True}]:
            self.assertIn('error', await self.call(value))
        self.assertEqual(self.service.motion.snapshot()['recorded_frames'], 0)

    async def test_default_backend_opt_in_and_filesystem_metadata(self):
        other = await motion.MotionSimulator(self.base / 'disabled').start()
        try:
            value, _ = await other.gateway.dispatch(request('status'))
            self.assertFalse(value['allow_motion_simulation'])
            with self.assertRaises(rpc.RpcError):
                await other.gateway.dispatch(request('run', PARAMS, True))
            info = json.loads((other.directory / 'motion-simulation.json').read_text())
            self.assertTrue(info['motion_simulation'])
            self.assertFalse(info['physical_movement_enabled'])
            self.assertEqual((other.directory / 'gateway.sock').stat().st_mode & 0o777, 0o600)
        finally:
            await other.stop()

    async def test_expiry_and_backend_shutdown_leave_no_callback_or_socket(self):
        await self.call(request('run', {**PARAMS, 'duration_ms': 100}, True))
        deadline = asyncio.get_running_loop().time() + 2
        while self.service.motion.snapshot()['active_lease_id'] is not None:
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.01)
        self.assertEqual(self.service.motion.snapshot()['phase'], 'expired')
        path = self.service.directory / 'gateway.sock'
        await self.service.stop()
        self.assertFalse(path.exists())
        self.assertFalse(self.service.motion.snapshot()['callback_pending'])

    async def test_actual_cli_opt_in_metadata_and_clean_shutdown(self):
        path = self.base / 'cli-simulation'
        process = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'linux/microduck/motion_simulator.py'),
            '--directory', str(path), '--allow-motion', stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            line = await asyncio.wait_for(process.stdout.readline(), 3)
            info = json.loads(line)
            self.assertEqual(info['pid'], process.pid)
            self.assertTrue(info['motion_simulation'])
            self.assertTrue(info['allowed_motion_simulation'])
            self.assertFalse(info['physical_movement_enabled'])
            self.assertTrue((path / 'motion-simulation.json').is_file())
        finally:
            if process.returncode is None:
                process.terminate()
            _, error = await asyncio.wait_for(process.communicate(), 3)
        self.assertEqual(process.returncode, 0, error.decode())
        self.assertFalse((path / 'gateway.sock').exists())


SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL = os.environ.get('SMALLVM_MICRODUCK_BINARY')


@unittest.skipUnless(sys.platform == 'linux' and struct.calcsize('P') == 8 and (EXTERNAL or shutil.which('gcc') and (SOURCE / '.git').is_dir()), 'native LP64 VM and pinned compiler/source required')
class MotionNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='microduck-motion-native-')
        cls.base = Path(cls.temporary.name)
        if EXTERNAL:
            cls.binary = Path(EXTERNAL)
            if not cls.binary.is_absolute() or not cls.binary.is_file() or not os.access(cls.binary, os.X_OK):
                raise AssertionError('Explicit native binary must exist and be executable')
        else:
            result = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE), '--output', str(cls.base / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise AssertionError(result.stdout + result.stderr)
            cls.binary = cls.base / 'build/smallvm'
        spec = importlib.util.spec_from_file_location('motion_vm_helpers', ROOT / 'tests/test_linux_microduck_vm.py')
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)
    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()
    async def asyncSetUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.service = await motion.MotionSimulator(self.work / 'simulation', True).start()
        self.runtime = None
    async def asyncTearDown(self):
        if self.runtime:
            runtime = self.runtime
            await asyncio.to_thread(runtime.stop)
            log = runtime.log_path.read_text()
            self.assertEqual(runtime.process.returncode, 0, log)
            self.assertNotIn('AddressSanitizer', log)
            self.assertNotIn('runtime error:', log)
        await self.service.stop()
    async def start_vm(self, path=None):
        data = self.work / 'programs'
        data.mkdir(mode=0o700)
        self.runtime = await asyncio.to_thread(self.helpers.Runtime, self.binary, data, path or self.service.directory / 'gateway.sock')
    async def primitive(self, name, args=(), error=None, command=False):
        return await asyncio.to_thread(self.runtime.primitive, name, args, error, command)
    async def call(self, name, params=None, confirmed=False):
        job = await self.primitive('begin', (motion.PREFIX + name, json.dumps({} if params is None else params), confirmed))
        deadline = asyncio.get_running_loop().time() + 4
        while await self.primitive('status', (job,)) == 'pending':
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.01)
        reply = json.loads(await self.primitive('result', (job,)))
        await self.primitive('release', (job,), command=True)
        return reply

    async def test_real_vm_status_run_scaled_notification_and_cancel(self):
        await self.start_vm()
        self.assertEqual((await self.call('status'))['result']['recorded_frames'], 0)
        result = (await self.call('run', {**PARAMS, 'duration_ms': 2000}, True))['result']
        self.assertTrue(result['simulation'])
        self.assertFalse(result['physical_movement_enabled'])
        self.assertEqual(result['last_notification']['params'], {'vx': .1, 'vy': -.05, 'vyaw': .25})
        stopped = (await self.call('cancel'))['result']
        self.assertIsNone(stopped['active_lease_id'])
        self.assertTrue(stopped['final_zero_attempted'])
        for sign in (-1, 1):
            edge = {'vx_mm_s': sign * 300, 'vy_mm_s': sign * 300, 'vyaw_mrad_s': sign * 1500, 'duration_ms': 2000}
            state = (await self.call('run', edge, True))['result']
            self.assertEqual(state['active_requested_integer_units'], edge)
            self.assertEqual(state['last_notification']['params'], {'vx': sign * .3, 'vy': sign * .3, 'vyaw': sign * 1.5})
            await self.call('cancel')

    async def test_native_confirmation_bounds_and_actual_robot_method_refused_before_io(self):
        await self.start_vm()
        values = [(motion.PREFIX + 'run', json.dumps(PARAMS), False), ('robot.move', '{}', True)]
        for key, value in [('vx_mm_s', 301), ('vx_mm_s', -301), ('vy_mm_s', True), ('vy_mm_s', -301), ('vyaw_mrad_s', 1501), ('vyaw_mrad_s', -1501), ('duration_ms', 99), ('duration_ms', 2001), ('duration_ms', 500.0)]:
            values.append((motion.PREFIX + 'run', json.dumps({**PARAMS, key: value}), True))
        values.append((motion.PREFIX + 'run', '{"vx_mm_s":0,"vx_mm_s":1,"vy_mm_s":0,"vyaw_mrad_s":0,"duration_ms":100}', True))
        values.append((motion.PREFIX + 'cancel', '{"extra":1}', False))
        for args in values:
            await self.primitive('begin', args, error=32)
        self.assertEqual(self.service.motion.snapshot()['recorded_frames'], 0)
        self.assertEqual(self.service.gateway.active, 0)

    async def test_native_validated_request_still_requires_backend_opt_in(self):
        self.service.motion.allow_motion = False
        await self.start_vm()
        result = await self.call('run', PARAMS, True)
        self.assertEqual(result['error']['code'], -32003)
        self.assertEqual(self.service.motion.snapshot()['recorded_frames'], 0)

    async def test_native_prefix_on_ordinary_gateway_is_denied_without_motion(self):
        ordinary = await gateway.Gateway({'robot': {'path': str(self.service.directory / 'robot.sock'), 'uid': os.geteuid()}}).start(self.work / 'ordinary.sock')
        try:
            await self.start_vm(ordinary.path)
            reply = await self.call('run', PARAMS, True)
            self.assertEqual(reply['error']['code'], -32601)
            self.assertEqual(self.service.motion.snapshot()['recorded_frames'], 0)
        finally:
            await ordinary.stop()


if __name__ == '__main__':
    unittest.main(verbosity=2)
