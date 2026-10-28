"""Real Unix/VM transport with fictional ModelResult; no physical geometry."""
# SPDX-License-Identifier: MIT
import copy
import json
import sys
import unittest
import test_linux_microduck_robot_service as helper

svc=helper.svc

def fixture():
    return {'asset':'SIMULATION_UNCALIBRATED','trunk_height_m':.123,
            'joint_names':list(svc.state.JOINT_NAMES),'head_joints':list(svc.state.JOINT_NAMES[5:9]),
            'tof_beams':[[0.,0.,1.] for _ in range(64)],'tof_fov_deg':45.,
            'frames_at_zero':{'camera':{'pos':[.1,-.02,.3],'quat':[1.,0.,0.,0.]},'tof':{'pos':[.12,0.,.25],'quat':[1.,0.,0.,0.]},'head_imu':None},
            'skeleton':[{'name':'SIMULATION_root'},{'name':'SIMULATION_head','parent':0}]}

class ModelProtocol(unittest.TestCase):
    def test_source_shapes_absence_scaling_reference_and_root_default(self):
        m=svc.model.validate_model(fixture());self.assertEqual(len(svc.model.FIELDS),18)
        self.assertEqual(svc.model.sample(m,'trunk_height_m')['value'],123)
        self.assertEqual(svc.model.sample(m,'frames.camera.pos',component=2)['value'],-20)
        self.assertEqual(svc.model.sample(m,'tof_beam',64,3)['value'],1000000)
        self.assertEqual(svc.model.sample(m,'skeleton_parent',2)['value'],1)
        self.assertTrue(svc.model.sample(m,'skeleton_parent')['source_default'])
        for field in svc.model.FIELDS:self.assertEqual(svc.model.sample({},field)['status'],'not_reported')
        self.assertEqual(svc.model.sample(m,'frames.head_imu.pos')['status'],'not_reported')
        self.assertEqual(svc.model.sample({'trunk_height_m':1e300},'trunk_height_m')['status'],'out_of_range')
        self.assertEqual(svc.model.sample({'asset':'é'*65},'asset')['status'],'out_of_range')

    def test_malformed_bounds_bool_nan_parent_and_optional_parts(self):
        for delta in [{'trunk_height_m':True},{'tof_fov_deg':float('nan')},{'joint_names':['a']*129},{'head_joints':['a']*5},{'tof_beams':[[0.,0.,1.]]*65},{'tof_beams':[[1,2]]},{'frames_at_zero':{'camera':None}},{'skeleton':[{'name':'a','parent':1}]},{'skeleton':[{'name':'a','parent':True}]}]:
            with self.assertRaises(helper.rpc.RpcError):svc.model.validate_model({**fixture(),**delta})
        for ids in ([True],[-1],[256],list(range(256))+[0]):
            with self.assertRaises(helper.rpc.RpcError):svc.health.validate_health({**helper.health(),'bus':{'missing':ids}})
        h=svc.health.validate_health({**helper.health(),'bus':{'missing':[]}})
        self.assertEqual(svc.health.sample(h,'bus.missing_count')['value'],0)
        self.assertEqual(svc.health.sample(h,'bus.missing_id')['status'],'not_reported')
        self.assertEqual(svc.health.sample({'healthy':True},'bus.missing_count')['status'],'not_reported')

    def test_closed_requests_and_no_model_hz_or_unbounded_indices(self):
        self.assertEqual(svc.validate(helper.request(p={'kind':'model'}))[1],{'kind':'model'})
        for params in [{'kind':'model','hz':10},{'kind':'model','method':'robot.enable'}]:
            with self.assertRaises(helper.rpc.RpcError):svc.validate(helper.request(p=params))
        for kind,field,index,component in [('model','tof_beam',65,1),('model','frames.camera.pos',1,4),('health','bus.missing_id',257,1),('health','bus.missing_count',2,1)]:
            with self.assertRaises(helper.rpc.RpcError):svc.validate(helper.request('read',helper.read('a'*32,field,kind,index,component)))

@unittest.skipUnless(sys.platform=='linux' and not getattr(helper.RobotServiceNativeAdapter,'__unittest_skip__',False),'Linux native VM required')
class ModelNative(unittest.IsolatedAsyncioTestCase):
    setUpClass=classmethod(helper.RobotServiceNativeAdapter.setUpClass.__func__)
    tearDownClass=classmethod(helper.RobotServiceNativeAdapter.tearDownClass.__func__)
    asyncTearDown=helper.RobotServiceNativeAdapter.asyncTearDown
    primitive=helper.RobotServiceNativeAdapter.primitive
    execute=helper.RobotServiceNativeAdapter.execute
    call=helper.RobotServiceNativeAdapter.call
    typed=helper.RobotServiceNativeAdapter.typed
    async def asyncSetUp(self):
        await helper.RobotServiceNativeAdapter.asyncSetUp(self);self.wire.model=fixture()

    async def test_actual_model_transport_all_selectors_and_reference_values(self):
        handle=(await self.typed(await self.call(p={'kind':'model'})))[1]
        for field,(indices,components,unit,_) in svc.model.FIELDS.items():
            for component in range(1,components+1):
                expected=svc.model.sample(self.wire.model,field,1,component)
                record=await self.typed(await self.call('read',helper.read(handle,field,'model',1,component)))
                self.assertEqual(record,[expected['status'],expected['value'] if expected['status']=='ok' else '',unit,'ipc_default' if expected.get('source_default') else 'local_ipc'],(field,component))
        self.assertEqual((await self.typed(await self.call('read',helper.read(handle,'skeleton_parent','model',2))))[1],1)
        self.assertEqual((await self.typed(await self.call('read',helper.read(handle,'tof_beam','model',64,3))))[1],1000000)
        self.assertEqual([q['method'] for q in self.wire.audit],['hello','robot.model'])
        await self.call('release',{'handle':handle});self.assertEqual(self.normal.robot_read.entries,{})

    async def test_missing_servo_order_empty_absent_and_shared_capacity(self):
        h=(await self.typed(await self.call(p={'kind':'health'})))[1]
        for field,index,expected in [('bus.missing_count',1,2),('bus.missing_id',1,3),('bus.missing_id',2,11)]:
            self.assertEqual((await self.typed(await self.call('read',helper.read(h,field,'health',index))))[1],expected)
        self.assertEqual((await self.typed(await self.call('read',helper.read(h,'bus.missing_id','health',3))))[0],'not_reported')
        for kind in ('model','state','model'):self.assertEqual((await self.typed(await self.call(p={'kind':kind,**({'hz':10} if kind=='state' else {})})))[0],'ok')
        self.assertEqual((await self.typed(await self.call(p={'kind':'model'})))[0],'busy')
        self.assertEqual((await self.typed(await self.call('read',helper.read(h,'asset','model'))))[0],'wrong_kind')
        self.normal.robot_read.clock=lambda:6.
        self.assertEqual((await self.typed(await self.call('read',helper.read(h,'bus.missing_id','health'))))[0],'expired_or_unknown')

    async def test_model_defaults_forgery_and_request_bounds(self):
        self.wire.model={};h=(await self.typed(await self.call(p={'kind':'model'})))[1]
        for field in svc.model.FIELDS:
            self.assertEqual((await self.typed(await self.call('read',helper.read(h,field,'model'))))[0],'not_reported',field)
        store=svc.RobotStore(helper.source(self.wire.path));store.clock=lambda:0.;store.entries['a'*32]={'kind':'model','value':fixture(),'expires':5}
        good=store.read(helper.read('a'*32,'trunk_height_m','model'))
        for delta in [{'unit':'m'},{'value':True},{'source':'tofd'},{'source_default':True},{'index':2},{'component':2},{'simulation':False}]:
            self.assertNotEqual((await self.typed(json.dumps({'jsonrpc':'2.0','id':1,'result':{**good,**delta}})))[0],'ok')
        for params in [{'kind':'model','hz':10},{'kind':'model','extra':True}]:await self.primitive('begin',(svc.PREFIX+'capture',json.dumps(params),False),error=32)
        await self.primitive('begin',(svc.PREFIX+'read',json.dumps(helper.read(h,'tof_beam','model',65)),False),error=32)

if __name__=='__main__':unittest.main(verbosity=2)
