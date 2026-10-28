"""Bounded source-reported ModelResult views; no FK or calibrated geometry."""
# SPDX-License-Identifier: MIT
import copy
import math
try:
    from . import robot_telemetry as state
except ImportError:
    import robot_telemetry as state

# field -> index bound, component bound, unit, scale
FIELDS = {
    'asset': (1,1,'text',1), 'trunk_height_m': (1,1,'mm',1000),
    'joint_count': (1,1,'count',1), 'joint_name': (128,1,'text',1),
    'head_joint_count': (1,1,'count',1), 'head_joint_name': (4,1,'text',1),
    'tof_beam_count': (1,1,'count',1), 'tof_beam': (64,3,'ppm',1000000),
    'tof_fov_deg': (1,1,'mdeg',1000),
    'frames.camera.pos': (1,3,'mm',1000), 'frames.camera.quat': (1,4,'ppm',1000000),
    'frames.tof.pos': (1,3,'mm',1000), 'frames.tof.quat': (1,4,'ppm',1000000),
    'frames.head_imu.pos': (1,3,'mm',1000), 'frames.head_imu.quat': (1,4,'ppm',1000000),
    'skeleton_count': (1,1,'count',1), 'skeleton_name': (128,1,'text',1),
    'skeleton_parent': (128,1,'index1_or_root0',1),
}

def validate_model(value):
    state.require(isinstance(value,dict))
    if 'asset' in value: state.require(state.text(value['asset']))
    for field in ('trunk_height_m','tof_fov_deg'):
        if field in value: state.require(state.number(value[field]))
    for field,bound in (('joint_names',128),('head_joints',4)):
        if field in value:
            data=value[field];state.require(isinstance(data,list) and len(data)<=bound and all(state.text(x) for x in data))
    if 'tof_beams' in value:
        data=value['tof_beams'];state.require(isinstance(data,list) and len(data)<=64 and all(state.vector(x,3) for x in data))
    if 'frames_at_zero' in value:
        data=value['frames_at_zero'];state.require(isinstance(data,dict))
        for name in ('camera','tof','head_imu'):
            if name in data:state.require(name=='head_imu' and data[name] is None or state.pose(data[name]))
    if 'skeleton' in value:
        data=value['skeleton'];state.require(isinstance(data,list) and len(data)<=128)
        for entry in data:
            state.require(isinstance(entry,dict) and state.text(entry.get('name')))
            if entry.get('parent') is not None:state.require(state.integer(entry['parent'],0,len(data)-1))
    return copy.deepcopy(value)

def sample(value,field,index=1,component=1):
    a,b,unit,scale=FIELDS[field];state.require(state.integer(index,1,a) and state.integer(component,1,b))
    raw=None;default=False
    if field in ('asset','trunk_height_m','tof_fov_deg'):raw=value.get(field)
    elif field.startswith('frames.'):
        _,name,part=field.split('.');data=((value.get('frames_at_zero') or {}).get(name) or {}).get(part)
        if data is not None:raw=data[component-1]
    else:
        collection={'joint_count':'joint_names','joint_name':'joint_names','head_joint_count':'head_joints','head_joint_name':'head_joints','tof_beam_count':'tof_beams','tof_beam':'tof_beams','skeleton_count':'skeleton','skeleton_name':'skeleton','skeleton_parent':'skeleton'}[field]
        data=value.get(collection)
        if data is not None:
            if field.endswith('_count'):raw=len(data)
            elif index<=len(data):
                raw=data[index-1]
                if field=='tof_beam':raw=raw[component-1]
                elif field=='skeleton_name':raw=raw['name']
                elif field=='skeleton_parent':
                    default='parent' not in raw;parent=raw.get('parent');raw=0 if parent is None else parent+1
    out={'kind':'robot_reading','snapshot_kind':'model','status':'not_reported','field':field,'index':index,'component':component,'unit':unit,'value':None}
    if raw is None:return out
    if unit=='text':
        if not raw:return out
        if len(raw.encode('utf-8'))>128:return {**out,'status':'out_of_range'}
    else:
        scaled=float(raw)*scale
        if not math.isfinite(scaled):return {**out,'status':'out_of_range'}
        raw=math.floor(scaled+.5) if scaled>=0 else math.ceil(scaled-.5)
        if not -(2**30)<=raw<2**30:return {**out,'status':'out_of_range'}
    return {**out,'status':'ok','value':raw,**({'source_default':True} if default else {})}
