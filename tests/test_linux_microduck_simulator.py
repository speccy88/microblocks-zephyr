#!/usr/bin/env python3
"""Explicit simulated robot only; real Gateway and private Unix sockets, no hardware."""
# SPDX-License-Identifier: MIT
import asyncio
import importlib
import json
import math
import os
from pathlib import Path
import signal
import stat
import sys
import tempfile
import time
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
package = types.ModuleType('microduck_simulator_test')
package.__path__ = [str(ROOT / 'linux/microduck')]
sys.modules[package.__name__] = package
simulator = importlib.import_module(package.__name__ + '.simulator')
rpc = importlib.import_module(package.__name__ + '.protocol')


@unittest.skipUnless(sys.platform == 'linux', 'requires local Linux Unix peer credentials; no remote fallback')
class ExplicitSimulation(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='md-sim-test-')
        self.base = Path(self.temporary.name)
        self.service = None
        self.next_id = 1

    async def asyncTearDown(self):
        if self.service:
            await self.service.stop()
        self.temporary.cleanup()

    async def start(self, actions=False):
        self.service = await simulator.Simulator(self.base / 'session', actions).start()
        return self.service

    async def call(self, method, params=None, confirmed=False):
        reader, writer = await rpc.connect_checked(self.base / 'session/gateway.sock', os.geteuid(), rpc.MAX_REPLY, True)
        try:
            request_id = self.next_id
            self.next_id += 1
            writer.write(rpc.encode({'jsonrpc': '2.0', 'id': request_id, 'method': method,
                'params': {} if params is None else params, 'confirmed': confirmed}, rpc.MAX_REQUEST))
            await writer.drain()
            reply = await asyncio.wait_for(rpc.read_message(reader, rpc.MAX_REPLY), 2)
            self.assertEqual(reply['id'], request_id)
            return reply
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_private_startup_fictional_api44_fields_and_discovery(self):
        service = await self.start()
        directory = self.base / 'session'
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        for name in ('robot.sock', 'gateway.sock', 'simulation.json', 'actions.jsonl'):
            self.assertEqual(stat.S_IMODE((directory / name).stat().st_mode), 0o600)
        saved = json.loads((directory / 'simulation.json').read_text())
        self.assertEqual(saved, service.ready)
        self.assertTrue(saved['simulation'])
        self.assertEqual(saved['uid'], os.geteuid())
        self.assertEqual(saved['api_version'], 44)
        health = (await self.call('robot.health'))['result']
        self.assertFalse(health['healthy'])
        self.assertTrue(health['degraded'])
        self.assertIs(health['simulation'], True)
        self.assertIn('SIMULATION', health['reason'])
        self.assertIn('fictional', health['reason'])
        self.assertEqual(set(health['battery']), {'volts', 'percent'})
        self.assertEqual(health['battery'], {'volts': 7.8, 'percent': 73.25})
        self.assertEqual(health['cpu_temp_c'], 41.25)
        self.assertEqual(health['motors']['hottest'], 'SIMULATION-joint')
        self.assertEqual(health['control_loop']['achieved_hz'], 49.95)
        self.assertEqual(health['imu'], {'ready': False, 'missing': False, 'stale_blocks': 0, 'consecutive_stale_blocks': 0})
        self.assertTrue(all(math.isfinite(value) for value in (health['cpu_temp_c'], health['motors']['max_c'],
            health['motors']['mean_c'], health['control_loop']['target_hz'], health['control_loop']['achieved_hz'])))
        for word in ('temperatures', 'loop', 'IMU'):
            self.assertIn(word, health['reason'])
        policies = (await self.call('robot.policies'))['result']
        skills = (await self.call('robot.skills'))['result']
        self.assertFalse(policies['enabled'])
        self.assertEqual(policies['skills'], [row['name'] for row in skills['skills']])
        self.assertEqual(service.action_count, 0)

    async def test_default_gateway_readonly_even_with_request_confirmation(self):
        await self.start()
        for method, params in [('robot.sound', {'tag': 'chirp'}), ('robot.do', {'skill': simulator.SKILLS[0]}), ('robot.enable', {'on': True})]:
            reply = await self.call(method, params, True)
            self.assertEqual(reply['error']['code'], -32003)
        self.assertEqual((self.base / 'session/actions.jsonl').read_bytes(), b'')

    async def test_mock_actions_need_confirmation_discovery_and_bounded_private_log(self):
        with patch.object(simulator, 'MAX_ACTIONS', 2):
            await self.start(True)
            self.assertEqual((await self.call('robot.sound', {'tag': 'chirp'}))['error']['code'], -32003)
            self.assertEqual((await self.call('robot.do', {'skill': 'not_advertised'}, True))['error']['code'], -32005)
            self.assertEqual((await self.call('robot.enable', {'on': True}, True))['error']['code'], -32003)
            for method, params in [('robot.sound', {'tag': 'chirp'}), ('robot.do', {'skill': simulator.SKILLS[0]})]:
                result = (await self.call(method, params, True))['result']
                self.assertTrue(result['accepted'])
                self.assertTrue(result['simulated'])
                self.assertIn('no physical action', result['reason'])
            self.assertEqual((await self.call('robot.sound', {'tag': 'chirp'}, True))['error']['code'], -32010)
            entries = [json.loads(line) for line in (self.base / 'session/actions.jsonl').read_text().splitlines()]
            self.assertEqual([entry['sequence'] for entry in entries], [1, 2])
            self.assertTrue(all(entry['simulation'] for entry in entries))
            self.assertEqual(self.service.action_count, 2)

    async def test_refuses_existing_relative_and_symlink_paths_without_overwrite(self):
        occupied = self.base / 'occupied'
        occupied.mkdir()
        sentinel = occupied / 'keep'
        sentinel.write_text('preserved')
        linked = self.base / 'linked'
        linked.symlink_to(occupied, target_is_directory=True)
        for directory in (occupied, linked):
            with self.assertRaises(FileExistsError):
                await simulator.Simulator(directory).start()
        for directory in (Path('relative'), linked / 'new'):
            with self.assertRaises(ValueError):
                await simulator.Simulator(directory).start()
        self.assertEqual(sentinel.read_text(), 'preserved')
        self.assertFalse((occupied / 'new').exists())

    async def test_cleanup_retains_directory_artifacts_and_replaced_socket(self):
        service = await self.start()
        replaced = self.base / 'session/robot.sock'
        replaced.unlink()
        replaced.write_text('replacement must survive')
        await service.stop()
        self.assertEqual(replaced.read_text(), 'replacement must survive')
        self.assertFalse((self.base / 'session/gateway.sock').exists())
        self.assertTrue((self.base / 'session/simulation.json').is_file())
        self.assertTrue((self.base / 'session/actions.jsonl').is_file())

    async def test_cli_ready_json_and_sigterm_cleanup(self):
        target = self.base / 'cli'
        started = time.monotonic()
        child = await asyncio.create_subprocess_exec(sys.executable, str(ROOT / 'linux/microduck/simulator.py'),
            '--directory', str(target), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            ready = json.loads(await asyncio.wait_for(child.stdout.readline(), 2))
            self.assertLess(time.monotonic() - started, 2)
            self.assertTrue(ready['simulation'])
            self.assertEqual(ready['pid'], child.pid)
            self.assertEqual(ready['allowed_mock_actions'], [])
            self.assertEqual(ready['gateway_socket'], str(target / 'gateway.sock'))
            child.send_signal(signal.SIGTERM)
            self.assertEqual(await asyncio.wait_for(child.wait(), 2), 0)
            self.assertEqual(await child.stderr.read(), b'')
            self.assertFalse((target / 'robot.sock').exists())
            self.assertFalse((target / 'gateway.sock').exists())
            self.assertTrue((target / 'simulation.json').is_file())
        finally:
            if child.returncode is None:
                child.kill()
                await child.wait()


if __name__ == '__main__':
    unittest.main(verbosity=2)
