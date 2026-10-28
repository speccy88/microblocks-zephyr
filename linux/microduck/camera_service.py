"""Finite mediad UYVY reader. Raw camera bytes never enter generic JSON routing."""
# SPDX-License-Identifier: MIT
import asyncio
from pathlib import Path
import secrets

try:
    from .camera_rgb import rgb24
    from .head_imu_service import validate_source, load_source
    from .sensor_snapshots import SnapshotStore, token
    from .sensor_simulator import require, integer
    from .protocol import API_VERSION, RpcError, connect_checked, encode, read_message, response_result
except ImportError:
    from camera_rgb import rgb24
    from head_imu_service import validate_source, load_source
    from sensor_snapshots import SnapshotStore, token
    from sensor_simulator import require, integer
    from protocol import API_VERSION, RpcError, connect_checked, encode, read_message, response_result

PREFIX='microduck.camera.'
METHODS=frozenset(PREFIX+n for n in ('capture','metadata','pixel','release'))
MAX_BYTES=16*1024*1024
LINE_LIMIT=4096
DEADLINE=3.0
FIELDS={'width':'pixels','height':'pixels','bytes':'bytes','format':'format','rotate':'degrees_clockwise','captured_at_unix_us':'us_unix128'}
CHANNELS={'y':'luma_raw8','u':'chroma_u_raw8','v':'chroma_v_raw8','rgb':'rgb24_bt601_limited'}


def result(kind,status,**parts):
    return {'origin':'local_ipc','source':'mediad','physical_hardware_verified':False,
            'physical_movement_enabled':False,'kind':kind,'status':status,**parts}


def validate(request):
    require(isinstance(request,dict) and not set(request)-{'jsonrpc','id','method','params','confirmed'}
            and request.get('jsonrpc')=='2.0' and integer(request.get('id'),1,0x7fffffff))
    method,p=request.get('method'),request.get('params',{})
    require(isinstance(method,str) and method in METHODS and isinstance(p,dict)
            and ('confirmed' not in request or type(request['confirmed']) is bool))
    name=method.removeprefix(PREFIX)
    if name=='capture':require(not p)
    else:
        keys={'handle'} | ({'field'} if name=='metadata' else {'x','y','channel'} if name=='pixel' else set())
        require(set(p)==keys and token(p['handle']))
        if name=='metadata':require(isinstance(p['field'],str) and p['field'] in FIELDS)
        if name=='pixel':require(integer(p['x'],1,MAX_BYTES//2) and integer(p['y'],1,MAX_BYTES//4)
                                and isinstance(p['channel'],str) and p['channel'] in CHANNELS)
    return name,dict(p)


def validate_header(header):
    require(isinstance(header,dict) and set(header)==set(FIELDS))
    require(integer(header['width'],2,MAX_BYTES//2) and header['width']%2==0
            and integer(header['height'],1,MAX_BYTES//4) and header['format']=='UYVY'
            and integer(header['bytes'],4,MAX_BYTES) and header['bytes']==header['width']*header['height']*2
            and type(header['rotate']) is int and header['rotate'] in (0,90,180,270)
            and integer(header['captured_at_unix_us'],0,2**128-1))
    return dict(header)


async def read_frame(config):
    config=validate_source(config,'mediad');writer=None
    try:
        async with asyncio.timeout(DEADLINE):
            reader,writer=await connect_checked(Path(config['path']),config['uid'],LINE_LIMIT)
            writer.write(encode({'jsonrpc':'2.0','id':1,'method':'hello','params':{'api_version':API_VERSION}},LINE_LIMIT));await writer.drain()
            hello=response_result(await read_message(reader,LINE_LIMIT),1)
            require(isinstance(hello,dict) and integer(hello.get('api_version'),API_VERSION,API_VERSION))
            writer.write(encode({'jsonrpc':'2.0','id':2,'method':'media.frame'},LINE_LIMIT));await writer.drain()
            header=validate_header(response_result(await read_message(reader,LINE_LIMIT),2))
            pixels=await reader.readexactly(header['bytes'])
            # The pinned endpoint closes after this single binary tail.
            require(not await reader.read(1))
            return 'ok',{'header':header,'pixels':pixels}
    except TimeoutError:return 'timeout',None
    except asyncio.IncompleteReadError:raise RpcError(-32011,'Camera binary tail was truncated') from None
    finally:
        if writer:
            writer.close()
            try:await writer.wait_closed()
            except OSError:pass


class CameraStore(SnapshotStore):
    def __init__(self,config):
        self.config=validate_source(config,'mediad')
        super().__init__(Path(self.config['path']).parent)

    async def acquire(self):
        self.purge()
        if len(self.entries)+self.pending>=4:return result('camera_capture','busy')
        self.pending+=1
        try:
            status,state=await read_frame(self.config)
            if state is None:return result('camera_capture',status)
            now,handle=self.purge(),secrets.token_hex(16);require(handle not in self.entries)
            self.entries[handle]={'state':state,'expires':now+5}
            return result('camera_capture','ok',handle=handle,expires_in_ms=5000)
        finally:self.pending-=1

    def read(self,name,p):
        self.purge();entry=self.entries.get(p['handle'])
        extra={'field':p['field'],'unit':FIELDS[p['field']]} if name=='metadata' else {'x':p['x'],'y':p['y'],'channel':p['channel'],'unit':CHANNELS[p['channel']]}
        if entry is None:return result('camera_'+name,'expired_or_unknown',value=None,**extra)
        state=entry['state'];header=state['header']
        if name=='metadata':
            value=header[p['field']]
            if p['field']=='captured_at_unix_us':value=str(value)
        else:
            if p['x']>header['width'] or p['y']>header['height']:return result('camera_pixel','out_of_range',value=None,**extra)
            x,y=p['x']-1,p['y']-1;pair=(y*header['width']+(x//2)*2)*2
            pixels=state['pixels']
            value=(rgb24(pixels[pair+1+2*(x%2)],pixels[pair],pixels[pair+2]) if p['channel']=='rgb'
                   else pixels[pair+({'u':0,'v':2}.get(p['channel'],1+2*(x%2)))])
        return result('camera_'+name,'ok',value=value,**extra)

    async def dispatch(self,request):
        name,p=validate(request)
        if name=='capture':value=await self.acquire()
        elif name=='release':
            self.purge();removed=self.entries.pop(p['handle'],None)
            value=result('camera_release','released' if removed is not None else 'not_retained')
        else:value=self.read(name,p)
        encode({'jsonrpc':'2.0','id':0x7fffffff,'result':value},760)
        return value
