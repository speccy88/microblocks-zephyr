"""Local MediaPipe face features and explicit synthetic demonstration input."""
# SPDX-License-Identifier: MIT
from dataclasses import dataclass
import math
from pathlib import Path
import struct
from pose_tracker import Sample

DEFAULT_FACE_MODEL=str(Path(__file__).resolve().parents[1]/'build-artifacts/pose/face_landmarker.task')

@dataclass(frozen=True)
class FaceSample:
    visible:bool=False
    x:int=500
    y:int=500
    left_eye:int=0
    right_eye:int=0
    head:int=0
    look:int=0

    def packet(self,sequence):
        body=struct.pack('<4sBBBBIHHBBH',b'P4FC',1,int(self.visible),self.left_eye,self.right_eye,
                         sequence&0xffffffff,self.x,self.y,self.head,self.look,0)
        return bytes((251,212,0,21,0))+body+b'\xfe'

def eye_state(blink):
    return 2 if blink>=.6 else (1 if blink<=.25 else 0)

def look_direction(scores):
    left=(scores.get('eyeLookOutLeft',0)+scores.get('eyeLookInRight',0))/2
    right=(scores.get('eyeLookInLeft',0)+scores.get('eyeLookOutRight',0))/2
    if max(left,right)<.35 or abs(left-right)<.15:return 2
    return 1 if left>right else 3

class FaceTracker:
    """One spatially continuous face; no identity recognition or frame storage."""
    def __init__(self,model=DEFAULT_FACE_MODEL,mirror=False):
        import mediapipe as mp
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision
        if not Path(model).is_file():raise FileNotFoundError('Run tools/fetch_face_model.py first: '+model)
        self.mp=mp;self.mirror=mirror;self.center=None;self.last_seen=None;self.gaze=None;self.last_update=None
        self.landmarker=vision.FaceLandmarker.create_from_options(vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model)),num_faces=3,
            min_face_detection_confidence=.6,min_face_presence_confidence=.6,min_tracking_confidence=.6,
            output_face_blendshapes=True,output_facial_transformation_matrixes=True))

    def infer(self,bgr,now):
        import cv2
        rgb=cv2.cvtColor(bgr,cv2.COLOR_BGR2RGB)
        result=self.landmarker.detect(self.mp.Image(image_format=self.mp.ImageFormat.SRGB,data=rgb))
        faces=[]
        for index,points in enumerate(result.face_landmarks):
            if len(points)<478:continue
            xs=[p.x for p in points];ys=[p.y for p in points]
            box=(min(xs),min(ys),max(xs),max(ys));cx=(box[0]+box[2])/2;cy=(box[1]+box[3])/2
            if not all(math.isfinite(v) for v in box) or not(0<=cx<=1 and 0<=cy<=1):continue
            faces.append((index,cx,cy,(box[2]-box[0])*(box[3]-box[1])))
        if self.last_seen is not None and now-self.last_seen>3:self.center=self.gaze=None
        if self.center is None:chosen=max(faces,key=lambda f:f[3],default=None)
        else:chosen=min((f for f in faces if math.dist(f[1:3],self.center)<.30),key=lambda f:math.dist(f[1:3],self.center),default=None)
        if chosen is None:return FaceSample()
        index,cx,cy,_=chosen;dt=0 if self.last_update is None else max(0,now-self.last_update)
        alpha=1 if self.gaze is None else 1-math.exp(-dt/.18)
        self.gaze=(cx,cy) if self.gaze is None else tuple(a+alpha*(b-a) for a,b in zip(self.gaze,(cx,cy)))
        self.center=(cx,cy);self.last_seen=self.last_update=now
        scores={c.category_name:c.score for c in result.face_blendshapes[index]} if index<len(result.face_blendshapes) else {}
        left=eye_state(scores['eyeBlinkLeft']) if 'eyeBlinkLeft' in scores else 0
        right=eye_state(scores['eyeBlinkRight']) if 'eyeBlinkRight' in scores else 0
        look=look_direction(scores) if scores and left==right==1 else 0
        head=0
        if index<len(result.facial_transformation_matrixes):
            r=result.facial_transformation_matrixes[index]
            yaw=math.degrees(math.atan2(float(r[0,2]),float(r[2,2])))
            if math.isfinite(yaw):head=1 if yaw< -15 else (3 if yaw>15 else 2)
        x,y=self.gaze
        return FaceSample(True,round((1-x if self.mirror else x)*1000),round(y*1000),left,right,head,look)

    def close(self):self.landmarker.close()

def demo_samples(seconds):
    """36 s cycle. Synthetic coordinates/features only; never calls a detector."""
    t=seconds%36
    if t<14 or t>=28:return FaceSample(),Sample()
    phase=t-14;x=round(500+350*math.sin(phase*.65));y=round(450+120*math.sin(phase*.4))
    # Brief occlusion exercises the native grace period without a sleep flicker.
    if 20<=t<20.6:return FaceSample(),Sample()
    gesture=0 if phase<3 else (1 if phase<5 else (2 if phase<7 else (3 if phase<9 else (4 if phase<11 else 5))))
    closed=2 if 18<=t<18.8 else 1
    return FaceSample(True,x,y,closed,closed,2,2),Sample(True,x,y,950,gesture)
