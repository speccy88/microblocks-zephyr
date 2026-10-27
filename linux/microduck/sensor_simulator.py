#!/usr/bin/env python3
"""Read-only SIMULATION ToF/gamepad blocks. Fixed fake services, no real endpoint."""
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
    from .gateway import Gateway
    from .protocol import RpcError, encode, connect_checked, peer_uid, read_message, response_result
    from .simulator import Simulator, _fresh_file
except ImportError:
    from gateway import Gateway
    from protocol import RpcError, encode, connect_checked, peer_uid, read_message, response_result
    from simulator import Simulator, _fresh_file

PREFIX = 'microduck.sensorSim.'
METHODS = frozenset(PREFIX + part for part in ('tof', 'axis', 'button'))
LINE_LIMIT, EVENTS, DEADLINE = 16384, 16, .35


def integer(value, low, high):
    return type(value) is int and low <= value <= high


def require(good):
    if not good:
        raise RpcError(-32011, 'Invalid or unsupported sensor stream shape')


def text(value):
    return isinstance(value, str) and 0 < len(value) <= 128 and not any(ord(c) < 32 for c in value)


def validate_sensor(request):
    if not isinstance(request, dict) or set(request) - {'jsonrpc', 'id', 'method', 'params', 'confirmed'} or request.get('jsonrpc') != '2.0' or not integer(request.get('id'), 1, 0x7fffffff):
        raise RpcError(-32600, 'Bounded numeric request ID required')
    method, params = request.get('method'), request.get('params', {})
    if not isinstance(method, str) or method not in METHODS:
        raise RpcError(-32601, 'Local sensor simulation method required')
    if not isinstance(params, dict) or 'confirmed' in request and type(request['confirmed']) is not bool:
        raise RpcError(-32602, 'Invalid sensor parameters')
    good = set(params) == {'row', 'col'} and all(integer(params[k], 1, 8) for k in params) if method == PREFIX + 'tof' else set(params) == {'code'} and integer(params['code'], 0, 65535)
    if not good:
        raise RpcError(-32602, 'Sensor selector is out of bounds')
    return method.removeprefix(PREFIX), dict(params)


def notification(value, method):
    require(isinstance(value, dict) and set(value) == {'jsonrpc', 'method', 'params'} and value.get('jsonrpc') == '2.0' and value.get('method') == method and isinstance(value.get('params'), dict))
    return value['params']


def base(service):
    return {'simulation': True, 'physical_movement_enabled': False, 'source': service,
        'sample_basis': 'first_frame_on_new_subscription', 'status': 'waiting', 'value': None}


def tof_result(description, frame, row, col):
    require(integer(row, 1, 8) and integer(col, 1, 8))
    require(isinstance(description, dict) and type(description.get('accepted')) is bool)
    result = {**base('tofd'), 'row': row, 'col': col, 'unit': 'mm'}
    if not description['accepted']:
        return {**result, 'status': 'refused'}
    require(description.get('sensor') is None or text(description['sensor']))
    if description.get('sensor') is None:
        return {**result, 'status': 'absent'}
    require(description.get('rows') == 8 and type(description['rows']) is int and description.get('cols') == 8 and type(description['cols']) is int and integer(description.get('hz'), 0, 255))
    if frame is None:
        return result
    require(isinstance(frame, dict) and type(frame.get('rows')) is int and frame['rows'] == 8 and type(frame.get('cols')) is int and frame['cols'] == 8)
    for field in ('seq', 'at_us', 't_ns'):
        require(integer(frame.get(field, 0) if field == 't_ns' else frame.get(field), 0, 2**64-1))
    distances, statuses = frame.get('distance_mm'), frame.get('status')
    require(isinstance(distances, list) and len(distances) == 64 and all(integer(x, -32768, 32767) for x in distances))
    require(isinstance(statuses, list) and len(statuses) == 64 and all(integer(x, 0, 255) for x in statuses))
    i = (row-1)*8+col-1
    raw, code = distances[i], statuses[i]
    status = 'ok' if code in (5, 9) and raw > 0 else 'no_target' if code == 255 else 'unusable'
    return {**result, 'status': status, 'value': raw if status == 'ok' else None,
        'raw_distance_mm': raw, 'raw_status': code, 'seq': str(frame['seq']),
        'at_us': str(frame['at_us']), 't_ns': str(frame.get('t_ns', 0))}


def device_report(device):
    require(isinstance(device, dict) and text(device.get('name')) and text(device.get('node')))
    require(all(integer(device.get(k), 0, 65535) for k in ('bus', 'vendor', 'product')))
    require(isinstance(device.get('axes'), list) and len(device['axes']) <= 64 and isinstance(device.get('buttons'), list) and len(device['buttons']) <= 256)
    for key in ('axes', 'buttons'):
        seen = set()
        for item in device[key]:
            require(isinstance(item, dict) and integer(item.get('code'), 0, 65535) and item['code'] not in seen and text(item.get('name')))
            seen.add(item['code'])
            if key == 'axes':
                require(all(integer(item.get(k), -2**31, 2**31-1) for k in ('min', 'max', 'value', 'flat', 'fuzz')) and item['min'] < item['max'] and item['min'] <= item['value'] <= item['max'])
            else:
                require(type(item.get('pressed')) is bool)
    return device


def pad_result(device, frame, kind, code):
    result = {**base('padd'), 'code': code, 'unit': 'raw' if kind == 'axis' else 'pressed'}
    if device is None:
        return result
    entries = device['axes' if kind == 'axis' else 'buttons']
    selected = next((item for item in entries if item['code'] == code), None)
    if selected is None:
        return {**result, 'status': 'unsupported'}
    if kind == 'axis':
        result.update(min=selected['min'], max=selected['max'])
    if frame is None:
        return result
    require(isinstance(frame, dict) and frame.get('report') == 'frame')
    for name in ('seq', 'at_us', 'socket_dropped'):
        require(integer(frame.get(name, 0) if name == 'socket_dropped' else frame.get(name), 0, 2**64-1))
    require(frame.get('since_us') is None or integer(frame['since_us'], -2**63, 2**63-1))
    require(type(frame.get('after_drop', False)) is bool and isinstance(frame.get('events'), list) and len(frame['events']) <= 128)
    match = None
    for event in frame['events']:
        require(isinstance(event, dict) and integer(event.get('kind'), 0, 65535) and integer(event.get('code'), 0, 65535) and integer(event.get('value'), -2**31, 2**31-1) and text(event.get('name')))
        if event['kind'] == (3 if kind == 'axis' else 1) and event['code'] == code:
            match = event['value']
    result.update(seq=str(frame['seq']), at_us=str(frame['at_us']), since_us=None if frame.get('since_us') is None else str(frame['since_us']), socket_dropped=str(frame.get('socket_dropped', 0)), after_drop=frame.get('after_drop', False))
    if result['after_drop'] or frame.get('socket_dropped', 0):
        return {**result, 'status': 'dropped'}
    if match is None:
        return {**result, 'status': 'no_event'}
    if kind == 'axis':
        require(selected['min'] <= match <= selected['max'])
    return {**result, 'status': 'ok', 'value': match if kind == 'axis' else match != 0, 'raw_value': match}


async def read_sample(directory, kind, params):
    """One bounded subscription; this module only calls fixed private fake paths."""
    service = 'tof' if kind == 'tof' else 'pad'
    method = 'tof.stream' if kind == 'tof' else 'pad.input'
    writer, result = None, {**base('tofd' if kind == 'tof' else 'padd'), 'status':'timeout'}
    description, device = None, None
    try:
        async with asyncio.timeout(DEADLINE):
            reader, writer = await connect_checked(directory/(service+'.sock'), os.geteuid(), LINE_LIMIT, private_parent=True)
            writer.write(encode({'jsonrpc':'2.0','id':1,'method':method,'params':{}}, LINE_LIMIT))
            await writer.drain()
            description = response_result(await read_message(reader, LINE_LIMIT), 1)
            if kind == 'tof':
                result = tof_result(description, None, **params)
            else:
                require(isinstance(description, dict) and type(description.get('accepted')) is bool)
                result = pad_result(None, None, kind, params['code'])
                if not description['accepted']:
                    result['status'] = 'refused'
            if result['status'] != 'waiting':
                return result
            for _ in range(EVENTS):
                report = notification(await read_message(reader, LINE_LIMIT), 'tof.frame' if kind == 'tof' else 'pad.report')
                if kind == 'tof':
                    return tof_result(description, report, **params)
                tag = report.get('report')
                if tag == 'attached':
                    device = device_report(report.get('device'))
                    result = pad_result(device, None, kind, params['code'])
                    if result['status'] == 'unsupported':
                        return result
                elif tag == 'detached':
                    require(text(report.get('why')))
                    return {**pad_result(None, None, kind, params['code']), 'status':'detached'}
                elif tag == 'frame':
                    require(device is not None)
                    return pad_result(device, report, kind, params['code'])
                elif tag not in ('imu_attached', 'imu', 'imu_detached'):
                    require(False)
            return {**result, 'status':'event_limit'}
    except TimeoutError:
        return result
    finally:
        if writer:
            writer.close()
            await writer.wait_closed()


def fixture(service, profile):
    """All values fictional. No fixture file or external provider is loaded."""
    if service == 'tof':
        description = {'accepted':True, 'rows':8, 'cols':8, 'hz':15}
        if profile == 'absent':
            return {**description, 'unavailable':'SIMULATION no sensor fitted'}, []
        frame = {'seq':2**63+7, 'at_us':9000001, 't_ns':9000001000, 'rows':8, 'cols':8, 'distance_mm':[1000+i for i in range(64)], 'status':[5]*64}
        frame['status'][1:4], frame['distance_mm'][3] = [255,4,9], -3
        return {**description, 'sensor':'SIMULATED-VL53L8CX'}, [{'jsonrpc':'2.0','method':'tof.frame','params':frame}]
    description = {'accepted':True}
    if profile == 'absent':
        return description, []
    device = {'name':'SIMULATED controller','node':'/dev/input/SIMULATION','bus':3,'vendor':0,'product':0,
        'axes':[{'code':0,'name':'ABS_X','min':-32768,'max':32767,'flat':128,'fuzz':0,'value':0}],
        'buttons':[{'code':304,'name':'BTN_SOUTH','pressed':False}]}
    frame = {'report':'frame','seq':2**63+3,'at_us':1793050000000000,'since_us':-25,
        'events':[{'kind':3,'code':0,'value':1583,'name':'ABS_X'}, {'kind':1,'code':304,'value':2,'name':'BTN_SOUTH'}]}
    return description, [{'jsonrpc':'2.0','method':'pad.report','params':{'report':'attached','device':device}}, {'jsonrpc':'2.0','method':'pad.report','params':frame}]


class SensorGateway(Gateway):
    def __init__(self, upstreams, directory):
        super().__init__(upstreams, allowed_mutations=())
        self.directory = directory

    async def dispatch(self, request):
        if isinstance(request, dict) and isinstance(request.get('method'), str) and request['method'] in METHODS:
            kind, params = validate_sensor(request)
            result = await read_sample(self.directory, kind, params)
            encode({'jsonrpc':'2.0','id':0x7fffffff,'result':result}, 760)
            return result, None
        return await super().dispatch(request)


class SensorSimulator(Simulator):
    def __init__(self, directory, profile='normal'):
        if profile not in ('normal', 'absent'):
            raise ValueError('Known internal simulation profile required')
        super().__init__(directory, allow_mock_actions=False)
        self.profile, self.streams, self.identities = profile, [], {}
        self.subscriptions = 0

    def _make_gateway(self, allowed):
        return SensorGateway({'robot':{'path':str(self.directory/'robot.sock'), 'uid':os.geteuid()}}, self.directory)

    async def start(self):
        try:
            await super().start()
            for service in ('tof','pad'):
                sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
                try:
                    path = self.directory/(service+'.sock')
                    sock.bind(str(path)); os.chmod(path,0o600)
                    meta = path.lstat(); self.identities[path] = meta.st_dev,meta.st_ino
                    sock.listen(4); sock.setblocking(False)
                    self.streams.append(await asyncio.start_unix_server(lambda r,w,s=service:self.stream(s,r,w), sock=sock, limit=LINE_LIMIT))
                except BaseException:
                    sock.close()
                    raise
            self.ready.update(sensor_simulation=True, physical_movement_enabled=False, sensor_profile=self.profile, sensor_methods=sorted(METHODS))
            _fresh_file(self.directory/'sensor-simulation.json',self.ready)
            return self
        except BaseException:
            await self.stop()
            raise

    async def stream(self, service, reader, writer):
        task = asyncio.current_task(); self.tasks.add(task); self.clients.add(writer)
        counted = False
        try:
            require(peer_uid(writer.get_extra_info('socket')) == os.geteuid() and self.active < 4)
            self.active += 1; counted = True
            async with asyncio.timeout(1):
                request = await read_message(reader, LINE_LIMIT)
                method = 'tof.stream' if service == 'tof' else 'pad.input'
                require(request == {'jsonrpc':'2.0','id':1,'method':method,'params':{}} and type(request['id']) is int)
                self.subscriptions += 1
                description, reports = fixture(service,self.profile)
                writer.write(encode({'jsonrpc':'2.0','id':1,'result':description}, LINE_LIMIT))
                for report in reports:
                    writer.write(encode(report, LINE_LIMIT))
                await writer.drain()
                await reader.read(1)  # no background production; wait for bounded reader cleanup
        except (RpcError, OSError, TimeoutError):
            pass
        finally:
            if counted: self.active -= 1
            writer.close()
            try: await writer.wait_closed()
            except OSError: pass
            self.tasks.discard(task); self.clients.discard(writer)

    async def stop(self):
        for server in self.streams:
            server.close(); await server.wait_closed()
        self.streams.clear()
        await super().stop()
        for path, identity in self.identities.items():
            try:
                meta = path.lstat()
                if stat.S_ISSOCK(meta.st_mode) and (meta.st_dev,meta.st_ino) == identity: path.unlink()
            except FileNotFoundError: pass
        self.identities.clear()


async def main(args):
    service = SensorSimulator(args.directory,args.fixture)
    stopped = asyncio.Event(); loop = asyncio.get_running_loop()
    for signum in (signal.SIGINT,signal.SIGTERM): loop.add_signal_handler(signum,stopped.set)
    try:
        await service.start()
        print(json.dumps(service.ready,separators=(',',':')),flush=True)
        await stopped.wait()
    finally: await service.stop()


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--directory',required=True,type=Path)
    parser.add_argument('--fixture',choices=('normal','absent'),default='normal')
    args=parser.parse_args()
    if sys.platform != 'linux': parser.error('Linux peer credentials required')
    try: asyncio.run(main(args))
    except (ValueError,OSError,RpcError) as error: parser.exit(1,f'Sensor simulation refused: {error}\n')
