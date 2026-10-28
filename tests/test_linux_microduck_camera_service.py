"""Real Unix framing/native VM with fictional UYVY pixels; no camera or robot."""
# SPDX-License-Identifier: MIT
import asyncio
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT=Path(__file__).resolve().parents[1]
pkg=types.ModuleType('camera_service_tests');pkg.__path__=[str(ROOT/'linux/microduck')];sys.modules[pkg.__name__]=pkg
svc=importlib.import_module(pkg.__name__+'.camera_service')
gateway=importlib.import_module(pkg.__name__+'.gateway')
rpc=importlib.import_module(pkg.__name__+'.protocol')
client=importlib.import_module(pkg.__name__+'.client')

def header():return {'width':4,'height':2,'format':'UYVY','bytes':16,'rotate':90,'captured_at_unix_us':2**128-1}
PIXELS=bytes([10,0,20,255,30,42,40,100,50,16,60,235,70,80,90,128])
def request(name='capture',p=None):return {'jsonrpc':'2.0','id':1,'method':svc.PREFIX+name,'params':p or {},'confirmed':False}
def source(path):return {'version':1,'daemon':'mediad','path':str(path),'uid':os.geteuid()}


class CameraWire:
    """Pinned hello then JSON header plus binary tail, closes after one capture."""
    def __init__(self,path):
        self.path=path;self.header=header();self.pixels=PIXELS;self.audit=[];self.api=44;self.id=2
        self.raw_header=None;self.refuse=False;self.silent=False;self.fragment=3;self.clients=set();self.tasks=set()
    async def start(self):
        self.server=await asyncio.start_unix_server(self.handle,path=str(self.path),limit=4096);self.path.chmod(0o600);return self
    async def handle(self,reader,writer):
        task=asyncio.current_task();self.tasks.add(task);self.clients.add(writer)
        try:
            hello=await rpc.read_message(reader,4096);self.audit.append(hello)
            if hello!={'jsonrpc':'2.0','id':1,'method':'hello','params':{'api_version':44}}:return
            writer.write(rpc.encode({'jsonrpc':'2.0','id':1,'result':{'api_version':self.api,'daemon_version':'0.0.0-fixture','revision':None}},4096));await writer.drain()
            line=await reader.readline()
            if not line:return
            q=rpc.decode(line,4096);self.audit.append(q)
            if q!={'jsonrpc':'2.0','id':2,'method':'media.frame'}:return
            if self.silent:await reader.read();return
            if self.refuse:
                data=rpc.encode({'jsonrpc':'2.0','id':2,'error':{'code':-32603,'message':'fictional camera unavailable'}},4096)
            else:
                data=(self.raw_header if self.raw_header is not None else rpc.encode({'jsonrpc':'2.0','id':self.id,'result':self.header},4096))+self.pixels
            for i in range(0,len(data),self.fragment):
                writer.write(data[i:i+self.fragment]);await writer.drain();await asyncio.sleep(0)
        except (OSError,rpc.RpcError):pass
        finally:
            writer.close()
            try:await writer.wait_closed()
            except OSError:pass
            self.clients.discard(writer);self.tasks.discard(task)
    async def stop(self):
        self.server.close();await self.server.wait_closed()
        for w in list(self.clients):w.close()
        for t in list(self.tasks):t.cancel()
        await asyncio.gather(*list(self.tasks),return_exceptions=True)
        self.path.unlink(missing_ok=True)


class CameraContract(unittest.TestCase):
    def test_pinned_geometry_limits_before_binary_allocation(self):
        self.assertEqual(svc.validate_header(header()),header())
        for changes in ({'width':3},{'width':True},{'height':0},{'height':2**32},{'format':'RGB'},
                        {'bytes':17},{'bytes':svc.MAX_BYTES+1},{'rotate':45},{'rotate':True},
                        {'captured_at_unix_us':-1},{'captured_at_unix_us':2**128},{'captured_at_unix_us':True},
                        {'width':8388608,'height':2,'bytes':33554432},{'stride':8}):
            with self.assertRaises(rpc.RpcError):svc.validate_header({**header(),**changes})
        for key in header():
            h=header();h.pop(key)
            with self.assertRaises(rpc.RpcError):svc.validate_header(h)
    def test_method_and_coordinate_validation_is_closed(self):
        self.assertEqual(gateway.validate(request())[0],svc.PREFIX+'capture')
        for q in (request('capture',{'path':'/run/mediad.sock'}),request('pixel',{'handle':'a'*32,'x':True,'y':1,'channel':'y'}),
                  request('pixel',{'handle':'a'*32,'x':0,'y':1,'channel':'y'}),request('pixel',{'handle':'a'*32,'x':1,'y':1,'channel':'rgb'}),
                  request('metadata',{'handle':'A'*32,'field':'width'}),request('metadata',{'handle':'a'*32,'field':'unknown'}),
                  request('release',{'handle':'a'*32,'extra':0}),{**request(),'confirmed':1}):
            with self.assertRaises(rpc.RpcError):svc.validate(q)
        for method in ('media.frame','media.stream','robot.move'):
            with self.assertRaises(rpc.RpcError):gateway.validate({**request(),'method':method})


@unittest.skipUnless(sys.platform=='linux','Linux checked Unix transport required')
class CameraUnix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='camera-fixture-');self.root=Path(self.temp.name)
        self.wire=await CameraWire(self.root/'media.sock').start()
        self.normal=await gateway.Gateway({},camera=source(self.wire.path)).start(self.root/'gateway.sock')
        self.client=client.Client(self.normal.path)
    async def asyncTearDown(self):
        await self.normal.stop();await self.wire.stop();self.temp.cleanup()
    async def call(self,name='capture',p=None):return await self.client.call(svc.PREFIX+name,p)
    async def test_fragmented_binary_all_pixels_and_exact_metadata_single_capture(self):
        self.normal.camera.clock=lambda:0
        capture=await self.call();h=capture['handle']
        for y in range(1,3):
            for x in range(1,5):
                pair=((y-1)*4+((x-1)//2)*2)*2
                for channel,offset in [('y',1+2*((x-1)%2)),('u',0),('v',2)]:
                    v=await self.call('pixel',{'handle':h,'x':x,'y':y,'channel':channel})
                    self.assertEqual(v['value'],PIXELS[pair+offset]);self.assertEqual(v['unit'],svc.CHANNELS[channel])
        for field in svc.FIELDS:
            v=await self.call('metadata',{'handle':h,'field':field})
            self.assertEqual(v['value'],str(header()[field]) if field=='captured_at_unix_us' else header()[field])
            self.assertFalse(v['physical_hardware_verified']);self.assertNotIn('simulation',v)
        self.assertEqual([q['method'] for q in self.wire.audit],['hello','media.frame'])
    async def test_out_of_bounds_release_expiry_and_clock_regression(self):
        clock=[10.0];self.normal.camera.clock=lambda:clock[0]
        h=(await self.call())['handle']
        v=await self.call('pixel',{'handle':h,'x':5,'y':1,'channel':'y'})
        self.assertEqual((v['status'],v['value']),('out_of_range',None))
        clock[0]=15;v=await self.call('metadata',{'handle':h,'field':'width'})
        self.assertEqual((v['status'],v['value']),('expired_or_unknown',None))
        h=(await self.call())['handle'];clock[0]=14
        self.assertEqual((await self.call('release',{'handle':h}))['status'],'not_retained')
        h=(await self.call())['handle'];self.assertEqual((await self.call('release',{'handle':h}))['status'],'released')
        self.assertFalse(self.normal.camera.entries)
    async def test_capacity_counts_pending_and_retained(self):
        self.normal.camera.clock=lambda:0
        handles=[(await self.call())['handle'] for _ in range(4)]
        self.assertEqual((await self.call())['status'],'busy');self.assertEqual(len(self.wire.audit),8)
        await self.call('release',{'handle':handles.pop()});self.normal.camera.pending=1
        try:self.assertEqual((await self.call())['status'],'busy')
        finally:self.normal.camera.pending=0
    async def test_api_skew_uid_mismatch_and_disabled_never_request_frame(self):
        self.wire.api=45
        with self.assertRaises(rpc.RpcError):await self.call()
        self.assertEqual(len(self.wire.audit),1)
        self.normal.camera.config['uid']+=1
        with self.assertRaises(rpc.RpcError):await self.call()
        self.assertEqual(len(self.wire.audit),1)
        saved=self.normal.camera;self.normal.camera=None
        try:
            with self.assertRaises(rpc.RpcError) as error:await self.call()
            self.assertEqual(error.exception.code,-32004)
        finally:self.normal.camera=saved
    async def test_bad_headers_partial_tail_extra_tail_and_refusal_retain_nothing(self):
        self.wire.fragment=4096  # Test malformed framing, independent of the separate slow-reader deadline test.
        for changes in ({'id':99},{'header':{**header(),'bytes':20}},{'pixels':PIXELS[:-1]},
                        {'pixels':PIXELS+b'x'},{'raw_header':b'x'*4097+b'\n'},
                        {'raw_header':b'{"jsonrpc":"2.0","id":2,"id":2,"result":{}}\n'},{'refuse':True}):
            saved={k:getattr(self.wire,k) for k in changes}
            for k,v in changes.items():setattr(self.wire,k,v)
            try:
                with self.subTest(changes=tuple(changes)):
                    with self.assertRaises(rpc.RpcError):await self.call()
                self.assertFalse(self.normal.camera.entries);self.assertEqual(self.normal.camera.pending,0)
            finally:
                for k,v in saved.items():setattr(self.wire,k,v)
    async def test_silent_timeout_and_shutdown_cancel_release_resources(self):
        self.wire.silent=True
        with patch.object(svc,'DEADLINE',.05):
            self.assertEqual((await self.call())['status'],'timeout')
        self.assertEqual(self.normal.camera.pending,0);self.assertFalse(self.normal.camera.entries)
        task=asyncio.create_task(self.normal.camera.acquire())
        await asyncio.sleep(.01);self.assertEqual(self.normal.camera.pending,1);task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        self.assertEqual(self.normal.camera.pending,0)
        self.wire.silent=False;await self.call();await self.normal.stop();self.assertFalse(self.normal.camera.entries)
    async def test_zero_timestamp_is_reported_and_config_does_not_change_permissions(self):
        self.wire.header['captured_at_unix_us']=0
        h=(await self.call())['handle'];v=await self.call('metadata',{'handle':h,'field':'captured_at_unix_us'})
        self.assertEqual((v['status'],v['value']),('ok','0'))
        config=self.root/'camera.json';config.write_text(json.dumps(source(self.wire.path)));config.chmod(0o600)
        self.assertEqual(svc.load_source(config,'mediad'),source(self.wire.path))
        config.chmod(0o644)
        with self.assertRaises(ValueError):svc.load_source(config,'mediad')
        self.assertEqual(config.stat().st_mode&0o777,0o644)
        caps=await self.client.call('microduck.capabilities');self.assertEqual(caps['read_only_adapters']['camera']['max_frame_bytes'],svc.MAX_BYTES)


@unittest.skipUnless(sys.platform=='linux' and os.environ.get('SMALLVM_MICRODUCK_BINARY'),'Verified local native VM required')
class CameraNative(CameraUnix):
    async def asyncSetUp(self):
        await super().asyncSetUp()
        spec=importlib.util.spec_from_file_location('camera_vm_helpers',ROOT/'tests/test_linux_microduck_vm.py')
        self.vm=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.vm)
        data=self.root/'program';data.mkdir(mode=0o700)
        self.runtime=await asyncio.to_thread(self.vm.Runtime,Path(os.environ['SMALLVM_MICRODUCK_BINARY']),data,self.normal.path)
    async def asyncTearDown(self):
        await asyncio.to_thread(self.runtime.stop)
        self.assertEqual(self.runtime.process.returncode,0);log=self.runtime.log_path.read_text()
        self.assertNotIn('AddressSanitizer',log);self.assertNotIn('runtime error:',log)
        await super().asyncTearDown()
    async def primitive(self,name,args=(),error=None,command=False):return await asyncio.to_thread(self.runtime.primitive,name,args,error,command)
    async def execute(self,p):return await asyncio.to_thread(self.runtime.execute,p.finish())
    async def call(self,name='capture',p=None):
        job=await self.primitive('begin',(svc.PREFIX+name,json.dumps(p or {}),False));end=asyncio.get_running_loop().time()+4
        while await self.primitive('status',(job,))=='pending':
            self.assertLess(asyncio.get_running_loop().time(),end);await asyncio.sleep(.005)
        raw=await self.primitive('result',(job,));await self.primitive('release',(job,),command=True)
        value=json.loads(raw)
        if 'error' in value:raise rpc.RpcError(value['error']['code'],'Fixture gateway error')
        return value['result']
    async def typed(self,value):
        P,V=self.vm.Program,self.vm.Var
        await self.execute(P().call('cameraReading',(json.dumps({'jsonrpc':'2.0','id':1,'result':value}),)).op(7,3).push(0))
        return [await self.execute(P().push(i).push(V(3)).op(81,2)) for i in range(1,5)]
    async def test_native_exact128_raw_zero_and_unavailable_extraction(self):
        capture=await self.typed(await self.call());self.assertEqual(capture[0],'ok');h=capture[1]
        for field in svc.FIELDS:
            expected=str(header()[field]) if field=='captured_at_unix_us' else header()[field]
            self.assertEqual(await self.typed(await self.call('metadata',{'handle':h,'field':field})),['ok',expected,svc.FIELDS[field],'local_ipc'])
        self.assertEqual(await self.typed(await self.call('pixel',{'handle':h,'x':1,'y':1,'channel':'y'})),['ok',0,'luma_raw8','local_ipc'])
        self.assertEqual((await self.typed(await self.call('pixel',{'handle':h,'x':5,'y':1,'channel':'y'})))[:2],['out_of_range',''])
        await self.primitive('readingValue',(self.vm.Var(3),),error=32)
    async def test_native_strict_metadata_pixel_envelopes_and_unsupported_route(self):
        good=svc.result('camera_pixel','ok',x=1,y=1,channel='y',unit='luma_raw8',value=0)
        for change in ({'source':'tofd'},{'simulation':True},{'physical_hardware_verified':True},{'physical_movement_enabled':True},
                       {'value':True},{'value':256},{'x':0},{'unit':'lux'},{'channel':'rgb'},{'kind':'depth_reading'}):
            self.assertNotEqual((await self.typed({**good,**change}))[0],'ok')
        for value in (str(2**128),'01','-1','1e6','',True):
            self.assertNotEqual((await self.typed(svc.result('camera_metadata','ok',field='captured_at_unix_us',unit='us_unix128',value=value)))[0],'ok')
        for method,p in [('media.frame',{}),(svc.PREFIX+'capture',{'path':'/run/mediad.sock'}),
                         (svc.PREFIX+'pixel',{'handle':'a'*32,'x':0,'y':1,'channel':'y'})]:
            await self.primitive('begin',(method,json.dumps(p),False),error=32)
        self.assertFalse(self.wire.audit)
    async def test_native_reading_record_survives_moving_gc(self):
        P,V=self.vm.Program,self.vm.Var
        await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0));start=len(self.runtime.wire.events)
        value=svc.result('camera_metadata','ok',field='captured_at_unix_us',unit='us_unix128',value=str(2**128-1))
        self.assertEqual(await self.typed(value),['ok',str(2**128-1),'us_unix128','local_ipc'])
        self.assertTrue(any(k==20 and i==255 and b'GC took' in b for k,i,b in self.runtime.wire.events[start:]))


if __name__=='__main__':unittest.main(verbosity=2)
