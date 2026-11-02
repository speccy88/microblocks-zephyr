"""Pure COCO-17 tracking and arm gestures; no camera, model or serial imports."""
# SPDX-License-Identifier: MIT
from collections import deque
from dataclasses import dataclass
import math
import struct

GESTURES = ('neutral', 'left hand up', 'right hand up', 'both hands up', 'arms out', 'wave')


class FrameMux:
    """Inject pose only between complete editor frames, never inside an upload."""
    def __init__(self,write):
        self.write=write;self.pending=bytearray()

    def feed(self,data):
        self.pending.extend(data)
        if len(self.pending)>16384:raise ValueError('Editor frame buffer limit')
        while self.pending:
            if self.pending[0]==250:
                size=3
            elif self.pending[0]==251:
                if len(self.pending)<5:return
                size=5+int.from_bytes(self.pending[3:5],'little')
                if size>8197:raise ValueError('Editor frame size limit')
            else:
                raise ValueError('Unframed editor data')
            if len(self.pending)<size:return
            self.write(bytes(self.pending[:size]));del self.pending[:size]

    def inject(self,packet):
        if self.pending:return False
        self.write(packet);return True


@dataclass(frozen=True)
class Sample:
    visible: bool = False
    x: int = 500
    y: int = 500
    confidence: int = 0
    gesture: int = 0

    def packet(self, sequence):
        body = struct.pack('<4sBBBBIHHHH', b'P4PS', 1, int(self.visible), self.gesture,
                           0, sequence & 0xffffffff, self.x, self.y, self.confidence, 0)
        return bytes((251, 210, 0, len(body)+1, 0)) + body + b'\xfe'


class Tracker:
    """Tracks one spatially continuous person. Coordinates are normalized 0..1.

    Candidates: {'box': [x1,y1,x2,y2], 'confidence': float,
    'keypoints': 17 triples of x,y,confidence}. Person labels are anatomical.
    """
    def __init__(self, mirror=False, threshold=.5, debounce=.25, smoothing=.12, max_gap=.75, wave_window=1.3):
        self.mirror, self.threshold = mirror, threshold
        self.debounce, self.smoothing = debounce, smoothing
        self.max_gap,self.wave_window=max_gap,wave_window
        self.reset()

    def reset(self):
        self.center = self.gaze = self.last_seen = self.last_update = None
        self.pending, self.since, self.gesture = 0, 0., 0
        self.wave = {9: deque(), 10: deque()}

    def _valid(self, person):
        try:
            box, points, conf = person['box'], person['keypoints'], person['confidence']
            if len(box)!=4 or len(points)!=17 or not math.isfinite(conf) or not self.threshold<=conf<=1:
                return False
            if not all(math.isfinite(v) and 0<=v<=1 for v in box) or box[2]<=box[0] or box[3]<=box[1]:
                return False
            return all(len(p)==3 and all(math.isfinite(v) and 0<=v<=1 for v in p) for p in points)
        except (KeyError, TypeError, ValueError):
            return False

    def update(self, people, now):
        if not math.isfinite(now):
            raise ValueError('Finite monotonic time required')
        if self.last_update is not None and now < self.last_update:
            self.reset()
        people = [p for p in people if self._valid(p)]
        if self.last_seen is not None and now-self.last_seen > self.max_gap:
            self.reset()
        def center(p):
            b=p['box'];return ((b[0]+b[2])/2,(b[1]+b[3])/2)
        if self.center is not None:
            # Hold the previous identity through brief occlusion; no jumping to
            # an unrelated person at the other side of the picture.
            people=[p for p in people if math.dist(center(p),self.center)<.30]
            person=min(people,key=lambda p:math.dist(center(p),self.center),default=None)
        else:
            person=max(people,key=lambda p:(p['box'][2]-p['box'][0])*(p['box'][3]-p['box'][1]),default=None)
        if person is None:
            self.wave={9:deque(),10:deque()};self.pending=self.gesture=0;self.since=now
            return Sample()
        points=person['keypoints']
        def joint(index):
            p=points[index]
            return p if p[2]>=self.threshold and not(p[0]==0 and p[1]==0) else None
        nose,left,right=joint(0),joint(5),joint(6)
        if nose is not None:
            target=nose[:2]
        elif left is not None and right is not None:
            target=((left[0]+right[0])/2,(left[1]+right[1])/2)
        else:
            self.wave={9:deque(),10:deque()};self.pending=self.gesture=0;self.since=now
            return Sample()
        self.center=center(person);self.last_seen=now
        dt=0 if self.last_update is None else now-self.last_update
        alpha=1 if self.gaze is None else 1-math.exp(-max(0,dt)/self.smoothing)
        self.gaze=target if self.gaze is None else tuple(a+alpha*(b-a) for a,b in zip(self.gaze,target))
        self.last_update=now
        shoulder_width=math.dist(left[:2],right[:2]) if left and right else .2
        margin=max(.035,shoulder_width*.18)
        raised=[];out=[];waving=False
        for wrist_index,shoulder in ((9,left),(10,right)):
            wrist=joint(wrist_index)
            up=bool(wrist and shoulder and wrist[1]<shoulder[1]-margin)
            raised.append(up)
            out.append(bool(wrist and shoulder and abs(wrist[1]-shoulder[1])<margin*1.8 and
                            abs(wrist[0]-shoulder[0])>shoulder_width*.65))
            history=self.wave[wrist_index]
            if not up:
                history.clear()
            else:
                history.append((now,wrist[0]))
                while history and (now-history[0][0]>self.wave_window or len(history)>90):
                    history.popleft()
                # Count directional reversals only after meaningful travel.
                anchor=history[0][1];direction=0;turns=0
                for _,position in history:
                    delta=position-anchor
                    if abs(delta)>max(.04,shoulder_width*.25):
                        new=1 if delta>0 else -1
                        if direction and new!=direction:turns+=1
                        direction=new;anchor=position
                waving |= turns>=2
        raw=5 if waving else (3 if all(raised) else (1 if raised[0] else (2 if raised[1] else (4 if all(out) else 0))))
        if raw!=self.pending:
            self.pending=raw;self.since=now
        if now-self.since>=self.debounce:
            self.gesture=raw
        gx,gy=self.gaze
        if self.mirror:gx=1-gx
        return Sample(True,round(gx*1000),round(gy*1000),round(person['confidence']*1000),self.gesture)


def candidates(result):
    """Convert real Ultralytics Results without retaining frames/tensors."""
    if result.keypoints is None or result.boxes is None:
        return []
    xy=result.keypoints.xyn.cpu().tolist()
    conf=result.keypoints.conf
    if conf is None:
        raise ValueError('Pose model must supply joint confidences')
    conf=conf.cpu().tolist()
    boxes=result.boxes.xyxyn.cpu().tolist();scores=result.boxes.conf.cpu().tolist()
    return [dict(box=[min(1,max(0,v)) for v in box],confidence=score,
                 keypoints=[[min(1,max(0,x)),min(1,max(0,y)),c] for (x,y),c in zip(points,visibility)])
            for box,score,points,visibility in zip(boxes,scores,xy,conf)]
