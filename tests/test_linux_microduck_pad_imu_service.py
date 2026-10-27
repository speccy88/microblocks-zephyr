"""Normal padd IMU wrappers/VM with fictional services, never a physical device."""
# SPDX-License-Identifier: MIT
import asyncio
import copy
import importlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile
import types
import unittest
from unittest import mock

ROOT=Path(__file__).resolve().parents[1]
package=types.ModuleType('pad_imu_service_tests');package.__path__=[str(ROOT/'linux/microduck')];sys.modules[package.__name__]=package
svc=importlib.import_module(package.__name__+'.pad_imu_service');core=svc.core
rpc=importlib.import_module(package.__name__+'.protocol')
gateway=importlib.import_module(package.__name__+'.gateway')
client=importlib.import_module(package.__name__+'.client')
def request(name='capture',p=None):return {'jsonrpc':'2.0','id':1,'method':svc.PREFIX+name,'params':p or {},'confirmed':False}
def select(handle,field='accel_mg',sample=1,component=1):return {'handle':handle,'field':field,'sample':sample,'component':component}
def source(path,uid=None):return {'version':1,'daemon':'padd','path':str(path),'uid':os.geteuid() if uid is None else uid}
def state(profile='normal'):
    _,reports=core.fixture(profile);return {'device':core.validate_device(reports[0]['device']),'samples':core.validate_batch(reports[1])}
async def normal_gateway(directory,path,uid=None):
    directory.mkdir(mode=0o700);p=directory/'pad-imu.json';p.write_text(json.dumps(source(path,uid)));p.chmod(0o600)
    return await gateway.Gateway({},pad_imu=svc.load_source(p)).start(directory/'gateway.sock')

class PadImuServiceProtocol(unittest.TestCase):
    def test_explicit_padd_source_and_closed_parameters(self):
        good={'version':1,'daemon':'padd','path':'/run/padd.sock','uid':1000};self.assertEqual(svc.validate_source(good),good)
        for delta in [{'daemon':'robotd'},{'uid':True},{'path':'relative'},{'version':2}]:
            with self.assertRaises(ValueError):svc.validate_source({**good,**delta})
        for q in [request(p={'endpoint':'any'}),request('capturePad'),request('read',select('a'*32,'sample_count',2)),request('read',select('a'*32,component=4)),request('read',select('A'*32)),{**request(),'confirmed':1}]:
            with self.assertRaises(rpc.RpcError):svc.validate(q)
    def test_same_reviewed_batch_values_with_strict_normal_markers(self):
        self.assertEqual(len(svc.FIELDS),13);s=state()
        self.assertEqual(core.sample_reading(s,'accel_mg',1,2)['value'],-1000)
        for field in svc.FIELDS:
            normal=core.sample_reading(s,field,1,1,svc.result);old=core.sample_reading(s,field,1,1)
            self.assertEqual(normal['value'],old['value']);self.assertEqual(normal['origin'],'local_ipc');self.assertEqual(normal['source'],'padd');self.assertNotIn('simulation',normal);self.assertTrue(old['simulation'])
    def test_library_has_all_selector_helpers_without_simulation_calls(self):
        text=(ROOT/'linux/microduck/Pad_IMU.ubl').read_text(encoding='utf-8')
        self.assertIn('[microduck:padImuReading]',text);self.assertNotIn('microduck.imuSim.',text);self.assertNotIn(' true)',text)
        for field in svc.FIELDS:self.assertIn("'"+field+"'",text)
        self.assertIn('SIMULATION ONLY',(ROOT/'linux/microduck/Pad_IMU_Simulation.ubl').read_text())

@unittest.skipUnless(sys.platform=='linux','Linux peer credentials required')
class PadImuServiceUnix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='pimu-read-');self.base=Path(self.temp.name);self.fixture=await core.ImuSimulator(self.base/'sim').start();self.normal=await normal_gateway(self.base/'normal',self.fixture.directory/'pad.sock')
    async def asyncTearDown(self):
        await self.normal.stop();await self.fixture.stop();self.temp.cleanup()
    async def capture(self):return (await self.normal.dispatch(request()))[0]
    async def test_immutable_batch_all_queries_one_first_request_subscription(self):
        self.normal.pad_imu.clock=lambda:0.;v=await self.capture();self.assertEqual(v['sample_count'],3);handle=v['handle'];self.assertEqual(self.fixture.subscriptions,1)
        self.fixture.imu_profile='dropped'
        for field,(unit,components) in svc.FIELDS.items():
            for component in range(1,components+1):
                value=(await self.normal.dispatch(request('read',select(handle,field,component=component))))[0];self.assertEqual(value['status'],'ok',field);self.assertEqual(value['unit'],unit);self.assertEqual(value['origin'],'local_ipc');self.assertNotIn('simulation',value)
        self.assertEqual(self.fixture.subscriptions,1);self.assertEqual(self.fixture.action_count,0)
        caps=(await self.normal.dispatch({'jsonrpc':'2.0','id':1,'method':'microduck.capabilities','params':{}}))[0];self.assertEqual(set(caps['methods']),svc.METHODS);self.assertEqual(caps['allowed_mutations'],[])
    async def test_profile_availability_and_event_cap_are_explicit(self):
        for profile,expected in [('no_imu','not_reported'),('waiting','waiting'),('detached','detached'),('refused','refused'),('dropped','dropped'),('bad_order','dropped')]:
            self.fixture.imu_profile=profile;v=await self.capture();self.assertEqual(v['status'],expected,profile);self.assertNotIn('handle',v)
        _,notes=core.wire.fixture('pad','normal');reports=[notes[1]['params']]*16
        with mock.patch.object(core,'fixture',return_value=({'accepted':True},reports)):
            self.assertEqual((await self.capture())['status'],'event_limit')
    async def test_malformed_oversized_and_batch_before_attachment_fail_closed(self):
        self.fixture.imu_profile='oversized'
        with self.assertRaises(rpc.RpcError):await self.capture()
        ack,reports=core.fixture('normal')
        for payload in [[reports[1]],[{**reports[0],'device':{**reports[0]['device'],'gyro_per_dps':-1}},reports[1]]]:
            with mock.patch.object(core,'fixture',return_value=(ack,payload)):
                with self.assertRaises(rpc.RpcError):await self.capture()
        self.assertEqual(self.normal.pad_imu.pending,0);self.assertEqual(self.normal.pad_imu.entries,{})
    async def test_untrusted_source_uid_and_mode_refuse_before_write(self):
        self.normal.pad_imu.config['uid']=os.geteuid()+1
        with self.assertRaises(rpc.RpcError):await self.capture()
        self.normal.pad_imu.config['uid']=os.geteuid();(self.fixture.directory/'pad.sock').chmod(0o666)
        with self.assertRaises(rpc.RpcError):await self.capture()
        self.assertEqual(self.fixture.subscriptions,0)
    async def test_capacity_expiry_release_regression_and_no_read_renewal(self):
        # Isolate store lifetime from the independent350ms transport deadline.
        captured=(svc.result('pad_imu_capture','ok',sample_count=3),state())
        with mock.patch.object(self.normal.pad_imu,'read_source',new=mock.AsyncMock(return_value=captured)):
            clock=[10.];self.normal.pad_imu.clock=lambda:clock[0];values=[await self.capture() for _ in range(4)];self.assertEqual((await self.capture())['status'],'busy')
            handle=values[0]['handle'];clock[0]=14.;self.assertEqual(self.normal.pad_imu.read(handle,'sample_count',1,1)['value'],3)
            clock[0]=15.;self.assertEqual(self.normal.pad_imu.read(handle,'sample_count',1,1)['status'],'expired_or_unknown')
            handle=(await self.capture())['handle'];self.normal.pad_imu.release(handle);self.assertEqual(self.normal.pad_imu.release(handle)['status'],'not_retained')
            handle=(await self.capture())['handle'];clock[0]=14.;self.assertEqual(self.normal.pad_imu.read(handle,'seq',1,1)['status'],'expired_or_unknown')
    async def test_pending_capacity_and_cancel_closes_readers(self):
        self.fixture.imu_profile='waiting';tasks=[asyncio.create_task(self.capture()) for _ in range(4)]
        for _ in range(100):
            if self.normal.pad_imu.pending==4:break
            await asyncio.sleep(.002)
        self.assertEqual((await self.capture())['status'],'busy')
        for t in tasks:t.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        for _ in range(100):
            if not self.fixture.active:break
            await asyncio.sleep(.002)
        self.assertEqual(self.normal.pad_imu.pending,0);self.assertEqual(self.fixture.active,0)
    async def test_python_client_guards_and_disabled_store(self):
        c=client.Client(self.base/'normal/gateway.sock');v=await c.call(svc.PREFIX+'capture');self.assertEqual((await c.call(svc.PREFIX+'read',select(v['handle'],'sample_count')))['value'],3)
        with self.assertRaises(rpc.RpcError):await c.call('pad.input')
        self.normal.pad_imu=None
        with self.assertRaises(rpc.RpcError) as e:await c.call(svc.PREFIX+'capture')
        self.assertEqual(e.exception.code,-32004)
    async def test_private_config_symlink_and_preack_timeout(self):
        p=self.base/'normal/pad-imu.json';p.chmod(0o644)
        with self.assertRaises(ValueError):svc.load_source(p)
        p.chmod(0o600);link=self.base/'normal/link';link.symlink_to(p)
        with self.assertRaises(OSError):svc.load_source(link)
        closed=asyncio.Event()
        async def silent(reader,writer):
            try:await reader.read()
            finally:writer.close();await writer.wait_closed();closed.set()
        path=self.base/'silent.sock';server=await asyncio.start_unix_server(silent,path=str(path));path.chmod(0o600)
        try:
            v,empty=await core.capture_source(path,os.geteuid(),envelope=svc.result);self.assertEqual(v['status'],'timeout');self.assertIsNone(empty);await asyncio.wait_for(closed.wait(),1)
        finally:server.close();await server.wait_closed()
    async def test_actual_gateway_cli_explicit_source(self):
        p=self.base/'normal/gateway.json';p.write_text('{"version":1,"upstreams":{}}');p.chmod(0o600)
        process=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/gateway.py'),'--config',str(p),'--pad-imu-config',str(self.base/'normal/pad-imu.json'),'--socket',str(self.base/'normal/cli.sock'),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            self.assertIn(b'gateway ready',await asyncio.wait_for(process.stdout.readline(),3));self.assertEqual((await client.Client(self.base/'normal/cli.sock').call(svc.PREFIX+'capture'))['status'],'ok')
        finally:
            if process.returncode is None:process.terminate()
            _,error=await asyncio.wait_for(process.communicate(),3)
        self.assertEqual(process.returncode,0,error.decode())
    async def test_user_fixture_cli_labels_simulation_and_cleans_sockets(self):
        root=self.base/'demo';p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/pad_imu_gateway_fixture.py'),'--directory',str(root),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            ready=json.loads(await asyncio.wait_for(p.stdout.readline(),3));self.assertTrue(ready['simulation']);self.assertFalse(ready['physical_hardware_verified']);self.assertEqual((await client.Client(Path(ready['gateway_socket'])).call(svc.PREFIX+'capture'))['status'],'ok')
        finally:
            if p.returncode is None:p.terminate()
            _,error=await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode());self.assertFalse((root/'normal/gateway.sock').exists());self.assertFalse((root/'source/pad.sock').exists())

SOURCE=Path(os.environ.get('SMALLVM_UPSTREAM',ROOT.parent/'smallvm-linux-upstream'));EXTERNAL=os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform=='linux' and struct.calcsize('P')==8 and (EXTERNAL or shutil.which('gcc') and (SOURCE/'.git').is_dir()),'native LP64 compiler/source required')
class PadImuServiceNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='pimu-read-vm-');cls.base=Path(cls.temp.name)
        if EXTERNAL:cls.binary=Path(EXTERNAL)
        else:
            p=subprocess.run([sys.executable,str(ROOT/'linux/arm64/build.py'),'--upstream',str(SOURCE),'--output',str(cls.base/'build'),'--sanitize'],capture_output=True,text=True,timeout=120)
            if p.returncode:raise AssertionError(p.stdout+p.stderr)
            cls.binary=cls.base/'build/smallvm'
        spec=importlib.util.spec_from_file_location('pimu_service_vm_helpers',ROOT/'tests/test_linux_microduck_vm.py');cls.helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.helpers)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    async def asyncSetUp(self):
        self.work=Path(tempfile.mkdtemp(dir=self.base));self.fixture=await core.ImuSimulator(self.work/'sim').start();self.normal=await normal_gateway(self.work/'normal',self.fixture.directory/'pad.sock');self.normal.pad_imu.clock=lambda:0.
        data=self.work/'programs';data.mkdir(mode=0o700);self.runtime=await asyncio.to_thread(self.helpers.Runtime,self.binary,data,self.work/'normal/gateway.sock')
    async def asyncTearDown(self):
        await asyncio.to_thread(self.runtime.stop);log=self.runtime.log_path.read_text();self.assertEqual(self.runtime.process.returncode,0,log);self.assertNotIn('AddressSanitizer',log);self.assertNotIn('runtime error:',log);await self.normal.stop();await self.fixture.stop()
    async def primitive(self,name,args=(),error=None,command=False):return await asyncio.to_thread(self.runtime.primitive,name,args,error,command)
    async def execute(self,p):return await asyncio.to_thread(self.runtime.execute,p.finish())
    async def call(self,name='capture',p=None):
        job=await self.primitive('begin',(svc.PREFIX+name,json.dumps(p or {}),False));deadline=asyncio.get_running_loop().time()+4
        while await self.primitive('status',(job,))=='pending':self.assertLess(asyncio.get_running_loop().time(),deadline);await asyncio.sleep(.005)
        value=await self.primitive('result',(job,));await self.primitive('release',(job,),command=True);return value
    async def typed(self,reply,primitive='padImuReading'):
        P,V=self.helpers.Program,self.helpers.Var;await self.execute(P().call(primitive,(reply,)).op(7,3).push(0));return [await self.execute(P().push(i).push(V(3)).op(81,2)) for i in range(1,5)]
    async def test_all_selectors_and_samples_one_subscription_actual_vm(self):
        capture=await self.typed(await self.call());self.assertEqual(capture[0],'ok');handle=capture[1]
        for field,(unit,components) in svc.FIELDS.items():
            for sample in range(1,2 if field in ('sample_count','accel_per_g','gyro_per_dps','accel_max','gyro_max') else 4):
                for component in range(1,components+1):
                    expected=core.sample_reading(state(),field,sample,component)['value'];self.assertEqual(await self.typed(await self.call('read',select(handle,field,sample,component))),['ok',expected,unit,'local_ipc'],(field,sample,component))
        self.assertEqual(self.fixture.subscriptions,1);self.assertEqual(self.fixture.action_count,0)
    async def test_native_unscaled_absence_loss_and_unavailable_extraction(self):
        self.fixture.imu_profile='unscaled';handle=(await self.typed(await self.call()))[1];self.assertEqual(await self.typed(await self.call('read',select(handle,'accel_raw'))),['ok',0,'raw','local_ipc']);self.assertEqual((await self.typed(await self.call('read',select(handle))))[0],'not_reported');await self.primitive('readingValue',(self.helpers.Var(3),),error=32);await self.call('release',{'handle':handle})
        for profile,expected in [('dropped','dropped'),('no_imu','not_reported'),('waiting','waiting'),('detached','detached'),('refused','refused')]:
            self.fixture.imu_profile=profile;self.assertEqual((await self.typed(await self.call()))[0],expected)
    async def test_native_exact_u64_backward_wall_time_and_signed_scaling(self):
        ack,reports=core.fixture('normal');reports[1]['samples'][0]['at_us']=2**64-1;reports[1]['samples'][1]['at_us']=0;reports[1]['samples'][2]['seq']=2**63+2
        with mock.patch.object(core,'fixture',return_value=(ack,reports)):handle=(await self.typed(await self.call()))[1]
        for field,sample,value in [('seq',1,str(2**63)),('at_us',1,str(2**64-1)),('at_us',2,'0'),('gyro_mdps',1,1000)]:self.assertEqual((await self.typed(await self.call('read',select(handle,field,sample))))[1],value)
        self.assertEqual((await self.typed(await self.call('read',select(handle,'gyro_mdps',1,3))))[1],-500)
        await self.call('release',{'handle':handle});self.assertEqual((await self.typed(await self.call('read',select(handle))))[0],'expired_or_unknown')
    async def test_native_sources_markers_bounds_and_disabled_adapter(self):
        good=core.sample_reading(state(),'accel_mg',1,1,svc.result)
        for delta in [{'source':'tofd'},{'source':'robotd'},{'simulation':False},{'simulation':True},{'physical_hardware_verified':True},{'value':True},{'unit':'raw'},{'component':4},{'sample':33}]:
            self.assertNotEqual((await self.typed(json.dumps({'jsonrpc':'2.0','id':1,'result':{**good,**delta}})))[0],'ok')
        for primitive in ('imuSample','headImuReading','gamepadReading','robotReading'):
            self.assertNotEqual((await self.typed(json.dumps({'jsonrpc':'2.0','id':1,'result':good}),primitive))[0],'ok')
        for p in [select('a'*32,'sample_count',2),select('a'*32,component=4)]:await self.primitive('begin',(svc.PREFIX+'read',json.dumps(p),False),error=32)
        self.normal.pad_imu=None;self.assertEqual((await self.typed(await self.call()))[0],'error')
    async def test_native_exact_counter_survives_actual_compacting_gc(self):
        good=core.sample_reading(state(),'seq',1,1,svc.result);reply=json.dumps({'jsonrpc':'2.0','id':1,'result':good});P,V=self.helpers.Program,self.helpers.Var;events=self.runtime.wire.events
        await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0));start=len(events);self.assertEqual((await self.typed(reply))[1],str(2**63));self.assertTrue(any(k==20 and i==255 and b'GC took' in b for k,i,b in events[start:]));self.assertEqual(await self.primitive('readingValue',(V(3),)),str(2**63))

if __name__=='__main__':unittest.main(verbosity=2)
