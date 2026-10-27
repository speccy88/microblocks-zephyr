"""Bounded read-only padd state/discovery; local_ipc is transport, not freshness."""
# SPDX-License-Identifier: MIT
import asyncio
import copy
from pathlib import Path
import secrets

try:
    from . import head_imu_service as config_io
    from . import sensor_simulator as wire
    from .sensor_snapshots import PadWindow, SnapshotStore, token
    from .protocol import connect_checked, encode, read_message, response_result
except ImportError:
    import head_imu_service as config_io
    import sensor_simulator as wire
    from sensor_snapshots import PadWindow, SnapshotStore, token
    from protocol import connect_checked, encode, read_message, response_result

PREFIX='microduck.gamepad.'
METHODS=frozenset(PREFIX+n for n in ('capture','axis','button','control','metadata','release'))
AXIS_FIELDS={'raw':'raw','position':'permille','event_seq':'count64'}
BUTTON_FIELDS={'pressed':'boolean','event_seq':'count64'}
CONTROL_FIELDS={'code':'code','name':'text','min':'raw','max':'raw','flat':'raw','fuzz':'raw'}
META_FIELDS={'seq':'count64','at_us':'us_unix','since_us':'us_delta','frames':'count',
             'axis_count':'count','button_count':'count','device_name':'text','bus':'id','vendor':'id','product':'id','observation_state':'state'}


def validate_source(config):return config_io.validate_source(config,'padd')
def load_source(path):return config_io.load_source(path,'padd')


def text(value):
    try:
        return isinstance(value,str) and 0<len(value.encode('utf-8'))<=128 and not any(ord(c)<32 or ord(c)==127 for c in value)
    except UnicodeError:
        return False


def validate(request):
    wire.require(isinstance(request,dict) and not set(request)-{'jsonrpc','id','method','params','confirmed'}
                 and request.get('jsonrpc')=='2.0' and wire.integer(request.get('id'),1,0x7fffffff))
    method,p=request.get('method'),request.get('params',{})
    wire.require(isinstance(method,str) and method in METHODS and isinstance(p,dict)
                 and ('confirmed' not in request or type(request['confirmed']) is bool))
    name=method.removeprefix(PREFIX)
    if name=='capture':wire.require(not p)
    else:
        keys={'handle'} | ({'code','field'} if name in ('axis','button') else {'kind','index','field'} if name=='control' else {'field'} if name=='metadata' else set())
        wire.require(set(p)==keys and token(p['handle']))
        if name in ('axis','button'):
            wire.require(wire.integer(p['code'],0,65535) and isinstance(p['field'],str) and p['field'] in (AXIS_FIELDS if name=='axis' else BUTTON_FIELDS))
        if name=='control':
            wire.require(isinstance(p['kind'],str) and p['kind'] in ('axis','button') and wire.integer(p['index'],1,64 if p['kind']=='axis' else 256)
                         and isinstance(p['field'],str) and p['field'] in (CONTROL_FIELDS if p['kind']=='axis' else {'code','name'}))
        if name=='metadata':wire.require(isinstance(p['field'],str) and p['field'] in META_FIELDS)
    return name,dict(p)


def result(kind,status,**parts):
    return {'origin':'local_ipc','source':'padd','physical_hardware_verified':False,'physical_movement_enabled':False,
            'kind':kind,'status':status,**parts}


def validate_device(device):
    device=copy.deepcopy(wire.device_report(device))
    wire.require(text(device['name']) and all(text(item['name']) for key in ('axes','buttons') for item in device[key]))
    return device


async def read_padd(config):
    config=validate_source(config);writer=None;window=PadWindow();status='timeout';ended='event_limit'
    try:
        async with asyncio.timeout(wire.DEADLINE):
            reader,writer=await connect_checked(Path(config['path']),config['uid'],wire.LINE_LIMIT)
            writer.write(encode({'jsonrpc':'2.0','id':1,'method':'pad.input','params':{}},wire.LINE_LIMIT));await writer.drain()
            description=response_result(await read_message(reader,wire.LINE_LIMIT),1)
            wire.require(isinstance(description,dict) and type(description.get('accepted')) is bool)
            if not description['accepted']:return 'refused',None
            status='waiting'
            for _ in range(wire.EVENTS):
                report=wire.notification(await read_message(reader,wire.LINE_LIMIT),'pad.report')
                if report.get('report')=='attached':
                    report={**report,'device':validate_device(report.get('device'))}
                window.apply(report)
    except TimeoutError:
        ended='deadline'
    finally:
        if writer:
            writer.close();await writer.wait_closed()
    if window.device is not None:
        return 'ok',{'device':copy.deepcopy(window.device),'observation':window.snapshot(),'window_end':ended}
    return ('detached' if window.status=='detached' else 'event_limit' if status!='timeout' and ended=='event_limit' else status),None


def reading(state,name,p):
    field=p['field'];obs,device=state['observation'],state['device']
    unit=(AXIS_FIELDS if name=='axis' else BUTTON_FIELDS if name=='button' else CONTROL_FIELDS if name=='control' else META_FIELDS)[field]
    base=result('gamepad_reading','not_reported',section=name,**{('control_kind' if k=='kind' else k):v for k,v in p.items() if k!='handle'},unit=unit,value=None)
    if name=='metadata':
        values={'seq':obs['seq'],'at_us':obs['at_us'],'since_us':obs['since_us'],'frames':obs['frames'],
                'axis_count':len(device['axes']),'button_count':len(device['buttons']),'device_name':device['name'],
                'bus':device['bus'],'vendor':device['vendor'],'product':device['product'],'observation_state':obs['status']}
        value=values[field]
        if value is None:return base
    elif name=='control':
        controls=device['axes' if p['kind']=='axis' else 'buttons']
        if p['index']>len(controls):return {**base,'status':'unsupported'}
        value=controls[p['index']-1][field]
    else:
        item=obs['axes' if name=='axis' else 'buttons'].get(p['code'])
        if item is None:return {**base,'status':'unsupported'}
        if item['status']!='ok':return {**base,'status':item['status']}
        value=item['event_seq'] if field=='event_seq' else item['value']
        if value is None:return base
        if field=='pressed':value=value!=0
        if field=='position':
            low,high=item['min'],item['max'];value=((value-low)*1000+(high-low)//2)//(high-low)
    if field=='since_us':value=str(value)
    if type(value) is int and not -(2**30)<=value<2**30:return {**base,'status':'out_of_range'}
    return {**base,'status':'ok','value':value}


class GamepadStore(SnapshotStore):
    def __init__(self,config):
        self.config=validate_source(config);super().__init__(Path(self.config['path']).parent)

    async def acquire(self):
        self.purge()
        if len(self.entries)+self.pending>=4:return result('gamepad_capture','busy')
        self.pending+=1
        try:
            status,state=await read_padd(self.config)
            if state is None:return result('gamepad_capture',status)
            now,handle=self.purge(),secrets.token_hex(16);wire.require(handle not in self.entries)
            self.entries[handle]={'state':state,'expires':now+5}
            return result('gamepad_capture','ok',handle=handle,frames=state['observation']['frames'],sample_basis='bounded_observed_events',expires_in_ms=5000)
        finally:self.pending-=1

    def release(self,handle):
        self.purge();removed=self.entries.pop(handle,None)
        return result('gamepad_release','released' if removed is not None else 'not_retained')

    def read(self,name,p):
        self.purge();entry=self.entries.get(p['handle'])
        if entry is None:
            unit=(AXIS_FIELDS if name=='axis' else BUTTON_FIELDS if name=='button' else CONTROL_FIELDS if name=='control' else META_FIELDS)[p['field']]
            return result('gamepad_reading','expired_or_unknown',section=name,**{('control_kind' if k=='kind' else k):v for k,v in p.items() if k!='handle'},unit=unit,value=None)
        return reading(entry['state'],name,p)

    async def dispatch(self,request):
        name,p=validate(request)
        value=await self.acquire() if name=='capture' else self.release(p['handle']) if name=='release' else self.read(name,p)
        encode({'jsonrpc':'2.0','id':0x7fffffff,'result':value},760)
        return value
