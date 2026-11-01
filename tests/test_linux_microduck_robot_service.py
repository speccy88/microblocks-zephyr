"""Normal Gateway/VM with source-shaped fictional robotd; never physical motion."""
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

ROOT=Path(__file__).resolve().parents[1]
package=types.ModuleType('robot_service_tests');package.__path__=[str(ROOT/'linux/microduck')];sys.modules[package.__name__]=package
svc=importlib.import_module(package.__name__+'.robot_service')
rpc=importlib.import_module(package.__name__+'.protocol')
gateway=importlib.import_module(package.__name__+'.gateway')
client=importlib.import_module(package.__name__+'.client')

def request(name='capture',p=None):return {'jsonrpc':'2.0','id':1,'method':svc.PREFIX+name,'params':{'kind':'state','hz':10} if p is None else p,'confirmed':False}
def read(handle,field='loop.hz',kind='state',index=1,component=1):return {'handle':handle,'kind':kind,'field':field,'index':index,'component':component}
def source(path,uid=None):return {'version':1,'daemon':'robotd','path':str(path),'uid':os.geteuid() if uid is None else uid}
def health():return {'healthy':False,'degraded':True,'reason':'SIMULATION no controller','battery':{'percent':0.,'volts':7.8},'cpu_temp_c':41.25,'motors':{'hottest':'fictional','max_c':45.5,'mean_c':40.25},'control_loop':{'target_hz':50.,'achieved_hz':49.95,'ticks':2**64-1,'missed':2**63+5,'last_tick_age_ms':4},'bus':{'consecutive_errors':0,'startup_failures':0},'imu':{'ready':True,'missing':False,'stale_blocks':2**63+1,'consecutive_stale_blocks':25}}

async def normal_gateway(directory,path,uid=None):
    directory.mkdir(mode=0o700);config=directory/'robot.json';config.write_text(json.dumps(source(path,uid)));config.chmod(0o600)
    return await gateway.Gateway({},robot_read=svc.load_source(config)).start(directory/'gateway.sock')

class RobotServiceProtocol(unittest.TestCase):
    def test_explicit_robotd_config_and_closed_request_schema(self):
        good={'version':1,'daemon':'robotd','path':'/run/robot.sock','uid':1000};self.assertEqual(svc.validate_source(good),good)
        for delta in [{'daemon':'padd'},{'uid':True},{'path':'relative'},{'version':2}]:
            with self.assertRaises(ValueError):svc.validate_source({**good,**delta})
        for q in [request(p={'kind':'health','hz':10}),request(p={'kind':'state','hz':0}),request(p={'kind':['state'],'hz':10}),request('read',read('a'*32,'cpu_temp_c','state')),request('read',read('a'*32,'healthy','health',2)),request('release',{'handle':'A'*32}),{**request(),'confirmed':1}]:
            with self.assertRaises(rpc.RpcError):svc.validate(q)

    def test_all_health_units_values_and_zero_are_typed(self):
        h=svc.health.validate_health(health());self.assertEqual(len(svc.health.FIELDS),21)
        for field,(unit,_) in svc.health.FIELDS.items():
            s=svc.health.sample(h,field);self.assertEqual((s['status'],s['unit']),('ok',unit),field)
        self.assertIs(svc.health.sample(h,'healthy')['value'],False)
        self.assertEqual(svc.health.sample(h,'battery.percent')['value'],0)
        self.assertEqual(svc.health.sample(h,'battery.volts')['value'],7800)
        self.assertEqual(svc.health.sample(h,'control_loop.ticks')['value'],str(2**64-1))

    def test_schema_defaults_are_explicit_but_measurements_are_unavailable(self):
        h=svc.health.validate_health({'healthy':False,'imu':{}})
        for field in ('degraded','health.state','bus.consecutive_errors','bus.startup_failures','imu.ready','imu.missing','imu.stale_blocks','imu.consecutive_stale_blocks','imu.state'):
            self.assertTrue(svc.health.sample(h,field)['source_default'],field)
        for field in ('battery.volts','cpu_temp_c','control_loop.achieved_hz','reason'):
            self.assertEqual(svc.health.sample(h,field)['status'],'not_reported')
        self.assertEqual(svc.health.sample({'healthy':True},'imu.state')['status'],'not_reported')

    def test_health_frozen_threshold_and_diagnostic_precedence(self):
        h=health();h['imu'].update(ready=True,missing=False,consecutive_stale_blocks=24)
        self.assertEqual(svc.health.sample(h,'imu.state')['value'],'converged')
        h['imu']['consecutive_stale_blocks']=25;self.assertEqual(svc.health.sample(h,'imu.state')['value'],'frozen')
        h['imu']['missing']=True;self.assertEqual(svc.health.sample(h,'imu.state')['value'],'missing')
        h['healthy']=True;self.assertEqual(svc.health.sample(h,'health.state')['value'],'healthy')

    def test_malformed_required_health_and_nonfinite_values_refused(self):
        for delta in [{'healthy':1},{'degraded':None},{'battery':{}},{'bus':None},{'control_loop':{}},{'cpu_temp_c':float('nan')},{'imu':{'ready':1}},{'bus':{'consecutive_errors':2**32}}]:
            with self.assertRaises(rpc.RpcError):svc.health.validate_health({**health(),**delta})
        self.assertEqual(svc.health.sample({**health(),'cpu_temp_c':1e300},'cpu_temp_c')['status'],'out_of_range')

    def test_health_text_utf8_limit_and_no_control_or_surrogate_values(self):
        h=health();h['reason']='\u00e9'*64;self.assertEqual(svc.health.sample(h,'reason')['value'],'\u00e9'*64)
        for text in ('\u00e9'*65,'\ud800'):
            h['reason']=text;self.assertEqual(svc.health.sample(h,'reason')['status'],'out_of_range')
        with self.assertRaises(rpc.RpcError):svc.health.validate_health({**h,'reason':'bad\ntext'})

    def test_state_optional_zero_counters_and_default_contract_preserved(self):
        s=svc.state.validate_state(svc.state.fixture());self.assertEqual(len(svc.state.FIELDS),29)
        self.assertEqual(svc.state.sample(s,'move.applied')['value'],0)
        s.pop('velocities');self.assertEqual(svc.state.sample(s,'velocities')['status'],'not_reported')
        s['move'].pop('limited_by');self.assertTrue(svc.state.sample(s,'move.limit_count')['source_default'])
        s['t_ns']=0;self.assertEqual(svc.state.sample(s,'t_ns')['status'],'not_reported')

    def test_library_has_separate_capture_kinds_and_no_control_calls(self):
        text=(ROOT/'linux/microduck/Robot.ubl').read_text()
        self.assertIn('"kind":"health"',text);self.assertIn('"kind":"state"',text)
        self.assertNotIn('robotSim.',text);self.assertNotIn(' true)',text)
        for method in ('robot.move','robot.enable','robot.do','robot.stop'):self.assertNotIn(method,text)
        for field in svc.health.FIELDS:self.assertIn("'"+field+"'",text)

class RobotWire:
    """Protocol-shaped source only. No policy, controller, device or physical model."""
    def __init__(self,path):
        self.path=path;self.frame=svc.state.fixture();self.health=health();self.profile='normal';self.version=45;self.audit=[];self.active=0;self.tasks=set()
    async def start(self):
        self.server=await asyncio.start_unix_server(self.handle,path=str(self.path));self.path.chmod(0o600);return self
    async def stop(self):
        self.server.close();await self.server.wait_closed()
        for task in list(self.tasks):task.cancel()
        await asyncio.gather(*list(self.tasks),return_exceptions=True)
        self.path.unlink(missing_ok=True)
    async def handle(self,reader,writer):
        task=asyncio.current_task();self.tasks.add(task);self.active+=1
        try:
            q=await rpc.read_message(reader,8192);self.audit.append(q)
            assert q=={'jsonrpc':'2.0','id':0,'method':'hello','params':{'api_version':45}}
            writer.write(rpc.encode({'jsonrpc':'2.0','id':0,'result':{'api_version':True if self.profile=='badhello' else self.version,'daemon_version':'0.0.0','revision':'SIMULATION'}},16384));await writer.drain()
            q=await rpc.read_message(reader,8192);self.audit.append(q)
            assert q['id']==1 and q['method'] in ('robot.health','robot.subscribe')
            if self.profile=='eof':return
            if self.profile=='preack_timeout':await reader.read();return
            if self.profile=='rpcerror':writer.write(rpc.encode({'jsonrpc':'2.0','id':1,'error':{'code':-32003,'message':'do not echo this'}},16384));await writer.drain();return
            value=copy.deepcopy(self.health) if q['method']=='robot.health' else {'accepted':self.profile!='refused'}
            if self.profile=='badack':value={'accepted':1}
            writer.write(rpc.encode({'jsonrpc':'2.0','id':2 if self.profile=='wrongid' else 1,'result':value},16384))
            if q['method']=='robot.subscribe' and self.profile not in ('absent','refused'):
                note={'jsonrpc':'2.0','method':'wrong' if self.profile=='badstate' else 'robot.state','params':self.frame}
                if self.profile=='large':note['params']={**self.frame,'reason':'x'*17000}
                writer.write(rpc.encode(note,65536))
            await writer.drain();await reader.read()
        except (rpc.RpcError,OSError,AssertionError):pass
        finally:
            writer.close()
            try:await writer.wait_closed()
            except OSError:pass
            self.active-=1;self.tasks.discard(task)

@unittest.skipUnless(sys.platform=='linux','Linux peer credentials required')
class RobotServiceUnix(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='robot-read-');self.base=Path(self.temp.name);self.wire=await RobotWire(self.base/'robot.sock').start();self.normal=await normal_gateway(self.base/'normal',self.wire.path)
    async def asyncTearDown(self):
        await self.normal.stop();await self.wire.stop();self.temp.cleanup()
    async def capture(self,kind='state'):
        return (await self.normal.dispatch(request(p={'kind':kind,**({'hz':10} if kind=='state' else {})})))[0]
    async def test_normal_gateway_state_and_health_coherent_views_no_mutations(self):
        self.normal.robot_read.clock=lambda:0.
        for kind,fields in [('state',svc.state.FIELDS),('health',svc.health.FIELDS)]:
            capture=await self.capture(kind);self.assertEqual(capture['reported_api_version'],45);self.assertNotIn('simulation',capture)
            handle=capture['handle']
            for field in fields:
                result=(await self.normal.dispatch(request('read',read(handle,field,kind))))[0]
                expected=svc.state.sample(self.wire.frame,field) if kind=='state' else svc.health.sample(self.wire.health,field)
                self.assertEqual((result['status'],result['source'],result['origin']),(expected['status'],'robotd','local_ipc'),field)
        methods=[q['method'] for q in self.wire.audit];self.assertEqual(methods,['hello','robot.subscribe','hello','robot.health'])
        caps=(await self.normal.dispatch({'jsonrpc':'2.0','id':1,'method':'microduck.capabilities','params':{}}))[0];self.assertEqual(caps['allowed_mutations'],[]);self.assertEqual(set(caps['methods']),svc.METHODS)
    async def test_real_python_client_routes_readonly_wrappers_and_disabled_source(self):
        c=client.Client(self.base/'normal/gateway.sock');v=await c.call(svc.PREFIX+'capture',{'kind':'health'});handle=v['handle']
        self.assertEqual((await c.call(svc.PREFIX+'read',read(handle,'battery.percent','health')))['value'],0)
        with self.assertRaises(rpc.RpcError):await c.call('robot.subscribe',{'hz':10})
        self.normal.robot_read=None
        with self.assertRaises(rpc.RpcError) as error:await c.call(svc.PREFIX+'capture',{'kind':'health'})
        self.assertEqual(error.exception.code,-32004)
    async def test_api_skew_diagnostic_and_refusal_timeout_states(self):
        self.wire.version=44;self.assertEqual((await self.capture())['reported_api_version'],44)
        for profile,expected in [('refused','refused'),('absent','waiting'),('preack_timeout','timeout')]:
            self.wire.profile=profile;self.assertEqual((await self.capture())['status'],expected)
    async def test_malformed_envelopes_errors_and_line_bounds(self):
        for profile in ('badhello','wrongid','rpcerror','badack','badstate','eof','large'):
            self.wire.profile=profile
            with self.assertRaises(rpc.RpcError):await self.capture()
            self.assertEqual(self.normal.robot_read.pending,0)
    async def test_source_uid_permissions_checked_before_any_write(self):
        self.normal.robot_read.config['uid']=os.geteuid()+1
        with self.assertRaises(rpc.RpcError):await self.capture()
        self.assertEqual(self.wire.audit,[])
        self.normal.robot_read.config['uid']=os.geteuid();self.wire.path.chmod(0o666)
        with self.assertRaises(rpc.RpcError):await self.capture()
        self.assertEqual(self.wire.audit,[])
    async def test_shared_capacity_expiry_regression_release_and_wrong_kind(self):
        clock=[10.];self.normal.robot_read.clock=lambda:clock[0]
        values=[await self.capture('health' if i%2 else 'state') for i in range(4)]
        self.assertEqual((await self.capture())['status'],'busy');h=values[0]['handle']
        self.assertEqual(self.normal.robot_read.read(read(h,'healthy','health'))['status'],'wrong_kind')
        self.normal.robot_read.release(values[1]['handle']);self.assertEqual((await self.capture())['status'],'ok')
        clock[0]=15.;self.assertEqual(self.normal.robot_read.read(read(h))['status'],'expired_or_unknown')
        new=(await self.capture())['handle'];clock[0]=14.;self.assertEqual(self.normal.robot_read.read(read(new))['status'],'expired_or_unknown')
    async def test_pending_capacity_and_cancellation_close_source(self):
        self.wire.profile='absent';tasks=[asyncio.create_task(self.capture()) for _ in range(4)]
        for _ in range(100):
            if self.normal.robot_read.pending==4:break
            await asyncio.sleep(.002)
        self.assertEqual((await self.capture('health'))['status'],'busy')
        for task in tasks:task.cancel()
        await asyncio.gather(*tasks,return_exceptions=True)
        for _ in range(100):
            if not self.wire.active:break
            await asyncio.sleep(.002)
        self.assertEqual(self.normal.robot_read.pending,0);self.assertEqual(self.wire.active,0)
    async def test_private_config_ownership_bounds_symlink_and_daemon(self):
        p=self.base/'normal/robot.json';self.assertEqual(svc.load_source(p)['daemon'],'robotd');p.chmod(0o644)
        with self.assertRaises(ValueError):svc.load_source(p)
        p.chmod(0o600);link=self.base/'normal/link';link.symlink_to(p)
        with self.assertRaises(OSError):svc.load_source(link)
    async def test_actual_gateway_cli_private_config(self):
        config=self.base/'normal/gateway.json';config.write_text('{"version":1,"upstreams":{}}');config.chmod(0o600)
        p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/gateway.py'),'--config',str(config),'--robot-read-config',str(self.base/'normal/robot.json'),'--socket',str(self.base/'normal/cli.sock'),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            self.assertIn(b'gateway ready',await asyncio.wait_for(p.stdout.readline(),3))
            c=client.Client(self.base/'normal/cli.sock');v=await c.call(svc.PREFIX+'capture',{'kind':'health'});self.assertEqual(v['status'],'ok')
        finally:
            if p.returncode is None:p.terminate()
            _,error=await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode())
    async def test_user_fictional_fixture_cli_and_cleanup(self):
        directory=self.base/'demo';p=await asyncio.create_subprocess_exec(sys.executable,str(ROOT/'linux/microduck/robot_gateway_fixture.py'),'--directory',str(directory),stdout=asyncio.subprocess.PIPE,stderr=asyncio.subprocess.PIPE)
        try:
            ready=json.loads(await asyncio.wait_for(p.stdout.readline(),3));self.assertTrue(ready['simulation']);self.assertFalse(ready['physical_hardware_verified'])
            c=client.Client(Path(ready['gateway_socket']));self.assertEqual((await c.call(svc.PREFIX+'capture',{'kind':'health'}))['status'],'ok')
        finally:
            if p.returncode is None:p.terminate()
            _,error=await asyncio.wait_for(p.communicate(),3)
        self.assertEqual(p.returncode,0,error.decode());self.assertFalse((directory/'normal/gateway.sock').exists());self.assertFalse((directory/'source/robot.sock').exists())

SOURCE=Path(os.environ.get('SMALLVM_UPSTREAM',ROOT.parent/'smallvm-linux-upstream'))
EXTERNAL=os.environ.get('SMALLVM_MICRODUCK_BINARY')
@unittest.skipUnless(sys.platform=='linux' and struct.calcsize('P')==8 and (EXTERNAL or shutil.which('gcc') and (SOURCE/'.git').is_dir()),'native LP64 compiler/source required')
class RobotServiceNativeAdapter(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp=tempfile.TemporaryDirectory(prefix='robot-read-vm-');cls.base=Path(cls.temp.name)
        if EXTERNAL:cls.binary=Path(EXTERNAL)
        else:
            p=subprocess.run([sys.executable,str(ROOT/'linux/arm64/build.py'),'--upstream',str(SOURCE),'--output',str(cls.base/'build'),'--sanitize'],capture_output=True,text=True,timeout=120)
            if p.returncode:raise AssertionError(p.stdout+p.stderr)
            cls.binary=cls.base/'build/smallvm'
        spec=importlib.util.spec_from_file_location('robot_service_vm_helpers',ROOT/'tests/test_linux_microduck_vm.py');cls.helpers=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.helpers)
    @classmethod
    def tearDownClass(cls):cls.temp.cleanup()
    async def asyncSetUp(self):
        self.work=Path(tempfile.mkdtemp(dir=self.base));self.wire=await RobotWire(self.work/'robot.sock').start();self.normal=await normal_gateway(self.work/'normal',self.wire.path);self.normal.robot_read.clock=lambda:0.
        data=self.work/'programs';data.mkdir(mode=0o700);self.runtime=await asyncio.to_thread(self.helpers.Runtime,self.binary,data,self.work/'normal/gateway.sock')
    async def asyncTearDown(self):
        await asyncio.to_thread(self.runtime.stop);log=self.runtime.log_path.read_text();self.assertEqual(self.runtime.process.returncode,0,log);self.assertNotIn('AddressSanitizer',log);self.assertNotIn('runtime error:',log)
        await self.normal.stop();await self.wire.stop()
    async def primitive(self,name,args=(),error=None,command=False):return await asyncio.to_thread(self.runtime.primitive,name,args,error,command)
    async def execute(self,p):return await asyncio.to_thread(self.runtime.execute,p.finish())
    async def call(self,name='capture',p=None):
        job=await self.primitive('begin',(svc.PREFIX+name,json.dumps({'kind':'state','hz':10} if p is None else p),False));deadline=asyncio.get_running_loop().time()+4
        while await self.primitive('status',(job,))=='pending':self.assertLess(asyncio.get_running_loop().time(),deadline);await asyncio.sleep(.005)
        value=await self.primitive('result',(job,));await self.primitive('release',(job,),command=True);return value
    async def typed(self,reply,primitive='robotReading'):
        P,V=self.helpers.Program,self.helpers.Var;await self.execute(P().call(primitive,(reply,)).op(7,3).push(0));return [await self.execute(P().push(i).push(V(3)).op(81,2)) for i in range(1,5)]
    async def test_all_state_selectors_coherent_and_exact_on_actual_vm(self):
        capture=await self.typed(await self.call());self.assertEqual(capture[0],'ok');handle=capture[1]
        for field,(indices,components) in svc.state.FIELDS.items():
            for component in range(1,components+1):
                expected=svc.state.sample(self.wire.frame,field,1,component);record=await self.typed(await self.call('read',read(handle,field,component=component)))
                self.assertEqual(record,[expected['status'],expected['value'] if expected['status']=='ok' else '',expected['unit'],'local_ipc'],(field,component))
        self.assertEqual([q['method'] for q in self.wire.audit],['hello','robot.subscribe'])
    async def test_all_health_selectors_and_u64_counters_on_actual_vm(self):
        handle=(await self.typed(await self.call(p={'kind':'health'})))[1]
        for field in svc.health.FIELDS:
            expected=svc.health.sample(self.wire.health,field);self.assertEqual(await self.typed(await self.call('read',read(handle,field,'health'))),['ok',expected['value'],expected['unit'],'local_ipc'],field)
        self.assertEqual([q['method'] for q in self.wire.audit],['hello','robot.health'])
    async def test_native_defaults_missing_false_zero_and_extraction_refusal(self):
        self.wire.health={'healthy':False,'imu':{}};handle=(await self.typed(await self.call(p={'kind':'health'})))[1]
        for field,value,unit in [('degraded',False,'boolean'),('health.state','unhealthy','state'),('bus.startup_failures','0','count64'),('imu.state','not_converged','state')]:
            self.assertEqual(await self.typed(await self.call('read',read(handle,field,'health'))),['ok',value,unit,'ipc_default'])
        self.assertEqual((await self.typed(await self.call('read',read(handle,'battery.percent','health'))))[0],'not_reported');await self.primitive('readingValue',(self.helpers.Var(3),),error=32)
        self.wire.frame['move'].pop('limited_by');state=(await self.typed(await self.call()))[1]
        self.assertEqual(await self.typed(await self.call('read',read(state,'move.limit_count'))),['ok',0,'count','ipc_default'])
    async def test_native_cross_source_markers_types_and_defaults_are_rejected(self):
        h=svc.RobotStore(source(self.wire.path));h.clock=lambda:0.;h.entries['a'*32]={'kind':'health','value':health(),'expires':5};good=h.read(read('a'*32,'battery.volts','health'))
        for delta in [{'source':'tofd'},{'simulation':False},{'simulation':True},{'physical_hardware_verified':True},{'unit':'count64'},{'value':True},{'source_default':True},{'index':2},{'snapshot_kind':'state'}]:
            record=await self.typed(json.dumps({'jsonrpc':'2.0','id':1,'result':{**good,**delta}}));self.assertNotEqual(record[0],'ok',delta)
        for primitive in ('gamepadReading','headImuReading','depthReading','telemetrySample'):
            self.assertNotEqual((await self.typed(json.dumps({'jsonrpc':'2.0','id':1,'result':good}),primitive))[0],'ok')
        counter=h.read(read('a'*32,'control_loop.ticks','health'))
        for value in ('01',str(2**64),True):self.assertNotEqual((await self.typed(json.dumps({'jsonrpc':'2.0','id':1,'result':{**counter,'value':value}})))[0],'ok')
    async def test_native_invalid_requests_disabled_store_expiry_and_wrong_kind(self):
        for p in [{'kind':'state','hz':51},{'kind':'health','hz':1},{'kind':'robot.enable'}]:await self.primitive('begin',(svc.PREFIX+'capture',json.dumps(p),False),error=32)
        handle=(await self.typed(await self.call()))[1];self.assertEqual((await self.typed(await self.call('read',read(handle,'healthy','health'))))[0],'wrong_kind')
        await self.call('release',{'handle':handle});self.assertEqual((await self.typed(await self.call('read',read(handle))))[0],'expired_or_unknown')
        self.normal.robot_read=None;self.assertEqual((await self.typed(await self.call()))[0],'error')
    async def test_native_health_utf8_survives_actual_compacting_gc(self):
        h=health();h['reason']='\u00e9'*64;store=svc.RobotStore(source(self.wire.path));store.clock=lambda:0.;store.entries['a'*32]={'kind':'health','value':h,'expires':5}
        reply=json.dumps({'jsonrpc':'2.0','id':1,'result':store.read(read('a'*32,'reason','health'))})
        P,V=self.helpers.Program,self.helpers.Var;events=self.runtime.wire.events;await self.execute(P().call('newByteArray',(262080,),prim_set=1).op(19,1).push(0));start=len(events)
        self.assertEqual((await self.typed(reply))[1],'\u00e9'*64);self.assertTrue(any(k==20 and i==255 and b'GC took' in b for k,i,b in events[start:]));self.assertEqual(await self.primitive('readingValue',(V(3),)),'\u00e9'*64)

if __name__=='__main__':unittest.main(verbosity=2)
