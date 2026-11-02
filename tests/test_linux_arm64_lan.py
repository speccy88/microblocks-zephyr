# SPDX-License-Identifier: MIT
import asyncio
from http import HTTPStatus
from pathlib import Path
import time
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock
import sys
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


if __name__ == '__main__':
    unittest.main(verbosity=2)
