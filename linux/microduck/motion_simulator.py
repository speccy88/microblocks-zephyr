#!/usr/bin/env python3
"""SIMULATION ONLY: bounded twist leases; no live control transport or hardware.

Local microduck.motionSim.* wrappers are not Pollen methods. Their internal
recording service accepts only source-shaped robot.move notifications. No
endpoint, transport or motor provider can be injected. Existing real gateway
and BLE allowlists are unchanged. No applied movement/physics is modelled.
"""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
from collections import deque
import json
import math
import os
from pathlib import Path
import signal
import sys
import time

try:
    from .gateway import Gateway
    from .protocol import RpcError, API_VERSION, SOURCE_COMMIT, MAX_REQUEST, decode, encode
    from .simulator import Simulator, _fresh_file
except ImportError:
    from gateway import Gateway
    from protocol import RpcError, API_VERSION, SOURCE_COMMIT, MAX_REQUEST, decode, encode
    from simulator import Simulator, _fresh_file

PREFIX = 'microduck.motionSim.'
METHODS = frozenset(PREFIX + name for name in ('status', 'run', 'cancel'))
MAX_LEASES, MAX_FRAMES, HISTORY = 128, 4096, 64
INTERVAL, MAX_GAP = 0.1, 0.25
BOUNDS = {'vx_mm_s': (-300, 300), 'vy_mm_s': (-300, 300),
          'vyaw_mrad_s': (-1500, 1500), 'duration_ms': (100, 2000)}


def validate_motion(request):
    if (not isinstance(request, dict) or set(request) - {'jsonrpc', 'id', 'method', 'params', 'confirmed'}
            or request.get('jsonrpc') != '2.0' or type(request.get('id')) is not int
            or not 1 <= request['id'] <= 0x7fffffff):
        raise RpcError(-32600, 'Bounded local simulation request required')
    method, params = request.get('method'), request.get('params', {})
    if not isinstance(method, str) or method not in METHODS:
        raise RpcError(-32601, 'Method is outside the motion simulation interface')
    if not isinstance(params, dict) or 'confirmed' in request and type(request['confirmed']) is not bool:
        raise RpcError(-32602, 'Invalid simulation parameters')
    if method == PREFIX + 'run':
        if set(params) != set(BOUNDS) or any(type(params[key]) is not int or not lo <= params[key] <= hi for key, (lo, hi) in BOUNDS.items()):
            raise RpcError(-32602, 'Simulation twist or duration is outside local integer bounds')
    elif params:
        raise RpcError(-32602, 'This simulation method takes no parameters')
    return method, dict(params)


class _ControlRecording:
    """Internal reliable ordered recording, deliberately not a live adapter."""
    def __init__(self, fault=None):
        if fault not in (None, 'write-before', 'write-after', 'drop'):
            raise ValueError('Unknown simulation fault')
        self.open = True
        self.fault = fault
        self.count = 0
        self.frames = deque(maxlen=HISTORY)

    def send(self, raw):
        value = decode(raw, MAX_REQUEST)
        params = value.get('params') if isinstance(value, dict) else None
        if (not isinstance(value, dict) or set(value) != {'jsonrpc', 'method', 'params'}
                or value['jsonrpc'] != '2.0' or value['method'] != 'robot.move'
                or not isinstance(params, dict) or set(params) != {'vx', 'vy', 'vyaw'}
                or any(type(params[key]) not in (int, float) or not math.isfinite(params[key])
                       or abs(params[key]) > limit for key, limit in [('vx', .3), ('vy', .3), ('vyaw', 1.5)])):
            raise RpcError(-32602, 'Only bounded source-shaped twist notifications may be recorded')
        if not self.open or self.fault in ('write-before', 'drop'):
            self.open = False
            raise RpcError(-32009, 'Simulated control write failed before recording', 'not_sent')
        if self.count >= MAX_FRAMES:
            self.open = False
            raise RpcError(-32010, 'Simulation frame budget exhausted')
        self.count += 1
        self.frames.append({'sequence': self.count, 'notification': value, 'simulation': True})
        if self.fault == 'write-after':
            self.open = False
            raise RpcError(-32009, 'Simulated control outcome is unknown', 'unknown')


class MotionSimulation:
    def __init__(self, allow_motion=False, *, fault=None, clock=None, schedule=None):
        if type(allow_motion) is not bool or (clock is None) != (schedule is None):
            raise ValueError('Invalid simulation configuration')
        if clock is not None and (not callable(clock) or not callable(schedule)):
            raise ValueError('Invalid simulation clock')
        self.allow_motion = allow_motion
        self._clock = clock or time.monotonic
        self._schedule = schedule or (lambda at, callback: asyncio.get_running_loop().call_at(at, callback))
        self._control = _ControlRecording(fault)
        self._timer = None
        self._active = None
        self._attempts = 0
        self._phase = 'idle'
        self._closed = False
        self._outcome = None
        self._final_zero_attempted = False

    def snapshot(self):
        active = self._active
        return {'simulation': True, 'physical_movement_enabled': False, 'applied_motion': None,
            'controller_safety_and_physics': 'not_modelled', 'local_protocol_version': 1,
            'source_api_version': API_VERSION, 'source_commit': SOURCE_COMMIT,
            'control_transport': 'internal simulated reliable ordered control',
            'allow_motion_simulation': self.allow_motion, 'phase': self._phase,
            'lease_attempts': self._attempts, 'active_lease_id': active['id'] if active else None,
            'callback_pending': self._timer is not None,
            'active_requested_integer_units': dict(active['params']) if active else None,
            'last_outcome': self._outcome, 'final_zero_attempted': self._final_zero_attempted,
            'recorded_frames': self._control.count, 'frame_history': json.loads(json.dumps(list(self._control.frames))),
            'limits': {'leases': MAX_LEASES, 'frames': MAX_FRAMES, 'history': HISTORY,
                'interval_ms': 100, 'max_gap_ms': 250, 'max_duration_ms': 2000}}

    def _emit(self, values):
        self._control.send(encode({'jsonrpc': '2.0', 'method': 'robot.move',
            'params': dict(zip(('vx', 'vy', 'vyaw'), values))}, MAX_REQUEST))

    def _arm(self, at):
        handle = self._schedule(at, self._tick)
        if not callable(getattr(handle, 'cancel', None)):
            raise ValueError('Invalid simulation timer')
        self._timer = handle

    def _finish(self, reason):
        if self._timer is not None:
            try:
                self._timer.cancel()
            except Exception:
                pass
            self._timer = None
        active, self._active = self._active, None
        self._phase = reason
        if active and self._control.open:
            self._final_zero_attempted = True
            try:
                self._emit((0, 0, 0))
            except RpcError as error:
                self._outcome = error.outcome
                self._phase = 'write_failed'

    def _tick(self):
        self._timer = None
        active = self._active
        if self._closed or not active:
            return
        try:
            now = self._clock()
        except Exception:
            self._finish('clock_invalid')
            return
        if type(now) not in (int, float) or not math.isfinite(now) or now < active['last']:
            self._finish('clock_invalid')
            return
        if now >= active['until']:
            self._finish('expired')
            return
        if now - active['last'] >= MAX_GAP:
            self._finish('stale_tick')
            return
        try:
            self._emit(active['values'])
            active['last'] = now
            self._arm(min(now + INTERVAL, active['until']))
        except RpcError as error:
            self._outcome = error.outcome
            self._finish('write_failed')
        except Exception:
            self._finish('schedule_failed')

    def run(self, params, confirmed=False):
        # Validate even direct callers; the socket layer validates independently.
        validate_motion({'jsonrpc': '2.0', 'id': 1, 'method': PREFIX + 'run', 'params': params, 'confirmed': confirmed})
        if not self.allow_motion or confirmed is not True:
            raise RpcError(-32003, 'Simulation opt-in and per-request confirmation are required')
        if self._closed or not self._control.open:
            raise RpcError(-32004, 'Simulation control is closed; no automatic reconnect')
        if self._active:
            raise RpcError(-32006, 'A simulation lease is already active; nothing is queued')
        if self._attempts >= MAX_LEASES:
            raise RpcError(-32010, 'Simulation lease budget exhausted')
        try:
            now = self._clock()
        except Exception:
            raise RpcError(-32009, 'Simulation clock is unavailable') from None
        if type(now) not in (int, float) or not math.isfinite(now):
            raise RpcError(-32009, 'Simulation clock is unavailable')
        self._attempts += 1
        values = tuple(params[key] / 1000 for key in ('vx_mm_s', 'vy_mm_s', 'vyaw_mrad_s'))
        self._active = {'id': self._attempts, 'values': values, 'params': dict(params),
                        'last': now, 'until': now + params['duration_ms'] / 1000}
        self._phase, self._outcome, self._final_zero_attempted = 'active', 'recorded_in_simulation', False
        try:
            self._arm(min(now + INTERVAL, self._active['until']))
        except Exception:
            self._active = None
            self._timer = None
            self._phase, self._outcome = 'schedule_failed', 'not_sent'
            raise RpcError(-32009, 'Simulation scheduler is unavailable') from None
        try:
            self._emit(values)
        except RpcError as error:
            self._outcome = error.outcome
            self._finish('write_failed')
            raise
        return self.snapshot()

    def cancel(self):
        if self._active:
            self._finish('cancelled')
        return self.snapshot()

    def close(self):
        if self._closed:
            return
        self._closed = True
        self._finish('closed')
        self._control.open = False


class MotionGateway(Gateway):
    def __init__(self, upstreams, model):
        if type(model) is not MotionSimulation:
            raise ValueError('An internal simulation model is required')
        super().__init__(upstreams, allowed_mutations=())
        self.model = model

    @staticmethod
    def _reply(state):
        # Keep native block reports within the VM's bounded reporter message.
        # Full history remains in the local model/evidence, never an RPC stream.
        keys = ('simulation', 'physical_movement_enabled', 'allow_motion_simulation', 'applied_motion', 'local_protocol_version',
            'phase', 'active_lease_id', 'active_requested_integer_units', 'last_outcome',
            'recorded_frames', 'final_zero_attempted', 'callback_pending')
        result = {key: state[key] for key in keys}
        result['last_notification'] = state['frame_history'][-1]['notification'] if state['frame_history'] else None
        if len(encode({'jsonrpc': '2.0', 'id': 0x7fffffff, 'result': result}, 65536)) > 760:
            raise RpcError(-32010, 'Simulation summary exceeds its reporter bound', 'unknown')
        return result

    async def dispatch(self, request):
        if isinstance(request, dict) and isinstance(request.get('method'), str) and request['method'] in METHODS:
            method, params = validate_motion(request)
            if method == PREFIX + 'run':
                return self._reply(self.model.run(params, request.get('confirmed', False))), None
            if method == PREFIX + 'cancel':
                return self._reply(self.model.cancel()), None
            return self._reply(self.model.snapshot()), None
        return await super().dispatch(request)


class MotionSimulator(Simulator):
    def __init__(self, directory, allow_motion=False, *, fault=None):
        super().__init__(directory, allow_mock_actions=False)
        self.motion = MotionSimulation(allow_motion, fault=fault)

    def _make_gateway(self, allowed):
        return MotionGateway({'robot': {'path': str(self.directory / 'robot.sock'), 'uid': os.geteuid()}}, self.motion)

    async def start(self):
        try:
            await super().start()
            self.ready.update(motion_simulation=True, physical_movement_enabled=False,
                allowed_motion_simulation=self.motion.allow_motion, motion_methods=sorted(METHODS))
            _fresh_file(self.directory / 'motion-simulation.json', self.ready)
            return self
        except BaseException:
            await self.stop()
            raise

    async def stop(self):
        self.motion.close()
        await super().stop()


async def main(args):
    service = MotionSimulator(args.directory, args.allow_motion)
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
    parser.add_argument('--allow-motion', action='store_true', help='Allow confirmed internal twist recording ONLY; no physical motion')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Linux Unix peer credentials are required')
    try:
        asyncio.run(main(args))
    except (ValueError, OSError, RpcError) as error:
        parser.exit(1, f'Motion simulation refused: {error}\n')
