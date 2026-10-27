"""API45 robot.state shapes and bounded scalar readings; no controller/physics."""
# SPDX-License-Identifier: MIT
import copy
import math
try:
 from .protocol import RpcError
except ImportError:
 from protocol import RpcError

SOURCE_COMMIT='5def2f3e66501f0f365d4fb1183020b8ee875443'
API_VERSION=45
JOINT_NAMES=('left_hip_yaw','left_hip_roll','left_hip_pitch','left_knee','left_ankle','neck_pitch','head_pitch','head_yaw','head_roll','mouth','right_hip_yaw','right_hip_roll','right_hip_pitch','right_knee','right_ankle')
# field -> (largest index, largest component). This is a lab resource bound,
# not a claim that an arbitrary shipping model has that many joints/links.
FIELDS={
 'move.requested':(1,3),'move.applied':(1,3),'move.limit_count':(1,1),'move.limited_by':(64,1),
 'loop.hz':(1,1),'loop.missed':(1,1),'safety.fallen':(1,1),'safety.limp':(1,1),'safety.picked_up':(1,1),'safety.gain':(1,1),'safety.gravity':(1,3),
 'joints':(128,1),'targets':(128,1),'velocities':(128,1),'currents_ma':(128,1),
 'odom.position':(1,3),'odom.yaw':(1,1),'imu.gyro':(1,3),'imu.quat':(1,4),
 'frames.camera.pos':(1,3),'frames.camera.quat':(1,4),'frames.tof.pos':(1,3),'frames.tof.quat':(1,4),
 'frames.head_imu.pos':(1,3),'frames.head_imu.quat':(1,4),'skeleton.pos':(128,3),'skeleton.quat':(128,4),
 't_ns':(1,1),'policy':(1,1)}


def require(good):
 if not good:raise RpcError(-32011,'Invalid bounded robot state or selector')


def number(value):
 try:return type(value) in (int,float) and math.isfinite(value)
 except OverflowError:return False


def integer(value,low,high):return type(value) is int and low<=value<=high
def text(value):
 if not isinstance(value,str) or len(value)>128 or any(ord(c)<32 or ord(c)==127 for c in value):return False
 try:value.encode('utf-8');return True
 except UnicodeError:return False
def vector(value,size):return isinstance(value,list) and len(value)==size and all(number(v) for v in value)
def pose(value):return isinstance(value,dict) and all(k not in value or vector(value[k],n) for k,n in [('pos',3),('quat',4)])


def validate_state(s):
 require(isinstance(s,dict) and number(s.get('t')) and s['t']>=0 and vector(s.get('head'),4) and text(s.get('policy')))
 move=s.get('move');require(isinstance(move,dict) and vector(move.get('requested'),3) and vector(move.get('applied'),3))
 if 'limited_by' in move:require(isinstance(move['limited_by'],list) and len(move['limited_by'])<=64 and all(text(v) for v in move['limited_by']))
 safety=s.get('safety');require(isinstance(safety,dict) and type(safety.get('fallen')) is bool and type(safety.get('limp')) is bool)
 if 'gravity' in safety:require(vector(safety['gravity'],3))
 if 'gain' in safety:require(safety['gain'] is None or integer(safety['gain'],0,65535))
 if 'picked_up' in safety:require(type(safety['picked_up']) is bool)
 loop=s.get('loop');require(isinstance(loop,dict) and number(loop.get('hz')) and loop['hz']>=0 and integer(loop.get('missed'),0,2**64-1))
 for name in ('joints','targets','velocities','currents_ma'):
  if name in ('joints','targets') or name in s:
   value=s.get(name);require(isinstance(value,list) and len(value)<=128 and all(number(v) and (name!='currents_ma' or v>=0) for v in value))
 if 'odom' in s:
  value=s['odom'];require(isinstance(value,dict) and vector(value.get('position'),3) and number(value.get('yaw')))
 if s.get('imu') is not None:
  value=s['imu'];require(isinstance(value,dict) and all(k not in value or vector(value[k],n) for k,n in [('gyro',3),('quat',4)]))
 if s.get('frames') is not None:
  value=s['frames'];require(isinstance(value,dict))
  for name in ('camera','tof','head_imu'):
   if name in value:require(name=='head_imu' and value[name] is None or pose(value[name]))
 if 'skeleton' in s:require(isinstance(s['skeleton'],list) and len(s['skeleton'])<=128 and all(pose(v) for v in s['skeleton']))
 if 't_ns' in s:require(integer(s['t_ns'],0,2**64-1))
 return copy.deepcopy(s)


def unit_for(field,component=1):
 if field in ('move.requested','move.applied'):return 'mrad/s' if component==3 else 'mm/s'
 if field=='move.limit_count':return 'count'
 if field in ('move.limited_by','policy'):return 'text'
 if field=='loop.hz':return 'mHz'
 if field=='loop.missed':return 'count64'
 if field in ('safety.fallen','safety.limp','safety.picked_up'):return 'boolean'
 if field=='safety.gain':return 'gain'
 if field=='safety.gravity' or field.endswith('.quat'):return 'ppm'
 if field in ('joints','targets','odom.yaw'):return 'mrad'
 if field in ('velocities','imu.gyro'):return 'mrad/s'
 if field=='currents_ma':return 'uA'
 if field=='t_ns':return 'ns'
 return 'mm'


def sample(state,field,index=1,component=1):
 require(isinstance(field,str) and field in FIELDS)
 limits=FIELDS[field];require(integer(index,1,limits[0]) and integer(component,1,limits[1]))
 result={'simulation':True,'physical_movement_enabled':False,'kind':'telemetry_reading','status':'not_reported','value':None,'unit':'','field':field,'index':index,'component':component}
 value=None;scale=1;unit=unit_for(field,component)
 if field.startswith('move.'):
  move=state['move']
  if field in ('move.requested','move.applied'):value=move[field.split('.')[1]][component-1];scale=1000;unit='mrad/s' if component==3 else 'mm/s'
  elif field=='move.limit_count':
   value=len(move.get('limited_by',[]));unit='count'
   if 'limited_by' not in move:result['source_default']=True
  elif 'limited_by' in move and index<=len(move['limited_by']):value=move['limited_by'][index-1];unit='text'
 elif field=='loop.hz':value=state['loop']['hz'];scale=1000;unit='mHz'
 elif field=='loop.missed':value=str(state['loop']['missed']);unit='count64'
 elif field.startswith('safety.'):
  name=field.split('.')[1];value=state['safety'].get(name)
  if name=='gravity':value=None if value is None else value[component-1];scale=1000000;unit='ppm'
  else:unit='gain' if name=='gain' else 'boolean'
 elif field in ('joints','targets','velocities','currents_ma'):
  values=state.get(field,[]);value=values[index-1] if index<=len(values) else None
  scale=1000;unit='uA' if field=='currents_ma' else 'mrad/s' if field=='velocities' else 'mrad'
 elif field.startswith('odom.'):
  odom=state.get('odom',{});name=field.split('.')[1];value=odom.get(name)
  if name=='position':value=None if value is None else value[component-1]
  scale=1000;unit='mm' if name=='position' else 'mrad'
 elif field.startswith('imu.'):
  imu=state.get('imu') or {};name=field.split('.')[1];values=imu.get(name)
  value=None if values is None else values[component-1];scale=1000 if name=='gyro' else 1000000;unit='mrad/s' if name=='gyro' else 'ppm'
 elif field.startswith('frames.'):
  _,name,part=field.split('.');values=((state.get('frames') or {}).get(name) or {}).get(part)
  value=None if values is None else values[component-1];scale=1000 if part=='pos' else 1000000;unit='mm' if part=='pos' else 'ppm'
 elif field.startswith('skeleton.'):
  poses=state.get('skeleton',[]);values=poses[index-1].get(field.split('.')[1]) if index<=len(poses) else None
  value=None if values is None else values[component-1];scale=1000 if field.endswith('.pos') else 1000000;unit='mm' if field.endswith('.pos') else 'ppm'
 elif field=='t_ns':value=str(state['t_ns']) if state.get('t_ns',0)>0 else None;unit='ns'
 elif field=='policy':value=state['policy'];unit='text'
 result['unit']=unit
 if value is None:return result
 if unit=='boolean':require(type(value) is bool)
 elif unit in ('text','ns','count64'):
  require(isinstance(value,str))
  if len(value.encode('utf-8'))>128:return {**result,'status':'out_of_range'}
 else:
  require(number(value));scaled=float(value)*scale
  if not math.isfinite(scaled):return {**result,'status':'out_of_range'}
  rounded=math.floor(scaled+.5) if scaled>=0 else math.ceil(scaled-.5)
  if not -1073741824<=rounded<=1073741823:return {**result,'status':'out_of_range'}
  value=rounded
 return {**result,'status':'ok','value':value}


def fixture():
 """Fictional source-shaped data; values never model controller admission/physics."""
 return {'t':234.5,'move':{'requested':[.125,-.05,.3],'applied':[0.0,0.0,0.0],'limited_by':['SIMULATION_fixture_limit']},
 'head':[0.0]*4,'policy':'held','safety':{'fallen':False,'limp':True,'gravity':[0.0,0.0,-1.0],'gain':None,'picked_up':False},
 'loop':{'hz':48.5,'missed':2**63+1},'joints':[i/100 for i in range(15)],'targets':[(i+1)/100 for i in range(15)],
 'velocities':[-.2+i/100 for i in range(15)],'currents_ma':[i*1.25 for i in range(15)],
 'odom':{'position':[0.0,0.0,0.0],'yaw':.1},'t_ns':2**63+123,
 'imu':{'gyro':[.1,.2,-.1],'quat':[1.0,0.0,0.0,0.0]},
 'frames':{'camera':{'pos':[.1,.02,.3],'quat':[1.0,0.0,0.0,0.0]},'tof':{'pos':[.12,.01,.25],'quat':[1.0,0.0,0.0,0.0]}},
 'skeleton':[{'pos':[0.0,0.0,0.0],'quat':[1.0,0.0,0.0,0.0]},{'pos':[.1,.02,.3],'quat':[1.0,0.0,0.0,0.0]}]}
