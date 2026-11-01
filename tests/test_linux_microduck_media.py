"""Media metadata/relay preparation; all services and packets are simulated."""
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
package = types.ModuleType('media_lab_services')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
media = importlib.import_module(package.__name__ + '.media_simulator')
rpc = importlib.import_module(package.__name__ + '.protocol')
spec = importlib.util.spec_from_file_location('media_robot_test_helpers', ROOT / 'tests/test_linux_microduck_robot.py')
robot_tests = importlib.util.module_from_spec(spec)
spec.loader.exec_module(robot_tests)
PREVIEWS = {k: v for k, v in robot_tests.PREVIEWS.items() if k in media.DISCRETE}


def request(name='reading', p=None, confirmed=False):
    return {'jsonrpc': '2.0', 'id': 1, 'method': media.PREFIX + name,
            'params': {'field': 'video.width'} if p is None else p, 'confirmed': confirmed}


class MediaProtocol(unittest.TestCase):
    def test_closed_methods_parameters_and_library_defaults(self):
        for bad in [request(p={'field': 'audio.start'}), request(p={'field': 'video.width', 'url': 'invalid'}),
                    {**request(), 'endpoint': 'invalid'}, {**request(), 'id': True}, {**request(), 'confirmed': 1}]:
            with self.assertRaises(rpc.RpcError):
                media.validate(bad)
        lib = (ROOT / 'linux/microduck/Media_Simulation.ubl').read_text()
        self.assertIn('SIMULATION ONLY', lib)
        self.assertNotIn("'bool' true", lib)
        example = (ROOT / 'linux/microduck/media-simulation.ubp').read_text()
        self.assertNotIn('microduckSimRelayPreview', example)

    def test_all_five_source_registration_states_and_unknown_account(self):
        lab = media.MediaLab()
        for state in media.STATES:
            lab.remote_status = {'service': 'SIMULATION', 'since': -2**63, 'state': state}
            if state == 'registered':
                lab.remote_status.update(account=None, peerId='SIMULATION', lastHeartbeat=2**63 - 1)
            if state == 'retrying':
                lab.remote_status['reason'] = 'SIMULATION internal reason, never exposed'
            self.assertEqual(lab.status_reading('relay.state')['value'], state)
            self.assertEqual(lab.status_reading('relay.since')['value'], str(-2**63))
            heartbeat = lab.status_reading('relay.heartbeat')
            self.assertEqual(heartbeat['value'], str(2**63 - 1) if state == 'registered' else None)
            if state == 'registered':
                self.assertIs(lab.status_reading('relay.account_known')['value'], False)
        lab.remote_status = None
        self.assertEqual(lab.status_reading('relay.state')['status'], 'absent')

    def test_malformed_status_is_not_inferred_as_signed_out_or_zero(self):
        lab = media.MediaLab()
        for state in [None, 'ready', [], True]:
            lab.remote_status = {'state': state, 'service': 'SIMULATION', 'since': 0}
            with self.assertRaises(rpc.RpcError):
                lab.status_reading('relay.state')
        for delta in [{'since': True}, {'lastHeartbeat': 2**63}, {'peerId': ''}, {'account': 4}]:
            lab.remote_status = {**media.MediaLab().remote_status, **delta}
            with self.assertRaises(rpc.RpcError):
                lab.status_reading('relay.state')

    def test_rolling_and_lifetime_budget_backwards_clock(self):
        clock = [0.0]
        budget = media.Budget(lambda: clock[0])
        for window in range(4):
            clock[0] = window * 60
            self.assertTrue(all(budget.take() for _ in range(32)))
            self.assertFalse(budget.take())
        clock[0] = 240
        self.assertFalse(budget.take())
        clock[0] = 1
        with self.assertRaises(rpc.RpcError):
            budget.take()

    def test_discrete_preview_envelopes_and_confirmation_without_upstream(self):
        lab = media.MediaLab(True)
        for method, args in PREVIEWS.items():
            result = lab.record(method, args, True)
            self.assertEqual(result['status'], 'recorded_not_executed')
            self.assertIsNone(result['admission'])
            self.assertIsNone(result['applied'])
        self.assertEqual(len(lab.preview_envelopes), 9)
        self.assertTrue(all(p['type'] == 'peer' and p['sessionId'] == media.SESSION and 'id' in p['rpc'] for p in lab.preview_envelopes))
        for allow, confirm in [(False, True), (True, False), (True, 1)]:
            other = media.MediaLab(allow)
            with self.assertRaises(rpc.RpcError):
                other.record('robot.init', {}, confirm)
            self.assertEqual(other.preview_envelopes, [])
            self.assertEqual(other.budget.total, 0)

    def test_teleop_held_sound_subscriptions_stream_and_credentials_are_refused(self):
        lab = media.MediaLab(True)
        for method, args in {**{k: v for k, v in robot_tests.PREVIEWS.items() if k not in media.DISCRETE},
                             'robot.sound': {'tag': 'wheee', 'hold': True}, 'robot.subscribe': {'hz': 50},
                             'media.stream': {'url': None}, 'account.login': {}}.items():
            with self.assertRaises(rpc.RpcError):
                lab.record(method, args, True)
        self.assertEqual(lab.preview_envelopes, [])
        self.assertEqual(lab.budget.total, 0)


@unittest.skipUnless(sys.platform == 'linux', 'Linux verified private sockets required')
class MediaUnixBackend(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='media-lab-')
        self.base = Path(self.temp.name)
        self.service = await media.MediaSimulator(self.base / 'sim', True).start()

    async def asyncTearDown(self):
        await self.service.stop()
        self.temp.cleanup()

    async def call(self, p=None, name='reading', confirmed=False):
        reader, writer = await rpc.connect_checked(self.service.directory / 'gateway.sock', os.geteuid(), 8192, True)
        try:
            writer.write(rpc.encode(request(name, p, confirmed), 8192))
            await writer.drain()
            return await rpc.read_message(reader, 8192)
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_all_fields_preserve_unsupported_zero_false_exact_counters_and_source_envelopes(self):
        for field, unit in media.FIELDS.items():
            result = (await self.call({'field': field}))['result']
            self.assertEqual(result['unit'], unit)
            self.assertEqual(result['status'], 'unsupported' if field.startswith('audio.') else 'ok')
            self.assertLessEqual(len(rpc.encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': result}, 8192)), 760)
        self.assertEqual((await self.call({'field': 'stream.replies'}))['result']['value'], str(2**63 + 17))
        self.assertIs((await self.call({'field': 'robot.healthy'}))['result']['value'], False)
        audit = self.service.media.relay.audit
        self.assertTrue(all(p['rpc']['params'] == {} for p in audit))
        self.assertEqual({p['rpc']['method'] for p in audit}, {'media.video', 'media.stream', 'robot.health', 'robot.policies'})

    async def test_named_failures_and_wrong_session_or_id_never_become_known_values(self):
        for fault in media.FAULTS[1:]:
            self.service.media.relay.fault = fault
            result = (await self.call({'field': 'video.width'}))['result']
            self.assertEqual(result['status'], 'timeout' if fault == 'timeout' else 'absent' if fault == 'absent' else 'error')
            self.assertIsNone(result['value'])
        self.assertEqual(len(self.service.media.relay.audit), 6)  # no replay

    async def test_previews_never_call_mock_or_real_services_and_share_unique_ids_with_reads(self):
        await self.call({'field': 'video.width'})
        with mock.patch.object(rpc.Upstream, 'call', side_effect=AssertionError('no upstream mutation')), \
             mock.patch.object(self.service.media.relay, 'exchange', side_effect=AssertionError('no preview sent')):
            for method, args in PREVIEWS.items():
                result = (await self.call({'method': method, 'args': args}, 'preview', True))['result']
                self.assertTrue(result['recorded'])
        packets = self.service.media.relay.audit + self.service.media.preview_envelopes
        self.assertEqual(len({p['rpc']['id'] for p in packets}), len(packets))
        self.assertEqual(self.service.preview.audit, [])
        self.assertEqual(self.service.action_count, 0)

    async def test_missing_status_rate_limit_and_error_envelopes_are_explicit(self):
        self.service.media.remote_status = None
        self.assertEqual((await self.call({'field': 'relay.state'}))['result']['status'], 'absent')
        for _ in range(32):
            self.assertEqual((await self.call())['result']['status'], 'ok')
        self.assertEqual((await self.call())['result']['status'], 'rate_limited')
        limited = (await self.call({'method': 'robot.stop', 'args': {}}, 'preview', True))['result']
        self.assertFalse(limited['recorded'])
        self.assertEqual(self.service.media.preview_envelopes, [])
        self.assertIn('error', await self.call({'field': 'unknown'}))
        self.assertEqual(len(self.service.media.relay.audit), 32)

    async def test_cancellation_has_no_replay_and_audio_has_no_rpc(self):
        self.service.media.relay.fault = 'timeout'
        task = asyncio.create_task(self.service.media.sample('video.width'))
        await asyncio.sleep(.01)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):
            await task
        self.assertEqual(len(self.service.media.relay.audit), 1)
        await self.service.media.sample('audio.receive')
        self.assertEqual(len(self.service.media.relay.audit), 1)

    async def test_actual_cli_default_flags_and_clean_shutdown(self):
        p = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'linux/microduck/media_simulator.py'),
                                                '--directory', str(self.base / 'cli'), stdout=asyncio.subprocess.PIPE,
                                                stderr=asyncio.subprocess.PIPE)
        try:
            value = json.loads(await asyncio.wait_for(p.stdout.readline(), 3))
            self.assertFalse(value['allow_relay_previews'])
            self.assertFalse(value['live_transport'])
            self.assertFalse(value['physical_movement_enabled'])
        finally:
            if p.returncode is None:
                p.terminate()
            _, error = await asyncio.wait_for(p.communicate(), 3)
        self.assertEqual(p.returncode, 0, error.decode())
        self.assertFalse((self.base / 'cli/gateway.sock').exists())
        failed = media.MediaSimulator(self.base / 'failed-metadata')
        with mock.patch.object(media, '_fresh_file', side_effect=OSError('SIMULATION metadata write refused')):
            with self.assertRaises(OSError):
                await failed.start()
        self.assertIsNone(failed.gateway)
        self.assertEqual(failed.streams, [])
        self.assertFalse((failed.directory / 'robot.sock').exists())
        self.assertFalse((failed.directory / 'gateway.sock').exists())


SOURCE = Path(os.environ.get('SMALLVM_UPSTREAM', ROOT.parent / 'smallvm-linux-upstream'))
EXTERNAL = os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform == 'linux' and struct.calcsize('P') == 8 and
                     (EXTERNAL or shutil.which('gcc') and (SOURCE / '.git').is_dir()), 'native LP64 compiler/source required')
class MediaNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='media-native-')
        cls.base = Path(cls.temp.name)
        if EXTERNAL:
            cls.binary = Path(EXTERNAL)
        else:
            p = subprocess.run([sys.executable, str(ROOT / 'linux/arm64/build.py'), '--upstream', str(SOURCE),
                                '--output', str(cls.base / 'build'), '--sanitize'], capture_output=True, text=True, timeout=120)
            if p.returncode:
                raise AssertionError(p.stdout + p.stderr)
            cls.binary = cls.base / 'build/smallvm'
        spec = importlib.util.spec_from_file_location('media_vm_helpers', ROOT / 'tests/test_linux_microduck_vm.py')
        cls.helpers = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.helpers)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    async def asyncSetUp(self):
        self.work = Path(tempfile.mkdtemp(dir=self.base))
        self.service = await media.MediaSimulator(self.work / 'sim', True).start()
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

    async def call(self, p, name='reading', confirmed=False):
        job = await self.primitive('begin', (media.PREFIX + name, json.dumps(p), confirmed))
        deadline = asyncio.get_running_loop().time() + 4
        while await self.primitive('status', (job,)) == 'pending':
            self.assertLess(asyncio.get_running_loop().time(), deadline)
            await asyncio.sleep(.005)
        result = await self.primitive('result', (job,))
        await self.primitive('release', (job,), command=True)
        return result

    async def typed(self, reply):
        P, V = self.helpers.Program, self.helpers.Var
        await self.execute(P().call('mediaSample', (reply,)).op(7, 3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81, 2)) for i in range(1, 5)]

    async def test_real_vm_all_seventeen_readings(self):
        for field, unit in media.FIELDS.items():
            actual = await self.typed(await self.call({'field': field}))
            self.assertEqual(actual[0], 'unsupported' if field.startswith('audio.') else 'ok', field)
            self.assertEqual(actual[2:], [unit, 'simulation'])
        self.assertEqual(await self.typed(await self.call({'field': 'stream.sent'})), ['ok', '0', 'count64', 'simulation'])
        self.assertEqual(await self.typed(await self.call({'field': 'robot.enabled'})), ['ok', False, 'boolean', 'simulation'])

    async def test_native_guards_reject_unconfirmed_teleop_and_unknown_fields_before_io(self):
        await self.primitive('begin', (media.PREFIX + 'preview', '{"method":"robot.init","args":{}}', False), error=32)
        for name, p in [('reading', {'field': 'audio.start'}), ('preview', {'method': 'robot.move', 'args': robot_tests.PREVIEWS['robot.move']}),
                        ('preview', {'method': 'robot.sound', 'args': {'tag': 'wheee', 'hold': True}}),
                        ('preview', {'method': 'media.stream', 'args': {'url': None}})]:
            await self.primitive('begin', (media.PREFIX + name, json.dumps(p), True), error=32)
        self.assertEqual(self.service.media.budget.total, 0)
        self.assertEqual(self.service.media.relay.audit, [])

    async def test_native_discrete_previews_and_disabled_backend(self):
        with mock.patch.object(rpc.Upstream, 'call', side_effect=AssertionError('no mutation')):
            for method, args in PREVIEWS.items():
                result = json.loads(await self.call({'method': method, 'args': args}, 'preview', True))['result']
                self.assertTrue(result['recorded'])
                self.assertIsNone(result['applied'])
        self.assertEqual(len(self.service.media.preview_envelopes), 9)
        self.service.media.preview.allowed = False
        self.assertIn('error', json.loads(await self.call({'method': 'robot.init', 'args': {}}, 'preview', True)))

    async def test_native_failure_and_unsupported_values_cannot_be_extracted(self):
        for fault in media.FAULTS[1:]:
            self.service.media.relay.fault = fault
            actual = await self.typed(await self.call({'field': 'video.width'}))
            self.assertEqual(actual, ['timeout' if fault == 'timeout' else 'absent' if fault == 'absent' else 'error', '', 'px', 'simulation'])
        await self.typed(await self.call({'field': 'audio.receive'}))
        await self.primitive('readingValue', (self.helpers.Var(3),), error=32)

    async def test_native_signed_timestamp_counter_types_units_and_false_claims(self):
        def envelope(field, value, unit):
            return json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': {**media.reading(field, 'ok', value), 'unit': unit}})
        for value in (str(-2**63), str(2**63 - 1), '0'):
            self.assertEqual((await self.typed(envelope('relay.since', value, 'epoch_s')))[1], value)
        for field, value, unit in [('relay.since', str(2**63), 'epoch_s'), ('relay.since', '-0', 'epoch_s'),
                                   ('stream.sent', str(2**64), 'count64'), ('video.width', 0, 'px'),
                                   ('video.rotate', 45, 'degrees'), ('robot.enabled', 0, 'boolean'),
                                   ('audio.send', False, 'boolean'), ('relay.state', 'ready', 'state'), ('video.width', 640, 'mm')]:
            self.assertNotEqual((await self.typed(envelope(field, value, unit)))[0], 'ok')

    async def test_native_media_reading_allocation_survives_moving_gc(self):
        P, V = self.helpers.Program, self.helpers.Var
        events = self.runtime.wire.events
        await self.execute(P().call('newByteArray', (262080,), prim_set=1).op(19, 1).push(0))
        start = len(events)
        reply = json.dumps({'jsonrpc': '2.0', 'id': 1, 'result': media.reading('relay.heartbeat', 'ok', str(2**63 - 1))})
        self.assertEqual((await self.typed(reply))[1], str(2**63 - 1))
        self.assertTrue(any(k == 20 and i == 255 and b'GC took' in b for k, i, b in events[start:]))
        self.assertEqual(await self.primitive('readingValue', (V(3),)), str(2**63 - 1))


if __name__ == '__main__':
    unittest.main(verbosity=2)
