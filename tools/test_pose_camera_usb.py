#!/usr/bin/env python3
"""Authorized bounded P4-camera/YOLO test. Saves numbers only, no images."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import asyncio
import json
from pathlib import Path
import secrets
import time
from pose_eyes import call,load_model,DEFAULT_MODEL,unpack_gray4
from pose_tracker import Tracker,Sample,candidates,GESTURES
from pose_camera_rpc import request_packet,decode_reply,capture_frame


def main(a):
    import cv2
    import numpy as np
    from p4_serial import P4SerialVM
    model=load_model(a.model)
    model.predict(np.zeros((108,192,3),dtype=np.uint8),imgsz=320,conf=.5,verbose=False) # warm up before live acquisition
    tracker=Tracker(max_gap=3,wave_window=4);vm=P4SerialVM();sequence=0;image=0
    report={'frames':[],'camera_source':'P4-attached IMX219','inference_location':'computer','images_saved':False,'eye_tracking_user_confirmation':False}
    class RPC:
        async def request(self,op,session=0,offset=0,count=0):
            nonlocal sequence
            sequence+=1;start=len(vm.events);vm.send(request_packet(op,sequence,session,offset,count))
            body=vm.wait(lambda e:e[0]==211 and len(e[2])>=16 and int.from_bytes(e[2][8:12],'little')==sequence,after=start,seconds=6)[2]
            vm.events.clear()
            return decode_reply(bytes([251,211,0])+len(body).to_bytes(2,'little')+body)
    rpc=RPC()
    try:
        vm.short(15)
        assert call(vm,'begin',64,0,60,primitive_set=26)
        assert call(vm,'follow',True,True,primitive_set=27)
        assert call(vm,'cameraEnabled',True,primitive_set=27)
        image=vm.call('imageCreate',1,1,1);assert image
        for index in range(a.frames):
            session=secrets.randbelow(0x1ffffffe)+1;began=time.monotonic()
            frame=asyncio.run(capture_frame(rpc,session))
            if frame is None:raise RuntimeError('Pose camera is disabled/busy')
            raw,captured=frame;gray=unpack_gray4(raw)
            assert vm.call('imageValid',image) is True,'RPC released a VM-owned image'
            result=model.predict(cv2.cvtColor(gray,cv2.COLOR_GRAY2BGR),imgsz=320,conf=.5,verbose=False)[0]
            people=candidates(result);sample=tracker.update(people,captured);age=time.monotonic()-captured
            sample=sample if age<=2 else Sample()
            vm.send(sample.packet(index+1));vm.pump()
            row=dict(frame=index+1,people=len(people),visible=sample.visible,gesture=GESTURES[sample.gesture],gray_min=int(gray.min()),gray_max=int(gray.max()),gray_levels=int(np.unique(gray).size),age_ms=round(age*1000),total_ms=round((time.monotonic()-began)*1000),receiver_visible=call(vm,'visible',primitive_set=27))
            report['frames'].append(row);print(json.dumps(row),flush=True)
        report['result']='PASS' if any(r['visible'] for r in report['frames']) else 'FAIL_NO_VISIBLE_PERSON'
    except BaseException as error:
        report.update(result='FAIL',error=type(error).__name__+': '+str(error));raise
    finally:
        try:
            call(vm,'cameraEnabled',False,primitive_set=27);call(vm,'follow',False,False,primitive_set=27)
            if image:vm.call('imageRelease',image)
            report['cleanup']={'camera_idle':not vm.call('cameraBusy'),'images':vm.call('imageCount')}
            call(vm,'automatic',1,True,2,1,primitive_set=26)
        finally:
            vm.close();a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n')
            print(json.dumps({k:v for k,v in report.items() if k!='frames'},indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--frames',type=int,default=3);p.add_argument('--model',default=DEFAULT_MODEL);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
    if not a.execute or not 1<=a.frames<=30:p.error('--execute, current camera-test authorization and 1..30 frames required')
    main(a)
