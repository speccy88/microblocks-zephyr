#!/usr/bin/env python3
"""Explicit SIMULATION backend for the real Unix Gateway; standard library only.

Creates a fresh private directory; never opens hardware, TCP, SSH or a real daemon.
API44 fixture shapes follow duck-ipc-proto at protocol.SOURCE_COMMIT. Battery
values and advertised skills are fictional. This is not robot acceptance evidence.
Optional mock actions require both this CLI opt-in and the Gateway's per-request
confirmation/discovery gates. At most 128 actions are recorded in a private log.
Stop removes only sockets this process created; metadata/logs and directory remain.
"""
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
    from .gateway import Gateway, validate
    from .protocol import API_VERSION, SOURCE_COMMIT, MAX_REQUEST, MAX_REPLY, RpcError, encode, peer_uid, read_message
except ImportError:
    from gateway import Gateway, validate
    from protocol import API_VERSION, SOURCE_COMMIT, MAX_REQUEST, MAX_REPLY, RpcError, encode, peer_uid, read_message

MAX_ACTIONS = 128
MOCK_ACTIONS = ('robot.do', 'robot.sound')
SKILLS = ('simulation_bow', 'simulation_nod')
NOTICE = 'SIMULATION ONLY: no robot connected; battery, temperatures, loop, IMU and skills are fictional.'


def _fresh_file(path, value):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
    with os.fdopen(fd, 'wb') as output:
        output.write(encode(value, MAX_REPLY))


class Simulator:
    def __init__(self, directory, allow_mock_actions=False):
        if type(allow_mock_actions) is not bool:
            raise ValueError('Mock-action opt-in must be boolean')
        self.directory = Path(directory)
        self.allow_mock_actions = allow_mock_actions
        self.server = self.gateway = None
        self.robot_identity = None
        self.tasks, self.clients = set(), set()
        self.action_count = self.active = 0
        self.action_log = None
        self.ready = None

    def _make_gateway(self, allowed):
        """Fixed private mock service; subclasses may add local-only lab methods."""
        return Gateway({'robot': {'path': str(self.directory / 'robot.sock'), 'uid': os.geteuid()}}, allowed_mutations=allowed)

    async def start(self):
        path = self.directory
        if not path.is_absolute() or path.parent.resolve(strict=True) != path.parent or path.name in ('', '.', '..'):
            raise ValueError('A canonical absolute new directory is required; symlink parents are refused')
        # Atomic fresh creation: existing directories, files and symlinks are refused.
        path.mkdir(mode=0o700)
        meta = path.lstat()
        if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.geteuid() or meta.st_mode & 0o077:
            raise ValueError('Simulation directory must be private and current-user-owned')
        try:
            log_fd = os.open(path / 'actions.jsonl', os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW | os.O_CLOEXEC, 0o600)
            self.action_log = os.fdopen(log_fd, 'wb')
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(str(path / 'robot.sock'))
                os.chmod(path / 'robot.sock', 0o600)
                meta = (path / 'robot.sock').lstat()
                self.robot_identity = meta.st_dev, meta.st_ino
                sock.listen(4)
                sock.setblocking(False)
                self.server = await asyncio.start_unix_server(self.handle, sock=sock, limit=MAX_REQUEST)
            except BaseException:
                sock.close()
                raise
            allowed = MOCK_ACTIONS if self.allow_mock_actions else ()
            self.gateway = self._make_gateway(allowed)
            await self.gateway.start(path / 'gateway.sock')
            self.ready = {'simulation': True, 'notice': NOTICE, 'api_version': API_VERSION,
                'upstream_commit': SOURCE_COMMIT, 'directory': str(path), 'pid': os.getpid(), 'uid': os.geteuid(),
                'robot_socket': str(path / 'robot.sock'), 'gateway_socket': str(path / 'gateway.sock'),
                'action_log': str(path / 'actions.jsonl'), 'allowed_mock_actions': list(allowed), 'max_actions': MAX_ACTIONS}
            _fresh_file(path / 'simulation.json', self.ready)
            return self
        except BaseException:
            await self.stop()
            raise

    def result(self, method, params):
        if method == 'robot.health':
            return {'healthy': False, 'degraded': True, 'simulation': True, 'reason': NOTICE,
                'battery': {'volts': 7.8, 'percent': 73.25},
                'cpu_temp_c': 41.25,
                'motors': {'hottest': 'SIMULATION-joint', 'max_c': 45.5, 'mean_c': 40.25},
                'control_loop': {'target_hz': 50.0, 'achieved_hz': 49.95, 'ticks': 0, 'missed': 0, 'last_tick_age_ms': 4},
                'bus': {'consecutive_errors': 0, 'startup_failures': 0},
                'imu': {'ready': False, 'missing': False, 'stale_blocks': 0, 'consecutive_stale_blocks': 0}}
        if method == 'robot.policies':
            return {'mode': 'walk', 'enabled': False, 'slots': [], 'skills': list(SKILLS),
                'homed': False, 'sitting': False, 'change_error': NOTICE}
        if method == 'robot.skills':
            return {'skills': [{'name': name, 'duration': 1.0} for name in SKILLS]}
        if method in MOCK_ACTIONS and self.allow_mock_actions:
            if method == 'robot.do' and params.get('skill') not in SKILLS:
                raise RpcError(-32005, 'Skill was not advertised by this simulation')
            if self.action_count >= MAX_ACTIONS:
                raise RpcError(-32010, 'Simulation action log is full; no action was recorded')
            entry = {'sequence': self.action_count + 1, 'simulation': True, 'method': method, 'params': params}
            self.action_log.write(encode(entry, 1024))
            self.action_log.flush()
            self.action_count += 1
            # Extra simulated flag is intentional, never a physical IntentResult claim.
            return {'accepted': True, 'reason': 'SIMULATION ONLY: recorded; no physical action occurred.', 'simulated': True}
        raise RpcError(-32601, 'Method is unavailable in this explicit simulation')

    async def handle(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.clients.add(writer)
        counted = False
        request_id = None
        try:
            if peer_uid(writer.get_extra_info('socket')) != os.geteuid() or self.active >= 4:
                raise RpcError(-32001, 'Simulation accepts at most four same-UID clients')
            self.active += 1
            counted = True
            async with asyncio.timeout(3):
                hello = await read_message(reader, MAX_REQUEST)
                if hello != {'jsonrpc': '2.0', 'id': 0, 'method': 'hello', 'params': {'api_version': API_VERSION}} or type(hello.get('id')) is not int:
                    raise RpcError(-32600, 'Simulation requires the API44 hello handshake')
                request_id = 0
                writer.write(encode({'jsonrpc': '2.0', 'id': 0, 'result': {'api_version': API_VERSION}}, MAX_REPLY))
                await writer.drain()
                request = await read_message(reader, MAX_REQUEST)
                if isinstance(request, dict) and type(request.get('id')) is int:
                    request_id = request['id']
                method, params = validate(request)
                result = self.result(method, params)
                writer.write(encode({'jsonrpc': '2.0', 'id': request_id, 'result': result}, MAX_REPLY))
                await writer.drain()
        except (RpcError, OSError, TimeoutError, ValueError, RecursionError) as error:
            if not isinstance(error, RpcError):
                error = RpcError(-32009, 'Simulation transport did not complete')
            try:
                writer.write(encode({'jsonrpc': '2.0', 'id': request_id,
                    'error': {'code': error.code, 'message': error.message, 'data': {'outcome': error.outcome}}}, MAX_REPLY))
                await asyncio.wait_for(writer.drain(), 1)
            except (OSError, TimeoutError):
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

    async def stop(self):
        if self.gateway:
            await self.gateway.stop()
            self.gateway = None
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            self.server = None
        tasks = list(self.tasks)
        for writer in list(self.clients):
            writer.close()
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        if self.robot_identity:
            try:
                path = self.directory / 'robot.sock'
                meta = path.lstat()
                if stat.S_ISSOCK(meta.st_mode) and (meta.st_dev, meta.st_ino) == self.robot_identity:
                    path.unlink()
            except FileNotFoundError:
                pass
            self.robot_identity = None
        if self.action_log:
            self.action_log.close()
            self.action_log = None


async def main(args):
    service = Simulator(args.directory, args.allow_mock_actions)
    stopped = asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stopped.set)
    try:
        await service.start()
        print(json.dumps(service.ready, separators=(',', ':')), flush=True)
        await stopped.wait()
    finally:
        await service.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True, help='Absolute new private simulation directory')
    parser.add_argument('--allow-mock-actions', action='store_true', help='Allow confirmed simulated sound/advertised skills only')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux Unix peer credentials are required')
    try:
        asyncio.run(main(args))
    except (ValueError, OSError, RpcError) as error:
        parser.exit(1, f'Simulation refused: {error}\n')
