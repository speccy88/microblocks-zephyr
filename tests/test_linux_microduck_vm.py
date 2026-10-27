#!/usr/bin/env python3
"""Real sanitizer-built SmallVM primitives over official PTY bytecode.

The interpreter, GC, scheduler, primitive dispatch and Linux socket client are
real. Only MicroDuck daemons and adverse gateway replies are simulated in private
Unix sockets. No SSH, Pi, physical robot, motor, service install or TCP is used.
This suite never invokes the numeric acceptance suite. By default it builds the
local pinned source under Linux with ASan and UBSan, without fetching dependencies.
SMALLVM_MICRODUCK_BINARY may instead name an absolute existing executable; its
architecture and sanitizer provenance must then be supplied by its build manifest.
"""
# SPDX-License-Identifier: MPL-2.0
import asyncio
import importlib
import importlib.util
import json
import os
from pathlib import Path
import platform
import shutil
import signal
import struct
import subprocess
import sys
import tempfile
import time
import types
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL_BINARY = os.environ.get('SMALLVM_MICRODUCK_BINARY')
wire_protocol = None
if platform.system() == 'Linux':
    spec = importlib.util.spec_from_file_location('microduck_vm_wire', ROOT / 'tests/linux_arm64_protocol.py')
    wire_protocol = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(wire_protocol)
package = types.ModuleType('microduck_vm_services')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
gateway_module = importlib.import_module(package.__name__ + '.gateway')
rpc = importlib.import_module(package.__name__ + '.protocol')

# Auditable feature-suite manifest. The Pi runner requires these exact methods;
# adding a test requires updating its group instead of weakening a count gate.
TEST_GROUPS = {
    'adapter': (
        'test_disabled_default_is_queryable_and_never_connects',
        'test_real_dispatch_health_optional_battery_and_policy_skill_discovery',
        'test_native_json_quote_roundtrips_unicode_control_and_quotes',
        'test_native_and_gateway_mutation_gates_then_known_sound',
        'test_delayed_job_keeps_another_real_vm_task_and_ping_running',
        'test_moving_gc_during_pending_job_does_not_retain_vm_object_addresses',
        'test_stop_all_cancels_sent_job_as_unknown_without_replay',
        'test_four_job_slots_are_retained_until_release_and_ids_are_not_reused',
        'test_malformed_wrong_id_eof_and_oversized_replies_are_unknown',
        'test_actual_ten_second_deadline_does_not_block_or_retry',
    ),
    'typed_readings': (
        'test_typed_snapshot_fields_and_simulation_origin_are_read_only',
        'test_typed_optional_required_and_upstream_defaults_preserve_zero_false',
        'test_typed_scaled_numbers_round_and_respect_signed31_bounds',
        'test_typed_health_state_does_not_claim_motion_readiness',
        'test_typed_imu_state_defaults_and_frozen_missing_precedence',
        'test_typed_schema_parse_and_error_envelope_validation',
        'test_typed_reading_value_checks_record_shape_and_status',
        'test_typed_record_allocation_survives_moving_gc',
    ),
}


class RawString:
    """Deliberately invalid UTF-8 code literal for VM validation, never user input."""
    def __init__(self, raw):
        self.raw = raw


class Var:
    def __init__(self, index):
        self.index = index


class Program:
    """Encode the pinned compiler's actual opcodes and tagged string literals."""
    def __init__(self):
        self.code = bytearray(struct.pack('<H', 9))  # initLocals(0)
        self.fixups = []

    def op(self, opcode, arg=0):
        self.code += struct.pack('<H', opcode | ((arg & 255) << 8))
        return self

    def push(self, value):
        if isinstance(value, Var):
            self.op(6, value.index)
        elif isinstance(value, bool):
            self.op(2, 4 if value else 0)
        elif isinstance(value, int):
            self.op(4)
            self.code += struct.pack('<I', ((value << 1) | 1) & 0xffffffff)
        elif isinstance(value, (str, RawString)):
            self.op(5)
            self.fixups.append((len(self.code), value.raw if isinstance(value, RawString) else value, 0))
            self.code += b'\0\0'
        else:
            raise ValueError('Unsupported test literal')
        return self

    def call(self, name, args=(), prim_set=22, command=False):
        for arg in args:
            self.push(arg)
        self.op(36 if command else 37, len(args))
        self.fixups.append((len(self.code), name, prim_set << 10))
        self.code += b'\0\0'
        return self

    def finish(self):
        self.op(35).op(127).op(240)
        self.code += b'\0' * 6
        if len(self.code) % 4:
            self.code += b'\0\0'
        for operand, text, prefix in self.fixups:
            offset = (len(self.code) - operand) // 2
            if not 0 < offset < 1024:
                raise ValueError('Literal exceeds pinned 10-bit primitive offset')
            struct.pack_into('<H', self.code, operand, prefix | offset)
            raw = (text if isinstance(text, bytes) else text.encode('utf-8')) + b'\0'
            raw += b'\0' * (-len(raw) % 4)
            self.code += struct.pack('<I', ((len(raw) // 4) << 4) | 4) + raw
        return bytes(self.code)


class Runtime:
    def __init__(self, binary, data, gateway_path):
        self.info = data / 'pty.json'
        self.log_path = data / 'runtime.log'
        self.log = open(self.log_path, 'w+', encoding='utf-8')
        command = [str(binary), '--data-dir', str(data), '--pty-info', str(self.info)]
        if gateway_path is not None:
            command += ['--microduck-socket', str(gateway_path)]
        environment = dict(os.environ)
        environment['UBSAN_OPTIONS'] = 'halt_on_error=1:print_stacktrace=1'
        environment['ASAN_OPTIONS'] = 'detect_leaks=1:abort_on_error=1'
        self.process = subprocess.Popen(command, stdout=self.log, stderr=subprocess.STDOUT, env=environment)
        self.wire = None
        try:
            deadline = time.monotonic() + 5
            while not self.info.exists():
                if self.process.poll() is not None or time.monotonic() >= deadline:
                    raise RuntimeError('VM startup failed: ' + self.log_path.read_text())
                time.sleep(.01)
            self.wire = wire_protocol.Wire(json.loads(self.info.read_text())['pty'])
            self.wire.ping()
        except BaseException:
            self.stop()
            raise

    def stop(self):
        if self.wire:
            self.wire.close()
            self.wire = None
        if self.process.poll() is None:
            self.process.send_signal(signal.SIGTERM)
            try:
                self.process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=5)
        self.log.close()

    def execute(self, code, error=None, chunk=0):
        vm = self.wire
        vm.upload(chunk, code, 2)
        start = len(vm.events)
        vm.short(3, chunk)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            for kind, index, payload in vm.events[start:]:
                if index != chunk or kind not in (18, 19):
                    continue
                if error is not None:
                    if kind != 19 or not payload or payload[0] != error:
                        raise AssertionError(f'Expected VM error {error}; actual {(kind, payload.hex())}')
                    return None
                if kind == 19:
                    raise AssertionError('Actual SmallVM task error: ' + payload.hex())
                if payload[0] == 1:
                    return struct.unpack('<i', payload[1:5])[0]
                if payload[0] == 2:
                    return payload[1:].decode('utf-8')
                if payload[0] == 3:
                    return bool(payload[1])
                raise AssertionError('Unexpected SmallVM reporter type')
            vm.pump(.02)
        raise TimeoutError('Real SmallVM reporter did not finish')

    def primitive(self, name, args=(), error=None, command=False):
        program = Program().call(name, args, command=command)
        if command:
            program.push(0)
        return self.execute(program.finish(), error)


class MockRobot:
    def __init__(self, path):
        self.path, self.server = path, None
        self.tasks = set()
        self.calls = []
        self.release = None
        self.received = asyncio.Event()
        self.health = {'healthy': True, 'battery': {'volts': 7.8, 'percent': 73.25}}
        self.policies = {'skills': ['bow', 'nod'], 'slots': [{'slot': 'walk', 'path': '/policies/walk.onnx'}]}

    async def start(self):
        self.server = await asyncio.start_unix_server(self.handle, path=str(self.path))
        self.path.chmod(0o600)
        return self

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            hello = await rpc.read_message(reader, rpc.MAX_REQUEST)
            if hello != {'jsonrpc': '2.0', 'id': 0, 'method': 'hello', 'params': {'api_version': 44}}:
                raise AssertionError('Fixture received a non-official hello')
            writer.write(rpc.encode({'jsonrpc': '2.0', 'id': 0, 'result': {'api_version': 44}}, rpc.MAX_REPLY))
            await writer.drain()
            q = await rpc.read_message(reader, rpc.MAX_REQUEST)
            self.calls.append(q)
            self.received.set()
            if self.release is not None:
                await self.release.wait()
            result = self.health if q['method'] == 'robot.health' else self.policies if q['method'] == 'robot.policies' else {'accepted': True}
            writer.write(rpc.encode({'jsonrpc': '2.0', 'id': q['id'], 'result': result}, rpc.MAX_REPLY))
            await writer.drain()
        except (OSError, rpc.RpcError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            self.tasks.discard(task)

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


class AdverseGateway:
    def __init__(self, path):
        self.path, self.server = path, None
        self.mode = 'wrong_id'
        self.calls, self.tasks = [], set()

    async def start(self):
        self.server = await asyncio.start_unix_server(self.handle, path=str(self.path))
        self.path.chmod(0o600)
        return self

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            q = await rpc.read_message(reader, rpc.MAX_REQUEST)
            self.calls.append(q)
            if self.mode == 'eof':
                return
            if self.mode == 'timeout':
                await asyncio.sleep(12)
                return
            if self.mode == 'malformed':
                writer.write(b'broken-json\n')
            elif self.mode == 'oversized':
                writer.write(b'x' * (rpc.MAX_REPLY + 1))
            else:
                writer.write(rpc.encode({'jsonrpc': '2.0', 'id': q['id'] + 1, 'result': {}}, rpc.MAX_REPLY))
            await writer.drain()
        except (OSError, rpc.RpcError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            self.tasks.discard(task)

    async def stop(self):
        self.server.close()
        await self.server.wait_closed()
        tasks = list(self.tasks)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@unittest.skipUnless(platform.system() == 'Linux' and struct.calcsize('P') == 8
                     and (EXTERNAL_BINARY or (shutil.which('gcc') and (SOURCE / '.git').is_dir())),
                     'requires LP64 Linux and an external executable or local GCC/pinned source; no remote fallback')
class RealSmallVMMicroDuck(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary = tempfile.TemporaryDirectory(prefix='md-vm-')
        cls.work = Path(cls.temporary.name)
        if EXTERNAL_BINARY:
            candidate = Path(EXTERNAL_BINARY)
            if not candidate.is_absolute() or not candidate.is_file() or not os.access(candidate, os.X_OK):
                cls.temporary.cleanup()
                raise AssertionError('SMALLVM_MICRODUCK_BINARY must name an absolute existing executable')
            cls.binary = candidate.resolve(strict=True)
            return
        build = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE), '--output', str(cls.work / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
        if build.returncode:
            cls.temporary.cleanup()
            raise AssertionError('Real SmallVM sanitizer build failed:\n' + build.stdout + build.stderr)
        cls.binary = cls.work / 'build/smallvm'
        manifest = json.loads((cls.work / 'build/build-manifest.json').read_text())
        if not manifest['sanitize']:
            raise AssertionError('Native VM test requires sanitizer instrumentation')

    @classmethod
    def tearDownClass(cls):
        cls.temporary.cleanup()

    async def asyncSetUp(self):
        self.base = Path(tempfile.mkdtemp(prefix='case-', dir=self.work))
        self.robot = await MockRobot(self.base / 'robot.sock').start()
        self.gateway = await gateway_module.Gateway({'robot': {'path': str(self.robot.path), 'uid': os.geteuid()}}, timeout=3).start(self.base / 'gateway.sock')
        self.adverse = await AdverseGateway(self.base / 'adverse.sock').start()
        self.runtime = None

    async def asyncTearDown(self):
        try:
            if self.runtime:
                await asyncio.to_thread(self.runtime.stop)
                log = self.runtime.log_path.read_text()
                self.assertEqual(self.runtime.process.returncode, 0, log)
                self.assertNotIn('runtime error:', log)
                self.assertNotIn('AddressSanitizer', log)
        finally:
            await self.gateway.stop()
            await self.robot.stop()
            await self.adverse.stop()

    async def start_vm(self, path='gateway'):
        data = self.base / 'data'
        data.mkdir(mode=0o700)
        selected = self.base / (path + '.sock') if path is not None else None
        self.runtime = await asyncio.to_thread(Runtime, self.binary, data, selected)
        return self.runtime

    async def primitive(self, name, args=(), error=None, command=False):
        return await asyncio.to_thread(self.runtime.primitive, name, args, error, command)

    async def begin(self, method='robot.health', params=None, confirmed=False):
        job = await self.primitive('begin', (method, json.dumps({} if params is None else params, separators=(',', ':')), confirmed))
        self.assertIsInstance(job, int)
        self.assertTrue(1 <= job <= 1073741823)
        return job

    async def terminal(self, job, timeout=4):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            status = await self.primitive('status', (job,))
            if status != 'pending':
                self.assertIn(status, ('ready', 'error', 'unknown'))
                text = await self.primitive('result', (job,))
                reply = json.loads(text)
                self.assertEqual(reply['jsonrpc'], '2.0')
                self.assertEqual(reply['id'], job)
                return status, reply
            await asyncio.sleep(.01)
        self.fail('Native MicroDuck job did not terminate within its stated deadline')

    async def release(self, job):
        self.assertEqual(await self.primitive('release', (job,), command=True), 0)

    async def reading(self, reply, field):
        """Inspect an actual VM List using pinned at(index,list)=opcode81.

        interp.c at_op dispatches primAt(arg,sp-arg); dataPrims.c primAt uses
        args[0]=one-based index,args[1]=List. Opcode83 dispatches primLength.
        No host-side emulation of the new primitive or its record is involved.
        """
        text = reply if isinstance(reply, (str, RawString)) else json.dumps(reply, separators=(',', ':'), allow_nan=False)
        program = Program().call('healthSample', (text, field)).op(7, 3).push(0)
        await asyncio.to_thread(self.runtime.execute, program.finish())
        count = Program().push(Var(3)).op(83, 1).finish()
        self.assertEqual(await asyncio.to_thread(self.runtime.execute, count), 4)
        values = []
        for index in range(1, 5):
            code = Program().push(index).push(Var(3)).op(81, 2).finish()
            values.append(await asyncio.to_thread(self.runtime.execute, code))
        return values

    async def assert_reading(self, result, field, status, value, unit, origin='unmarked'):
        reply = {'jsonrpc': '2.0', 'id': 1, 'result': result}
        actual = await self.reading(reply, field)
        self.assertEqual(actual, [status, value, unit, origin])
        if status == 'ok':
            extracted = await self.primitive('readingValue', (Var(3),))
            self.assertIs(type(extracted), type(value), 'false/zero and integer/string must remain distinct')
            self.assertEqual(extracted, value)
        else:
            await self.primitive('readingValue', (Var(3),), error=32)

    async def test_disabled_default_is_queryable_and_never_connects(self):
        await self.start_vm(None)
        self.assertIs(await self.primitive('configured'), False)
        await self.primitive('begin', ('robot.health', '{}', False), error=27)
        self.assertEqual(self.robot.calls, [])
        self.assertEqual(self.gateway.active, 0)

    async def test_real_dispatch_health_optional_battery_and_policy_skill_discovery(self):
        await self.start_vm()
        self.assertIs(await self.primitive('configured'), True)
        self.assertEqual(self.robot.calls, [], 'configuration alone must not contact a robot')
        job = await self.begin()
        status, reply = await self.terminal(job)
        self.assertEqual(status, 'ready')
        self.assertEqual(reply['result']['battery'], {'volts': 7.8, 'percent': 73.25})
        await self.release(job)
        self.robot.health.pop('battery')
        job = await self.begin()
        self.assertNotIn('battery', (await self.terminal(job))[1]['result'])
        await self.release(job)
        job = await self.begin('robot.policies')
        self.assertEqual((await self.terminal(job))[1]['result']['skills'], ['bow', 'nod'])

    async def test_native_json_quote_roundtrips_unicode_control_and_quotes(self):
        await self.start_vm()
        text = 'duck "α"\\path\nnext\tline'
        quoted = await self.primitive('quote', (text,))
        self.assertEqual(json.loads(quoted), text)
        self.assertEqual(self.robot.calls, [])

    async def test_native_and_gateway_mutation_gates_then_known_sound(self):
        await self.start_vm()
        await self.primitive('begin', ('robot.sound', '{"tag":"chirp"}', False), error=32)
        self.assertEqual(self.robot.calls, [])
        job = await self.begin('robot.sound', {'tag': 'chirp'}, True)
        status, reply = await self.terminal(job)
        self.assertEqual(status, 'error')
        self.assertEqual(reply['error']['data']['outcome'], 'not_sent')
        self.assertEqual(self.robot.calls, [])
        await self.release(job)
        await self.gateway.stop()
        self.gateway = await gateway_module.Gateway({'robot': {'path': str(self.robot.path), 'uid': os.geteuid()}}, allowed_mutations=['robot.sound']).start(self.base / 'gateway.sock')
        job = await self.begin('robot.sound', {'tag': 'chirp'}, True)
        self.assertEqual((await self.terminal(job))[0], 'ready')
        self.assertEqual([q['method'] for q in self.robot.calls], ['robot.sound'])

    async def test_delayed_job_keeps_another_real_vm_task_and_ping_running(self):
        await self.start_vm()
        self.robot.release = asyncio.Event()
        job = await self.begin()
        await asyncio.wait_for(self.robot.received.wait(), 2)
        self.assertEqual(await self.primitive('status', (job,)), 'pending')
        await self.primitive('result', (job,), error=32)
        loop = struct.pack('<4H', 9, 2 | (3 << 8), 8 | (15 << 8), 22 | (253 << 8))
        await asyncio.to_thread(self.runtime.wire.upload, 5, loop)
        await asyncio.to_thread(self.runtime.wire.short, 3, 5)
        await asyncio.to_thread(self.runtime.wire.ping, 90)
        first = await asyncio.to_thread(self.runtime.wire.variable, 15)
        await asyncio.sleep(.05)
        await asyncio.to_thread(self.runtime.wire.ping, 91)
        second = await asyncio.to_thread(self.runtime.wire.variable, 15)
        self.assertGreater(second, first)
        self.robot.release.set()
        self.assertEqual((await self.terminal(job))[0], 'ready')
        await asyncio.to_thread(self.runtime.wire.short, 4, 5)

    async def test_moving_gc_during_pending_job_does_not_retain_vm_object_addresses(self):
        await self.start_vm()
        vm = self.runtime.wire
        await asyncio.to_thread(vm.long, 8, 0, b'\x02robot.health')
        await asyncio.to_thread(vm.long, 8, 1, b'\x02{}')
        await asyncio.to_thread(vm.ping, 92)
        p = Program().call('newByteArray', (16000,), prim_set=1).op(19, 1)
        p.call('begin', (Var(0), Var(1), False)).op(7, 2)
        p.push(False).op(7, 0).push(False).op(7, 1)
        p.call('newByteArray', (250000,), prim_set=1).op(19, 1).push(Var(2))
        start = len(vm.events)
        job = await asyncio.to_thread(self.runtime.execute, p.finish())
        self.assertTrue(any(kind == 20 and index == 255 and b'GC took' in body for kind, index, body in vm.events[start:]), 'workload must actually trigger the moving collector')
        status, reply = await self.terminal(job)
        self.assertEqual(status, 'ready')
        self.assertTrue(reply['result']['healthy'])
        self.assertEqual(self.robot.calls[-1]['method'], 'robot.health')

    async def test_stop_all_cancels_sent_job_as_unknown_without_replay(self):
        await self.start_vm()
        self.robot.release = asyncio.Event()
        job = await self.begin()
        await asyncio.wait_for(self.robot.received.wait(), 2)
        await asyncio.to_thread(self.runtime.wire.short, 6, 0)
        await asyncio.to_thread(self.runtime.wire.ping, 93)
        status, reply = await self.terminal(job)
        self.assertEqual(status, 'unknown')
        self.assertEqual(reply['error']['data']['outcome'], 'unknown')
        # Recover the retained handle through the actual List reporter after StopAll.
        count = Program().call('jobs').op(83, 1).finish()
        first = Program().push(1).call('jobs').op(81, 2).finish()
        self.assertEqual(await asyncio.to_thread(self.runtime.execute, count), 1)
        self.assertEqual(await asyncio.to_thread(self.runtime.execute, first), job)
        self.robot.release.set()
        await asyncio.sleep(.05)
        await asyncio.to_thread(self.runtime.wire.ping, 94)
        self.assertEqual([q['method'] for q in self.robot.calls], ['robot.health'])
        await self.release(job)
        self.assertEqual(await asyncio.to_thread(self.runtime.execute, count), 0)
        await self.primitive('status', (job,), error=18)

    async def test_four_job_slots_are_retained_until_release_and_ids_are_not_reused(self):
        await self.start_vm()
        jobs = []
        for _ in range(4):
            job = await self.begin()
            jobs.append(job)
            self.assertEqual((await self.terminal(job))[0], 'ready')
        await self.primitive('begin', ('robot.health', '{}', False), error=10)
        await self.release(jobs[0])
        await self.primitive('status', (jobs[0],), error=18)
        await self.primitive('result', (jobs[0],), error=18)
        next_job = await self.begin()
        self.assertGreater(next_job, max(jobs))
        self.assertEqual((await self.terminal(next_job))[0], 'ready')

    async def test_malformed_wrong_id_eof_and_oversized_replies_are_unknown(self):
        await self.start_vm('adverse')
        for mode in ('malformed', 'wrong_id', 'eof', 'oversized'):
            self.adverse.mode = mode
            with self.subTest(mode=mode):
                before = len(self.adverse.calls)
                job = await self.begin()
                status, reply = await self.terminal(job)
                self.assertEqual(status, 'unknown')
                self.assertEqual(reply['error']['data']['outcome'], 'unknown')
                self.assertEqual(len(self.adverse.calls), before + 1)
                await self.release(job)

    async def test_actual_ten_second_deadline_does_not_block_or_retry(self):
        await self.start_vm('adverse')
        self.adverse.mode = 'timeout'
        started = time.monotonic()
        job = await self.begin()
        status, reply = await self.terminal(job, timeout=12)
        elapsed = time.monotonic() - started
        self.assertEqual(status, 'unknown')
        self.assertEqual(reply['error']['data']['outcome'], 'unknown')
        self.assertGreaterEqual(elapsed, 9.5)
        self.assertLess(elapsed, 12)
        self.assertEqual(len(self.adverse.calls), 1)
        await asyncio.to_thread(self.runtime.wire.ping, 95)

    async def test_typed_snapshot_fields_and_simulation_origin_are_read_only(self):
        await self.start_vm()
        self.robot.health = {'healthy': False, 'degraded': True, 'simulation': True,
            'battery': {'percent': 43.21, 'volts': 7.654}, 'cpu_temp_c': 41.25,
            'motors': {'hottest': 'SIMULATION-joint', 'max_c': 45.5, 'mean_c': 40.25},
            'control_loop': {'target_hz': 50, 'achieved_hz': 49.95, 'last_tick_age_ms': 4},
            'bus': {'consecutive_errors': 2, 'startup_failures': 1},
            'imu': {'ready': False, 'missing': False, 'stale_blocks': 7, 'consecutive_stale_blocks': 3}}
        job = await self.begin()
        _, reply = await self.terminal(job)
        await self.release(job)
        for field, value, unit in (
            ('healthy', False, 'boolean'), ('degraded', True, 'boolean'), ('health.state', 'degraded', 'state'),
            ('battery.percent', 4321, '0.01%'), ('battery.volts', 7654, 'mV'), ('cpu_temp_c', 41250, 'mC'),
            ('motors.max_c', 45500, 'mC'), ('motors.mean_c', 40250, 'mC'),
            ('control_loop.target_hz', 50000, 'mHz'), ('control_loop.achieved_hz', 49950, 'mHz'),
            ('control_loop.last_tick_age_ms', 4, 'ms'), ('bus.consecutive_errors', 2, 'count'),
            ('bus.startup_failures', 1, 'count'), ('imu.ready', False, 'boolean'), ('imu.missing', False, 'boolean'),
            ('imu.stale_blocks', 7, 'count'), ('imu.consecutive_stale_blocks', 3, 'count'), ('imu.state', 'not_converged', 'state'),
        ):
            with self.subTest(field=field):
                await self.assert_reading(reply['result'], field, 'ok', value, unit, 'simulation')
        for markers, origin in (({}, 'unmarked'), ({'simulation': False}, 'unmarked'),
            ({'simulation': 'true'}, 'unmarked'), ({'simulated': True}, 'simulation'),
            ({'simulation': False, 'simulated': True}, 'simulation')):
            await self.assert_reading({'healthy': False, **markers}, 'healthy', 'ok', False, 'boolean', origin)
        self.assertEqual([q['method'] for q in self.robot.calls], ['robot.health'], 'conversion must open no new socket')

    async def test_typed_optional_required_and_upstream_defaults_preserve_zero_false(self):
        await self.start_vm(None)
        for field, unit in (('battery.percent', '0.01%'), ('motors.max_c', 'mC'), ('cpu_temp_c', 'mC'),
            ('control_loop.target_hz', 'mHz'), ('imu.ready', 'boolean'), ('imu.state', 'state')):
            await self.assert_reading({'healthy': False}, field, 'unknown', '', unit)
        for result, field, unit in (
            ({'battery': {}}, 'battery.percent', '0.01%'), ({'battery': {'volts': None}}, 'battery.volts', 'mV'),
            ({'motors': {}}, 'motors.max_c', 'mC'), ({'motors': {'mean_c': None}}, 'motors.mean_c', 'mC'),
            ({'control_loop': {}}, 'control_loop.target_hz', 'mHz'),
            ({'control_loop': {'last_tick_age_ms': None}}, 'control_loop.last_tick_age_ms', 'ms'),
            ({'degraded': None}, 'degraded', 'boolean'), ({'bus': None}, 'bus.startup_failures', 'count'),
            ({'imu': {'ready': None}}, 'imu.ready', 'boolean'), ({'imu': {'missing': None}}, 'imu.missing', 'boolean'),
            ({'imu': {'stale_blocks': None}}, 'imu.stale_blocks', 'count'),
        ):
            with self.subTest(field=field, result=result):
                await self.assert_reading({'healthy': False, **result}, field, 'invalid', '', unit)
        for result, field, value, unit in (
            ({}, 'degraded', False, 'boolean'), ({}, 'bus.consecutive_errors', 0, 'count'),
            ({'bus': {}}, 'bus.startup_failures', 0, 'count'), ({'imu': {}}, 'imu.ready', False, 'boolean'),
            ({'imu': {}}, 'imu.missing', False, 'boolean'), ({'imu': {}}, 'imu.stale_blocks', 0, 'count'),
            ({'imu': {}}, 'imu.consecutive_stale_blocks', 0, 'count'),
            ({'battery': {'percent': 0, 'volts': 0}}, 'battery.percent', 0, '0.01%'),
            ({'control_loop': {'last_tick_age_ms': 0}}, 'control_loop.last_tick_age_ms', 0, 'ms'),
        ):
            await self.assert_reading({'healthy': False, **result}, field, 'ok', value, unit)
        for result in ({'control_loop': {}}, {'control_loop': {'achieved_hz': None}}):
            await self.assert_reading({'healthy': False, **result}, 'control_loop.achieved_hz', 'unknown', '', 'mHz')
        await self.assert_reading({'healthy': False, 'imu': None}, 'imu.ready', 'unknown', '', 'boolean')
        self.assertEqual(self.robot.calls, [])

    async def test_typed_scaled_numbers_round_and_respect_signed31_bounds(self):
        await self.start_vm(None)
        for result, field, status, value, unit in (
            ({'battery': {'percent': 1.125}}, 'battery.percent', 'ok', 113, '0.01%'),
            ({'battery': {'volts': 1.0625}}, 'battery.volts', 'ok', 1063, 'mV'),
            ({'cpu_temp_c': -1.0625}, 'cpu_temp_c', 'ok', -1063, 'mC'),
            ({'cpu_temp_c': 1073741.823}, 'cpu_temp_c', 'ok', 1073741823, 'mC'),
            ({'cpu_temp_c': -1073741.824}, 'cpu_temp_c', 'ok', -1073741824, 'mC'),
            ({'cpu_temp_c': 1073741.824}, 'cpu_temp_c', 'out_of_range', '', 'mC'),
            ({'cpu_temp_c': -1073741.825}, 'cpu_temp_c', 'out_of_range', '', 'mC'),
            ({'cpu_temp_c': 1e308}, 'cpu_temp_c', 'out_of_range', '', 'mC'),
            ({'battery': {'percent': False}}, 'battery.percent', 'invalid', '', '0.01%'),
            ({'battery': {'volts': '7.8'}}, 'battery.volts', 'invalid', '', 'mV'),
            ({'bus': {'consecutive_errors': 1073741823}}, 'bus.consecutive_errors', 'ok', 1073741823, 'count'),
            ({'bus': {'consecutive_errors': 1073741824}}, 'bus.consecutive_errors', 'out_of_range', '', 'count'),
            ({'bus': {'consecutive_errors': -1}}, 'bus.consecutive_errors', 'invalid', '', 'count'),
            ({'bus': {'consecutive_errors': 0.0}}, 'bus.consecutive_errors', 'invalid', '', 'count'),
        ):
            with self.subTest(field=field, result=result):
                await self.assert_reading({'healthy': False, **result}, field, status, value, unit)

    async def test_typed_health_state_does_not_claim_motion_readiness(self):
        await self.start_vm(None)
        for result, status, state in (({'healthy': True}, 'ok', 'healthy'),
            ({'healthy': True, 'degraded': True}, 'ok', 'healthy'),
            ({'healthy': False, 'degraded': True}, 'ok', 'degraded'),
            ({'healthy': False}, 'ok', 'unhealthy'), ({}, 'invalid', ''),
            ({'healthy': 1}, 'invalid', ''), ({'healthy': False, 'degraded': 0}, 'invalid', '')):
            await self.assert_reading(result, 'health.state', status, state, 'state')
        await self.assert_reading({'battery': {'volts': 7.8}}, 'battery.volts', 'invalid', '', 'mV')
        self.assertEqual(self.robot.calls, [])

    async def test_typed_imu_state_defaults_and_frozen_missing_precedence(self):
        await self.start_vm(None)
        for imu, status, value in (({}, 'ok', 'not_converged'), ({'ready': True}, 'ok', 'converged'),
            ({'ready': True, 'consecutive_stale_blocks': 24}, 'ok', 'converged'),
            ({'ready': True, 'consecutive_stale_blocks': 25}, 'ok', 'frozen'),
            ({'ready': False, 'consecutive_stale_blocks': 25}, 'ok', 'frozen'),
            ({'missing': True, 'ready': True, 'consecutive_stale_blocks': 100}, 'ok', 'missing'),
            ({'ready': 1}, 'invalid', ''), ({'missing': None}, 'invalid', ''),
            ({'consecutive_stale_blocks': -1}, 'invalid', ''), ({'consecutive_stale_blocks': 1.5}, 'invalid', '')):
            await self.assert_reading({'healthy': False, 'imu': imu}, 'imu.state', status, value, 'state')
        await self.assert_reading({'healthy': False, 'imu': {'ready': True, 'consecutive_stale_blocks': 25}}, 'imu.ready', 'ok', True, 'boolean')

    async def test_typed_schema_parse_and_error_envelope_validation(self):
        await self.start_vm(None)
        for reply in ({}, [], {'jsonrpc': '1.0', 'id': 1, 'result': {'healthy': True}},
            {'jsonrpc': '2.0', 'id': True, 'result': {'healthy': True}},
            {'jsonrpc': '2.0', 'id': 0, 'result': {'healthy': True}},
            {'jsonrpc': '2.0', 'id': 1, 'result': []},
            {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -1}},
            {'jsonrpc': '2.0', 'id': 1, 'result': {'healthy': True}, 'error': {'code': -1, 'message': 'mock'}}):
            self.assertEqual(await self.reading(reply, 'healthy'), ['invalid', '', 'boolean', 'unmarked'])
        for index in (None, 1):
            reply = {'jsonrpc': '2.0', 'id': index, 'error': {'code': -32008, 'message': 'fixture service offline'}}
            self.assertEqual(await self.reading(reply, 'healthy'), ['error', '', 'boolean', 'unmarked'])
            await self.primitive('readingValue', (Var(3),), error=32)
        for text in ('{', '{"jsonrpc":"2.0","id":1,"result":{"healthy":true,"healthy":false}}',
            '{"jsonrpc":"2.0","id":1,"result":{"healthy":true,"cpu_temp_c":NaN}}', RawString(b'\xff')):
            await self.primitive('healthSample', (text, 'healthy'), error=32)
        await self.primitive('healthSample', ('{}', RawString(b'\xff')), error=32)
        await self.primitive('healthSample', ('{}', 'unsupported.field'), error=32)
        await self.primitive('healthSample', (1, 'healthy'), error=14)
        await self.primitive('healthSample', ('{}', False), error=14)
        await self.primitive('healthSample', ('{}',), error=28)
        # Keep uploaded bytecode below the official 1019-byte code-message
        # payload; grow the oversized input inside the actual VM heap instead.
        oversized = Program().push('x' * 512).op(7, 0)
        for _ in range(8):
            oversized.call('join', (Var(0), Var(0)), prim_set=1).op(7, 0)
        oversized.call('healthSample', (Var(0), 'healthy'))
        code = oversized.finish()
        self.assertLess(len(code), 1019)
        await asyncio.to_thread(self.runtime.execute, code, 32)

    async def test_typed_reading_value_checks_record_shape_and_status(self):
        await self.start_vm(None)
        await self.primitive('readingValue', (False,), error=11)
        await self.primitive('readingValue', (), error=28)
        for parts in (('unknown', '', 'mV', 'unmarked'), ('ok', 1, 'mV'), ('ok', 1, 'mV', 'unmarked', 'extra'),
            ('ok', 1, False, 'unmarked'), ('ok', 1, 'mV', False), ('ready', 1, 'mV', 'unmarked')):
            code = Program().call('makeList', parts, prim_set=1).op(7, 3).call('readingValue', (Var(3),)).finish()
            await asyncio.to_thread(self.runtime.execute, code, 32)
        nested = Program().call('makeList', (), prim_set=1).op(7, 5)
        nested.call('makeList', ('ok', Var(5), 'mV', 'unmarked'), prim_set=1).op(7, 3).call('readingValue', (Var(3),))
        await asyncio.to_thread(self.runtime.execute, nested.finish(), 32)
        for value in (0, False, ''):
            code = Program().call('makeList', ('ok', value, 'state', 'unmarked'), prim_set=1).op(7, 3).call('readingValue', (Var(3),)).finish()
            actual = await asyncio.to_thread(self.runtime.execute, code)
            self.assertIs(type(actual), type(value))
            self.assertEqual(actual, value)

    async def test_typed_record_allocation_survives_moving_gc(self):
        await self.start_vm(None)
        vm = self.runtime.wire
        start = len(vm.events)
        fill = Program().call('newByteArray', (262080,), prim_set=1).op(19, 1).push(0).finish()
        await asyncio.to_thread(self.runtime.execute, fill)
        self.assertFalse(any(kind == 20 and index == 255 and b'GC took' in body for kind, index, body in vm.events[start:]), 'heap setup must fit without collecting')
        start = len(vm.events)
        # Only healthSample allocates VM objects between setup and this record.
        await self.assert_reading({'healthy': False, 'simulation': True}, 'health.state', 'ok', 'unhealthy', 'state', 'simulation')
        self.assertTrue(any(kind == 20 and index == 255 and b'GC took' in body for kind, index, body in vm.events[start:]), 'record construction must actually compact the heap')
        self.assertEqual(self.robot.calls, [])


if __name__ == '__main__':
    if platform.system() != 'Linux':
        raise SystemExit('Real SmallVM MicroDuck primitive tests require local Linux; no remote fallback')
    unittest.main(verbosity=2)
