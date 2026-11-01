#!/usr/bin/env python3
"""SIMULATION mediad metadata and discrete relay packet previews; no live transport."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import collections
import copy
import json
import os
import signal
import sys
import time
from pathlib import Path

try:
    from . import robot_simulator as robot
    from .protocol import RpcError, encode, response_result
    from .sensor_simulator import _fresh_file
except ImportError:
    import robot_simulator as robot
    from protocol import RpcError, encode, response_result
    from sensor_simulator import _fresh_file

PREFIX = 'microduck.mediaSim.'
METHODS = frozenset(PREFIX + name for name in ('reading', 'preview'))
SESSION = 'SIMULATION_media_session'
STATES = ('signed_out', 'connecting', 'registered', 'refused', 'retrying')
FIELDS = {
    'audio.receive': 'boolean', 'audio.send': 'boolean',
    'relay.state': 'state', 'relay.since': 'epoch_s', 'relay.heartbeat': 'epoch_s',
    'relay.account_known': 'boolean',
    'video.width': 'px', 'video.height': 'px', 'video.rotate': 'degrees',
    'stream.streaming': 'boolean', 'stream.connected': 'boolean',
    'stream.sent': 'count64', 'stream.dropped': 'count64',
    'stream.replies': 'count64', 'stream.reconnects': 'count64',
    'robot.healthy': 'boolean', 'robot.enabled': 'boolean',
}
DISCRETE = robot.PREVIEWS - robot.NOTIFICATIONS
FAULTS = ('normal', 'timeout', 'wrong_session', 'wrong_id', 'error', 'absent', 'malformed')


def require(good, code=-32602):
    if not good:
        raise RpcError(code, 'Invalid bounded media simulation data')


def validate(request):
    require(isinstance(request, dict) and not set(request) - {'jsonrpc', 'id', 'method', 'params', 'confirmed'}
            and request.get('jsonrpc') == '2.0' and robot.telemetry.integer(request.get('id'), 1, 0x7fffffff), -32600)
    require(isinstance(request.get('method'), str) and request['method'] in METHODS, -32601)
    require('confirmed' not in request or type(request['confirmed']) is bool)
    p = request.get('params', {})
    require(isinstance(p, dict))
    name = request['method'].removeprefix(PREFIX)
    if name == 'reading':
        require(set(p) == {'field'} and isinstance(p['field'], str) and p['field'] in FIELDS)
    else:
        require(set(p) == {'method', 'args'} and isinstance(p['method'], str) and p['method'] in DISCRETE)
        params = robot.preview_params(p['method'], p['args'])
        require(not (p['method'] == 'robot.sound' and 'hold' in params))
    return name, copy.deepcopy(p)


def reading(field, status='not_reported', value=None):
    return {'simulation': True, 'physical_movement_enabled': False, 'kind': 'media_reading',
            'field': field, 'status': status, 'value': value, 'unit': FIELDS[field]}


class Budget:
    """Conservative local consumer bound; never models the service's own lease."""
    def __init__(self, clock=time.monotonic):
        self.clock, self.window, self.total, self.last = clock, collections.deque(), 0, None

    def take(self):
        now = self.clock()
        require(robot.telemetry.number(now) and now >= 0 and (self.last is None or now >= self.last), -32011)
        self.last = now
        while self.window and self.window[0] <= now - 60:
            self.window.popleft()
        if len(self.window) >= 32 or self.total >= 128:
            return False
        self.window.append(now)
        self.total += 1
        return True


class FakeRelay:
    """Internal source-shaped messages only. No endpoint/provider/credential input."""
    def __init__(self, fault='normal'):
        require(fault in FAULTS)
        self.fault, self.audit = fault, []

    async def exchange(self, envelope):
        require(set(envelope) == {'type', 'sessionId', 'rpc'} and envelope['type'] == 'peer'
                and envelope['sessionId'] == SESSION)
        call = envelope['rpc']
        require(set(call) == {'jsonrpc', 'id', 'method', 'params'} and call['jsonrpc'] == '2.0'
                and robot.telemetry.integer(call['id'], 1, 128) and call['params'] == {}
                and call['method'] in ('media.video', 'media.stream', 'robot.health', 'robot.policies'))
        require(len(self.audit) < 128, -32010)
        self.audit.append(copy.deepcopy(envelope))
        if self.fault == 'timeout':
            await asyncio.Future()
        if self.fault == 'absent':
            raise ConnectionError('SIMULATION unavailable')
        value = {'media.video': {'width': 640, 'height': 480, 'rotate': 180},
                 'media.stream': {'streaming': False, 'connected': False, 'sent': 0, 'dropped': 0,
                                  'replies': 2**63 + 17, 'reconnects': 0},
                 'robot.health': {'healthy': False}, 'robot.policies': {'enabled': False}}[call['method']]
        rpc = {'jsonrpc': '2.0', 'id': call['id'], 'result': value}
        if self.fault == 'error':
            rpc = {'jsonrpc': '2.0', 'id': call['id'], 'error': {'code': -32603, 'message': 'SIMULATION no media'}}
        if self.fault == 'wrong_id':
            rpc['id'] += 1
        reply = {'type': 'peer', 'sessionId': SESSION, 'rpc': rpc}
        if self.fault == 'wrong_session':
            reply['sessionId'] = 'SIMULATION_other_session'
        if self.fault == 'malformed':
            reply['rpc']['result'] = {'streaming': 0}
        # Exercise actual JSON serialization and bounds, without a live SSE/HTTP client.
        return json.loads(encode(reply, 8192))


class MediaLab:
    def __init__(self, allow_previews=False, fault='normal'):
        self.preview = robot.PreviewRecorder(allow_previews)
        self.relay, self.budget, self.preview_envelopes = FakeRelay(fault), Budget(), []
        self.remote_status = {'service': 'https://SIMULATION.invalid', 'since': 1793120000,
                              'state': 'registered', 'account': None, 'peerId': 'SIMULATION_peer',
                              'lastHeartbeat': 1793120005}

    def status_reading(self, field):
        s = self.remote_status
        if s is None:
            return reading(field, 'absent')
        require(isinstance(s, dict) and isinstance(s.get('service'), str) and s.get('state') in STATES
                and robot.telemetry.integer(s.get('since'), -(2**63), 2**63 - 1), -32011)
        if s['state'] == 'registered':
            require(isinstance(s.get('peerId'), str) and 0 < len(s['peerId']) <= 128
                    and (s.get('account') is None or robot.telemetry.text(s['account']))
                    and robot.telemetry.integer(s.get('lastHeartbeat'), -(2**63), 2**63 - 1), -32011)
        if s['state'] == 'retrying':
            require(isinstance(s.get('reason'), str), -32011)
        if field == 'relay.state':
            return reading(field, 'ok', s['state'])
        if field == 'relay.since':
            return reading(field, 'ok', str(s['since']))
        if s['state'] != 'registered':
            return reading(field)
        return reading(field, 'ok', str(s['lastHeartbeat']) if field == 'relay.heartbeat' else s.get('account') is not None)

    async def sample(self, field):
        if field.startswith('audio.'):
            return reading(field, 'unsupported')
        if field.startswith('relay.'):
            return self.status_reading(field)
        if not self.budget.take():
            return reading(field, 'rate_limited')
        method = 'media.video' if field.startswith('video.') else 'media.stream' if field.startswith('stream.') else 'robot.health' if field == 'robot.healthy' else 'robot.policies'
        call = {'jsonrpc': '2.0', 'id': self.budget.total, 'method': method, 'params': {}}
        try:
            async with asyncio.timeout(.5):
                reply = await self.relay.exchange({'type': 'peer', 'sessionId': SESSION, 'rpc': call})
            require(isinstance(reply, dict) and set(reply) == {'type', 'sessionId', 'rpc'}
                    and reply.get('type') == 'peer' and reply.get('sessionId') == SESSION, -32011)
            result = response_result(reply['rpc'], call['id'])
            require(isinstance(result, dict), -32011)
            key = field.split('.')[1]
            value = result.get('healthy' if field == 'robot.healthy' else 'enabled' if field == 'robot.enabled' else key)
            unit = FIELDS[field]
            if unit == 'boolean':
                require(type(value) is bool, -32011)
            elif unit == 'count64':
                require(robot.telemetry.integer(value, 0, 2**64 - 1), -32011)
                value = str(value)
            elif unit == 'degrees':
                require(type(value) is int and value in (0, 90, 180, 270), -32011)
            else:
                require(robot.telemetry.integer(value, 1, 2**32 - 1), -32011)
                if value > 1073741823:
                    return reading(field, 'out_of_range')
            return reading(field, 'ok', value)
        except TimeoutError:
            return reading(field, 'timeout')
        except ConnectionError:
            return reading(field, 'absent')
        except RpcError:
            return reading(field, 'error')

    def record(self, method, args, confirmed):
        # Validation/confirmation before budget consumption and before a packet exists.
        validate({'jsonrpc': '2.0', 'id': 1, 'method': PREFIX + 'preview', 'params': {'method': method, 'args': args}})
        require(self.preview.allowed and confirmed is True, -32003)
        if not self.budget.take():
            return {'simulation': True, 'physical_movement_enabled': False, 'kind': 'relay_preview',
                    'status': 'rate_limited', 'recorded': False, 'admission': None, 'applied': None}
        result = self.preview.record(method, args, True)
        packet = copy.deepcopy(self.preview.audit[-1])
        packet['id'] = self.budget.total
        self.preview_envelopes.append({'type': 'peer', 'sessionId': SESSION, 'rpc': packet})
        return {**result, 'kind': 'relay_preview', 'recorded': True}


class MediaGateway(robot.RobotGateway):
    def __init__(self, upstreams, directory, preview, motion, media):
        super().__init__(upstreams, directory, preview, motion)
        self.media = media

    async def dispatch(self, request):
        if isinstance(request, dict) and isinstance(request.get('method'), str) and request['method'] in METHODS:
            name, p = validate(request)
            result = await self.media.sample(p['field']) if name == 'reading' else self.media.record(p['method'], p['args'], request.get('confirmed', False))
            encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': result}, 760)
            return result, None
        return await super().dispatch(request)


class MediaSimulator(robot.RobotSimulator):
    def __init__(self, directory, allow_relay_previews=False, fault='normal'):
        self.media = MediaLab(allow_relay_previews, fault)
        super().__init__(directory)  # Existing robot/motion mutation previews stay disabled.

    def _make_gateway(self, allowed):
        return MediaGateway({'robot': {'path': str(self.directory / 'robot.sock'), 'uid': os.geteuid()}},
                            self.directory, self.preview, self.motion, self.media)

    async def start(self):
        try:
            await super().start()
            self.ready.update(media_simulation=True, allow_relay_previews=self.media.preview.allowed,
                              audio='unsupported_by_reviewed_mediad_interface', live_transport=False)
            _fresh_file(self.directory / 'media-simulation.json', self.ready)
            return self
        except BaseException:
            await self.stop()
            raise


async def main(args):
    service = MediaSimulator(args.directory, args.allow_relay_previews, args.fault)
    stopped = asyncio.Event()
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
    parser.add_argument('--directory', required=True, type=Path)
    parser.add_argument('--allow-relay-previews', action='store_true')
    parser.add_argument('--fault', choices=FAULTS, default='normal')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux verified private sockets required')
    asyncio.run(main(args))
