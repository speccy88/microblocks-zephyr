#!/usr/bin/env python3
"""Capture a requested P4 photo locally into ignored build-artifacts only."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
from pathlib import Path
import time
from pose_eyes import call

def main(a):
    import numpy as np
    from PIL import Image
    from p4_serial import P4SerialVM
    output=a.output.resolve();root=Path(__file__).resolve().parents[1]/'build-artifacts'
    if not output.is_relative_to(root):raise ValueError('Private photos must stay under ignored build-artifacts')
    vm=P4SerialVM()
    try:
        vm.short(15);call(vm,'cameraEnabled',False,primitive_set=27)
        if not vm.call('cameraRequest'):raise RuntimeError(vm.call('cameraStatus'))
        deadline=time.monotonic()+8
        while vm.call('cameraBusy'):
            if time.monotonic()>deadline:raise TimeoutError('Camera capture')
        handle=vm.call('cameraResult')
        if not handle:raise RuntimeError(vm.call('cameraStatus'))
        small=vm.call('imageResize',handle,a.width,a.height);vm.call('imageRelease',handle)
        if not small:raise RuntimeError('Photo resize')
        size=a.width*a.height*2;raw=bytearray()
        for offset in range(0,size,512):
            n=min(512,size-offset);chunk=vm.image_request(2,small,offset,n)
            if len(chunk)!=n:raise ValueError('Truncated RGB565 photo')
            raw.extend(chunk);vm.events.clear()
        px=np.frombuffer(raw,dtype='<u2').reshape(a.height,a.width)
        rgb=np.stack((((px>>11)&31)*255//31,((px>>5)&63)*255//63,(px&31)*255//31),axis=-1).astype(np.uint8)
        output.parent.mkdir(parents=True,exist_ok=True);Image.fromarray(rgb).save(output)
        gray=np.mean(rgb,axis=-1)
        print(json.dumps(dict(photo=str(output),width=a.width,height=a.height,min=int(rgb.min()),max=int(rgb.max()),mean=round(float(gray.mean()),2),std=round(float(gray.std()),2),nonblack_fraction=round(float((gray>25).mean()),3))),flush=True)
    finally:vm.call('imageReleaseAll');vm.close()
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--output',type=Path,required=True);p.add_argument('--width',type=int,default=320);p.add_argument('--height',type=int,default=180);a=p.parse_args()
    if not a.execute or not(16<=a.width<=320 and 16<=a.height<=180):p.error('Use --execute and <=320x180')
    main(a)
