# SPDX-License-Identifier: MIT
import asyncio
from http import HTTPStatus
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
import sys
import socket
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'linux/arm64'))
Headers = Bridge = SafeAssets = None
if sys.platform == 'linux':
    try:
        from websockets.datastructures import Headers
        from bridge import Bridge, SafeAssets
    except ImportError:
        pass
from lan_editor import LanEditor, Policy, LoopbackProxyPolicy, separate_runtime


class Backend:
    response = staticmethod(Bridge.response) if Bridge is not None else None
    def __init__(self):
        self.handle = AsyncMock()
        self.assets = SimpleNamespace(read=lambda path: (SafeAssets.path(path) and b'fixture', 'text/html'))
    def close(self):
        pass


@unittest.skipUnless(Bridge is not None and Headers is not None, 'Linux and pinned websockets required')
class OpenLanTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.policy = Policy('192.168.1.105', 8877, '192.168.1.0/24')
        self.backend = Backend()
        self.server = LanEditor(self.backend, self.policy)

    def headers(self, **changes):
        values = {'Host': self.policy.host, 'Origin': self.policy.origin, 'Upgrade': 'websocket'}
        values.update(changes)
        return Headers((k, v) for k, v in values.items() if v is not None)

    async def test_no_key_or_authentication_exchange(self):
        self.server.deadline = time.monotonic() + 30
        socket = SimpleNamespace(recv=AsyncMock(), close=AsyncMock())
        await self.server.handle(socket)
        self.backend.handle.assert_awaited_once_with(socket)
        socket.recv.assert_not_awaited()
        socket.close.assert_not_awaited()

    async def test_exact_http_origin(self):
        self.assertTrue(self.policy.request_allowed(('192.168.1.109', 1), '/ws/vm', self.headers()))
        for origin in (None, 'null', 'https://speccy88.github.io', 'https://192.168.1.105:8877', 'http://192.168.1.105:80'):
            self.assertFalse(self.policy.request_allowed(('192.168.1.109', 1), '/ws/vm', self.headers(Origin=origin)))

    async def test_host_duplicates_and_outside_lan(self):
        for field in ('Host', 'Origin', 'Upgrade'):
            h = self.headers(); h[field] = h[field]
            self.assertFalse(self.policy.request_allowed(('192.168.1.109', 1), '/ws/vm', h))
        for peer in (('192.168.2.1', 1), ('8.8.8.8', 1), ('::ffff:192.168.1.109', 1), None):
            self.assertFalse(self.policy.request_allowed(peer, '/ws/vm', self.headers()))
        self.assertFalse(self.policy.request_allowed(('192.168.1.109', 1), '/ws/vm', self.headers(Host='other.test:8877')))

    async def test_paths_are_exact_and_assets_remain_bounded(self):
        for path in ('/ws/vm?x=1', '/ws/vm/', '/other'):
            self.assertFalse(self.policy.request_allowed(('192.168.1.109', 1), path, self.headers()))
        for path in ('/../private', '/%2e%2e/key', '/.hidden', '/a?token=bad'):
            request = SimpleNamespace(path=path, headers=self.headers(Origin=None, Upgrade=None))
            self.assertEqual(self.server.request(SimpleNamespace(remote_address=('192.168.1.109', 1)), request).status_code, HTTPStatus.NOT_FOUND)

    async def test_activation_guard_and_bind_scope(self):
        factory = AsyncMock()
        with self.assertRaises(ValueError):
            await self.server.start(factory=factory)
        factory.assert_not_awaited()
        listener = SimpleNamespace(sockets=[SimpleNamespace(getsockname=lambda: ('192.168.1.105', 8877))],
            close=lambda: None, wait_closed=AsyncMock())
        factory.return_value = listener
        await self.server.start(activated=True, factory=factory)
        self.assertEqual(factory.call_args.args[1:3], ('192.168.1.105', 8877))
        self.assertEqual(factory.call_args.kwargs['origins'], ['http://192.168.1.105:8877'])
        self.assertNotIn('ssl', factory.call_args.kwargs)
        await self.server.stop()

    async def test_expiry_refuses_vm_access(self):
        self.server.deadline = time.monotonic() - 1
        socket = SimpleNamespace(close=AsyncMock())
        await self.server.handle(socket)
        self.backend.handle.assert_not_awaited()
        socket.close.assert_awaited_once_with(1001, 'Temporary session expired')

    async def test_scope_and_runtime_validation(self):
        for bind, port, scope in (('0.0.0.0', 8877, '192.168.1.0/24'), ('127.0.0.1', 8877, '192.168.1.0/24'),
                ('192.168.1.105', 80, '192.168.1.0/24'), ('192.168.1.105', 8877, '0.0.0.0/0')):
            with self.assertRaises(ValueError):
                Policy(bind, port, scope)
        with self.assertRaises(ValueError):
            LanEditor(self.backend, self.policy, lease=1801)
        with self.assertRaises(ValueError):
            separate_runtime(Path('/editor'), [Path('/editor/data/pty.json')])

    async def test_proxy_keeps_public_origin_but_accepts_only_local_caddy(self):
        policy = LoopbackProxyPolicy('http://192.168.1.105', 8877)
        headers = Headers({'Host': '192.168.1.105', 'Origin': 'http://192.168.1.105', 'Upgrade': 'websocket'})
        self.assertTrue(policy.request_allowed(('127.0.0.1', 1), '/ws/vm', headers))
        self.assertFalse(policy.request_allowed(('192.168.1.109', 1), '/ws/vm', headers))
        headers['X-Forwarded-For'] = '127.0.0.1'
        self.assertFalse(policy.request_allowed(('192.168.1.109', 1), '/ws/vm', headers))
        headers = Headers({'Host': '127.0.0.1:8877', 'Origin': 'http://192.168.1.105', 'Upgrade': 'websocket'})
        self.assertFalse(policy.request_allowed(('127.0.0.1', 1), '/ws/vm', headers))
        for origin in ('https://192.168.1.105', 'http://example.com', 'http://192.168.1.105:80', 'http://192.168.1.105/path'):
            with self.assertRaises(ValueError):
                LoopbackProxyPolicy(origin, 8877)

    async def test_explicit_permanent_mode_has_no_expiry_timer(self):
        server = LanEditor(self.backend, self.policy, permanent=True)
        listener = SimpleNamespace(sockets=[SimpleNamespace(getsockname=lambda: ('192.168.1.105', 8877))],
            close=lambda: None, wait_closed=AsyncMock())
        await server.start(activated=True, factory=AsyncMock(return_value=listener))
        self.assertIsNone(server.timer)
        self.assertEqual(server.deadline, float('inf'))
        await server.stop()

    async def test_proxy_additional_origins_keep_exact_host_origin_and_loopback(self):
        policy = LoopbackProxyPolicy('http://192.168.2.50', 8877, ['http://100.100.10.20'])
        for host in ('192.168.2.50', '100.100.10.20'):
            for path in ('/ws/vm', '/ws/update'):
                headers = Headers({'Host': host, 'Origin': 'http://' + host, 'Upgrade': 'websocket'})
                self.assertTrue(policy.request_allowed(('127.0.0.1', 1), path, headers))
                self.assertFalse(policy.request_allowed(('100.100.10.21', 1), path, headers))
                for field in ('Host', 'Origin', 'Upgrade'):
                    duplicate = headers.copy(); duplicate[field] = duplicate[field]
                    self.assertFalse(policy.request_allowed(('127.0.0.1', 1), path, duplicate))
                for origin in (None, 'http://attacker.invalid', 'http://100.100.10.21',
                        'http://100.100.10.20' if host.startswith('192.') else 'http://192.168.2.50'):
                    wrong = Headers({'Host': host, 'Upgrade': 'websocket'})
                    if origin is not None: wrong['Origin'] = origin
                    self.assertFalse(policy.request_allowed(('127.0.0.1', 1), path, wrong))
        for host in ('100.100.10.21', '127.0.0.1:8877', 'attacker.invalid'):
            headers = Headers({'Host': host, 'X-Forwarded-Host': '100.100.10.20'})
            self.assertFalse(policy.request_allowed(('127.0.0.1', 1), '/', headers))

    async def test_proxy_origin_validation_is_canonical_bounded_and_opt_in(self):
        for origin in ('http://100.63.255.255', 'http://100.128.0.1', 'http://8.8.8.8',
                'http://100.100.10.020', 'http://100.100.10.20:80', 'https://100.100.10.20',
                'http://100.100.10.20/', 'http://100.100.10.20?x=1',
                'http://user@100.100.10.20', 'http://100.100.10.20#fragment',
                'http://pi.example', 'http://[fd7a:115c:a1e0::1]', None):
            with self.subTest(origin=origin), self.assertRaises(ValueError):
                LoopbackProxyPolicy('http://192.168.2.50', 8877, [origin])
        for additional in (None, 'http://100.100.10.20', ['http://192.168.2.50'],
                ['http://100.100.10.20'] * 2, ['http://100.100.10.' + str(n) for n in range(1, 6)]):
            with self.subTest(additional=additional), self.assertRaises(ValueError):
                LoopbackProxyPolicy('http://192.168.2.50', 8877, additional)
        policy = LoopbackProxyPolicy('http://100.64.0.1', 8877, ['http://100.127.255.254', 'http://192.168.2.50'])
        self.assertEqual(policy.origins, ['http://100.64.0.1', 'http://100.127.255.254', 'http://192.168.2.50'])
        unconfigured = LoopbackProxyPolicy('http://192.168.2.50', 8877)
        self.assertFalse(unconfigured.request_allowed(('127.0.0.1', 1), '/', Headers({'Host': '100.100.10.20'})))

    async def test_proxy_csp_and_framework_origin_list_follow_configured_hosts(self):
        policy = LoopbackProxyPolicy('http://192.168.2.50', 8877, ['http://100.100.10.20'])
        server = LanEditor(self.backend, policy, permanent=True)
        for host in ('192.168.2.50', '100.100.10.20'):
            response = server.request(SimpleNamespace(remote_address=('127.0.0.1', 1)),
                SimpleNamespace(path='/', headers=Headers({'Host': host})))
            self.assertEqual(response.status_code, HTTPStatus.OK)
            self.assertIn("connect-src 'self' ws://" + host + ';', response.headers['Content-Security-Policy'])
        listener = SimpleNamespace(sockets=[SimpleNamespace(getsockname=lambda: ('127.0.0.1', 8877))],
            close=lambda: None, wait_closed=AsyncMock())
        factory = AsyncMock(return_value=listener)
        await server.start(activated=True, factory=factory)
        self.assertEqual(factory.call_args.kwargs['origins'], ['http://192.168.2.50', 'http://100.100.10.20'])
        await server.stop()

    async def test_actual_http_and_websocket_framework_accepts_both_proxy_origins(self):
        from websockets.asyncio.client import connect
        from websockets.exceptions import InvalidStatus
        with socket.socket() as reservation:
            reservation.bind(('127.0.0.1', 0))
            port = reservation.getsockname()[1]
        policy = LoopbackProxyPolicy('http://192.168.2.50', port, ['http://100.100.10.20'])
        async def ready_only(ws):
            await ws.send('ready')
            await ws.wait_closed()
        self.backend.handle = ready_only
        server = LanEditor(self.backend, policy, permanent=True)
        await server.start(activated=True)
        try:
            for host in ('192.168.2.50', '100.100.10.20'):
                reader, writer = await asyncio.open_connection('127.0.0.1', port)
                writer.write(('GET / HTTP/1.1\r\nHost: ' + host + '\r\nConnection: close\r\n\r\n').encode())
                await writer.drain()
                response = await asyncio.wait_for(reader.read(), 3)
                writer.close(); await writer.wait_closed()
                self.assertTrue(response.startswith(b'HTTP/1.1 200 OK'))
                self.assertIn(('ws://' + host).encode(), response)
                async with connect('ws://' + host + '/ws/vm', host='127.0.0.1', port=port,
                        proxy=None, origin='http://' + host, open_timeout=3) as ws:
                    self.assertEqual(await asyncio.wait_for(ws.recv(), 3), 'ready')
                with self.assertRaises(InvalidStatus) as refused:
                    async with connect('ws://' + host + '/ws/vm', host='127.0.0.1', port=port,
                            proxy=None, origin='http://attacker.invalid', open_timeout=3):
                        self.fail('Wrong browser origin accepted')
                self.assertEqual(refused.exception.response.status_code, HTTPStatus.FORBIDDEN)
        finally:
            await server.stop()


if __name__ == '__main__':
    unittest.main(verbosity=2)
