#!/usr/bin/env python3
"""Mock official daemons over real private Unix sockets; no robot/SSH/BLE access."""
# SPDX-License-Identifier: MIT
import asyncio
import importlib
import json
import os
from pathlib import Path
import socket
import stat
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

package = types.ModuleType('microduck_local_test')
package.__path__ = [str(Path(__file__).resolve().parents[1] / 'linux/microduck')]
sys.modules['microduck_local_test'] = package
protocol = importlib.import_module('microduck_local_test.protocol')
gateway = importlib.import_module('microduck_local_test.gateway')
client = importlib.import_module('microduck_local_test.client')


def request(method='robot.health', params=None, confirmed=False, index=1):
    return {'jsonrpc': '2.0', 'id': index, 'method': method, 'params': {} if params is None else params, 'confirmed': confirmed}


class Protocol(unittest.TestCase):
    def test_strict_json_bounds_utf8_duplicate_members_and_nonfinite_numbers(self):
        q = request()
        self.assertEqual(protocol.decode(protocol.encode(q, protocol.MAX_REQUEST), protocol.MAX_REQUEST), q)
        for raw in [b'{}', b'[]\nextra', b'\xff\n', b'{"x":1,"x":2}\n', b'{"x":NaN}\n', b'{"x":1e10000}\n', b'[' * 100 + b'0' + b']' * 100 + b'\n', b'x' * 8193 + b'\n']:
            with self.subTest(raw=raw[:25]), self.assertRaises(protocol.RpcError):
                protocol.decode(raw, protocol.MAX_REQUEST)

    def test_exact_method_parameter_allowlist_and_positive_request_ids(self):
        self.assertEqual(gateway.validate(request('robot.enable', {'on': False}))[1], {'on': False, 'toggle': False})
        self.assertEqual(gateway.validate(request('system.logs', {'unit': 'robotd'}))[1], {'unit': 'robotd', 'lines': 50, 'boot': 0})
        for method in ['system.authenticate', 'system.pairingPin', 'net.connect', 'robot.move', 'robot.head', 'robot.stop', 'robot.relax', 'media.frame', 'update.apply', 'exec', '__proto__', []]:
            with self.subTest(method=method), self.assertRaises(protocol.RpcError):
                gateway.validate(request(method))
        bad = [request(index=0), request(index=True), request(index=2**31), request('robot.do', {'skill': []}), request('robot.sound', {'tag': 'wheee'}), request('robot.enable', {'on': 1}), request('system.logs', {'unit': '--directory'}), request('robot.health', {'command': 'arbitrary shell'}), {**request(), 'extra': 1}]
        for q in bad:
            with self.subTest(request=q), self.assertRaises(protocol.RpcError):
                gateway.validate(q)

    def test_response_ids_errors_and_unknown_outcome_are_preserved(self):
        for reply in [{'jsonrpc': '2.0', 'id': 2, 'result': {}}, {'jsonrpc': '2.0', 'id': 1, 'result': {}, 'error': {'code': 1}}]:
            with self.assertRaises(protocol.RpcError):
                protocol.response_result(reply, 1)
        reply = {'jsonrpc': '2.0', 'id': 1, 'error': {'code': -32008, 'message': 'do not expose token', 'data': {'outcome': 'unknown'}}}
        with self.assertRaises(protocol.RpcError) as error:
            protocol.response_result(reply, 1, gateway_outcome=True)
        self.assertEqual(error.exception.outcome, 'unknown')
        self.assertNotIn('token', str(error.exception))


class MockDaemon:
    def __init__(self, path):
        self.path, self.server = path, None
        self.calls, self.tasks = [], set()
        self.mode, self.api = 'normal', 44
        self.health = {'healthy': True, 'battery': {'volts': 7.8, 'percent': 73.25}, 'bus': {'failures': 0}}
        self.policies = {'skills': ['bow', 'nod'], 'homed': True, 'sitting': False, 'slots': [{'slot': 'walk', 'path': '/policies/walk.onnx'}, {'slot': 'stand', 'path': '/policies/stand.onnx'}]}

    async def start(self):
        self.server = await asyncio.start_unix_server(self.handle, path=str(self.path), limit=protocol.MAX_REQUEST)
        self.path.chmod(0o600)
        return self

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        try:
            hello = await protocol.read_message(reader, protocol.MAX_REQUEST)
            self.calls.append(hello)
            assert hello == {'jsonrpc': '2.0', 'id': 0, 'method': 'hello', 'params': {'api_version': 44}}
            writer.write(protocol.encode({'jsonrpc': '2.0', 'id': 0, 'result': {'api_version': self.api}}, protocol.MAX_REPLY))
            await writer.drain()
            line = await reader.readline()
            if not line:
                return
            q = protocol.decode(line, protocol.MAX_REQUEST)
            self.calls.append(q)
            assert set(q) == {'jsonrpc', 'id', 'method', 'params'}
            if self.mode == 'timeout':
                await asyncio.sleep(.5)
                return
            if self.mode == 'malformed':
                writer.write(b'not-json\n')
            elif self.mode == 'oversized':
                writer.write((json.dumps({'jsonrpc': '2.0', 'id': q['id'], 'result': 'x' * 65536}) + '\n').encode())
            elif self.mode == 'error':
                writer.write(protocol.encode({'jsonrpc': '2.0', 'id': q['id'], 'error': {'code': -32001, 'message': 'PRIVATE_TEST_TOKEN', 'data': 'PRIVATE_TEST_DATA'}}, protocol.MAX_REPLY))
            else:
                result = self.health if q['method'] == 'robot.health' else self.policies if q['method'] == 'robot.policies' else {'accepted': True, 'method': q['method']}
                if self.mode == 'near_limit':
                    result = 'x' * 65450
                writer.write(protocol.encode({'jsonrpc': '2.0', 'id': q['id'] + (1 if self.mode == 'wrong_id' else 0), 'result': result}, protocol.MAX_REPLY))
            await writer.drain()
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


@unittest.skipUnless(sys.platform == 'linux' and hasattr(socket, 'SO_PEERCRED'), 'Linux Unix peer credentials required')
class UnixGateway(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix='md-gw-')
        self.base = Path(self.tmp.name)
        self.base.chmod(0o700)
        self.robot = await MockDaemon(self.base / 'robot.sock').start()
        self.config = await MockDaemon(self.base / 'config.sock').start()
        self.updater = await MockDaemon(self.base / 'updater.sock').start()
        self.mapping = {name: {'path': str(self.base / (name + '.sock')), 'uid': os.geteuid()} for name in ('robot', 'config', 'updater')}
        self.gw = await gateway.Gateway(self.mapping, timeout=.1).start(self.base / 'gateway.sock')
        self.client = client.Client(self.base / 'gateway.sock', timeout=2)

    async def asyncTearDown(self):
        await self.gw.stop()
        await self.robot.stop()
        await self.config.stop()
        await self.updater.stop()
        self.tmp.cleanup()

    async def raw(self, data):
        reader, writer = await asyncio.open_unix_connection(str(self.base / 'gateway.sock'))
        writer.write(data)
        await writer.drain()
        reply = await asyncio.wait_for(reader.readline(), 2)
        writer.close()
        await writer.wait_closed()
        return protocol.decode(reply, protocol.MAX_REPLY)

    async def replace_gateway(self, **kwargs):
        await self.gw.stop()
        self.gw = await gateway.Gateway(self.mapping, timeout=.1, **kwargs).start(self.base / 'gateway.sock')

    async def test_capabilities_are_local_and_service_socket_is_private(self):
        caps = await self.client.call('microduck.capabilities')
        self.assertEqual(caps['api_version'], 44)
        self.assertEqual(caps['allowed_mutations'], [])
        self.assertEqual(caps['hardware_validation'], 'not performed')
        self.assertEqual(self.robot.calls + self.config.calls + self.updater.calls, [])
        self.assertEqual(stat.S_IMODE((self.base / 'gateway.sock').stat().st_mode), 0o600)

    async def test_exact_api44_handshake_route_and_optional_battery_fields(self):
        self.assertEqual(await self.client.battery(), {'volts': 7.8, 'percent': 73.25})
        self.assertEqual(self.client.last_metadata['upstream_api_version'], 44)
        await self.client.call('system.info')
        await self.client.call('update.status')
        self.assertEqual([q['method'] for q in self.robot.calls], ['hello', 'robot.health'])
        self.assertEqual([q['method'] for q in self.config.calls], ['hello', 'system.info'])
        self.assertEqual([q['method'] for q in self.updater.calls], ['hello', 'update.status'])
        self.robot.health.pop('battery')
        self.assertIsNone(await self.client.battery())

    async def test_mutations_need_both_operator_allowlist_and_request_confirmation(self):
        with self.assertRaises(protocol.RpcError) as error:
            await self.client.quack(confirmed=True)
        self.assertEqual(error.exception.code, -32003)
        self.assertEqual(self.robot.calls, [])
        await self.replace_gateway(allowed_mutations=['robot.sound'])
        with self.assertRaises(protocol.RpcError):
            await self.client.quack()
        self.assertEqual(self.robot.calls, [])
        result = await self.client.quack(confirmed=True)
        self.assertTrue(result['accepted'])
        self.assertEqual(self.robot.calls[-1]['params'], {'tag': 'chirp'})
        self.assertNotIn('confirmed', self.robot.calls[-1])

    async def test_skills_are_discovered_before_dispatch_and_unknown_names_never_execute(self):
        await self.replace_gateway(allowed_mutations=['robot.do'])
        with self.assertRaises(protocol.RpcError) as error:
            await self.client.perform_skill('invented', confirmed=True)
        self.assertEqual(error.exception.code, -32005)
        self.assertEqual([q['method'] for q in self.robot.calls], ['hello', 'robot.policies'])
        await self.client.perform_skill('bow', confirmed=True)
        self.assertEqual(self.robot.calls[-1]['method'], 'robot.do')
        self.assertEqual(self.robot.calls[-1]['params'], {'skill': 'bow'})
        self.robot.policies['skills'] = 'bow'
        with self.assertRaises(protocol.RpcError):
            await self.client.perform_skill('b', confirmed=True)

    async def test_policy_selection_uses_advertised_slots_and_paths_only(self):
        await self.replace_gateway(allowed_mutations=['robot.loadPolicy'])
        for params in [{'slot': 'unknown', 'path': None}, {'slot': 'walk', 'path': '/arbitrary/unsafe.onnx'}]:
            with self.assertRaises(protocol.RpcError):
                await self.client.call('robot.loadPolicy', params, True)
        self.assertFalse(any(q['method'] == 'robot.loadPolicy' for q in self.robot.calls))
        await self.client.call('robot.loadPolicy', {'slot': 'walk', 'path': '/policies/stand.onnx'}, True)
        await self.client.call('robot.loadPolicy', {'slot': 'walk', 'path': None}, True)
        self.assertEqual(self.robot.calls[-1]['params'], {'slot': 'walk', 'path': None})

    async def test_timeout_after_action_send_is_unknown_and_never_retried(self):
        await self.replace_gateway(allowed_mutations=['robot.sound'])
        self.robot.mode = 'timeout'
        with self.assertRaises(protocol.RpcError) as error:
            await self.client.quack(True)
        self.assertEqual(error.exception.code, -32008)
        self.assertEqual(error.exception.outcome, 'unknown')
        self.assertEqual(sum(q['method'] == 'robot.sound' for q in self.robot.calls), 1)

    async def test_wrong_ids_malformed_and_oversized_replies_cannot_be_success(self):
        for mode in ('wrong_id', 'malformed', 'oversized'):
            self.robot.mode = mode
            with self.subTest(mode=mode), self.assertRaises(protocol.RpcError) as error:
                await self.client.health()
            self.assertEqual(error.exception.outcome, 'unknown')

    async def test_remote_errors_are_sanitized_without_losing_refusal_code(self):
        self.robot.mode = 'error'
        with self.assertRaises(protocol.RpcError) as error:
            await self.client.health()
        self.assertEqual(error.exception.code, -32001)
        self.assertEqual(error.exception.outcome, 'rejected')
        self.assertNotIn('PRIVATE_TEST', str(error.exception))

    async def test_gateway_envelope_overflow_after_forwarding_remains_unknown(self):
        await self.replace_gateway(allowed_mutations=['robot.sound'])
        self.robot.mode = 'near_limit'
        with self.assertRaises(protocol.RpcError) as error:
            await self.client.quack(True)
        self.assertEqual(error.exception.code, -32010)
        self.assertEqual(error.exception.outcome, 'unknown')
        self.assertEqual(sum(q['method'] == 'robot.sound' for q in self.robot.calls), 1)

    async def test_private_config_is_strict_and_never_follows_a_symlink_or_fifo(self):
        path = self.base / 'config.json'
        path.write_text(json.dumps({'version': 1, 'upstreams': self.mapping}))
        path.chmod(0o600)
        self.assertEqual(gateway.load_config(path), self.mapping)
        path.chmod(0o644)
        with self.assertRaises(ValueError):
            gateway.load_config(path)
        path.chmod(0o600)
        link = self.base / 'config-link.json'
        link.symlink_to(path)
        with self.assertRaises(OSError):
            gateway.load_config(link)
        fifo = self.base / 'config-pipe'
        os.mkfifo(fifo)
        with self.assertRaises(ValueError):
            gateway.load_config(fifo)
        path.write_text(json.dumps({'version': True, 'upstreams': self.mapping}))
        with self.assertRaises(ValueError):
            gateway.load_config(path)

    async def test_actual_peer_credentials_and_upstream_owner_mismatch_refusal(self):
        self.gw.upstreams['robot'].uid = os.geteuid() + 1
        with self.assertRaises(protocol.RpcError) as error:
            await self.client.health()
        self.assertEqual(error.exception.code, -32001)
        self.assertEqual(error.exception.outcome, 'not_sent')
        self.assertEqual(self.robot.calls, [])
        # Fault-injected denied-client branch; ordinary calls above use real SO_PEERCRED.
        with patch.object(gateway, 'peer_uid', return_value=os.geteuid() + 1):
            with self.assertRaises(protocol.RpcError) as refused:
                await self.client.call('microduck.capabilities')
        self.assertEqual(refused.exception.code, -32001)

    async def test_upstream_symlink_and_world_access_are_refused(self):
        link = self.base / 'robot-link.sock'
        link.symlink_to(self.robot.path)
        self.gw.upstreams['robot'].path = link
        with self.assertRaises(protocol.RpcError):
            await self.client.health()
        self.gw.upstreams['robot'].path = self.robot.path
        self.robot.path.chmod(0o666)
        with self.assertRaises(protocol.RpcError):
            await self.client.health()
        self.robot.path.chmod(0o600)
        self.assertEqual(self.robot.calls, [])

    async def test_malformed_requests_and_oversized_input_never_reach_robot(self):
        for data in [b'[]\n', b'{"jsonrpc":"2.0","id":true,"method":"robot.health"}\n', b'{"id":1,"id":2}\n', b'x' * 8193 + b'\n']:
            reply = await self.raw(data)
            self.assertIn('error', reply)
        self.assertEqual(self.robot.calls, [])

    async def test_bounded_client_capacity_and_fresh_connection_reconnect(self):
        await self.replace_gateway(max_clients=1)
        reader, writer = await asyncio.open_unix_connection(str(self.base / 'gateway.sock'))
        try:
            for _ in range(20):
                if self.gw.active == 1:
                    break
                await asyncio.sleep(.001)
            with self.assertRaises(protocol.RpcError) as error:
                await self.client.call('microduck.capabilities')
            self.assertEqual(error.exception.code, -32006)
            self.assertEqual(error.exception.outcome, 'not_sent')
        finally:
            writer.close()
            await writer.wait_closed()
        for _ in range(20):
            if self.gw.active == 0:
                break
            await asyncio.sleep(.001)
        await self.client.health()
        await self.client.health()
        self.assertEqual([q['method'] for q in self.robot.calls], ['hello', 'robot.health', 'hello', 'robot.health'])

    async def test_api_skew_is_reported_instead_of_claiming_physical_compatibility(self):
        self.robot.api = 45
        await self.client.health()
        self.assertEqual(self.client.last_metadata['upstream_api_version'], 45)
        self.assertEqual(self.client.last_metadata['expected_api_version'], 44)
        caps = await self.client.call('microduck.capabilities')
        self.assertEqual(caps['last_upstream_api_versions']['robot'], 45)

    async def test_existing_socket_or_file_is_never_replaced_or_deleted(self):
        with self.assertRaises(FileExistsError):
            await gateway.Gateway(self.mapping).start(self.base / 'gateway.sock')
        path = self.base / 'existing'
        path.write_text('retain sentinel')
        with self.assertRaises(FileExistsError):
            await gateway.Gateway(self.mapping).start(path)
        self.assertEqual(path.read_text(), 'retain sentinel')
        self.gw.path.unlink()
        self.gw.path.write_text('replacement sentinel')
        await self.gw.stop()
        self.assertEqual((self.base / 'gateway.sock').read_text(), 'replacement sentinel')

    async def test_executable_client_preserves_stdin_request_id_without_a_shell(self):
        process = await asyncio.create_subprocess_exec(sys.executable, client.__file__, '--socket', str(self.base / 'gateway.sock'), stdin=asyncio.subprocess.PIPE, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        stdout, stderr = await asyncio.wait_for(process.communicate(protocol.encode(request(index=51), protocol.MAX_REQUEST)), 3)
        self.assertEqual(process.returncode, 0, stderr.decode())
        reply = protocol.decode(stdout, protocol.MAX_REPLY)
        self.assertEqual(reply['id'], 51)
        self.assertTrue(reply['result']['healthy'])
        self.assertEqual(self.robot.calls[-1]['id'], 51)

    async def test_executable_gateway_is_readonly_and_cleans_only_its_fixture_socket(self):
        config = self.base / 'cli-config.json'
        config.write_text(json.dumps({'version': 1, 'upstreams': self.mapping}))
        config.chmod(0o600)
        path = self.base / 'cli-gateway.sock'
        process = await asyncio.create_subprocess_exec(sys.executable, gateway.__file__, '--socket', str(path), '--config', str(config), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        try:
            line = await asyncio.wait_for(process.stdout.readline(), 3)
            self.assertIn(b'mutations: disabled', line)
            local = client.Client(path)
            self.assertTrue((await local.health())['healthy'])
            with self.assertRaises(protocol.RpcError) as error:
                await local.quack(True)
            self.assertEqual(error.exception.code, -32003)
        finally:
            if process.returncode is None:
                process.terminate()
            stdout, stderr = await asyncio.wait_for(process.communicate(), 3)
        self.assertEqual(process.returncode, 0, stderr.decode())
        self.assertFalse(path.exists())


if __name__ == '__main__':
    if sys.platform != 'linux':
        raise SystemExit('Explicit integration run requires Linux Unix peer credentials')
    unittest.main(verbosity=2)
