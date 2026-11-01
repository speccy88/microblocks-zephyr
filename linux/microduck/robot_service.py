"""Finite read-only robotd health/state; no intent transport or hardware claim."""
# SPDX-License-Identifier: MIT
import asyncio
from pathlib import Path
import secrets
try:
    from . import head_imu_service as config_io, robot_health as health, robot_telemetry as state
    from .sensor_snapshots import SnapshotStore, token
    from .protocol import connect_checked, encode, read_message, response_result
except ImportError:
    import head_imu_service as config_io, robot_health as health, robot_telemetry as state
    from sensor_snapshots import SnapshotStore, token
    from protocol import connect_checked, encode, read_message, response_result

PREFIX='microduck.robot.'
METHODS=frozenset(PREFIX+n for n in ('capture','read','release'))
LINE_LIMIT=16384
DEADLINE=.5

def validate_source(config):return config_io.validate_source(config,'robotd')
def load_source(path):return config_io.load_source(path,'robotd')

def validate(request):
    state.require(isinstance(request,dict) and not set(request)-{'jsonrpc','id','method','params','confirmed'} and request.get('jsonrpc')=='2.0' and state.integer(request.get('id'),1,0x7fffffff))
    method,p=request.get('method'),request.get('params',{})
    state.require(isinstance(method,str) and method in METHODS and isinstance(p,dict) and ('confirmed' not in request or type(request['confirmed']) is bool))
    name=method.removeprefix(PREFIX)
    if name=='capture':
        state.require(p.get('kind') in ('health','state') and set(p)==({'kind'} if p['kind']=='health' else {'kind','hz'}))
        if p['kind']=='state':state.require(state.integer(p['hz'],1,50))
    else:
        state.require(set(p)==({'handle'} if name=='release' else {'handle','kind','field','index','component'}) and token(p['handle']))
        if name=='read':
            state.require(p['kind'] in ('health','state') and isinstance(p['field'],str))
            fields={k:(1,1) for k in health.FIELDS} if p['kind']=='health' else state.FIELDS
            state.require(p['field'] in fields);a,b=fields[p['field']]
            state.require(state.integer(p['index'],1,a) and state.integer(p['component'],1,b))
    return name,dict(p)

def result(kind,status,**parts):
    return {'origin':'local_ipc','source':'robotd','physical_hardware_verified':False,'physical_movement_enabled':False,'kind':kind,'status':status,**parts}

async def capture(config,kind,hz=None):
    writer=None;stage='timeout';version=None
    try:
        async with asyncio.timeout(DEADLINE):
            reader,writer=await connect_checked(Path(config['path']),config['uid'],LINE_LIMIT)
            writer.write(encode({'jsonrpc':'2.0','id':0,'method':'hello','params':{'api_version':state.API_VERSION}},8192));await writer.drain()
            hello=response_result(await read_message(reader,LINE_LIMIT),0)
            state.require(isinstance(hello,dict) and state.integer(hello.get('api_version'),0,2**32-1));version=hello['api_version']
            method='robot.health' if kind=='health' else 'robot.subscribe'
            writer.write(encode({'jsonrpc':'2.0','id':1,'method':method,'params':{} if kind=='health' else {'hz':hz}},8192));await writer.drain()
            value=response_result(await read_message(reader,LINE_LIMIT),1)
            if kind=='state':
                state.require(isinstance(value,dict) and type(value.get('accepted')) is bool)
                if not value['accepted']:return 'refused',None,version
                stage='waiting';value=await read_message(reader,LINE_LIMIT)
                state.require(isinstance(value,dict) and set(value)=={'jsonrpc','method','params'} and value['jsonrpc']=='2.0' and value['method']=='robot.state')
                value=state.validate_state(value['params'])
            else:value=health.validate_health(value)
            return 'ok',value,version
    except TimeoutError:return stage,None,version
    finally:
        if writer:
            writer.close();await writer.wait_closed()

class RobotStore(SnapshotStore):
    def __init__(self,config):
        self.config=validate_source(config);super().__init__(Path(self.config['path']).parent)

    async def acquire(self,kind,hz=None):
        self.purge()
        if len(self.entries)+self.pending>=4:return result('robot_capture','busy',snapshot_kind=kind)
        self.pending+=1
        try:
            status,value,version=await capture(self.config,kind,hz)
            if value is None:return result('robot_capture',status,snapshot_kind=kind,reported_api_version=version)
            now,handle=self.purge(),secrets.token_hex(16);state.require(handle not in self.entries)
            self.entries[handle]={'kind':kind,'value':value,'expires':now+5}
            return result('robot_capture','ok',snapshot_kind=kind,handle=handle,reported_api_version=version,expires_in_ms=5000)
        finally:self.pending-=1

    def read(self,p):
        self.purge();entry=self.entries.get(p['handle']);kind=p['kind'];field=p['field']
        unit=health.FIELDS[field][0] if kind=='health' else state.unit_for(field,p['component'])
        base=dict(snapshot_kind=kind,field=field,index=p['index'],component=p['component'],unit=unit,value=None)
        if entry is None:return result('robot_reading','expired_or_unknown',**base)
        if entry['kind']!=kind:return result('robot_reading','wrong_kind',**base)
        value=health.sample(entry['value'],field) if kind=='health' else state.sample(entry['value'],field,p['index'],p['component'])
        value.pop('simulation',None);value.pop('physical_movement_enabled',None)
        value.update(kind='robot_reading',snapshot_kind=kind)
        return result(**value)

    def release(self,handle):
        self.purge();removed=self.entries.pop(handle,None)
        return result('robot_release','released' if removed is not None else 'not_retained')

    async def dispatch(self,request):
        name,p=validate(request)
        value=await self.acquire(p['kind'],p.get('hz')) if name=='capture' else self.release(p['handle']) if name=='release' else self.read(p)
        encode({'jsonrpc':'2.0','id':0x7fffffff,'result':value},760)
        return value
