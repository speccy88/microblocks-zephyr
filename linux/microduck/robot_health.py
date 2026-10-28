"""Reviewed HealthResult scalar views; source defaults are distinct from readings."""
# SPDX-License-Identifier: MIT
import copy
import math
try:
    from . import robot_telemetry as state
except ImportError:
    import robot_telemetry as state

# selector -> unit, conversion scale. Counters remain exact decimal strings.
FIELDS = {
    'healthy': ('boolean', 1), 'degraded': ('boolean', 1), 'health.state': ('state', 1),
    'battery.percent': ('0.01%', 100), 'battery.volts': ('mV', 1000),
    'cpu_temp_c': ('mC', 1000), 'motors.max_c': ('mC', 1000), 'motors.mean_c': ('mC', 1000),
    'control_loop.target_hz': ('mHz', 1000), 'control_loop.achieved_hz': ('mHz', 1000),
    'control_loop.last_tick_age_ms': ('ms64', 1), 'control_loop.ticks': ('count64', 1),
    'control_loop.missed': ('count64', 1), 'bus.consecutive_errors': ('count64', 1),
    'bus.startup_failures': ('count64', 1), 'imu.ready': ('boolean', 1), 'imu.missing': ('boolean', 1),
    'imu.stale_blocks': ('count64', 1), 'imu.consecutive_stale_blocks': ('count64', 1),
    'imu.state': ('state', 1), 'reason': ('text', 1),
    'motors.hottest': ('text', 1),
    'cpu_throttle.level': ('count64', 1), 'cpu_throttle.max_level': ('count64', 1),
    'cpu_throttle.khz': ('kHz64', 1), 'cpu_throttle.max_khz': ('kHz64', 1),
    'cpu_throttle.throttled': ('boolean', 1),
}
DEFAULT_FIELDS = frozenset(('degraded', 'health.state', 'bus.consecutive_errors', 'bus.startup_failures',
                           'imu.ready', 'imu.missing', 'imu.stale_blocks', 'imu.consecutive_stale_blocks', 'imu.state'))


def validate_health(value):
    state.require(isinstance(value, dict) and type(value.get('healthy')) is bool)
    if 'degraded' in value: state.require(type(value['degraded']) is bool)
    if value.get('reason') is not None: state.require(state.text(value['reason']) or isinstance(value['reason'], str) and not any(ord(c)<32 or ord(c)==127 for c in value['reason']))
    if value.get('cpu_temp_c') is not None: state.require(state.number(value['cpu_temp_c']))
    if value.get('cpu_throttle') is not None:
        part=value['cpu_throttle'];state.require(isinstance(part,dict))
        state.require(all(k not in part or state.integer(part[k],0,2**32-1) for k in ('level','max_level','khz','max_khz')))
    for section, fields in [('battery', ('volts','percent')), ('motors', ('max_c','mean_c')),
                            ('control_loop', ('target_hz',))]:
        if value.get(section) is not None:
            part=value[section];state.require(isinstance(part,dict) and all(state.number(part.get(k)) for k in fields))
            if section=='motors': state.require(isinstance(part.get('hottest'),str))
            if section=='control_loop':
                state.require(part.get('achieved_hz') is None or state.number(part['achieved_hz']))
                state.require(all(state.integer(part.get(k),0,2**64-1) for k in ('ticks','missed','last_tick_age_ms')))
    for section, fields, maximum in [('bus',('consecutive_errors','startup_failures'),2**32-1),
                                     ('imu',('stale_blocks','consecutive_stale_blocks'),2**64-1)]:
        if section in value:
            part=value[section]
            if section=='imu' and part is None: continue
            state.require(isinstance(part,dict) and all(k not in part or state.integer(part[k],0,maximum) for k in fields))
            if section=='imu': state.require(all(k not in part or type(part[k]) is bool for k in ('ready','missing')))
    return copy.deepcopy(value)


def sample(value, field):
    unit,scale=FIELDS[field];default=False;raw=None
    if field=='health.state':
        raw='healthy' if value['healthy'] else 'degraded' if value.get('degraded',False) else 'unhealthy'
        default='degraded' not in value and not value['healthy']
    elif field=='imu.state':
        imu=value.get('imu')
        if imu is not None:
            raw='missing' if imu.get('missing',False) else 'frozen' if imu.get('consecutive_stale_blocks',0)>=25 else 'converged' if imu.get('ready',False) else 'not_converged'
            default=any(k not in imu for k in ('missing','consecutive_stale_blocks','ready'))
    elif field=='cpu_throttle.throttled':
        part=value.get('cpu_throttle')
        if isinstance(part,dict) and all(k in part for k in ('level','khz','max_khz')):
            raw=part['level']>0 or part['max_khz']>0 and part['khz']<part['max_khz']
    elif '.' in field:
        section,key=field.split('.');part=value.get(section)
        if part is not None: raw=part.get(key)
        if field in DEFAULT_FIELDS and (section=='bus' and section not in value or isinstance(part,dict) and key not in part):
            raw=False if unit=='boolean' else 0;default=True
    elif field=='degraded':raw=value.get(field,False);default=field not in value
    else:raw=value.get(field)
    out={'kind':'robot_reading','snapshot_kind':'health','status':'not_reported','field':field,'index':1,'component':1,'unit':unit,'value':None}
    if raw is None:return out
    if unit in ('count64','ms64','kHz64'): raw=str(raw)
    elif unit in ('text','state'):
        if not state.text(raw) or len(raw.encode('utf-8'))>128:return {**out,'status':'out_of_range'}
    elif unit!='boolean':
        scaled=float(raw)*scale
        if not math.isfinite(scaled):return {**out,'status':'out_of_range'}
        raw=math.floor(scaled+.5) if scaled>=0 else math.ceil(scaled-.5)
        if not -(2**30)<=raw<2**30:return {**out,'status':'out_of_range'}
    return {**out,'status':'ok','value':raw,**({'source_default':True} if default else {})}
