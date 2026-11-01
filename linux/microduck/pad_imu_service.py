"""Explicit finite padd IMU source; local_ipc denotes transport, not hardware."""
# SPDX-License-Identifier: MIT
from pathlib import Path
try:
    from . import pad_imu_simulator as core, head_imu_service as config_io
except ImportError:
    import pad_imu_simulator as core, head_imu_service as config_io

PREFIX='microduck.padImu.'
METHODS=frozenset(PREFIX+n for n in ('capture','read','release'))
FIELDS=core.FIELDS

def validate_source(config):return config_io.validate_source(config,'padd')
def load_source(path):return config_io.load_source(path,'padd')

def validate(request):
    core.require(isinstance(request,dict) and isinstance(request.get('method'),str) and request['method'] in METHODS,-32601)
    name=request['method'].removeprefix(PREFIX)
    _,p=core.validate({**request,'method':core.PREFIX+('capturePad' if name=='capture' else name)})
    return name,p

def result(kind,status,**parts):
    return {'origin':'local_ipc','source':'padd','physical_hardware_verified':False,'physical_movement_enabled':False,'kind':kind,'status':status,**parts}

class ServiceStore(core.ImuStore):
    envelope=staticmethod(result)
    def __init__(self,config):
        self.config=validate_source(config)
        super().__init__(Path(self.config['path']).parent)
    async def read_source(self):
        return await core.capture_source(Path(self.config['path']),self.config['uid'],envelope=self.envelope)
    async def dispatch(self,request):
        name,p=validate(request)
        value=await self.acquire() if name=='capture' else self.release(p['handle']) if name=='release' else self.read(p['handle'],p['field'],p['sample'],p['component'])
        core.encode({'jsonrpc':'2.0','id':0x7fffffff,'result':value},760)
        return value
