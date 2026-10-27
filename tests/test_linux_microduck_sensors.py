"""Source-shaped fake ToF/pad streams, actual native jobs; never physical input."""
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
package=types.ModuleType('sensor_lab_services'); package.__path__=[str(ROOT/'linux/microduck')]
sys.modules[package.__name__]=package
sensor=importlib.import_module(package.__name__+'.sensor_simulator')
rpc=importlib.import_module(package.__name__+'.protocol')
gateway=importlib.import_module(package.__name__+'.gateway')


def request(kind='tof', params=None):
    return {'jsonrpc':'2.0','id':1,'method':sensor.PREFIX+kind,'params':params if params is not None else {'row':1,'col':1},'confirmed':False}


class SensorProtocol(unittest.TestCase):
    def test_local_exact_selectors_and_types(self):
        for params in ({'row':1,'col':1},{'row':8,'col':8}):
            self.assertEqual(sensor.validate_sensor(request(params=params)),('tof',params))
        for kind in ('axis','button'):
            self.assertEqual(sensor.validate_sensor(request(kind,{'code':65535})),(kind,{'code':65535}))
        for params in ({'row':0,'col':1},{'row':1,'col':9},{'row':True,'col':1},{'row':1.0,'col':1},{'row':1},{'row':1,'col':1,'extra':0}):
            with self.assertRaises(rpc.RpcError): sensor.validate_sensor(request(params=params))
        for code in (-1,65536,True,1.0):
            with self.assertRaises(rpc.RpcError): sensor.validate_sensor(request('axis',{'code':code}))
        for patch in ({'id':True},{'confirmed':'yes'},{'method':'tof.stream'},{'method':'robot.move'},{'extra':1}):
            with self.assertRaises(rpc.RpcError): sensor.validate_sensor({**request(),**patch})

    def test_duplicate_nonfinite_and_batches_rejected(self):
        for raw in (b'{"jsonrpc":"2.0","id":1,"id":2}\n',b'{"x":NaN}\n'):
            with self.assertRaises(rpc.RpcError): rpc.decode(raw,16384)
        with self.assertRaises(rpc.RpcError): sensor.validate_sensor([])

    def test_library_is_explicit_simulation_with_only_three_read_wrappers(self):
        library=(ROOT/'linux/microduck/Sensor_Simulation.ubl').read_text()
        self.assertIn('SIMULATION ONLY',library)
        for kind in ('tof','axis','button'): self.assertIn(sensor.PREFIX+kind,library)
        self.assertEqual(library.count('microduckRequest '),9)
        self.assertNotIn('robot.move',library)
        self.assertNotIn('true)',library)


class SensorSamples(unittest.TestCase):
    def test_tof_row_major_range_no_target_failed_negative_and_raw_status(self):
        description,reports=sensor.fixture('tof','normal'); frame=reports[0]['params']
        expected=[('ok',1000),('no_target',None),('unusable',None),('unusable',None)]
        for col,(status,value) in enumerate(expected,1):
            sample=sensor.tof_result(description,frame,1,col)
            self.assertEqual((sample['status'],sample['value']),(status,value))
        self.assertEqual(sensor.tof_result(description,frame,8,8)['value'],1063)
        frame['distance_mm'][0]=500; frame['status'][0]=9
        self.assertEqual(sensor.tof_result(description,frame,1,1)['value'],500)
        self.assertEqual(sensor.tof_result(description,frame,1,1)['seq'],str(2**63+7))

    def test_tof_absent_refused_waiting_and_old_clock(self):
        description,reports=sensor.fixture('tof','normal')
        self.assertEqual(sensor.tof_result({'accepted':False},None,1,1)['status'],'refused')
        self.assertEqual(sensor.tof_result({'accepted':True},None,1,1)['status'],'absent')
        self.assertEqual(sensor.tof_result(description,None,1,1)['status'],'waiting')
        frame=reports[0]['params']; del frame['t_ns']
        self.assertEqual(sensor.tof_result(description,frame,1,1)['t_ns'],'0')

    def test_tof_invalid_geometry_vector_integer_status_and_counter_fail_closed(self):
        description,reports=sensor.fixture('tof','normal'); frame=reports[0]['params']
        for patch in ({'rows':7},{'cols':True},{'distance_mm':[1]*63},{'distance_mm':[False]*64},{'distance_mm':[32768]*64},{'status':[256]*64},{'status':[5]*63},{'seq':-1},{'at_us':2**64},{'t_ns':1.0}):
            with self.assertRaises(rpc.RpcError): sensor.tof_result(description,{**frame,**patch},1,1)

    def test_raw_axis_ranges_and_repeat_button_preserve_signed_clock_and_u64(self):
        _,reports=sensor.fixture('pad','normal'); device=sensor.device_report(reports[0]['params']['device']); frame=reports[1]['params']
        axis=sensor.pad_result(device,frame,'axis',0)
        self.assertEqual((axis['value'],axis['min'],axis['max']),(1583,-32768,32767))
        self.assertEqual(axis['since_us'],'-25'); self.assertEqual(axis['seq'],str(2**63+3))
        button=sensor.pad_result(device,frame,'button',304)
        self.assertIs(button['value'],True); self.assertEqual(button['raw_value'],2)
        frame['events'][1]['value']=0
        self.assertIs(sensor.pad_result(device,frame,'button',304)['value'],False)

    def test_axis_signed32_is_not_coerced_to_vm_signed31(self):
        _,reports=sensor.fixture('pad','normal'); device=reports[0]['params']['device']; frame=reports[1]['params']
        device['axes'][0].update(min=-2**31,max=2**31-1)
        frame['events'][0]['value']=2**31-1
        self.assertEqual(sensor.pad_result(sensor.device_report(device),frame,'axis',0)['value'],2**31-1)

    def test_no_event_unknown_code_and_drops_are_never_zero_or_held(self):
        _,reports=sensor.fixture('pad','normal'); device=reports[0]['params']['device']; frame=reports[1]['params']
        self.assertEqual(sensor.pad_result(device,frame,'axis',1)['status'],'unsupported')
        for patch,status in [({'events':[]},'no_event'),({'after_drop':True},'dropped'),({'socket_dropped':1},'dropped')]:
            result=sensor.pad_result(device,{**frame,**patch},'axis',0)
            self.assertEqual(result['status'],status); self.assertIsNone(result['value'])

    def test_invalid_pad_device_and_events_fail_closed(self):
        _,reports=sensor.fixture('pad','normal'); device=reports[0]['params']['device']; frame=reports[1]['params']
        for patch in ({'seq':True},{'since_us':2**63},{'socket_dropped':-1},{'after_drop':1},{'events':[{}]},{'events':frame['events']*65}):
            with self.assertRaises(rpc.RpcError): sensor.pad_result(device,{**frame,**patch},'axis',0)
        for key,value in [('max',-32769),('min',True),('value',40000)]:
            bad=copy.deepcopy(device);bad['axes'][0][key]=value
            with self.assertRaises(rpc.RpcError): sensor.device_report(bad)
        bad=copy.deepcopy(device);bad['buttons']*=2
        with self.assertRaises(rpc.RpcError): sensor.device_report(bad)


@unittest.skipUnless(sys.platform=='linux','Linux private Unix sockets required')
class SensorUnixBackend(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temporary=tempfile.TemporaryDirectory(prefix='sensors-');self.base=Path(self.temporary.name)
        self.service=await sensor.SensorSimulator(self.base/'sim').start()
    async def asyncTearDown(self):
        await self.service.stop();self.temporary.cleanup()
    async def call(self,kind='tof',params=None):
        reader,writer=await rpc.connect_checked(self.service.directory/'gateway.sock',os.geteuid(),16384,True)
        try:
            writer.write(rpc.encode(request(kind,params),16384));await writer.drain()
            return await rpc.read_message(reader,16384)
        finally:
            writer.close();await writer.wait_closed()
    async def test_real_private_services_subscription_shapes_and_no_upstream_calls(self):
        with mock.patch.object(rpc.Upstream,'call',side_effect=AssertionError('ordinary upstream forbidden')):
            tof=(await self.call())['result'];axis=(await self.call('axis',{'code':0}))['result'];button=(await self.call('button',{'code':304}))['result']
        self.assertEqual((tof['value'],axis['value'],button['value']),(1000,1583,True))
        self.assertEqual(self.service.subscriptions,3)
        for sample in (tof,axis,button):
            self.assertTrue(sample['simulation']);self.assertFalse(sample['physical_movement_enabled'])
            self.assertLessEqual(len(rpc.encode({'jsonrpc':'2.0','id':0x7fffffff,'result':sample},16384)),760)
    async def test_absent_sensor_and_accepted_without_attached_pad(self):
        self.service.profile='absent'
        self.assertEqual((await self.call())['result']['status'],'absent')
        self.assertEqual((await self.call('axis',{'code':0}))['result']['status'],'waiting')
    async def test_detached_and_frame_before_attachment(self):
        original=sensor.fixture
        def detached(service,profile):
            description,reports=original(service,profile)
            return description,[{'jsonrpc':'2.0','method':'pad.report','params':{'report':'detached','why':'SIMULATION unplugged'}}]
        with mock.patch.object(sensor,'fixture',side_effect=detached):
            self.assertEqual((await self.call('button',{'code':304}))['result']['status'],'detached')
        def no_device(service,profile):
            description,reports=original(service,profile);return description,reports[1:]
        with mock.patch.object(sensor,'fixture',side_effect=no_device):
            self.assertEqual((await self.call('axis',{'code':0}))['error']['code'],-32011)
    async def test_notification_limit_and_malformed_stream(self):
        original=sensor.fixture
        def many(service,profile):
            description,reports=original(service,profile)
            return description,[{'jsonrpc':'2.0','method':'pad.report','params':{'report':'imu_detached','why':'SIMULATION'}}]*17
        with mock.patch.object(sensor,'fixture',side_effect=many):
            self.assertEqual((await self.call('axis',{'code':0}))['result']['status'],'event_limit')
        def bad(service,profile):
            description,reports=original(service,profile);reports[0]['params']['rows']=9;return description,reports
        with mock.patch.object(sensor,'fixture',side_effect=bad):
            self.assertIn('error',await self.call())
    async def test_invalid_and_actual_motion_or_stream_methods_are_refused(self):
        for value in (request(params={'row':0,'col':1}),{'jsonrpc':'2.0','id':1,'method':'robot.move','params':{},'confirmed':True},{'jsonrpc':'2.0','id':1,'method':'tof.stream','params':{}}, {'jsonrpc':'2.0','id':1,'method':'robot.enable','params':{'on':True},'confirmed':True}):
            with self.assertRaises(rpc.RpcError):await self.service.gateway.dispatch(value)
        self.assertEqual(self.service.subscriptions,0)
    async def test_private_metadata_cancellation_and_owned_socket_cleanup(self):
        self.service.profile='absent'
        task=asyncio.create_task(self.service.gateway.dispatch(request('axis',{'code':0})))
        while self.service.subscriptions==0:await asyncio.sleep(.005)
        task.cancel()
        with self.assertRaises(asyncio.CancelledError):await task
        info=json.loads((self.service.directory/'sensor-simulation.json').read_text())
        self.assertTrue(info['sensor_simulation']);self.assertFalse(info['physical_movement_enabled'])
        for name in ('gateway.sock','tof.sock','pad.sock'):
            self.assertEqual((self.service.directory/name).stat().st_mode&0o777,0o600)
        await self.service.stop()
        for name in ('gateway.sock','tof.sock','pad.sock'):self.assertFalse((self.service.directory/name).exists())
        self.assertTrue((self.service.directory/'sensor-simulation.json').is_file())
    async def test_actual_cli_fictional_profile_and_clean_shutdown(self):
        directory=self.base/'cli'
        process=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/sensor_simulator.py'),'--directory',str(directory),'--fixture','absent',stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            info=json.loads(await asyncio.wait_for(process.stdout.readline(),3))
            self.assertEqual(info['pid'],process.pid);self.assertTrue(info['sensor_simulation']);self.assertFalse(info['physical_movement_enabled'])
            self.assertEqual(info['sensor_profile'],'absent')
        finally:
            if process.returncode is None:process.terminate()
            _,error=await asyncio.wait_for(process.communicate(),3)
        self.assertEqual(process.returncode,0,error.decode())
        for name in ('gateway.sock','tof.sock','pad.sock'):self.assertFalse((directory/name).exists())


SOURCE=Path(os.environ.get('SMALLVM_UPSTREAM',ROOT.parent/'smallvm-linux-upstream'))
EXTERNAL=os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform=='linux' and struct.calcsize('P')==8 and (EXTERNAL or shutil.which('gcc') and (SOURCE/'.git').is_dir()),'native LP64 source/compiler required')
class SensorNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temporary=tempfile.TemporaryDirectory(prefix='sensor-native-');cls.base=Path(cls.temporary.name)
        if EXTERNAL:cls.binary=Path(EXTERNAL)
        else:
            result=subprocess.run([sys.executable,str(ROOT/'linux/arm64/build.py'),'--upstream',str(SOURCE),'--output',str(cls.base/'build'),'--sanitize'],capture_output=True,text=True,timeout=120)
            if result.returncode:raise AssertionError(result.stdout+result.stderr)
            cls.binary=cls.base/'build/smallvm'
        spec=importlib.util.spec_from_file_location('sensor_vm_helpers',ROOT/'tests/test_linux_microduck_vm.py')
        cls.helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.helpers)
    @classmethod
    def tearDownClass(cls):cls.temporary.cleanup()
    async def asyncSetUp(self):
        self.work=Path(tempfile.mkdtemp(dir=self.base));self.service=await sensor.SensorSimulator(self.work/'sim').start();self.runtime=None
    async def asyncTearDown(self):
        if self.runtime:
            await asyncio.to_thread(self.runtime.stop)
            log=self.runtime.log_path.read_text()
            self.assertEqual(self.runtime.process.returncode,0,log);self.assertNotIn('AddressSanitizer',log);self.assertNotIn('runtime error:',log)
        await self.service.stop()
    async def start_vm(self,path=None):
        data=self.work/'programs';data.mkdir(mode=0o700)
        self.runtime=await asyncio.to_thread(self.helpers.Runtime,self.binary,data,path or self.service.directory/'gateway.sock')
    async def primitive(self,name,args=(),error=None,command=False):return await asyncio.to_thread(self.runtime.primitive,name,args,error,command)
    async def call(self,kind,params):
        job=await self.primitive('begin',(sensor.PREFIX+kind,json.dumps(params),False))
        deadline=asyncio.get_running_loop().time()+4
        while await self.primitive('status',(job,))=='pending':
            self.assertLess(asyncio.get_running_loop().time(),deadline);await asyncio.sleep(.01)
        result=json.loads(await self.primitive('result',(job,)))
        await self.primitive('release',(job,),command=True)
        return result
    async def test_real_vm_depth_axis_button_and_full_precision_strings(self):
        await self.start_vm()
        tof=(await self.call('tof',{'row':8,'col':8}))['result'];axis=(await self.call('axis',{'code':0}))['result'];button=(await self.call('button',{'code':304}))['result']
        self.assertEqual((tof['value'],axis['value'],button['value']),(1063,1583,True));self.assertEqual(tof['seq'],str(2**63+7));self.assertEqual(axis['since_us'],'-25')
        self.assertFalse(tof['physical_movement_enabled'])
    async def test_native_exact_bounds_and_real_stream_rejected_before_io(self):
        await self.start_vm()
        values=[('tof',{'row':0,'col':1}),('tof',{'row':1,'col':9}),('tof',{'row':True,'col':1}),('tof',{'row':1.0,'col':1}),('tof',{'row':1}),('axis',{'code':-1}),('button',{'code':65536}),('button',{'code':True}),('axis',{'code':0,'extra':0})]
        for kind,params in values:await self.primitive('begin',(sensor.PREFIX+kind,json.dumps(params),False),error=32)
        for name in ('tof.stream','pad.input','robot.move'):await self.primitive('begin',(name,'{}',True),error=32)
        await self.primitive('begin',(sensor.PREFIX+'tof','{"row":1,"row":2,"col":1}',False),error=32)
        self.assertEqual(self.service.subscriptions,0)
    async def test_native_absent_and_no_target_are_unknown_not_zero(self):
        await self.start_vm()
        result=(await self.call('tof',{'row':1,'col':2}))['result'];self.assertEqual(result['status'],'no_target');self.assertIsNone(result['value'])
        self.service.profile='absent'
        result=(await self.call('tof',{'row':1,'col':1}))['result'];self.assertEqual(result['status'],'absent');self.assertIsNone(result['value'])
    async def test_ordinary_gateway_rejects_local_sensor_prefix(self):
        ordinary=await gateway.Gateway({'robot':{'path':str(self.service.directory/'robot.sock'),'uid':os.geteuid()}}).start(self.work/'ordinary.sock')
        try:
            await self.start_vm(ordinary.path)
            self.assertEqual((await self.call('axis',{'code':0}))['error']['code'],-32601)
            self.assertEqual(self.service.subscriptions,0)
        finally:await ordinary.stop()


if __name__=='__main__':unittest.main(verbosity=2)
