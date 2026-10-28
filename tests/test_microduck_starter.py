# SPDX-License-Identifier: MPL-2.0
"""Actual JS compilation and local native bytecode; all robot services fictional."""
import asyncio
import contextlib
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from package_js_editor import package


def helper(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'tests' / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class StarterFixture:
    @classmethod
    def setUpClass(cls):
        node = os.environ.get('NODE_BINARY') or shutil.which('node')
        source = Path(os.environ.get('JS_EDITOR_UPSTREAM', ROOT.parent / 'microblocks-editor-upstream-20261027'))
        if not node or not (source / '.git').exists():
            raise unittest.SkipTest('Pinned JS source and Node required')
        cls.temp = tempfile.TemporaryDirectory(prefix='microduck-starter-')
        cls.base = Path(cls.temp.name)
        cls.assets = cls.base / 'assets'
        package(source, cls.assets, profile='microduck')
        result = subprocess.run([node, str(ROOT / 'tests/js-microduck-starter.test.cjs'), str(cls.assets)], capture_output=True, text=True, timeout=45)
        if result.returncode:
            cls.temp.cleanup()
            raise AssertionError(result.stdout + result.stderr)
        cls.compiled = json.loads(result.stdout)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()


class MicroDuckStarterImport(StarterFixture, unittest.TestCase):
    def test_coherent_optional_import_exact_sources_and_roundtrip(self):
        self.assertTrue(self.compiled['roundtrip'])
        self.assertEqual(len(self.compiled['functions']), 186)
        meta = json.loads((self.assets / 'microduck-starter-libraries.json').read_text())
        bundle = (self.assets / meta['bundle']).read_bytes()
        self.assertEqual(meta['action_blocks'], 'simulation_only')
        self.assertEqual(len(meta['sources']), 10)
        for entry in meta['sources']:
            raw = (ROOT / entry['source_path']).read_bytes()
            self.assertEqual(raw, (self.assets / entry['packaged_source']).read_bytes())
            self.assertEqual(hashlib.sha256(raw).hexdigest(), entry['sha256'])
            self.assertEqual(raw, bundle[entry['bundle_offset']:entry['bundle_offset'] + entry['bytes']])
        self.assertEqual(len(json.loads((self.assets / 'microduck-libraries.json').read_text())['sources']), 6)
        self.assertFalse(json.loads((self.assets / 'target-profile.json').read_text())['connection_enabled'])


@unittest.skipUnless(sys.platform == 'linux' and os.environ.get('SMALLVM_MICRODUCK_BINARY'), 'Verified local Linux SmallVM required')
class MicroDuckStarterNative(StarterFixture, unittest.IsolatedAsyncioTestCase):
    async def test_actual_native_execution_layers_errors_confirmation_and_disposal(self):
        vm = helper('starter_vm_helpers', 'test_linux_microduck_vm.py')
        motion = helper('starter_motion_helpers', 'test_linux_microduck_motion.py')
        robot = helper('starter_robot_helpers', 'test_linux_microduck_robot.py')
        read = helper('starter_read_helpers', 'test_linux_microduck_robot_service.py')
        depth = helper('starter_depth_helpers', 'test_linux_microduck_depth_service.py')
        head = helper('starter_head_helpers', 'test_linux_microduck_head_service.py')
        pad = helper('starter_pad_helpers', 'test_linux_microduck_gamepad_service.py')
        binary = Path(os.environ['SMALLVM_MICRODUCK_BINARY'])
        self.assertTrue(binary.is_absolute() and binary.is_file())
        async def runtime(folder, socket=None):
            data = folder / 'program';data.mkdir(mode=0o700)
            r = await asyncio.to_thread(vm.Runtime, binary, data, socket)
            try:
                for function in self.compiled['functions']:
                    code = bytes(function['bytes']);code += bytes(-len(code) % 4)
                    await asyncio.to_thread(r.wire.upload, function['id'], code, 3)
            except BaseException:
                await asyncio.to_thread(r.stop)
                raise
            return r
        async def execute(r, name, error=None):
            code = bytes(self.compiled['probes'][name]);code += bytes(-len(code) % 4)
            return await asyncio.to_thread(r.execute, code, error, 250)
        async def stop(r):
            await asyncio.to_thread(r.stop)
            log = r.log_path.read_text()
            self.assertEqual(r.process.returncode, 0, log)
            self.assertNotIn('AddressSanitizer', log)
            self.assertNotIn('runtime error:', log)
        work = Path(tempfile.mkdtemp(dir=self.base))
        r = await runtime(work)
        try:
            for name in ('unavailableBattery', 'unavailableRange', 'unavailableButton', 'unavailableHead', 'invalidRange', 'invalidButton'):
                self.assertEqual(await execute(r, name), 'error', name)
        finally:
            await stop(r)
        wire = await read.RobotWire(work / 'robot.sock').start()
        gateway = await read.normal_gateway(work / 'read-only', wire.path)
        folder = work / 'health';folder.mkdir()
        r = await runtime(folder, gateway.path)
        try:
            self.assertEqual(await execute(r, 'batteryStatus'), 'ok')
            self.assertEqual(await execute(r, 'batteryValue'), 0)
            self.assertEqual(await execute(r, 'batteryUnit'), '0.01%')
            self.assertEqual(await execute(r, 'advancedBattery'), 'ok')
            self.assertEqual(await execute(r, 'boardTemperature'), 41250)
            self.assertEqual(await execute(r, 'healthVerdict'), 'degraded')
            self.assertEqual(await execute(r, 'advancedClock'), '408000')
            self.assertEqual(gateway.robot_read.entries, {})
            self.assertTrue(all(q['method'] in ('hello', 'robot.health') for q in wire.audit))
        finally:
            await stop(r);await gateway.stop();await wire.stop()
        for name, module, make, socket_name, store, probes in (
            ('depth', depth, depth.wire.SensorSimulator, 'tof.sock', 'depth', [('rangeValue', 1000), ('rangeNoTarget', 'no_target')]),
            ('head', head, head.imu.HeadSimulator, 'tofd.sock', 'head_imu', [('headValue', 23125)]),
            ('pad', pad, pad.wire.SensorSimulator, 'pad.sock', 'gamepad', [('buttonValue', False)])):
            folder = work / name;folder.mkdir()
            original = getattr(module, 'wire', None)
            original_fixture = original.fixture if name == 'pad' else None
            def pad_fixture(service, profile):
                description, messages = original_fixture(service, profile)
                if service == 'pad':
                    for message in messages:
                        for event in message['params'].get('events', []):
                            if event['kind'] == 1:
                                event['value'] = 0  # Explicit observed release, not descriptor state.
                return description, messages
            with mock.patch.object(original, 'fixture', side_effect=pad_fixture) if name == 'pad' else contextlib.nullcontext():
                service = await make(folder / 'fixture').start()
                gateway = await module.normal_gateway(folder / 'normal', service.directory / socket_name)
                r = await runtime(folder, gateway.path)
                try:
                    for probe, expected in probes:
                        self.assertEqual(await execute(r, probe), expected, probe)
                    self.assertEqual(getattr(gateway, store).entries, {})
                finally:
                    await stop(r);await gateway.stop();await service.stop()
        service = await motion.motion.MotionSimulator(work / 'motion', True).start()
        folder = work / 'moving-fixture';folder.mkdir()
        r = await runtime(folder, service.gateway.path)
        try:
            await execute(r, 'falseForward', 32);await execute(r, 'badSpeed', 32)
            self.assertEqual(service.motion.snapshot()['recorded_frames'], 0)
            reply = json.loads(await execute(r, 'forward'))['result']
            self.assertEqual(reply['last_notification']['params'], {'vx': .1, 'vy': 0., 'vyaw': 0.})
            self.assertFalse(reply['physical_movement_enabled'])
            await execute(r, 'cancel')
            reply = json.loads(await execute(r, 'turn'))['result']
            self.assertEqual(reply['last_notification']['params'], {'vx': 0., 'vy': 0., 'vyaw': .25})
            await execute(r, 'cancel')
            self.assertIsNone(json.loads(await execute(r, 'advancedStatus'))['result']['active_lease_id'])
            service.motion.allow_motion = False
            self.assertIn('error', json.loads(await execute(r, 'forward')))
        finally:
            await stop(r);await service.stop()
        service = await robot.robot.RobotSimulator(work / 'robot-preview', True).start()
        folder = work / 'discrete-fixture';folder.mkdir()
        r = await runtime(folder, service.gateway.path)
        try:
            await execute(r, 'falseStop', 32)
            for name in ('stop', 'chirp', 'skill', 'advancedStop'):
                reply = json.loads(await execute(r, name))['result']
                self.assertEqual(reply['status'], 'recorded_not_executed')
                self.assertFalse(reply['physical_movement_enabled'])
            self.assertEqual(len(service.preview.audit), 4)
            await execute(r, 'badSkill', 32)
            self.assertEqual(len(service.preview.audit), 4)
            service.preview.allowed = False
            self.assertIn('error', json.loads(await execute(r, 'chirp')))
            self.assertEqual(len(service.preview.audit), 4)
        finally:
            await stop(r);await service.stop()
        print(json.dumps({'microduck_starter': {'functions_uploaded': len(self.compiled['functions']), 'actual_local_vm': True, 'physical_hardware': False, 'simulated_services': True}}))
