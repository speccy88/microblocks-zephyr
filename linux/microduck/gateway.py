#!/usr/bin/env python3
"""Private, same-UID MicroDuck JSON-RPC gateway. No TCP, shell or BLE transport."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import json
import os
from pathlib import Path
import signal
import socket
import stat
import sys

try:
    from .protocol import API_VERSION, SOURCE_COMMIT, MAX_REQUEST, MAX_REPLY, RpcError, Upstream, decode, encode, peer_uid, read_message
except ImportError:
    from protocol import API_VERSION, SOURCE_COMMIT, MAX_REQUEST, MAX_REPLY, RpcError, Upstream, decode, encode, peer_uid, read_message

ROUTES = {name: service for service, names in {
    'robot': 'robot.health robot.policies robot.skills robot.model robot.vetbook pad.bindings robot.sound robot.do robot.init robot.enable robot.loadPolicy',
    'config': 'system.info system.services system.logs net.status net.scan pad.status',
    'updater': 'hello update.status update.check update.log update.show update.listInstalled',
}.items() for name in names.split()}
MUTATIONS = frozenset('robot.sound robot.do robot.init robot.enable robot.loadPolicy'.split())


def _text(value, maximum=128):
    return isinstance(value, str) and 0 < len(value) <= maximum and not any(ord(c) < 32 or ord(c) == 127 for c in value)


def validate(request):
    if not isinstance(request, dict) or set(request) - {'jsonrpc', 'id', 'method', 'params', 'confirmed'} or request.get('jsonrpc') != '2.0' or type(request.get('id')) is not int or not 1 <= request['id'] <= 0x7fffffff:
        raise RpcError(-32600, 'JSON-RPC request requires a bounded numeric ID')
    method, params = request.get('method'), request.get('params', {})
    if not isinstance(method, str) or method not in ROUTES and method != 'microduck.capabilities':
        raise RpcError(-32601, 'Method is outside the local allowlist')
    if not isinstance(params, dict) or 'confirmed' in request and type(request['confirmed']) is not bool:
        raise RpcError(-32602, 'Invalid request parameters')
    keys = {
        'hello': {'api_version'}, 'update.check': {'component'}, 'update.listInstalled': {'component'},
        'update.log': {'limit'}, 'update.show': {'run'}, 'system.logs': {'unit', 'lines', 'boot'},
        'robot.sound': {'tag'}, 'robot.do': {'skill'}, 'robot.enable': {'on', 'toggle'}, 'robot.loadPolicy': {'slot', 'path'},
    }.get(method, set())
    if set(params) - keys:
        raise RpcError(-32602, 'Unknown parameter member')
    p = dict(params)
    good = True
    if method == 'hello':
        p.setdefault('api_version', API_VERSION)
        good = type(p['api_version']) is int and p['api_version'] == API_VERSION
    elif method in ('update.check', 'update.listInstalled'):
        good = _text(p.get('component'), 64) and p['component'].isascii() and p['component'].replace('-', '').replace('_', '').isalnum()
    elif method == 'update.log':
        p.setdefault('limit', 20)
        good = type(p['limit']) is int and 1 <= p['limit'] <= 100
    elif method == 'update.show':
        p.setdefault('run', None)
        good = p['run'] is None or type(p['run']) is int and 0 <= p['run'] <= 0x7fffffff
    elif method == 'system.logs':
        p.setdefault('lines', 50)
        p.setdefault('boot', 0)
        unit = p.get('unit')
        good = _text(unit, 64) and unit.removesuffix('.service').casefold() in {'updaterd', 'robotd', 'configd', 'btd', 'padd', 'netpadd', 'mediad', 'tofd', 'nfcd', 'bluetooth', 'networkmanager'} and type(p['lines']) is int and 1 <= p['lines'] <= 500 and type(p['boot']) is int and -1000 <= p['boot'] <= 0
    elif method == 'robot.sound':
        good = p.get('tag') in ('alarm', 'greet', 'inquire', 'peck', 'chirp', 'coo')
    elif method == 'robot.do':
        good = _text(p.get('skill'))
    elif method == 'robot.enable':
        p.setdefault('toggle', False)
        good = type(p.get('on')) is bool and type(p['toggle']) is bool
    elif method == 'robot.loadPolicy':
        p.setdefault('path', None)
        good = _text(p.get('slot'), 64) and (p['path'] is None or _text(p['path'], 512) and p['path'].startswith('/'))
    if not good:
        raise RpcError(-32602, 'Parameter value is invalid or out of bounds')
    return method, p


class Gateway:
    def __init__(self, upstreams, allowed_mutations=(), timeout=3, max_clients=4):
        if set(upstreams) - {'robot', 'config', 'updater'} or not upstreams or set(allowed_mutations) - MUTATIONS or not 1 <= max_clients <= 16:
            raise ValueError('Invalid gateway configuration')
        self.upstreams = {name: Upstream(value['path'], value['uid'], timeout) for name, value in upstreams.items()}
        self.allowed_mutations = frozenset(allowed_mutations)
        self.timeout, self.max_clients = timeout, max_clients
        self.server = self.path = self.identity = None
        self.active = 0
        self.last_versions = {}
        self.clients = set()
        self.tasks = set()

    async def dispatch(self, request):
        method, params = validate(request)
        if method == 'microduck.capabilities':
            return {'gateway_version': 1, 'api_version': API_VERSION, 'upstream_commit': SOURCE_COMMIT,
                'transport': 'unix-peercred', 'methods': sorted(name for name, service in ROUTES.items() if service in self.upstreams),
                'allowed_mutations': sorted(self.allowed_mutations), 'last_upstream_api_versions': dict(self.last_versions),
                'limits': {'request_bytes': MAX_REQUEST, 'reply_bytes': MAX_REPLY, 'clients': self.max_clients},
                'hardware_validation': 'not performed'}, None
        if method in MUTATIONS and (method not in self.allowed_mutations or request.get('confirmed') is not True):
            raise RpcError(-32003, 'Mutation needs operator allowlist and explicit per-request confirmation')
        service = ROUTES[method]
        if service not in self.upstreams:
            raise RpcError(-32004, 'Required robot service is not configured')
        upstream = self.upstreams[service]
        if method in ('robot.do', 'robot.loadPolicy'):
            policies, version = await upstream.call('robot.policies', {}, request['id'])
            self.last_versions[service] = version
            if not isinstance(policies, dict):
                raise RpcError(-32011, 'Robot did not report valid policy discovery')
            if method == 'robot.do':
                skills = policies.get('skills', [])
                if not isinstance(skills, list) or any(not isinstance(skill, str) for skill in skills) or params['skill'] not in skills:
                    raise RpcError(-32005, 'Skill was not advertised by this robot')
            if method == 'robot.loadPolicy':
                slots = policies.get('slots', [])
                if not isinstance(slots, list) or params['slot'] not in [slot.get('slot') for slot in slots if isinstance(slot, dict)]:
                    raise RpcError(-32005, 'Policy slot was not advertised by this robot')
                paths = [slot.get('path') for slot in slots if isinstance(slot, dict)]
                if params['path'] is not None and params['path'] not in paths:
                    raise RpcError(-32005, 'Policy path was not advertised by this robot')
        result, version = await upstream.call(method, params, request['id'])
        self.last_versions[service] = version
        return result, {'service': service, 'upstream_api_version': version, 'expected_api_version': API_VERSION}

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        request_id = None
        counted = False
        forwarded = False
        self.clients.add(writer)
        try:
            if peer_uid(writer.get_extra_info('socket')) != os.geteuid():
                raise RpcError(-32001, 'Only the gateway owner UID may connect')
            if self.active >= self.max_clients:
                raise RpcError(-32006, 'Gateway client limit reached')
            self.active += 1
            counted = True
            async with asyncio.timeout(self.timeout * 3):
                request = await read_message(reader, MAX_REQUEST)
                if isinstance(request, dict) and type(request.get('id')) is int and 1 <= request['id'] <= 0x7fffffff:
                    request_id = request['id']
                result, metadata = await self.dispatch(request)
                forwarded = metadata is not None
                reply = {'jsonrpc': '2.0', 'id': request_id, 'result': result}
                if metadata is not None:
                    reply['gateway'] = metadata
                writer.write(encode(reply, MAX_REPLY))
                await writer.drain()
        except (RpcError, TimeoutError, OSError, ValueError, RecursionError) as error:
            if not isinstance(error, RpcError):
                error = RpcError(-32008 if isinstance(error, TimeoutError) else -32009, 'Gateway operation did not complete', 'unknown' if request_id else 'not_sent')
            elif forwarded and error.outcome == 'not_sent':
                error.outcome = 'unknown'
            reply = {'jsonrpc': '2.0', 'id': request_id, 'error': {'code': error.code, 'message': error.message, 'data': {'outcome': error.outcome}}}
            try:
                writer.write(encode(reply, MAX_REPLY))
                await asyncio.wait_for(writer.drain(), 1)
            except (OSError, ConnectionError, TimeoutError):
                pass
        finally:
            if counted:
                self.active -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            self.clients.discard(writer)
            self.tasks.discard(task)

    async def start(self, path):
        path = Path(path)
        if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent:
            raise ValueError('Canonical absolute gateway socket path required')
        parent = path.parent.stat()
        if parent.st_uid != os.geteuid() or parent.st_mode & 0o077:
            raise ValueError('Gateway socket parent must be private and current-user-owned')
        if path.exists() or path.is_symlink():
            raise FileExistsError('Refusing to replace an existing socket or file')
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            sock.bind(str(path))
            os.chmod(path, 0o600)
            meta = path.lstat()
            self.path, self.identity = path, (meta.st_dev, meta.st_ino)
            sock.listen(self.max_clients)
            sock.setblocking(False)
            self.server = await asyncio.start_unix_server(self.handle, sock=sock, limit=MAX_REQUEST)
            return self
        except BaseException:
            sock.close()
            await self.stop()
            raise

    async def stop(self):
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        for writer in list(self.clients):
            writer.close()
        for task in list(self.tasks):
            task.cancel()
        if self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
        if self.clients:
            await asyncio.gather(*(writer.wait_closed() for writer in list(self.clients)), return_exceptions=True)
        if self.path:
            try:
                meta = self.path.lstat()
                if stat.S_ISSOCK(meta.st_mode) and (meta.st_dev, meta.st_ino) == self.identity:
                    self.path.unlink()
            except FileNotFoundError:
                pass
            self.path = None


def load_config(path):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_CLOEXEC | os.O_NONBLOCK)
    try:
        meta = os.fstat(fd)
        if not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077 or meta.st_size > MAX_REQUEST:
            raise ValueError('Config must be a bounded private file owned by the gateway user')
        config = decode(os.read(fd, MAX_REQUEST + 1).rstrip(b'\n') + b'\n', MAX_REQUEST)
    finally:
        os.close(fd)
    if not isinstance(config, dict) or set(config) != {'version', 'upstreams'} or type(config['version']) is not int or config['version'] != 1 or not isinstance(config['upstreams'], dict):
        raise ValueError('Invalid gateway config schema')
    for value in config['upstreams'].values():
        if not isinstance(value, dict) or set(value) != {'path', 'uid'}:
            raise ValueError('Each upstream needs only path and verified numeric uid')
    return config['upstreams']


async def main(args):
    service = Gateway(load_config(args.config), args.allow_mutation)
    await service.start(args.socket)
    print('MicroDuck Unix gateway ready; hardware validation pending; mutations: ' + (','.join(sorted(service.allowed_mutations)) or 'disabled'), flush=True)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(signum, stopped.set)
    try:
        await stopped.wait()
    finally:
        await service.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--socket', type=Path, required=True)
    parser.add_argument('--config', type=Path, required=True)
    parser.add_argument('--allow-mutation', choices=sorted(MUTATIONS), action='append', default=[])
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux Unix peer credentials are required')
    try:
        asyncio.run(main(args))
    except (ValueError, OSError, RpcError) as error:
        parser.exit(1, f'MicroDuck gateway refused: {error}\n')
