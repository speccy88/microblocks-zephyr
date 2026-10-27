#!/usr/bin/env python3
"""SIMULATION coherent typed gamepad IMU batches; fixed fake pad socket only."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import copy
import json
import math
import os
from pathlib import Path
import secrets
import signal
import sys
import time

try:
    from . import sensor_simulator as wire
    from .sensor_snapshots import token
    from .protocol import RpcError, connect_checked, encode, peer_uid, read_message, response_result
except ImportError:
    import sensor_simulator as wire
    from sensor_snapshots import token
    from protocol import RpcError, connect_checked, encode, peer_uid, read_message, response_result

PREFIX = 'microduck.imuSim.'
METHODS = frozenset(PREFIX + n for n in ('capturePad', 'read', 'release'))
FIELDS = {
    'accel_raw': ('raw', 3), 'gyro_raw': ('raw', 3),
    'accel_mg': ('mg', 3), 'gyro_mdps': ('mdps', 3),
    'seq': ('count64', 1), 'at_us': ('us_unix', 1), 'sample_count': ('count', 1),
    'accel_per_g': ('raw/g', 1), 'gyro_per_dps': ('raw/dps', 1),
    'accel_max': ('raw', 1), 'gyro_max': ('raw', 1),
    'accel_at_limit': ('boolean', 3), 'gyro_at_limit': ('boolean', 3),
}
PROFILES = ('normal', 'unscaled', 'dropped', 'no_imu', 'waiting', 'detached', 'refused', 'bad_order', 'oversized')
CAPACITY, TTL, MAX_SAMPLES = 4, 5.0, 32


def require(good, code=-32011):
    if not good:
        raise RpcError(code, 'Invalid bounded gamepad IMU data')


def validate(request):
    require(isinstance(request, dict) and not set(request) - {'jsonrpc', 'id', 'method', 'params', 'confirmed'}
            and request.get('jsonrpc') == '2.0' and wire.integer(request.get('id'), 1, 0x7fffffff), -32600)
    require(isinstance(request.get('method'), str) and request['method'] in METHODS, -32601)
    require('confirmed' not in request or type(request['confirmed']) is bool)
    name, p = request['method'].removeprefix(PREFIX), request.get('params', {})
    require(isinstance(p, dict))
    if name == 'capturePad':
        require(not p)
    elif name == 'release':
        require(set(p) == {'handle'} and token(p['handle']))
    else:
        require(set(p) == {'handle', 'field', 'sample', 'component'} and token(p['handle'])
                and isinstance(p['field'], str) and p['field'] in FIELDS)
        require(wire.integer(p['sample'], 1, MAX_SAMPLES) and wire.integer(p['component'], 1, FIELDS[p['field']][1]))
        if p['field'] in ('sample_count', 'accel_per_g', 'gyro_per_dps', 'accel_max', 'gyro_max'):
            require(p['sample'] == 1)
    return name, copy.deepcopy(p)


def result(kind, status, **parts):
    return {'simulation': True, 'physical_movement_enabled': False, 'kind': kind, 'status': status, **parts}


def validate_device(device):
    require(isinstance(device, dict) and wire.text(device.get('name')) and wire.text(device.get('node')))
    for name in ('accel_per_g', 'gyro_per_dps', 'accel_max', 'gyro_max'):
        require(wire.integer(device.get(name), 0, 2**31 - 1))
    return copy.deepcopy(device)


def validate_batch(batch):
    require(isinstance(batch, dict) and wire.integer(batch.get('socket_dropped', 0), 0, 2**64 - 1))
    samples = batch.get('samples')
    require(isinstance(samples, list) and 1 <= len(samples) <= MAX_SAMPLES)
    previous = None
    dropped = batch.get('socket_dropped', 0) > 0
    for sample in samples:
        require(isinstance(sample, dict) and all(wire.integer(sample.get(k), 0, 2**64 - 1) for k in ('seq', 'at_us')))
        for name in ('accel', 'gyro'):
            require(isinstance(sample.get(name), list) and len(sample[name]) == 3
                    and all(wire.integer(v, -(2**31), 2**31 - 1) for v in sample[name]))
        if previous is not None and sample['seq'] != previous + 1:
            dropped = True
        previous = sample['seq']
    return None if dropped else copy.deepcopy(samples)


async def capture(directory):
    writer, device = None, None
    status = 'timeout'
    try:
        async with asyncio.timeout(wire.DEADLINE):
            reader, writer = await connect_checked(directory / 'pad.sock', os.geteuid(), wire.LINE_LIMIT, True)
            writer.write(encode({'jsonrpc': '2.0', 'id': 1, 'method': 'pad.input', 'params': {}}, wire.LINE_LIMIT))
            await writer.drain()
            description = response_result(await read_message(reader, wire.LINE_LIMIT), 1)
            require(isinstance(description, dict) and type(description.get('accepted')) is bool)
            if not description['accepted']:
                return result('pad_imu_capture', 'refused'), None
            status = 'not_reported'
            for _ in range(wire.EVENTS):
                report = wire.notification(await read_message(reader, wire.LINE_LIMIT), 'pad.report')
                tag = report.get('report')
                require(isinstance(tag, str) and tag in ('attached', 'frame', 'detached', 'imu_attached', 'imu', 'imu_detached'))
                if tag == 'imu_attached':
                    device = validate_device(report.get('device'))
                    status = 'waiting'
                elif tag == 'imu_detached':
                    require(wire.text(report.get('why')))
                    return result('pad_imu_capture', 'detached'), None
                elif tag == 'imu':
                    require(device is not None)
                    samples = validate_batch(report)
                    if samples is None:
                        return result('pad_imu_capture', 'dropped'), None
                    return result('pad_imu_capture', 'ok', sample_count=len(samples)), {'device': device, 'samples': samples}
            status = 'event_limit'
    except TimeoutError:
        pass
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()
    return result('pad_imu_capture', status), None


def sample_reading(state, field, sample, component):
    unit = FIELDS[field][0]
    base = result('pad_imu_reading', 'not_reported', field=field, sample=sample, component=component, unit=unit, value=None)
    require(wire.integer(sample, 1, MAX_SAMPLES) and wire.integer(component, 1, FIELDS[field][1]))
    device, samples = state['device'], state['samples']
    if field == 'sample_count':
        value = len(samples)
    elif field in device:
        value = device[field]
    else:
        if sample > len(samples):
            return base
        row = samples[sample - 1]
        if field in ('seq', 'at_us'):
            return {**base, 'status': 'ok', 'value': str(row[field])}
        name = 'accel' if field.startswith('accel') else 'gyro'
        raw = row[name][component - 1]
        if field.endswith('_at_limit'):
            maximum = device[name + '_max']
            return base if maximum == 0 else {**base, 'status': 'ok', 'value': abs(raw) >= maximum}
        if field.endswith('_raw'):
            value = raw
        else:
            resolution = device['accel_per_g' if name == 'accel' else 'gyro_per_dps']
            if resolution == 0:
                return base
            numerator = raw * 1000
            magnitude, remainder = divmod(abs(numerator), resolution)
            value = (magnitude + (2 * remainder >= resolution)) * (-1 if numerator < 0 else 1)
    return {**base, 'status': 'ok' if -(2**30) <= value < 2**30 else 'out_of_range',
            'value': value if -(2**30) <= value < 2**30 else None}


class ImuStore:
    def __init__(self, directory, clock=time.monotonic):
        self.directory, self.clock = directory, clock
        self.entries, self.pending, self.last = {}, 0, None

    def purge(self):
        now = self.clock()
        require(type(now) in (int, float) and math.isfinite(now) and now >= 0)
        if self.last is not None and now < self.last:
            self.entries.clear()
        self.last = now
        self.entries = {h: v for h, v in self.entries.items() if v['expires'] > now}
        return now

    async def acquire(self):
        self.purge()
        if len(self.entries) + self.pending >= CAPACITY:
            return result('pad_imu_capture', 'busy')
        self.pending += 1
        try:
            meta, state = await capture(self.directory)
            if state is None:
                return meta
            now, handle = self.purge(), secrets.token_hex(16)
            require(handle not in self.entries)
            self.entries[handle] = {'state': state, 'expires': now + TTL}
            return {**meta, 'handle': handle, 'expires_in_ms': int(TTL * 1000)}
        finally:
            self.pending -= 1

    def read(self, handle, field, sample, component):
        self.purge()
        if handle not in self.entries:
            return result('pad_imu_reading', 'expired_or_unknown', field=field, sample=sample,
                          component=component, unit=FIELDS[field][0], value=None)
        return sample_reading(self.entries[handle]['state'], field, sample, component)

    def release(self, handle):
        self.purge()
        removed = self.entries.pop(handle, None)
        return result('pad_imu_release', 'released' if removed is not None else 'not_retained')


def fixture(profile):
    device = {'name': 'SIMULATION gamepad IMU', 'node': 'SIMULATION_no_device', 'accel_per_g': 4096,
              'gyro_per_dps': 14247, 'accel_max': 32767, 'gyro_max': 32767}
    if profile == 'unscaled':
        device.update(accel_per_g=0, gyro_per_dps=0, accel_max=0, gyro_max=0)
    samples = [{'seq': 2**63 + i, 'at_us': 1793120000000000 + i * 1666,
                'accel': [0, -4096, 2048 + i], 'gyro': [14247, 0, -7123]} for i in range(3)]
    if profile == 'bad_order':
        samples[1]['seq'] += 1
    if profile == 'oversized':
        samples = [copy.deepcopy(samples[0]) for _ in range(33)]
    reports = [] if profile == 'no_imu' else [{'report': 'imu_attached', 'device': device}]
    if profile == 'detached':
        reports.append({'report': 'imu_detached', 'why': 'SIMULATION disconnected'})
    elif profile not in ('no_imu', 'waiting'):
        reports.append({'report': 'imu', 'samples': samples, **({'socket_dropped': 1} if profile == 'dropped' else {})})
    return {'accepted': profile != 'refused'}, reports


class ImuGateway(wire.SensorGateway):
    def __init__(self, upstreams, directory):
        super().__init__(upstreams, directory)
        self.imu = ImuStore(directory)

    async def dispatch(self, request):
        if isinstance(request, dict) and isinstance(request.get('method'), str) and request['method'] in METHODS:
            name, p = validate(request)
            value = await self.imu.acquire() if name == 'capturePad' else self.imu.release(p['handle']) if name == 'release' else self.imu.read(p['handle'], p['field'], p['sample'], p['component'])
            encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': value}, 760)
            return value, None
        return await super().dispatch(request)


class ImuSimulator(wire.SensorSimulator):
    def __init__(self, directory, profile='normal'):
        require(profile in PROFILES)
        self.imu_profile = profile
        super().__init__(directory)

    def _make_gateway(self, allowed):
        return ImuGateway({'robot': {'path': str(self.directory / 'robot.sock'), 'uid': os.geteuid()}}, self.directory)

    async def start(self):
        try:
            await super().start()
            self.ready.update(pad_imu_simulation=True, imu_profile=self.imu_profile, physical_movement_enabled=False)
            wire._fresh_file(self.directory / 'pad-imu-simulation.json', self.ready)
            return self
        except BaseException:
            await self.stop()
            raise

    async def stream(self, service, reader, writer):
        if service != 'pad':
            return await super().stream(service, reader, writer)
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
                require(call == {'jsonrpc': '2.0', 'id': 1, 'method': 'pad.input', 'params': {}} and type(call['id']) is int)
                self.subscriptions += 1
                description, reports = fixture(self.imu_profile)
                writer.write(encode({'jsonrpc': '2.0', 'id': 1, 'result': description}, wire.LINE_LIMIT))
                _, controls = wire.fixture('pad', 'normal')
                controls = [note['params'] for note in controls]
                for report in (controls + reports if description['accepted'] else []):
                    writer.write(encode({'jsonrpc': '2.0', 'method': 'pad.report', 'params': report}, wire.LINE_LIMIT))
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
        store = self.gateway.imu if self.gateway else None
        await super().stop()
        if store:
            store.entries.clear()


async def main(args):
    service, stopped = ImuSimulator(args.directory, args.fixture), asyncio.Event()
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
