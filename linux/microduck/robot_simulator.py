#!/usr/bin/env python3
"""SIMULATION API45 robot packet previews and bounded typed telemetry; no live target."""
# SPDX-License-Identifier: MIT
import argparse
import asyncio
import copy
import json
import os
from pathlib import Path
import secrets
import signal
import sys
import time

try:
 from . import robot_telemetry as telemetry
 from .sensor_simulator import SensorSimulator, SensorGateway, _fresh_file
 from .sensor_snapshots import token
 from .motion_simulator import MotionSimulation, MotionGateway, METHODS as MOTION_METHODS, PREFIX as MOTION_PREFIX, validate_motion
 from .protocol import RpcError, encode, connect_checked, read_message, response_result, peer_uid
except ImportError:
 import robot_telemetry as telemetry
 from sensor_simulator import SensorSimulator, SensorGateway, _fresh_file
 from sensor_snapshots import token
 from motion_simulator import MotionSimulation, MotionGateway, METHODS as MOTION_METHODS, PREFIX as MOTION_PREFIX, validate_motion
 from protocol import RpcError, encode, connect_checked, read_message, response_result, peer_uid

PREFIX='microduck.robotSim.'
METHODS=frozenset(PREFIX+n for n in ('preview','capture','reading','release','model'))
NOTIFICATIONS=frozenset(('robot.move','robot.head','robot.pose','robot.mouth'))
NUMERIC={
 'robot.move':(('vx_mm_s',-300,300,1000),('vy_mm_s',-300,300,1000),('vyaw_mrad_s',-1500,1500,1000)),
 'robot.head':tuple((n+'_mrad',-3142,3142,1000) for n in ('neck_pitch','head_pitch','head_yaw','head_roll')),
 'robot.look':tuple((n+'_mm',-1000,1000,1000) for n in ('x','y','z'))+(('neck_pitch_mrad',-3142,3142,1000),),
 'robot.pose':(('z_mm',-25,10,1000),('roll_mrad',-260,260,1000),('pitch_mrad',-260,260,1000)),
 'robot.mouth':(('open_permille',0,1000,1000),)}
PREVIEWS=frozenset(NUMERIC)|frozenset(('robot.stop','robot.enable','robot.init','robot.relax','robot.do','robot.sound','robot.loadPolicy','robot.setMode'))
SKILLS=('simulation_bow','simulation_nod')
SLOTS={'walk':'/SIMULATION/walk.onnx','stand':'/SIMULATION/stand.onnx'}


def require(good,code=-32602,message='Invalid local robot simulation parameters'):
 if not good:raise RpcError(code,message)


def preview_params(method,args):
 require(isinstance(method,str) and method in PREVIEWS and isinstance(args,dict))
 if method in NUMERIC:
  fields=NUMERIC[method];keys={x[0] for x in fields}|({'active'} if method=='robot.pose' else set())
  require(set(args)==keys)
  result={}
  for name,low,high,scale in fields:
   require(telemetry.integer(args[name],low,high));source_name=name.removesuffix('_mm_s').removesuffix('_mrad_s') if method=='robot.move' else name.removesuffix('_mm').removesuffix('_mrad').removesuffix('_permille')
   result[source_name]=args[name]/scale
  if method=='robot.pose':require(type(args['active']) is bool);result['active']=args['active']
  return result
 if method in ('robot.stop','robot.init','robot.relax'):require(not args);return {}
 if method=='robot.enable':require(set(args)=={'on','toggle'} and type(args['on']) is bool and type(args['toggle']) is bool);return dict(args)
 if method=='robot.do':require(set(args)=={'skill'} and args.get('skill') in SKILLS);return dict(args)
 if method=='robot.setMode':require(set(args)=={'mode'} and args.get('mode') in ('walk','roller'));return dict(args)
 if method=='robot.sound':
  require(set(args)=={'tag','hold'} and args.get('tag') in ('alarm','greet','inquire','peck','chirp','coo','wheee'))
  require(type(args['hold']) is bool if args['tag']=='wheee' else args['hold'] is None)
  return {'tag':args['tag'],**({'hold':args['hold']} if args['hold'] is not None else {})}
 require(set(args)=={'slot','path'})
 slot,path=args['slot'],args['path'];require(slot is None or isinstance(slot,str) and slot in SLOTS)
 require(path is None or slot is not None and path==SLOTS[slot])
 return {'slot':slot,'path':path}


def validate(request):
 require(isinstance(request,dict) and not set(request)-{'jsonrpc','id','method','params','confirmed'} and request.get('jsonrpc')=='2.0' and telemetry.integer(request.get('id'),1,0x7fffffff),-32600)
 name=request.get('method');require(isinstance(name,str) and name in METHODS,-32601)
 require('confirmed' not in request or type(request['confirmed']) is bool)
 name=name.removeprefix(PREFIX);p=request.get('params',{});require(isinstance(p,dict))
 if name=='preview':require(set(p)=={'method','args'});preview_params(p['method'],p['args'])
 elif name=='capture':require(set(p)=={'hz'} and telemetry.integer(p['hz'],1,50))
 elif name=='release':require(set(p)=={'handle'} and token(p['handle']))
 elif name=='model':require(not p)
 else:
  require(set(p)=={'handle','field','index','component'} and token(p['handle']) and isinstance(p['field'],str) and p['field'] in telemetry.FIELDS)
  limits=telemetry.FIELDS[p['field']];require(telemetry.integer(p['index'],1,limits[0]) and telemetry.integer(p['component'],1,limits[1]))
 return name,copy.deepcopy(p)


class PreviewRecorder:
 def __init__(self,allowed=False):
  require(type(allowed) is bool);self.allowed=allowed;self.audit=[]
 def record(self,method,args,confirmed):
  params=preview_params(method,args)
  require(self.allowed and confirmed is True,-32003,'Simulation preview needs backend opt-in and explicit confirmation')
  require(len(self.audit)<128,-32010,'Simulation preview audit is full; no packet recorded')
  notification=method in NOTIFICATIONS or method=='robot.sound' and 'hold' in params
  packet={'jsonrpc':'2.0','method':method,'params':params}
  if not notification:packet['id']=len(self.audit)+1
  self.audit.append(copy.deepcopy(packet))
  return {'simulation':True,'physical_movement_enabled':False,'kind':'control_preview','status':'recorded_not_executed','record_sequence':len(self.audit),'source_method':method,'notification':notification,'admission':None,'applied':None}


def state_fixture():return telemetry.fixture()


async def capture_state(directory,hz):
 writer=None;meta={'simulation':True,'physical_movement_enabled':False,'kind':'telemetry_capture','status':'timeout'}
 try:
  async with asyncio.timeout(.5):
   reader,writer=await connect_checked(directory/'robot.sock',os.geteuid(),65536,True)
   writer.write(encode({'jsonrpc':'2.0','id':0,'method':'hello','params':{'api_version':telemetry.API_VERSION}},8192));await writer.drain()
   hello=response_result(await read_message(reader,65536),0);require(isinstance(hello,dict) and telemetry.integer(hello.get('api_version'),1,255),-32011)
   writer.write(encode({'jsonrpc':'2.0','id':1,'method':'robot.subscribe','params':{'hz':hz}},8192));await writer.drain()
   ack=response_result(await read_message(reader,65536),1);require(isinstance(ack,dict) and type(ack.get('accepted')) is bool,-32011)
   meta.update(status='waiting' if ack['accepted'] else 'refused',reported_api_version=hello['api_version'])
   if not ack['accepted']:return meta,None
   note=await read_message(reader,65536)
   require(isinstance(note,dict) and set(note)=={'jsonrpc','method','params'} and note.get('jsonrpc')=='2.0' and note.get('method')=='robot.state',-32011)
   state=telemetry.validate_state(note['params']);return {**meta,'status':'ok','source_time_ns':str(state['t_ns']) if 't_ns' in state else None},state
 except TimeoutError:return meta,None
 finally:
  if writer:writer.close();await writer.wait_closed()


class StateSnapshots:
 def __init__(self,directory,clock=time.monotonic):self.directory=directory;self.clock=clock;self.entries={};self.pending=0
 def purge(self):
  now=self.clock();require(telemetry.number(now) and now>=0,-32011)
  self.entries={k:v for k,v in self.entries.items() if v['created']<=now<v['created']+5};return now
 async def capture(self,hz):
  self.purge()
  if len(self.entries)+self.pending>=4:return {'simulation':True,'physical_movement_enabled':False,'kind':'telemetry_capture','status':'busy'}
  self.pending+=1
  try:
   meta,state=await capture_state(self.directory,hz)
   if state is None:return meta
   now=self.purge();handle=secrets.token_hex(16);require(handle not in self.entries,-32011)
   self.entries[handle]={'state':state,'created':now}
   return {**meta,'handle':handle,'expires_in_ms':5000}
  finally:self.pending-=1
 def reading(self,handle,field,index,component):
  self.purge();entry=self.entries.get(handle)
  if entry is None:return {'simulation':True,'physical_movement_enabled':False,'kind':'telemetry_reading','status':'expired_or_unknown','value':None,'unit':telemetry.unit_for(field,component),'field':field,'index':index,'component':component}
  return telemetry.sample(entry['state'],field,index,component)
 def release(self,handle):
  self.purge();removed=self.entries.pop(handle,None)
  return {'simulation':True,'physical_movement_enabled':False,'kind':'telemetry_release','status':'released' if removed else 'not_retained'}


class RobotGateway(SensorGateway):
 def __init__(self,upstreams,directory,preview,motion):
  super().__init__(upstreams,directory);self.preview=preview;self.motion=motion;self.state_snapshots=StateSnapshots(directory)
 async def dispatch(self,request):
  if isinstance(request,dict) and isinstance(request.get('method'),str) and request['method'] in METHODS:
   name,p=validate(request)
   if name=='preview':value=self.preview.record(p['method'],p['args'],request.get('confirmed',False))
   elif name=='capture':value=await self.state_snapshots.capture(p['hz'])
   elif name=='release':value=self.state_snapshots.release(p['handle'])
   elif name=='reading':value=self.state_snapshots.reading(p['handle'],p['field'],p['index'],p['component'])
   else:
    model,version=await self.upstreams['robot'].call('robot.model',{},request['id'])
    require(isinstance(model,dict) and telemetry.text(model.get('asset')) and isinstance(model.get('joint_names'),list) and len(model['joint_names'])<=128 and all(telemetry.text(n) for n in model['joint_names']) and isinstance(model.get('skeleton'),list) and len(model['skeleton'])<=128 and all(isinstance(x,dict) and telemetry.text(x.get('name')) for x in model['skeleton']),-32011)
    value={'simulation':True,'physical_movement_enabled':False,'kind':'model_metadata','asset':model.get('asset'),'joint_count':len(model['joint_names']),'skeleton_link_count':len(model['skeleton']),'joint_names':model['joint_names'],'skeleton_names':[x['name'] for x in model['skeleton']],'calibration':'not_modelled','reported_api_version':version}
   encode({'jsonrpc':'2.0','id':0x7fffffff,'result':value},760);return value,None
  if isinstance(request,dict) and isinstance(request.get('method'),str) and request['method'] in MOTION_METHODS:
   method,p=validate_motion(request)
   state=self.motion.run(p,request.get('confirmed',False)) if method==MOTION_PREFIX+'run' else self.motion.cancel() if method==MOTION_PREFIX+'cancel' else self.motion.snapshot()
   return MotionGateway._reply(state),None
  return await super().dispatch(request)


class RobotSimulator(SensorSimulator):
 def __init__(self,directory,allow_control_previews=False,allow_motion=False,profile='normal'):
  super().__init__(directory,profile);self.preview=PreviewRecorder(allow_control_previews);self.motion=MotionSimulation(allow_motion);self.state_subscriptions=0
 def _make_gateway(self,allowed):return RobotGateway({'robot':{'path':str(self.directory/'robot.sock'),'uid':os.geteuid()}},self.directory,self.preview,self.motion)
 async def start(self):
  try:
   await super().start();self.ready.update(robot_simulation=True,api_version=telemetry.API_VERSION,upstream_commit=telemetry.SOURCE_COMMIT,allow_control_previews=self.preview.allowed,physical_movement_enabled=False,robot_methods=sorted(METHODS),allow_motion_simulation=self.motion.allow_motion)
   _fresh_file(self.directory/'robot-simulation.json',self.ready);return self
  except BaseException:await self.stop();raise
 def result(self,method,params):
  if method=='robot.model':return {'simulation':True,'asset':'SIMULATION_UNCALIBRATED','joint_names':list(telemetry.JOINT_NAMES),'head_joints':list(telemetry.JOINT_NAMES[5:9]),'skeleton':[{'name':'SIMULATION_trunk'},{'name':'SIMULATION_head','parent':0}]}
  if method=='robot.policies':return {**super().result(method,params),'slots':[{'slot':k,'path':v,'error':'SIMULATION not loaded'} for k,v in SLOTS.items()]}
  return super().result(method,params)
 async def handle(self,reader,writer):
  task=asyncio.current_task();self.tasks.add(task);self.clients.add(writer);counted=False
  try:
   require(peer_uid(writer.get_extra_info('socket'))==os.geteuid() and self.active<4,-32001);self.active+=1;counted=True
   async with asyncio.timeout(3):
    hello=await read_message(reader,8192)
    require(isinstance(hello,dict) and hello.get('method')=='hello' and type(hello.get('id')) is int and hello['id']==0 and hello.get('jsonrpc')=='2.0' and isinstance(hello.get('params'),dict) and set(hello['params'])=={'api_version'} and telemetry.integer(hello['params']['api_version'],1,255),-32011)
    writer.write(encode({'jsonrpc':'2.0','id':0,'result':{'api_version':telemetry.API_VERSION,'daemon_version':'0.0.0','revision':'SIMULATION_API45_fixture'}},65536));await writer.drain()
    call=await read_message(reader,8192)
    require(isinstance(call,dict) and call.get('jsonrpc')=='2.0' and telemetry.integer(call.get('id'),1,0x7fffffff) and isinstance(call.get('params'),dict),-32011)
    if call.get('method')=='robot.subscribe':
     p=call['params'];require(not set(p)-{'hz'} and ('hz' not in p or telemetry.integer(p['hz'],1,50)))
     self.state_subscriptions+=1
     writer.write(encode({'jsonrpc':'2.0','id':call['id'],'result':{'accepted':True,'unavailable':'SIMULATION no controller'}},65536))
     if self.profile=='normal':writer.write(encode({'jsonrpc':'2.0','method':'robot.state','params':state_fixture()},65536))
     await writer.drain();await reader.read(1)
    else:
     require(call.get('method') in ('robot.health','robot.policies','robot.skills','robot.model') and not call['params'],-32601)
     writer.write(encode({'jsonrpc':'2.0','id':call['id'],'result':self.result(call['method'],call['params'])},65536));await writer.drain()
  except (RpcError,OSError,TimeoutError):pass
  finally:
   if counted:self.active-=1
   writer.close()
   try:await writer.wait_closed()
   except OSError:pass
   self.tasks.discard(task);self.clients.discard(writer)
 async def stop(self):
  store=self.gateway.state_snapshots if self.gateway else None;self.motion.close();await super().stop()
  if store:store.entries.clear()


async def main(args):
 service=RobotSimulator(args.directory,args.allow_control_previews,args.allow_motion,args.fixture);stopped=asyncio.Event();loop=asyncio.get_running_loop()
 for signum in (signal.SIGINT,signal.SIGTERM):loop.add_signal_handler(signum,stopped.set)
 try:
  await service.start();print(json.dumps(service.ready,separators=(',',':')),flush=True);await stopped.wait()
 finally:await service.stop()


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--directory',required=True,type=Path);parser.add_argument('--allow-control-previews',action='store_true');parser.add_argument('--allow-motion',action='store_true');parser.add_argument('--fixture',choices=('normal','absent'),default='normal');args=parser.parse_args()
 if sys.platform!='linux':parser.error('Linux peer credentials required')
 try:asyncio.run(main(args))
 except (ValueError,OSError,RpcError) as error:parser.exit(1,f'Robot simulation refused: {error}\n')
