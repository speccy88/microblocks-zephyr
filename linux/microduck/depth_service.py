"""Finite coherent depth adapter; local_ipc is transport, never hardware proof."""
# SPDX-License-Identifier: MIT
import asyncio
import copy
from pathlib import Path
import secrets

try:
    from .head_imu_service import validate_source, load_source, result
    from .head_imu_simulator import sensor_name
    from . import sensor_simulator as wire
    from .sensor_snapshots import SnapshotStore, token
    from .protocol import RpcError, connect_checked, encode, read_message, response_result
except ImportError:
    from head_imu_service import validate_source, load_source, result
    from head_imu_simulator import sensor_name
    import sensor_simulator as wire
    from sensor_snapshots import SnapshotStore, token
    from protocol import RpcError, connect_checked, encode, read_message, response_result

PREFIX = 'microduck.depth.'
METHODS = frozenset(PREFIX+n for n in ('capture','row','zone','metadata','release'))
ZONE_FIELDS = {'distance':'mm','raw_distance':'mm_raw','raw_status':'raw_status'}
META_FIELDS = {'seq':'count64','at_us':'us_sender','t_ns':'ns','rows':'count','cols':'count','rate':'Hz','sensor':'sensor'}


def validate(request):
    wire.require(isinstance(request,dict) and not set(request)-{'jsonrpc','id','method','params','confirmed'}
                 and request.get('jsonrpc')=='2.0' and wire.integer(request.get('id'),1,0x7fffffff))
    method,p=request.get('method'),request.get('params',{})
    wire.require(isinstance(method,str) and method in METHODS and isinstance(p,dict)
                 and ('confirmed' not in request or type(request['confirmed']) is bool))
    name=method.removeprefix(PREFIX)
    if name=='capture':
        wire.require(not p)
    else:
        keys={'handle'} | ({'row'} if name=='row' else {'row','col','field'} if name=='zone' else {'field'} if name=='metadata' else set())
        wire.require(set(p)==keys and token(p['handle']))
        if name in ('row','zone'):wire.require(wire.integer(p['row'],1,8))
        if name=='zone':wire.require(wire.integer(p['col'],1,8) and isinstance(p['field'],str) and p['field'] in ZONE_FIELDS)
        if name=='metadata':wire.require(isinstance(p['field'],str) and p['field'] in META_FIELDS)
    return name,dict(p)


def validate_frame(frame):
    wire.require(isinstance(frame,dict) and wire.integer(frame.get('rows'),8,8) and wire.integer(frame.get('cols'),8,8))
    for key in ('seq','at_us','t_ns'):
        if key in frame:wire.require(wire.integer(frame[key],0,2**64-1))
    for key,lo,hi in [('distance_mm',-32768,32767),('status',0,255)]:
        wire.require(isinstance(frame.get(key),list) and len(frame[key])==64 and all(wire.integer(v,lo,hi) for v in frame[key]))
    return copy.deepcopy(frame)


async def read_tofd_depth(config):
    config=validate_source(config)
    writer,status=None,'timeout'
    try:
        async with asyncio.timeout(wire.DEADLINE):
            reader,writer=await connect_checked(Path(config['path']),config['uid'],wire.LINE_LIMIT)
            writer.write(encode({'jsonrpc':'2.0','id':1,'method':'tof.stream','params':{}},wire.LINE_LIMIT));await writer.drain()
            description=response_result(await read_message(reader,wire.LINE_LIMIT),1)
            wire.require(isinstance(description,dict) and type(description.get('accepted')) is bool)
            if not description['accepted']:return 'refused',None
            if description.get('sensor') is None:return 'absent',None
            wire.require(sensor_name(description['sensor']) and wire.integer(description.get('rows'),8,8) and wire.integer(description.get('cols'),8,8))
            if 'hz' in description:wire.require(wire.integer(description['hz'],0,255))
            status='waiting'
            frame=validate_frame(wire.notification(await read_message(reader,wire.LINE_LIMIT),'tof.frame'))
            return 'ok',{'description':copy.deepcopy(description),'frame':frame}
    except TimeoutError:
        return status,None
    finally:
        if writer:
            writer.close();await writer.wait_closed()


def zone_reading(state,row,col,field):
    wire.require(wire.integer(row,1,8) and wire.integer(col,1,8) and isinstance(field,str) and field in ZONE_FIELDS)
    frame=state['frame'];i=(row-1)*8+col-1;raw,code=frame['distance_mm'][i],frame['status'][i]
    status='ok' if field!='distance' or code in (5,9) and raw>0 else 'no_target' if code==255 else 'unusable'
    return result('depth_reading',status,field=field,row=row,col=col,unit=ZONE_FIELDS[field],
                  value=(code if field=='raw_status' else raw) if status=='ok' else None,raw_distance_mm=raw,raw_status=code)


def metadata_reading(state,field):
    wire.require(isinstance(field,str) and field in META_FIELDS)
    description,frame=state['description'],state['frame']
    value=description.get('hz') if field=='rate' else description.get('sensor') if field=='sensor' else frame.get(field)
    if field=='t_ns' and value==0:value=None
    if value is not None and field in ('seq','at_us','t_ns'):value=str(value)
    return result('depth_metadata','not_reported' if value is None else 'ok',field=field,unit=META_FIELDS[field],value=value)


class DepthStore(SnapshotStore):
    def __init__(self,config):
        self.config=validate_source(config)
        super().__init__(Path(self.config['path']).parent)

    async def acquire(self):
        self.purge()
        if len(self.entries)+self.pending>=4:return result('tof_capture','busy')
        self.pending+=1
        try:
            status,state=await read_tofd_depth(self.config)
            if state is None:return result('tof_capture',status)
            now,handle=self.purge(),secrets.token_hex(16);wire.require(handle not in self.entries)
            self.entries[handle]={'state':state,'expires':now+5}
            return result('tof_capture','ok',handle=handle,rows=8,cols=8,expires_in_ms=5000)
        finally:self.pending-=1

    def release(self,handle):
        self.purge();removed=self.entries.pop(handle,None)
        return result('depth_release','released' if removed is not None else 'not_retained')

    def read(self,name,p):
        self.purge();entry=self.entries.get(p['handle']);kind={'row':'depth_row','zone':'depth_reading','metadata':'depth_metadata'}[name]
        if entry is None:
            if name=='row':return result(kind,'expired_or_unknown')
            unit=ZONE_FIELDS[p['field']] if name=='zone' else META_FIELDS[p['field']]
            return result(kind,'expired_or_unknown',**{k:v for k,v in p.items() if k!='handle'},unit=unit,value=None)
        state=entry['state']
        if name=='zone':return zone_reading(state,p['row'],p['col'],p['field'])
        if name=='metadata':return metadata_reading(state,p['field'])
        i=(p['row']-1)*8;frame=state['frame']
        return result('depth_row','ok',handle=p['handle'],row=p['row'],distance_mm=frame['distance_mm'][i:i+8],raw_status=frame['status'][i:i+8])

    async def dispatch(self,request):
        name,p=validate(request)
        value=await self.acquire() if name=='capture' else self.release(p['handle']) if name=='release' else self.read(name,p)
        encode({'jsonrpc':'2.0','id':0x7fffffff,'result':value},760)
        return value
