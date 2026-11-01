"""API45 control packet previews and typed state; every robot service is fictional."""
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

ROOT=Path(__file__).resolve().parents[1];package=types.ModuleType('robot_lab_services');package.__path__=[str(ROOT/'linux/microduck')];sys.modules[package.__name__]=package
robot=importlib.import_module(package.__name__+'.robot_simulator');telemetry=importlib.import_module(package.__name__+'.robot_telemetry');rpc=importlib.import_module(package.__name__+'.protocol')
PREVIEWS={
 'robot.move':{'vx_mm_s':125,'vy_mm_s':-50,'vyaw_mrad_s':300},
 'robot.head':{'neck_pitch_mrad':100,'head_pitch_mrad':-200,'head_yaw_mrad':300,'head_roll_mrad':0},
 'robot.look':{'x_mm':400,'y_mm':-50,'z_mm':250,'neck_pitch_mrad':100},
 'robot.stop':{},'robot.enable':{'on':False,'toggle':True},'robot.init':{},'robot.relax':{},'robot.do':{'skill':'simulation_bow'},
 'robot.pose':{'z_mm':-25,'roll_mrad':260,'pitch_mrad':-260,'active':False},'robot.mouth':{'open_permille':500},
 'robot.sound':{'tag':'chirp','hold':None},'robot.loadPolicy':{'slot':'walk','path':'/SIMULATION/walk.onnx'},'robot.setMode':{'mode':'roller'}}


def request(name,params=None,confirmed=False):return {'jsonrpc':'2.0','id':1,'method':robot.PREFIX+name,'params':{} if params is None else params,'confirmed':confirmed}
def select(handle,field,index=1,component=1):return {'handle':handle,'field':field,'index':index,'component':component}


class RobotPreviews(unittest.TestCase):
 def test_all_thirteen_mutation_families_are_recorded_without_admission_or_applied_motion(self):
  recorder=robot.PreviewRecorder(True)
  for method,args in PREVIEWS.items():
   reply=recorder.record(method,args,True);self.assertEqual(reply['status'],'recorded_not_executed');self.assertIsNone(reply['admission']);self.assertIsNone(reply['applied']);self.assertFalse(reply['physical_movement_enabled'])
   packet=recorder.audit[-1];self.assertEqual(packet['method'],method);self.assertEqual('id' not in packet,method in robot.NOTIFICATIONS)
  self.assertEqual(len(recorder.audit),13)
  self.assertEqual(recorder.audit[0]['params'],{'vx':.125,'vy':-.05,'vyaw':.3})
  self.assertEqual(recorder.audit[1]['params'],{'neck_pitch':.1,'head_pitch':-.2,'head_yaw':.3,'head_roll':0.0})
  self.assertEqual(recorder.audit[2]['params'],{'x':.4,'y':-.05,'z':.25,'neck_pitch':.1})
  self.assertEqual(recorder.audit[8]['params'],{'z':-.025,'roll':.26,'pitch':-.26,'active':False})
 def test_backend_opt_in_fresh_confirmation_and_audit_capacity(self):
  for recorder,confirmed in [(robot.PreviewRecorder(),True),(robot.PreviewRecorder(True),False),(robot.PreviewRecorder(True),1)]:
   with self.assertRaises(rpc.RpcError):recorder.record('robot.init',{},confirmed)
   self.assertEqual(recorder.audit,[])
  recorder=robot.PreviewRecorder(True)
  for _ in range(128):recorder.record('robot.stop',{},True)
  with self.assertRaises(rpc.RpcError):recorder.record('robot.stop',{},True)
  self.assertEqual(len(recorder.audit),128)
 def test_nullable_policy_resets_and_wheee_are_source_shaped(self):
  recorder=robot.PreviewRecorder(True)
  for args in ({'slot':'walk','path':None},{'slot':None,'path':None}):
   recorder.record('robot.loadPolicy',args,True);self.assertEqual(recorder.audit[-1]['params'],args)
  for held in (True,False):
   recorder.record('robot.sound',{'tag':'wheee','hold':held},True);self.assertNotIn('id',recorder.audit[-1]);self.assertIs(recorder.audit[-1]['params']['hold'],held)
 def test_invalid_bounds_boolean_types_unknown_fields_and_discovery_fail_closed(self):
  values=[('robot.move',{'vx_mm_s':301,'vy_mm_s':0,'vyaw_mrad_s':0}),('robot.head',{**PREVIEWS['robot.head'],'head_yaw_mrad':3143}),('robot.look',{**PREVIEWS['robot.look'],'x_mm':1001}),('robot.pose',{**PREVIEWS['robot.pose'],'z_mm':-26}),('robot.pose',{**PREVIEWS['robot.pose'],'active':1}),('robot.mouth',{'open_permille':True}),('robot.enable',{'on':True,'toggle':0}),('robot.do',{'skill':'unknown'}),('robot.setMode',{'mode':'fly'}),('robot.loadPolicy',{'slot':None,'path':'/SIMULATION/walk.onnx'}),('robot.loadPolicy',{'slot':'walk','path':'/etc/passwd'}),('robot.sound',{'tag':'wheee','hold':None}),('robot.stop',{'extra':1})]
  recorder=robot.PreviewRecorder(True)
  for method,args in values:
   with self.assertRaises(rpc.RpcError):recorder.record(method,args,True)
  self.assertEqual(recorder.audit,[])
 def test_request_selector_validation_and_library_defaults(self):
  for bad in (request('capture',{'hz':0}),request('reading',select('a'*32,'imu.quat',component=5)),request('reading',select('a'*32,'unknown')),request('release',{'handle':'A'*32}),{**request('model'),'id':True}):
   with self.assertRaises(rpc.RpcError):robot.validate(bad)
  library=(ROOT/'linux/microduck/Robot_Simulation.ubl').read_text();example=(ROOT/'linux/microduck/robot-simulation.ubp').read_text()
  self.assertIn('SIMULATION ONLY',library);self.assertNotIn(' confirmed _\' \'bool\' true',library)
  self.assertNotIn('microduckSimRobotPreview',example);self.assertNotIn('microduckSimMovePreview',example)


class RobotStateReadings(unittest.TestCase):
 def setUp(self):self.state=telemetry.validate_state(telemetry.fixture())
 def test_requested_applied_limits_loop_and_safety_are_distinct(self):
  cases=[('move.requested',1,1,125,'mm/s'),('move.requested',1,3,300,'mrad/s'),('move.applied',1,1,0,'mm/s'),('move.limit_count',1,1,1,'count'),('move.limited_by',1,1,'SIMULATION_fixture_limit','text'),('loop.hz',1,1,48500,'mHz'),('safety.fallen',1,1,False,'boolean'),('safety.limp',1,1,True,'boolean'),('safety.gravity',1,3,-1000000,'ppm')]
  for field,index,component,value,unit in cases:
   result=telemetry.sample(self.state,field,index,component);self.assertEqual((result['status'],result['value'],result['unit']),('ok',value,unit));self.assertIs(type(result['value']),type(value))
  self.assertEqual(telemetry.sample(self.state,'safety.gain')['status'],'not_reported')
 def test_joint_current_odom_imu_frames_and_skeleton_units(self):
  cases=[('joints',15,1,140,'mrad'),('targets',1,1,10,'mrad'),('velocities',1,1,-200,'mrad/s'),('currents_ma',1,1,0,'uA'),('currents_ma',2,1,1250,'uA'),('odom.position',1,1,0,'mm'),('odom.yaw',1,1,100,'mrad'),('imu.gyro',1,2,200,'mrad/s'),('imu.quat',1,1,1000000,'ppm'),('frames.camera.pos',1,3,300,'mm'),('frames.tof.pos',1,1,120,'mm'),('skeleton.pos',2,3,300,'mm'),('skeleton.quat',1,1,1000000,'ppm')]
  for field,index,component,value,unit in cases:
   result=telemetry.sample(self.state,field,index,component);self.assertEqual((result['value'],result['unit']),(value,unit))
  self.assertEqual(telemetry.sample(self.state,'frames.head_imu.pos')['status'],'not_reported')
 def test_exact_u64_timestamps_counters_and_legacy_clock_zero(self):
  self.assertEqual(telemetry.sample(self.state,'t_ns')['value'],str(2**63+123));self.assertEqual(telemetry.sample(self.state,'loop.missed')['value'],str(2**63+1))
  for clock in (0,None):
   state=copy.deepcopy(self.state)
   if clock is None:del state['t_ns']
   else:state['t_ns']=clock
   self.assertEqual(telemetry.sample(state,'t_ns')['status'],'not_reported')
 def test_missing_optional_fields_stay_unknown_and_present_zero_false_are_known(self):
  for name,field in [('velocities','velocities'),('currents_ma','currents_ma'),('odom','odom.position'),('imu','imu.gyro'),('frames','frames.camera.pos'),('skeleton','skeleton.pos')]:
   state=copy.deepcopy(self.state);del state[name];result=telemetry.sample(state,field);self.assertEqual(result['status'],'not_reported');self.assertIsNone(result['value']);self.assertTrue(result['unit'])
  state=copy.deepcopy(self.state);state['velocities']=[];self.assertEqual(telemetry.sample(state,'velocities')['status'],'not_reported')
  state['loop']['hz']=0.0;self.assertEqual(telemetry.sample(state,'loop.hz')['value'],0)
  state['move']['limited_by']=[];self.assertEqual(telemetry.sample(state,'move.limit_count')['value'],0)
  del state['move']['limited_by'];defaulted=telemetry.sample(state,'move.limit_count');self.assertEqual(defaulted['value'],0);self.assertIs(defaulted['source_default'],True)
  del state['safety']['picked_up'];self.assertEqual(telemetry.sample(state,'safety.picked_up')['status'],'not_reported')
 def test_nonfinite_bad_types_and_required_fields_are_invalid(self):
  for patch in ({'t':True},{'head':[0]*3},{'t_ns':2**64},{'joints':[False]},{'currents_ma':[-1]},{'imu':{'quat':[0]*3}},{'frames':{'camera':{'pos':[0]*2}}},{'skeleton':[{'quat':[0]*3}]}):
   with self.assertRaises(rpc.RpcError):telemetry.validate_state({**self.state,**patch})
  state=copy.deepcopy(self.state);state['move']['requested'][0]=float('nan')
  with self.assertRaises(rpc.RpcError):telemetry.validate_state(state)
  state=copy.deepcopy(self.state);state['safety']['fallen']=0
  with self.assertRaises(rpc.RpcError):telemetry.validate_state(state)
  with self.assertRaises(rpc.RpcError):telemetry.validate_state({**self.state,'policy':'\ud800'})
 def test_scaling_bounds_overflow_and_selector_bounds(self):
  state=copy.deepcopy(self.state);state['joints']=[1e306];self.assertEqual(telemetry.sample(telemetry.validate_state(state),'joints')['status'],'out_of_range')
  state['joints']=[-.0005];self.assertEqual(telemetry.sample(state,'joints')['value'],-1)
  for field,index,component in [('unknown',1,1),('joints',129,1),('imu.quat',1,5),('loop.hz',2,1)]:
   with self.assertRaises(rpc.RpcError):telemetry.sample(self.state,field,index,component)


@unittest.skipUnless(sys.platform=='linux','Linux verified private sockets required')
class RobotUnixBackend(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='robot-lab-');self.base=Path(self.temp.name);self.service=await robot.RobotSimulator(self.base/'sim',True).start()
 async def asyncTearDown(self):await self.service.stop();self.temp.cleanup()
 async def call(self,name,params=None,confirmed=False):
  reader,writer=await rpc.connect_checked(self.service.directory/'gateway.sock',os.geteuid(),65536,True)
  try:
   writer.write(rpc.encode(request(name,params,confirmed),8192));await writer.drain();return await rpc.read_message(reader,65536)
  finally:writer.close();await writer.wait_closed()
 async def test_all_preview_families_never_call_an_upstream_and_default_backend_is_disabled(self):
  with mock.patch.object(rpc.Upstream,'call',side_effect=AssertionError('mutation must stay internal')):
   for method,args in PREVIEWS.items():self.assertEqual((await self.call('preview',{'method':method,'args':args},True))['result']['status'],'recorded_not_executed')
  self.assertEqual(len(self.service.preview.audit),13);self.assertEqual(self.service.state_subscriptions,0)
  other=await robot.RobotSimulator(self.base/'default').start()
  try:
   with self.assertRaises(rpc.RpcError):await other.gateway.dispatch(request('preview',{'method':'robot.init','args':{}},True))
   self.assertEqual(other.preview.audit,[])
  finally:await other.stop()
 async def test_one_real_subscription_and_coherent_typed_queries_preserve_precision(self):
  capture=(await self.call('capture',{'hz':10}))['result'];handle=capture['handle'];self.assertEqual(capture['reported_api_version'],45)
  with mock.patch.object(rpc.Upstream,'call',side_effect=AssertionError('snapshot read must be local')):
   for field in telemetry.FIELDS:
    result=(await self.call('reading',select(handle,field)))['result'];self.assertTrue(result['simulation']);self.assertFalse(result['physical_movement_enabled']);self.assertLessEqual(len(rpc.encode({'jsonrpc':'2.0','id':0x7fffffff,'result':result},65536)),760)
  self.assertEqual(self.service.state_subscriptions,1)
  time_sample=(await self.call('reading',select(handle,'t_ns')))['result'];self.assertEqual(time_sample['value'],str(2**63+123))
 async def test_capacity_expiry_release_and_absence(self):
  store=self.service.gateway.state_snapshots;clock=[0.0];store.clock=lambda:clock[0]
  captures=[(await self.call('capture',{'hz':10}))['result'] for _ in range(4)]
  self.assertEqual((await self.call('capture',{'hz':10}))['result']['status'],'busy')
  self.assertEqual((await self.call('release',{'handle':captures[0]['handle']}))['result']['status'],'released')
  clock[0]=5
  self.assertEqual((await self.call('reading',select(captures[1]['handle'],'loop.hz')))['result']['status'],'expired_or_unknown')
  self.service.profile='absent';self.assertEqual((await self.call('capture',{'hz':10}))['result']['status'],'waiting')
 async def test_bad_state_notification_is_an_error_and_retains_no_snapshot(self):
  with mock.patch.object(robot,'state_fixture',return_value={'t':0}):self.assertIn('error',await self.call('capture',{'hz':10}))
  self.assertEqual(self.service.gateway.state_snapshots.entries,{})
 async def test_source_health_policies_and_model_are_read_only_and_labelled(self):
  for method in ('robot.health','robot.policies'):
   result,metadata=await self.service.gateway.dispatch({'jsonrpc':'2.0','id':1,'method':method,'params':{}});self.assertEqual(metadata['upstream_api_version'],45);self.assertTrue(result.get('simulation') or method=='robot.policies')
  model=(await self.call('model'))['result'];self.assertEqual(model['joint_count'],15);self.assertEqual(model['calibration'],'not_modelled');self.assertEqual(len(model['skeleton_names']),2)
  original=self.service.result
  with mock.patch.object(self.service,'result',side_effect=lambda method,params: {'asset':'SIMULATION','joint_names':[],'skeleton':[{}]} if method=='robot.model' else original(method,params)):
   self.assertIn('error',await self.call('model'))
 async def test_ordinary_actual_control_and_invalid_wrappers_are_rejected(self):
  for method in ('robot.move','robot.head','robot.look','robot.stop','robot.relax','robot.setMode'):
   with self.assertRaises(rpc.RpcError):await self.service.gateway.dispatch({'jsonrpc':'2.0','id':1,'method':method,'params':{},'confirmed':True})
  self.assertIn('error',await self.call('preview',{'method':'robot.init','args':{}}));self.assertEqual(self.service.preview.audit,[])
 async def test_actual_cli_metadata_and_clean_shutdown(self):
  directory=self.base/'cli';p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/robot_simulator.py'),'--directory',str(directory),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
  try:
   meta=json.loads(await asyncio.wait_for(p.stdout.readline(),3));self.assertTrue(meta['robot_simulation']);self.assertEqual(meta['api_version'],45);self.assertFalse(meta['allow_control_previews']);self.assertFalse(meta['physical_movement_enabled'])
  finally:
   if p.returncode is None:p.terminate()
   _,error=await asyncio.wait_for(p.communicate(),3)
  self.assertEqual(p.returncode,0,error.decode());self.assertFalse((directory/'gateway.sock').exists())


SOURCE=Path(os.environ.get('SMALLVM_UPSTREAM',ROOT.parent/'smallvm-linux-upstream'));EXTERNAL=os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform=='linux' and struct.calcsize('P')==8 and (EXTERNAL or shutil.which('gcc') and (SOURCE/'.git').is_dir()),'native LP64 compiler/source required')
class RobotNativeAdapter(unittest.IsolatedAsyncioTestCase):
 @classmethod
 def setUpClass(cls):
  cls.temp=tempfile.TemporaryDirectory(prefix='robot-native-tests-');cls.base=Path(cls.temp.name)
  if EXTERNAL:cls.binary=Path(EXTERNAL)
  else:
   p=subprocess.run([sys.executable,str(ROOT/'linux/arm64/build.py'),'--upstream',str(SOURCE),'--output',str(cls.base/'build'),'--sanitize'],capture_output=True,text=True,timeout=120)
   if p.returncode:raise AssertionError(p.stdout+p.stderr)
   cls.binary=cls.base/'build/smallvm'
  spec=importlib.util.spec_from_file_location('robot_vm_helpers',ROOT/'tests/test_linux_microduck_vm.py');cls.helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.helpers)
 @classmethod
 def tearDownClass(cls):cls.temp.cleanup()
 async def asyncSetUp(self):
  self.work=Path(tempfile.mkdtemp(dir=self.base));self.service=await robot.RobotSimulator(self.work/'sim',True).start();data=self.work/'programs';data.mkdir(mode=0o700);self.runtime=await asyncio.to_thread(self.helpers.Runtime,self.binary,data,self.service.directory/'gateway.sock')
 async def asyncTearDown(self):
  await asyncio.to_thread(self.runtime.stop);log=self.runtime.log_path.read_text();self.assertEqual(self.runtime.process.returncode,0,log);self.assertNotIn('AddressSanitizer',log);self.assertNotIn('runtime error:',log);await self.service.stop()
 async def primitive(self,name,args=(),error=None,command=False):return await asyncio.to_thread(self.runtime.primitive,name,args,error,command)
 async def execute(self,p):return await asyncio.to_thread(self.runtime.execute,p.finish())
 async def call(self,name,params=None,confirmed=False):
  job=await self.primitive('begin',(robot.PREFIX+name,json.dumps(params or {}),confirmed));deadline=asyncio.get_running_loop().time()+4
  while await self.primitive('status',(job,))=='pending':self.assertLess(asyncio.get_running_loop().time(),deadline);await asyncio.sleep(.005)
  result=await self.primitive('result',(job,));await self.primitive('release',(job,),command=True);return result
 async def reading(self,reply,primitive='telemetrySample'):
  P,V=self.helpers.Program,self.helpers.Var;p=P().call(primitive,(reply,'capture') if primitive=='sensorSample' else (reply,)).op(7,3).push(0);await self.execute(p)
  return [await self.execute(P().push(i).push(V(3)).op(81,2)) for i in range(1,5)]
 async def test_real_vm_all_control_previews_and_exact_notification_envelopes(self):
  with mock.patch.object(rpc.Upstream,'call',side_effect=AssertionError('no mutation upstream')):
   for method,args in PREVIEWS.items():
    receipt=json.loads(await self.call('preview',{'method':method,'args':args},True))['result'];self.assertEqual(receipt['status'],'recorded_not_executed');self.assertIsNone(receipt['applied'])
  self.assertEqual(len(self.service.preview.audit),13);self.assertNotIn('id',self.service.preview.audit[0]);self.assertEqual(self.service.preview.audit[0]['params']['vx'],.125)
 async def test_native_confirmation_and_bad_selectors_fail_before_io(self):
  await self.primitive('begin',(robot.PREFIX+'preview',json.dumps({'method':'robot.init','args':{}}),False),error=32)
  for name,p in [('capture',{'hz':51}),('reading',select('a'*32,'imu.quat',component=5)),('preview',{'method':'robot.pose','args':{**PREVIEWS['robot.pose'],'z_mm':-26}}),('preview',{'method':'robot.mouth','args':{'open_permille':True}}),('preview',{'method':'robot.look','args':{**PREVIEWS['robot.look'],'x_mm':1001}})]:
   await self.primitive('begin',(robot.PREFIX+name,json.dumps(p),True),error=32)
  self.assertEqual(self.service.preview.audit,[]);self.assertEqual(self.service.state_subscriptions,0)
 async def test_real_vm_every_field_preserves_typed_units_boolean_and_exact_timestamp(self):
  self.service.gateway.state_snapshots.clock=lambda:0.0
  capture=await self.call('capture',{'hz':10});record=await self.reading(capture,'sensorSample');self.assertEqual(record[0],'ok');handle=record[1]
  for field in telemetry.FIELDS:
   expected=telemetry.sample(telemetry.fixture(),field);actual=await self.reading(await self.call('reading',select(handle,field)))
   self.assertEqual(actual[0],expected['status'],field)
   if expected['status']=='ok':self.assertEqual(actual,['ok',expected['value'],expected['unit'],'simulation'],field);self.assertIs(type(actual[1]),type(expected['value']))
   else:self.assertEqual(actual[1],'')
  self.assertEqual(self.service.state_subscriptions,1)
  self.assertEqual((await self.reading(await self.call('reading',select(handle,'t_ns'))))[1],str(2**63+123))
  await self.call('release',{'handle':handle});self.assertEqual((await self.reading(await self.call('reading',select(handle,'loop.hz'))))[0],'expired_or_unknown')
 async def test_native_typed_decoder_rejects_wrong_units_types_u64_overflow_and_legacy_clock(self):
  def envelope(field,value,unit):return json.dumps({'jsonrpc':'2.0','id':1,'result':{'simulation':True,'physical_movement_enabled':False,'kind':'telemetry_reading','status':'ok','field':field,'index':1,'component':1,'value':value,'unit':unit}})
  for field,value,unit in [('loop.hz',True,'mHz'),('loop.hz',50000,'Hz'),('t_ns',str(2**64),'ns'),('t_ns','01','ns'),('safety.fallen',0,'boolean')]:self.assertNotEqual((await self.reading(envelope(field,value,unit)))[0],'ok')
  self.assertEqual((await self.reading(envelope('t_ns','0','ns')))[0],'not_reported')
  self.assertEqual(await self.reading(envelope('loop.hz',0,'mHz')),['ok',0,'mHz','simulation'])
  self.assertEqual(await self.reading(envelope('safety.fallen',False,'boolean')),['ok',False,'boolean','simulation'])
  defaulted=json.loads(envelope('move.limit_count',0,'count'));defaulted['result']['source_default']=True
  self.assertEqual(await self.reading(json.dumps(defaulted)),['ok',0,'count','sim_default'])
 async def test_backend_opt_in_and_ordinary_gateway_still_reject_controls(self):
  self.service.preview.allowed=False
  reply=json.loads(await self.call('preview',{'method':'robot.init','args':{}},True));self.assertEqual(reply['error']['code'],-32003);self.assertEqual(self.service.preview.audit,[])
  await self.primitive('begin',('robot.stop','{}',True),error=32)
 async def test_native_telemetry_record_allocation_survives_moving_gc(self):
  P,V=self.helpers.Program,self.helpers.Var;events=self.runtime.wire.events;start=len(events)
  await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0));self.assertFalse(any(k==20 and i==255 and b'GC took' in b for k,i,b in events[start:]))
  start=len(events);reply=json.dumps({'jsonrpc':'2.0','id':1,'result':telemetry.sample(telemetry.fixture(),'t_ns')})
  self.assertEqual((await self.reading(reply))[1],str(2**63+123));self.assertTrue(any(k==20 and i==255 and b'GC took' in b for k,i,b in events[start:]));self.assertEqual(await self.primitive('readingValue',(V(3),)),str(2**63+123))


if __name__=='__main__':unittest.main(verbosity=2)
