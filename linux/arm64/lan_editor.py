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
import re
from pathlib import Path
import signal
import time
from urllib.parse import urlsplit

PRIVATE = tuple(ipaddress.ip_network(n) for n in ('10.0.0.0/8', '172.16.0.0/12', '192.168.0.0/16'))
TAILSCALE = ipaddress.ip_network('100.64.0.0/10')


def proxy_origin(value):
    """An exact HTTP IPv4 or HTTPS Tailscale-name origin behind a local proxy."""
    if not isinstance(value, str):
        raise ValueError('Canonical private HTTP IPv4 or Tailscale HTTPS name origin required')
    parsed = urlsplit(value)
    host = parsed.hostname or ''
    if parsed.scheme == 'https':
        labels = host.split('.')
        if (value != 'https://' + host or len(host) > 253 or len(labels) != 4
                or labels[-2:] != ['ts', 'net']
                or not all(re.fullmatch(r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?', label) for label in labels[:2])):
            raise ValueError('Canonical exact HTTPS machine.tailnet.ts.net origin on port 443 required')
        return host
    address = ipaddress.ip_address(host)
    if (not isinstance(address, ipaddress.IPv4Address)
            or value != 'http://' + str(address)
            or not any(address in network for network in (*PRIVATE, TAILSCALE))):
        raise ValueError('Canonical private or Tailscale IPv4 HTTP origin on port 80 required')
    return str(address)


class Policy:
    def __init__(self, bind, port, clients):
        address = ipaddress.ip_address(bind)
        network = ipaddress.ip_network(clients, strict=True)
        loopback = bind == '127.0.0.1' and clients == '127.0.0.1/32'
        if (str(address) != bind or not isinstance(address, ipaddress.IPv4Address)
                or not (loopback or any(address in n for n in PRIVATE))
                or not isinstance(network, ipaddress.IPv4Network)
                or not (loopback or any(network.subnet_of(n) for n in PRIVATE))
                or network.prefixlen < 24 or type(port) is not int or not 1024 <= port <= 65535):
            raise ValueError('Exact private IPv4, port 1024..65535, and private /24 or narrower client scope required')
        self.bind, self.port, self.clients = bind, port, network
        self.host = f'{bind}:{port}'
        self.origin = 'http://' + self.host
        self.origins = [self.origin]
        self.host_origins = {self.host: self.origin}

    def request_allowed(self, peer, path, headers):
        try:
            allowed = isinstance(peer, tuple) and ipaddress.ip_address(peer[0]) in self.clients
        except (ValueError, TypeError, IndexError):
            allowed = False
        hosts = headers.get_all('Host')
        origin = self.host_origins.get(hosts[0]) if len(hosts) == 1 else None
        origins = headers.get_all('Origin')
        if (not allowed or origin is None
                or len(origins) > 1 or origins and origins != [origin]):
            return False
        if path in ('/ws/vm', '/ws/update'):
            return origins == [origin] and [v.lower() for v in headers.get_all('Upgrade')] == ['websocket']
        return not headers.get_all('Upgrade')


class LoopbackProxyPolicy(Policy):
    """Only a local reverse proxy; client filtering belongs to each public route.

    No forwarded header is trusted. The public Host and browser Origin remain
    unchanged through Caddy; the immediate backend peer must be 127.0.0.1.
    """
    def __init__(self, origin, port, additional_origins=()):
        address = proxy_origin(origin)
        if type(port) is not int or not 1024 <= port <= 65535:
            raise ValueError('Unprivileged backend port 1024..65535 required')
        if not isinstance(additional_origins, (list, tuple)) or len(additional_origins) > 4:
            raise ValueError('At most four exact additional proxy origins required')
        self.bind, self.port = '127.0.0.1', port
        self.clients = ipaddress.ip_network('127.0.0.1/32')
        self.host, self.origin = address, origin
        self.origins = [origin]
        self.host_origins = {address: origin}
        for extra in additional_origins:
            host = proxy_origin(extra)
            if host in self.host_origins:
                raise ValueError('Proxy origins must be unique')
            self.origins.append(extra)
            self.host_origins[host] = extra


class LanEditor:
    def __init__(self, backend, policy, *, lease=1800, permanent=False, updates=None):
        if type(permanent) is not bool or (not permanent and (type(lease) not in (int, float) or not 0 < lease <= 1800)):
            raise ValueError('Listener lifetime must be at most 30 minutes')
        self.backend, self.policy, self.lease = backend, policy, lease
        self.permanent = permanent
        self.updates = updates
        self.deadline = None
        self.server = self.timer = None

    def request(self, connection, request):
        if not self.policy.request_allowed(connection.remote_address, request.path, request.headers):
            return self.backend.response(HTTPStatus.FORBIDDEN, b'Exact local Host, Origin and client scope required')
        if request.path == '/api/pi/update':
            import json
            status = self.updates.status() if self.updates is not None else {
                'target': 'raspberry-pi5', 'current_vm_version': 417, 'supported_vm_versions': [417],
                'upload_enabled': False, 'native_install_enabled': False,
                'update': {'state': 'idle'}, 'reason': 'Managed native updater is not configured'}
            return self.backend.response(HTTPStatus.OK, json.dumps(status).encode(), 'application/json')
        if request.path == '/ws/update':
            if self.updates is None:
                return self.backend.response(HTTPStatus.NOT_FOUND, b'Managed native updates are unavailable')
            return None
        if request.path == '/ws/vm':
            return None
        try:
            body, mime = self.backend.assets.read(request.path)
            response = self.backend.response(HTTPStatus.OK, body, mime)
            response.headers['Content-Security-Policy'] = (
                "default-src 'self' data: blob:; connect-src 'self' " +
                self.policy.host_origins[request.headers['Host']].replace('https:', 'wss:', 1).replace('http:', 'ws:', 1) +
                "; script-src 'self' 'unsafe-inline' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; "
                "object-src 'none'; base-uri 'self'; frame-ancestors 'none'")
            return response
        except (OSError, RuntimeError, UnicodeError, ValueError):
            return self.backend.response(HTTPStatus.NOT_FOUND, b'Asset unavailable')

    async def handle(self, ws):
        if self.deadline is None or time.monotonic() >= self.deadline:
            await ws.close(1001, 'Temporary session expired')
            return
        if self.updates is not None and ws.request.path == '/ws/update':
            await self.updates.handle(ws)
            return
        if self.updates is not None and self.updates.applying:
            await ws.close(1013, 'Native runtime update in progress')
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
        self.deadline = float('inf') if self.permanent else time.monotonic() + self.lease
        self.server = await factory(self.handle, self.policy.bind, self.policy.port,
            process_request=self.request, origins=self.policy.origins, compression=None,
            open_timeout=5, close_timeout=2, max_size=4096, max_queue=8,
            write_limit=8192, server_header=None)
        if any(s.getsockname()[:2] != (self.policy.bind, self.policy.port) for s in self.server.sockets):
            self.expire()
            await self.server.wait_closed()
            raise ValueError('Unexpected listener address')
        if not self.permanent:
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
