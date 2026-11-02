#!/usr/bin/env python3
"""Temporary same-origin HTTP/WS Pi editor, explicitly open to its local LAN.

No login, token, TLS, proxy, router, firewall or service configuration. Start only
after approving the exact listener; defaults expire after 30 minutes. The verified
PTY bridge still owns one controller and forwards bounded binary VM messages.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse
import asyncio
from http import HTTPStatus
import ipaddress
from pathlib import Path
import signal
import time

PRIVATE = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))


class Policy:
    def __init__(self, bind, port, clients):
        address = ipaddress.ip_address(bind)
        network = ipaddress.ip_network(clients, strict=True)
        if (str(address) != bind or not isinstance(address, ipaddress.IPv4Address)
                or not any(address in n for n in PRIVATE)
                or not isinstance(network, ipaddress.IPv4Network)
                or not any(network.subnet_of(n) for n in PRIVATE)
                or network.prefixlen < 24 or type(port) is not int or not 1024 <= port <= 65535):
            raise ValueError('Exact private IPv4, port 1024..65535, and private /24 or narrower client scope required')
        self.bind, self.port, self.clients = bind, port, network
        self.host = f'{bind}:{port}'
        self.origin = 'http://' + self.host

    def request_allowed(self, peer, path, headers):
        try:
            allowed = isinstance(peer, tuple) and ipaddress.ip_address(peer[0]) in self.clients
        except (ValueError, TypeError, IndexError):
            allowed = False
        origins = headers.get_all('Origin')
        if (not allowed or headers.get_all('Host') != [self.host]
                or len(origins) > 1 or origins and origins != [self.origin]):
            return False
        if path == '/ws/vm':
            return origins == [self.origin] and [v.lower() for v in headers.get_all('Upgrade')] == ['websocket']
        return not headers.get_all('Upgrade')


class LanEditor:
    def __init__(self, backend, policy, *, lease=1800):
        if type(lease) not in (int, float) or not 0 < lease <= 1800:
            raise ValueError('Listener lifetime must be at most 30 minutes')
        self.backend, self.policy, self.lease = backend, policy, lease
        self.deadline = None
        self.server = self.timer = None

    def request(self, connection, request):
        if not self.policy.request_allowed(connection.remote_address, request.path, request.headers):
            return self.backend.response(HTTPStatus.FORBIDDEN, b'Exact local Host, Origin and client scope required')
        if request.path == '/ws/vm':
            return None
        try:
            body, mime = self.backend.assets.read(request.path)
            response = self.backend.response(HTTPStatus.OK, body, mime)
            response.headers['Content-Security-Policy'] = (
                "default-src 'self' data: blob:; connect-src 'self' " + self.policy.origin.replace('http:', 'ws:') +
                "; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
            return response
        except (OSError, RuntimeError, UnicodeError, ValueError):
            return self.backend.response(HTTPStatus.NOT_FOUND, b'Asset unavailable')

    async def handle(self, ws):
        if self.deadline is None or time.monotonic() >= self.deadline:
            await ws.close(1001, 'Temporary session expired')
            return
        # No authentication exchange. The verified backend sends ready only
        # after checking and opening the selected VM's PTY.
        await self.backend.handle(ws)

    async def start(self, *, activated=False, factory=None):
        if not activated:
            raise ValueError('Approve the exact unencrypted LAN listener before --activate')
        if self.deadline is not None:
            raise ValueError('A session cannot restart')
        if factory is None:
            from websockets.asyncio.server import serve
            factory = serve
        self.deadline = time.monotonic() + self.lease
        self.server = await factory(self.handle, self.policy.bind, self.policy.port,
            process_request=self.request, origins=[self.policy.origin], compression=None,
            open_timeout=5, close_timeout=2, max_size=4096, max_queue=8,
            write_limit=8192, server_header=None)
        if any(s.getsockname()[:2] != (self.policy.bind, self.policy.port) for s in self.server.sockets):
            self.expire()
            await self.server.wait_closed()
            raise ValueError('Unexpected listener address')
        self.timer = asyncio.get_running_loop().call_later(self.lease, self.expire)
        return self

    def expire(self):
        if self.server is not None:
            self.server.close()

    async def stop(self):
        self.expire()
        if self.timer is not None:
            self.timer.cancel()
        if self.server is not None:
            await self.server.wait_closed()
        self.backend.close()


def separate_runtime(editor, paths):
    if any(path == editor or editor in path.parents for path in paths):
        raise ValueError('VM executable and private data must be outside the served assets')


async def run(args):
    from bridge import Bridge
    editor = args.editor.resolve(strict=True)
    separate_runtime(editor, [p.resolve(strict=True) for p in (args.pty_info, args.vm_executable)])
    policy = Policy(args.bind, args.port, args.allow_clients)
    backend = Bridge(editor, args.pty_info, args.vm_executable, args.port)
    server = LanEditor(backend, policy)
    try:
        await server.start(activated=args.activate)
        print(f'Open local Pi editor: {policy.origin}/ (30 minutes; no authentication or encryption)', flush=True)
        for signum in (signal.SIGINT, signal.SIGTERM):
            asyncio.get_running_loop().add_signal_handler(signum, server.expire)
        await server.server.wait_closed()
    finally:
        await server.stop()


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--activate', action='store_true')
    for name in ('editor', 'pty-info', 'vm-executable'):
        p.add_argument('--' + name, required=True, type=Path)
    p.add_argument('--bind', required=True)
    p.add_argument('--port', type=int, default=8877)
    p.add_argument('--allow-clients', required=True)
    args = p.parse_args()
    if not args.activate:
        p.error('Approve this unencrypted LAN listener before --activate')
    try:
        asyncio.run(run(args))
    except (OSError, RuntimeError, ValueError) as error:
        p.exit(1, f'Local HTTP server refused: {error}\n')
