#!/usr/bin/env python3
"""Bounded tofd head-IMU IPC reader and SIMULATION block gateway; no device bus."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import copy
import math
import os
from pathlib import Path
import secrets
import signal
import socket
import stat
import sys
import json

try:
    from . import sensor_simulator as wire
    from .pad_imu_simulator import ImuStore
    from .sensor_snapshots import token
    from .simulator import Simulator, _fresh_file
    from .gateway import Gateway
    from .protocol import RpcError, connect_checked, encode, peer_uid, read_message, response_result
except ImportError:
    import sensor_simulator as wire
    from pad_imu_simulator import ImuStore
    from sensor_snapshots import token
    from simulator import Simulator, _fresh_file
    from gateway import Gateway
    from protocol import RpcError, connect_checked, encode, peer_uid, read_message, response_result

PREFIX = 'microduck.headImuSim.'
METHODS = frozenset(PREFIX + name for name in ('capture', 'read', 'release'))
FIELDS = {'gyro': ('mrad/s', 3), 'accel': ('mm/s2', 3), 'quat': ('ppm', 4),
          'temperature': ('mC', 1), 'seq': ('count64', 1), 'at_us': ('us_sender', 1),
          't_ns': ('ns', 1), 'sensor': ('sensor', 1), 'rate': ('Hz', 1)}
PROFILES = ('normal', 'absent', 'wrong_owner', 'refused', 'waiting', 'pre_ack_timeout',
            'partial', 'empty', 'zero_quat', 'legacy_clock', 'malformed')


def require(good, code=-32011):
    if not good:
        raise RpcError(code, 'Invalid bounded tofd head IMU data')


def number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and abs(value) <= 3.4028234663852886e38
    except OverflowError:
        return False


def sensor_name(value):
    return isinstance(value, str) and 0 < len(value) <= 64 and value.isascii() and all(c.isalnum() or c in '-_' for c in value)


def validate(request):
    require(isinstance(request, dict) and not set(request) - {'jsonrpc', 'id', 'method', 'params', 'confirmed'}
            and request.get('jsonrpc') == '2.0' and wire.integer(request.get('id'), 1, 0x7fffffff), -32600)
    require(isinstance(request.get('method'), str) and request['method'] in METHODS, -32601)
    require('confirmed' not in request or type(request['confirmed']) is bool)
    name, p = request['method'].removeprefix(PREFIX), request.get('params', {})
    require(isinstance(p, dict))
    if name == 'capture':
        require(not p)
    elif name == 'release':
        require(set(p) == {'handle'} and token(p['handle']))
    else:
        require(set(p) == {'handle', 'field', 'component'} and token(p['handle'])
                and isinstance(p['field'], str) and p['field'] in FIELDS
                and wire.integer(p['component'], 1, FIELDS[p['field']][1]))
    return name, copy.deepcopy(p)


def result(kind, status, **parts):
    return {'simulation': True, 'physical_movement_enabled': False, 'kind': kind, 'status': status, **parts}


def validate_frame(frame):
    require(isinstance(frame, dict))
    for name in ('seq', 'at_us', 't_ns'):
        if name in frame:
            require(wire.integer(frame[name], 0, 2**64 - 1))
    for name, size in (('gyro', 3), ('accel', 3), ('quat', 4)):
        if name in frame:
            require(isinstance(frame[name], list) and len(frame[name]) == size and all(number(v) for v in frame[name]))
    if 'temp_c' in frame:
        require(number(frame['temp_c']))
    return copy.deepcopy(frame)


async def read_tofd_head(path, uid, private_parent=False):
    """Real finite IPC reader; no simulation marker or auto-selected daemon/UID."""
    require(isinstance(path, (str, Path)))
    path = Path(path)
    require(path.is_absolute() and wire.integer(uid, 0, 0xffffffff) and type(private_parent) is bool)
    writer, status = None, 'timeout'
    try:
        async with asyncio.timeout(wire.DEADLINE):
            reader, writer = await connect_checked(path, uid, wire.LINE_LIMIT, private_parent)
            writer.write(encode({'jsonrpc': '2.0', 'id': 1, 'method': 'head_imu.stream', 'params': {}}, wire.LINE_LIMIT))
            await writer.drain()
            description = response_result(await read_message(reader, wire.LINE_LIMIT), 1)
            require(isinstance(description, dict) and type(description.get('accepted')) is bool)
            if not description['accepted']:
                return 'refused', None
            if description.get('sensor') is None:
                return 'absent', None
            require(sensor_name(description['sensor']))
            if 'hz' in description:
                require(wire.integer(description['hz'], 0, 255))
            status = 'waiting'
            frame = validate_frame(wire.notification(await read_message(reader, wire.LINE_LIMIT), 'head_imu.frame'))
            if not any(k in frame for k in ('gyro', 'accel', 'quat', 'temp_c')):
                return 'not_reported', None
            return 'ok', {'description': copy.deepcopy(description), 'frame': frame}
    except TimeoutError:
        return status, None
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()


def sample_reading(state, field, component, envelope=result):
    require(isinstance(field, str) and field in FIELDS and wire.integer(component, 1, FIELDS[field][1]))
    base = envelope('head_imu_reading', 'not_reported', field=field, component=component, unit=FIELDS[field][0], value=None)
    frame, description = state['frame'], state['description']
    if field == 'sensor':
        return {**base, 'status': 'ok', 'value': description['sensor']}
    if field == 'rate':
        value, scale = description.get('hz'), 1
    elif field in ('seq', 'at_us', 't_ns'):
        value = frame.get(field)
        if value is None or field == 't_ns' and value == 0:
            return base
        return {**base, 'status': 'ok', 'value': str(value)}
    elif field == 'temperature':
        value, scale = frame.get('temp_c'), 1000
    else:
        vector = frame.get(field)
        if vector is None:
            return base
        if field == 'quat' and all(v == 0 for v in vector):
            return {**base, 'status': 'unusable'}
        value, scale = vector[component - 1], 1000000 if field == 'quat' else 1000
    if value is None:
        return base
    scaled = value * scale
    if not math.isfinite(scaled):
        return {**base, 'status': 'out_of_range'}
    value = math.floor(scaled + .5) if scaled >= 0 else math.ceil(scaled - .5)
    return {**base, 'status': 'ok' if -(2**30) <= value < 2**30 else 'out_of_range',
            'value': value if -(2**30) <= value < 2**30 else None}


class HeadStore(ImuStore):
    def envelope(self, kind, status, **parts):
        return result(kind, status, **parts)

    async def read_source(self):
        return await read_tofd_head(self.directory / 'tofd.sock', os.geteuid(), True)

    async def acquire(self):
        self.purge()
        if len(self.entries) + self.pending >= 4:
            return self.envelope('head_imu_capture', 'busy')
        self.pending += 1
        try:
            status, state = await self.read_source()
            if state is None:
                return self.envelope('head_imu_capture', status)
            now, handle = self.purge(), secrets.token_hex(16)
            require(handle not in self.entries)
            self.entries[handle] = {'state': state, 'expires': now + 5}
            return self.envelope('head_imu_capture', 'ok', handle=handle, expires_in_ms=5000)
        finally:
            self.pending -= 1

    def read(self, handle, field, component):
        self.purge()
        if handle not in self.entries:
            return self.envelope('head_imu_reading', 'expired_or_unknown', field=field, component=component,
                          unit=FIELDS[field][0], value=None)
        return sample_reading(self.entries[handle]['state'], field, component, self.envelope)

    def release(self, handle):
        self.purge()
        removed = self.entries.pop(handle, None)
        return self.envelope('head_imu_release', 'released' if removed is not None else 'not_retained')

    def close(self):
        self.entries.clear()


def fixture(profile):
    description = {'accepted': True, 'sensor': 'BMI088', 'hz': 100}
    frame = {'seq': 2**63 + 5, 'at_us': 1234567, 't_ns': 2**63 + 77,
             'gyro': [.125, -.5, 0.0], 'accel': [0.0, 0.0, 9.81],
             'quat': [1.0, 0.0, 0.0, 0.0], 'temp_c': 23.125}
    if profile in ('absent', 'wrong_owner'):
        description.pop('sensor')
        description['unavailable'] = 'SIMULATION no sensor' if profile == 'absent' else 'SIMULATION beta: ask robotd; no automatic fallback'
    if profile == 'refused':
        description['accepted'] = False
    if profile in ('waiting', 'absent', 'wrong_owner', 'refused'):
        frame = None
    elif profile == 'partial':
        frame = {'gyro': [0.0, 0.0, 0.0]}
    elif profile == 'empty':
        frame = {'seq': 0, 't_ns': 0}
    elif profile == 'zero_quat':
        frame['quat'] = [0.0] * 4
    elif profile == 'legacy_clock':
        frame['t_ns'] = 0
    elif profile == 'malformed':
        frame['accel'] = [0.0, True, 9.81]
    return description, frame


class HeadGateway(Gateway):
    def __init__(self, upstreams, directory):
        super().__init__(upstreams, allowed_mutations=())
        self.head = HeadStore(directory)

    async def dispatch(self, request):
        if isinstance(request, dict) and isinstance(request.get('method'), str) and request['method'] in METHODS:
            name, p = validate(request)
            value = await self.head.acquire() if name == 'capture' else self.head.release(p['handle']) if name == 'release' else self.head.read(p['handle'], p['field'], p['component'])
            encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': value}, 760)
            return value, None
        return await super().dispatch(request)


class HeadSimulator(Simulator):
    def __init__(self, directory, profile='normal'):
        require(profile in PROFILES)
        self.profile, self.head_server, self.head_identity, self.subscriptions = profile, None, None, 0
        super().__init__(directory, allow_mock_actions=False)

    def _make_gateway(self, allowed):
        return HeadGateway({'robot': {'path': str(self.directory / 'robot.sock'), 'uid': os.geteuid()}}, self.directory)

    async def start(self):
        try:
            await super().start()
            path = self.directory / 'tofd.sock'
            sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            try:
                sock.bind(str(path))
                os.chmod(path, 0o600)
                info = path.lstat()
                self.head_identity = info.st_dev, info.st_ino
                sock.listen(4)
                sock.setblocking(False)
                self.head_server = await asyncio.start_unix_server(self.stream_head, sock=sock, limit=wire.LINE_LIMIT)
            except BaseException:
                sock.close()
                raise
            self.ready.update(head_imu_simulation=True, head_imu_profile=self.profile, reviewed_head_api=45,
                              physical_movement_enabled=False, tofd_only=True)
            _fresh_file(self.directory / 'head-imu-simulation.json', self.ready)
            return self
        except BaseException:
            await self.stop()
            raise

    async def stream_head(self, reader, writer):
        task = asyncio.current_task()
        self.tasks.add(task)
        self.clients.add(writer)
        counted = False
        try:
            require(peer_uid(writer.get_extra_info('socket')) == os.geteuid() and self.active < 4)
            self.active += 1
            counted = True
            async with asyncio.timeout(1):
                call = await read_message(reader, wire.LINE_LIMIT)
                require(call == {'jsonrpc': '2.0', 'id': 1, 'method': 'head_imu.stream', 'params': {}} and type(call['id']) is int)
                self.subscriptions += 1
                if self.profile == 'pre_ack_timeout':
                    await reader.read(1)
                    return
                description, frame = fixture(self.profile)
                writer.write(encode({'jsonrpc': '2.0', 'id': 1, 'result': description}, wire.LINE_LIMIT))
                if frame is not None:
                    writer.write(encode({'jsonrpc': '2.0', 'method': 'head_imu.frame', 'params': frame}, wire.LINE_LIMIT))
                await writer.drain()
                await reader.read(1)
        except (RpcError, OSError, TimeoutError):
            pass
        finally:
            if counted:
                self.active -= 1
            writer.close()
            try:
                await writer.wait_closed()
            except OSError:
                pass
            self.tasks.discard(task)
            self.clients.discard(writer)

    async def stop(self):
        store = self.gateway.head if self.gateway else None
        if self.head_server:
            self.head_server.close()
            await self.head_server.wait_closed()
            self.head_server = None
        await super().stop()
        if store:
            store.entries.clear()
        if self.head_identity:
            path = self.directory / 'tofd.sock'
            try:
                info = path.lstat()
                if stat.S_ISSOCK(info.st_mode) and (info.st_dev, info.st_ino) == self.head_identity:
                    path.unlink()
            except FileNotFoundError:
                pass
            self.head_identity = None


async def main(args):
    service, stopped = HeadSimulator(args.directory, args.fixture), asyncio.Event()
    loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(signum, stopped.set)
    try:
        await service.start()
        print(json.dumps(service.ready), flush=True)
        await stopped.wait()
    finally:
        await service.stop()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory', type=Path, required=True)
    parser.add_argument('--fixture', choices=PROFILES, default='normal')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux verified private sockets required')
    asyncio.run(main(args))
