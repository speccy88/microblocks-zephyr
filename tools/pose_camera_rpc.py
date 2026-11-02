"""Bounded P4 camera RPC over the editor's existing serial controller."""
# SPDX-License-Identifier: MIT
import asyncio
from dataclasses import dataclass
import json
import secrets
import struct
import time
from pose_tracker import Tracker,Sample,candidates,GESTURES
from pose_eyes import load_model,unpack_gray4,DEFAULT_MODEL

async def inference_work(function,*args):
    # Cancellation must not close MediaPipe while its native worker uses it.
    task=asyncio.create_task(asyncio.to_thread(function,*args))
    try:return await asyncio.shield(task)
    except asyncio.CancelledError:
        await task
        raise


def request_packet(operation,request,session=0,offset=0,count=0):
    if not 0<=operation<=4 or not 0<=request<=0xffffffff or not 0<=session<=0x1fffffff:
        raise ValueError('Invalid camera RPC operation/session')
    if operation and not session:raise ValueError('Camera session required')
    if not 0<=count<=512 or offset<0:raise ValueError('Camera chunk limit')
    if operation!=3 and (offset or count):raise ValueError('Unexpected camera range')
    if operation==3 and (not count or offset>10368 or count>10368-offset):raise ValueError('Camera packed range')
    body=struct.pack('<4sBBHIIIHH',b'P4CP',1,operation,0,request,session,offset,count,0)
    return bytes((251,211,0,25,0))+body+b'\xfe'


@dataclass(frozen=True)
class Reply:
    operation:int
    status:int
    state:int
    request:int
    session:int
    data:bytes


def decode_reply(frame):
    if len(frame)<21 or frame[:2]!=bytes((251,211)) or int.from_bytes(frame[3:5],'little')!=len(frame)-5:
        raise ValueError('Invalid camera reply frame')
    magic,version,operation,status,state,request,session=struct.unpack('<4sBBBBII',frame[5:21])
    if magic!=b'P4CP' or version!=1 or operation>4 or status>6 or state>3 or len(frame)>533:
        raise ValueError('Invalid camera reply contract')
    return Reply(operation,status,state,request,session,bytes(frame[21:]))


class FrameReader:
    def __init__(self):self.buffer=bytearray()
    def feed(self,data):
        self.buffer.extend(data)
        if len(self.buffer)>16384:raise ValueError('Serial frame buffer limit')
        out=[]
        while self.buffer:
            if self.buffer[0]==250:size=3
            elif self.buffer[0]==251:
                if len(self.buffer)<5:break
                size=5+int.from_bytes(self.buffer[3:5],'little')
                if size>8197:raise ValueError('Serial frame size limit')
            else:raise ValueError('Unframed serial response')
            if len(self.buffer)<size:break
            out.append(bytes(self.buffer[:size]));del self.buffer[:size]
        return out


class AsyncCameraRPC:
    def __init__(self,send):self.send=send;self.pending={};self.sequence=0;self.closed=False
    def accept(self,frame):
        reply=decode_reply(frame)
        entry=self.pending.get(reply.request)
        if entry:
            operation,session,future=entry
            if reply.operation==operation and reply.session==session and not future.done():future.set_result(reply)
    async def request(self,operation,session=0,offset=0,count=0):
        if self.closed:raise RuntimeError('Camera controller disconnected')
        if len(self.pending)>=4:raise RuntimeError('Camera request queue limit')
        self.sequence=(self.sequence+1)&0xffffffff
        request=self.sequence;packet=request_packet(operation,request,session,offset,count)
        future=asyncio.get_running_loop().create_future();self.pending[request]=(operation,session,future)
        try:
            deadline=time.monotonic()+3
            while not self.send(packet):
                if time.monotonic()>deadline:raise TimeoutError('Editor upload prevented camera insertion')
                await asyncio.sleep(.002)
            return await asyncio.wait_for(future,5)
        finally:self.pending.pop(request,None)
    def close(self):
        self.closed=True
        for _,_,future in self.pending.values():
            if not future.done():future.cancel()


async def capture_frame(rpc,session):
    """No VM chunk uploads. Always release only this session's owned frame."""
    started=await rpc.request(1,session)
    if started.status:return None
    try:
        deadline=time.monotonic()+8
        while True:
            reply=await rpc.request(2,session)
            if reply.status:raise RuntimeError('P4 camera status '+str(reply.status))
            if reply.state==2:break
            if reply.state!=1 or time.monotonic()>deadline:raise TimeoutError('P4 camera capture did not become ready')
            await asyncio.sleep(.03)
        meta=json.loads(reply.data)
        if (meta.get('width'),meta.get('height'),meta.get('bytes'))!=(192,108,10368):raise ValueError('Unexpected pose camera dimensions')
        age=meta.get('age_ms')
        if type(age) is not int or not 0<=age<=10000:raise ValueError('Invalid camera frame age')
        captured=time.monotonic()-age/1000
        raw=bytearray()
        for offset in range(0,10368,512):
            n=min(512,10368-offset);part=await rpc.request(3,session,offset,n)
            if part.status or len(part.data)!=n:raise RuntimeError('P4 camera chunk rejected or truncated')
            raw.extend(part.data)
        return bytes(raw),captured
    finally:
        await rpc.request(4,session)


class P4PoseProducer:
    def __init__(self,rpc,model=DEFAULT_MODEL,mirror=False,tracking_mode='both',face_model=None):
        self.rpc,self.model_path,self.mirror=rpc,model,mirror
        self.tracking_mode,self.face_model=tracking_mode,face_model
        self.stats={'frames':0,'person_frames':0,'face_frames':0,'stale_frames':0,'errors':0}
    async def run(self,send):
        from face_tracker import FaceTracker,FaceSample,DEFAULT_FACE_MODEL
        model=None;face=None;warmed=False
        tracker=Tracker(mirror=self.mirror,max_gap=3,wave_window=4)
        sequence=0;active=False
        def infer(raw,captured):
            import cv2
            frame=cv2.cvtColor(unpack_gray4(raw),cv2.COLOR_GRAY2BGR)
            f=face.infer(frame,captured) if face else FaceSample()
            people=candidates(model.predict(frame,imgsz=320,conf=.5,verbose=False)[0]) if model else []
            if face and f.visible:
                fx=(1000-f.x if self.mirror else f.x)/1000;fy=f.y/1000
                people=[p for p in people if p['box'][0]<=fx<=p['box'][2] and p['box'][1]<=fy<=p['box'][3]]
            return people,f
        try:
            while True:
                caps=await self.rpc.request(0)
                if caps.status:raise RuntimeError('Pose camera capability query failed')
                enabled=json.loads(caps.data).get('enabled') is True
                if not enabled:
                    if active:
                        sequence+=1;send(Sample().packet(sequence));send(FaceSample().packet(sequence));active=False;tracker.reset()
                    await asyncio.sleep(.25);continue
                active=True
                if not warmed:
                    if self.tracking_mode!='face':model=await asyncio.to_thread(load_model,self.model_path)
                    if self.tracking_mode!='pose':face=await asyncio.to_thread(FaceTracker,self.face_model or DEFAULT_FACE_MODEL,self.mirror)
                    # First inference can take seconds; warm up before a live acquisition.
                    await inference_work(infer,bytes(10368),time.monotonic());warmed=True
                    continue
                session=secrets.randbelow(0x1ffffffe)+1
                try:
                    frame=await capture_frame(self.rpc,session)
                    if frame is None:await asyncio.sleep(.10);continue
                    raw,captured=frame
                    people,f=await inference_work(infer,raw,captured)
                    current=await self.rpc.request(0)
                    if current.status or json.loads(current.data).get('enabled') is not True:
                        sequence+=1;send(Sample().packet(sequence));send(FaceSample().packet(sequence));continue
                    sample=tracker.update(people,captured)
                    self.stats['frames']+=1
                    if time.monotonic()-captured>2:sample=Sample();f=FaceSample();self.stats['stale_frames']+=1
                    self.stats['person_frames']+=int(sample.visible)
                    self.stats['face_frames']+=int(f.visible)
                    sequence+=1;send(sample.packet(sequence));send(f.packet(sequence))
                    if self.stats['frames']==1 or self.stats['frames']%5==0:
                        print(json.dumps(dict(source='P4 camera',tracking=self.tracking_mode,**self.stats,gesture=GESTURES[sample.gesture])),flush=True)
                except (ValueError,RuntimeError,TimeoutError) as error:
                    self.stats['errors']+=1
                    sequence+=1;send(Sample().packet(sequence));send(FaceSample().packet(sequence))
                    print('P4 pose capture: '+str(error),flush=True);await asyncio.sleep(.5)
        finally:
            if face:await asyncio.to_thread(face.close)
            print('P4 pose summary: '+json.dumps(self.stats),flush=True)
