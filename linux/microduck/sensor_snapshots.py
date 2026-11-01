"""Finite, immutable SIMULATION snapshots; no production endpoints or drive path."""
# SPDX-License-Identifier: MIT
import asyncio
import copy
import math
import os
import secrets
import time

try:
    from . import sensor_simulator as wire
    from .protocol import connect_checked, encode, read_message, response_result
except ImportError:
    import sensor_simulator as wire
    from protocol import connect_checked, encode, read_message, response_result

CAPACITY, TTL = 4, 5.0
METHODS = frozenset(wire.PREFIX + name for name in ('captureTof','capturePad','depthRow','padAxis','padButton','release'))


def token(value):
    return isinstance(value,str) and len(value)==32 and all(c in '0123456789abcdef' for c in value)


def validate(request):
    wire.require(isinstance(request,dict) and not set(request)-{'jsonrpc','id','method','params','confirmed'} and request.get('jsonrpc')=='2.0' and wire.integer(request.get('id'),1,0x7fffffff))
    method=request.get('method');wire.require(isinstance(method,str) and method in METHODS)
    wire.require('confirmed' not in request or type(request['confirmed']) is bool)
    name=method.removeprefix(wire.PREFIX);p=request.get('params',{});wire.require(isinstance(p,dict))
    if name in ('captureTof','capturePad'):wire.require(not p)
    elif name=='release':wire.require(set(p)=={'handle'} and token(p['handle']))
    elif name=='depthRow':wire.require(set(p)=={'handle','row'} and token(p['handle']) and wire.integer(p['row'],1,8))
    else:wire.require(set(p)=={'handle','code'} and token(p['handle']) and wire.integer(p['code'],0,65535))
    return name,dict(p)


def result(kind,status='waiting',**parts):
    return {'simulation':True,'physical_movement_enabled':False,'kind':kind,'status':status,**parts}


class PadWindow:
    """Cache only observed events; retained Attached values may predate subscription."""
    def __init__(self):
        self.device=None;self.axes={};self.buttons={};self.seq=None;self.frames=0
        self.at_us=self.since_us=None;self.status='waiting'

    def invalidate(self,status):
        for collection in (self.axes,self.buttons):
            for item in collection.values():item.update(status=status,value=None,event_seq=None)

    def apply(self,report):
        wire.require(isinstance(report,dict));tag=report.get('report')
        if tag=='attached':
            self.__init__();self.device=copy.deepcopy(wire.device_report(report.get('device')))
            self.axes={x['code']:{'min':x['min'],'max':x['max'],'value':None,'status':'unobserved','event_seq':None} for x in self.device['axes']}
            self.buttons={x['code']:{'value':None,'status':'unobserved','event_seq':None} for x in self.device['buttons']}
            return
        if tag=='detached':
            wire.require(wire.text(report.get('why')));self.__init__();self.status='detached';return
        if tag in ('imu_attached','imu','imu_detached'):return
        wire.require(tag=='frame' and self.device is not None)
        for name in ('seq','at_us','socket_dropped'):
            wire.require(wire.integer(report.get(name,0) if name=='socket_dropped' else report.get(name),0,2**64-1))
        wire.require(report.get('since_us') is None or wire.integer(report['since_us'],-2**63,2**63-1))
        wire.require(type(report.get('after_drop',False)) is bool and isinstance(report.get('events'),list) and len(report['events'])<=128)
        for event in report['events']:
            wire.require(isinstance(event,dict) and wire.integer(event.get('kind'),0,65535) and wire.integer(event.get('code'),0,65535) and wire.integer(event.get('value'),-2**31,2**31-1) and wire.text(event.get('name')))
            if event['kind']==3:
                axis=self.axes.get(event['code']);wire.require(axis is not None and axis['min']<=event['value']<=axis['max'])
            if event['kind']==1:wire.require(event['code'] in self.buttons)
        self.frames+=1
        bad_order=self.seq is not None and report['seq']!=self.seq+1
        if report.get('after_drop',False) or report.get('socket_dropped',0) or bad_order:
            self.invalidate('dropped')
        else:
            for event in report['events']:
                if event['kind'] in (1,3):
                    collection=self.axes if event['kind']==3 else self.buttons
                    collection[event['code']].update(value=event['value'],status='ok',event_seq=str(report['seq']))
        # Do not let a regressed frame make a later old packet look consecutive.
        if self.seq is None or report['seq']>=self.seq:
            self.seq=report['seq'];self.at_us=report['at_us'];self.since_us=report.get('since_us')
        self.status='ok'

    def snapshot(self):
        return copy.deepcopy({'axes':self.axes,'buttons':self.buttons,'seq':None if self.seq is None else str(self.seq),'at_us':None if self.at_us is None else str(self.at_us),'since_us':None if self.since_us is None else str(self.since_us),'frames':self.frames,'status':self.status})


async def capture(directory,kind):
    service,method=('tof','tof.stream') if kind=='tof' else ('pad','pad.input')
    writer=None;window=PadWindow();meta=result(kind+'_capture','timeout')
    try:
        async with asyncio.timeout(wire.DEADLINE):
            reader,writer=await connect_checked(directory/(service+'.sock'),os.geteuid(),wire.LINE_LIMIT,True)
            writer.write(encode({'jsonrpc':'2.0','id':1,'method':method,'params':{}},wire.LINE_LIMIT));await writer.drain()
            description=response_result(await read_message(reader,wire.LINE_LIMIT),1)
            if kind=='tof':
                sample=wire.tof_result(description,None,1,1);meta=result('tof_capture',sample['status'])
            else:
                wire.require(isinstance(description,dict) and type(description.get('accepted')) is bool)
                meta=result('pad_capture','waiting' if description['accepted'] else 'refused')
            if meta['status']!='waiting':return meta,None
            for _ in range(wire.EVENTS):
                report=wire.notification(await read_message(reader,wire.LINE_LIMIT),'tof.frame' if kind=='tof' else 'pad.report')
                if kind=='tof':
                    sample=wire.tof_result(description,report,1,1)
                    return result('tof_capture','ok',seq=sample['seq'],at_us=sample['at_us'],t_ns=sample['t_ns'],rows=8,cols=8),copy.deepcopy(report)
                window.apply(report)
            # Reaching the explicit event cap is a bounded observation window too.
    except TimeoutError:
        pass
    finally:
        if writer:
            writer.close();await writer.wait_closed()
    if kind=='pad':
        state=window.snapshot()
        if state['frames']:
            return result('pad_capture','ok',seq=state['seq'],at_us=state['at_us'],frames=state['frames'],sample_basis='bounded_observed_events'),state
        return result('pad_capture',state['status'] if meta['status']!='timeout' else 'timeout'),None
    return meta,None


class SnapshotStore:
    def __init__(self,directory,clock=time.monotonic):
        self.directory=directory;self.clock=clock;self.entries={};self.pending=0;self.last_time=None

    def purge(self):
        now=self.clock();wire.require(type(now) in (int,float) and math.isfinite(now) and now>=0)
        if self.last_time is not None and now<self.last_time:self.entries.clear()
        self.last_time=now
        self.entries={h:x for h,x in self.entries.items() if x['expires']>now}
        return now

    async def acquire(self,kind):
        self.purge()
        if len(self.entries)+self.pending>=CAPACITY:return result(kind+'_capture','busy')
        self.pending+=1
        try:
            meta,state=await capture(self.directory,kind)
            if state is None:return meta
            now=self.purge();handle=secrets.token_hex(16)
            wire.require(handle not in self.entries)
            self.entries[handle]={'kind':kind,'state':state,'meta':copy.deepcopy(meta),'expires':now+TTL}
            return {**meta,'handle':handle,'expires_in_ms':int(TTL*1000)}
        finally:self.pending-=1

    def read(self,kind,handle,selector):
        self.purge();entry=self.entries.get(handle)
        label='depth_row' if kind=='tof' else 'axis_state' if kind=='axis' else 'button_state'
        if entry is None:return result(label,'expired_or_unknown')
        if entry['kind']!=('tof' if kind=='tof' else 'pad'):return result(label,'wrong_kind')
        state=entry['state']
        if kind=='tof':
            index=(selector-1)*8
            return result(label,'ok',handle=handle,row=selector,seq=str(state['seq']),distance_mm=state['distance_mm'][index:index+8],raw_status=state['status'][index:index+8])
        item=state['axes' if kind=='axis' else 'buttons'].get(selector)
        if item is None:return result(label,'unsupported',unit='raw' if kind=='axis' else 'pressed',value=None)
        value=item['value']
        sample=result(label,item['status'],unit='raw' if kind=='axis' else 'pressed',value=value if kind=='axis' or value is None else value!=0,code=selector,seq=state['seq'],event_seq=item['event_seq'],sample_basis='bounded_observed_events')
        if kind=='axis':sample.update(min=item['min'],max=item['max'])
        return sample

    def release(self,handle):
        self.purge();removed=self.entries.pop(handle,None)
        return result('release','released' if removed is not None else 'not_retained')

    def close(self):self.entries.clear()
