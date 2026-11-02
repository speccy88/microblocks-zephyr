#!/usr/bin/env python3
"""Authorized COM5 tuning acceptance; evidence contains numbers, never pixels."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
from pathlib import Path
import secrets
import struct
import time
from pose_eyes import call

def main(a):
    import numpy as np
    from p4_serial import P4SerialVM
    vm=P4SerialVM();sequence=0;owned=0;session=0
    report={'test_pattern':False,'captures':[],'images_in_evidence':False}
    def rpc(op,client=0,values=(0,0,0)):
        nonlocal sequence
        sequence+=1;body=struct.pack('<4sBBHIIHHHH',b'P4CC',1,op,0,sequence,client,*values,0)
        start=len(vm.events);vm.send(bytes((251,213,0,25,0))+body+b'\xfe')
        response=vm.wait(lambda e:e[0]==213 and len(e[2])>=16 and int.from_bytes(e[2][8:12],'little')==sequence,after=start,seconds=6)[2]
        assert response[:4]==b'P4CC' and response[4]==1 and response[5]==op and int.from_bytes(response[12:16],'little')==client
        vm.events.clear();return response[6],response[7],json.loads(response[16:])
    try:
        vm.short(15);initial=rpc(0)[2];assert initial['supported'] and initial['pattern']==0
        assert tuple(initial[k] for k in ('exposure','analog','digital'))==(800,128,256)
        for values in [(3,128,256),(1157,128,256),(800,233,256),(800,128,255),(800,128,4096)]:assert rpc(1,values=values)[0]==1
        assert tuple(rpc(0)[2][k] for k in ('exposure','analog','digital'))==(800,128,256)
        report['invalid_tuples_rejected_without_mutation']=True
        owned=vm.call('imageCreate',1,1,1);assert owned
        for values in [(800,128,256),(1156,232,512)]:
            assert rpc(1,values=values)[0]==0
            session=secrets.randbelow(0x1ffffffe)+1;assert rpc(3,session)[0]==0
            assert rpc(5,(session%0x1fffffff)+1)[0]==1
            deadline=time.monotonic()+8
            while True:
                status,state,meta=rpc(4,session);assert status==0 and state!=3
                if state==2:break
                if time.monotonic()>deadline:raise TimeoutError('Tuner frame')
                time.sleep(.03)
            assert tuple(meta['used_'+k] for k in ('exposure','analog','digital'))==values
            handle=meta['handle'];assert handle and vm.call('imageValid',owned)
            raw=bytearray()
            for offset in range(0,320*180*2,512):
                n=min(512,320*180*2-offset);part=vm.image_request(2,handle,offset,n);assert len(part)==n;raw.extend(part);vm.events.clear()
            px=np.frombuffer(raw,dtype='<u2').reshape(180,320)
            rgb=np.stack((((px>>11)&31)*255//31,((px>>5)&63)*255//63,(px&31)*255//31),axis=-1).astype(np.uint8)
            gray=rgb.mean(axis=-1)
            row=dict(exposure=values[0],analog=values[1],digital=values[2],min=int(rgb.min()),max=int(rgb.max()),mean=round(float(gray.mean()),2),std=round(float(gray.std()),2),nonblack_fraction=round(float((gray>25).mean()),3))
            if a.private_photos:
                from PIL import Image
                output=a.private_photos.resolve();root=Path(__file__).resolve().parents[1]/'build-artifacts'
                if not output.is_relative_to(root):raise ValueError('Photos must stay under ignored build-artifacts')
                output.mkdir(parents=True,exist_ok=True);Image.fromarray(rgb).save(output/('p4-snapshot-%d-%d-%d.png'%values))
            report['captures'].append(row);print(json.dumps(row),flush=True)
            assert rpc(5,session)[0]==0;session=0;assert vm.call('imageValid',owned)
        assert rpc(2)[0]==0;reset=rpc(0)[2];assert tuple(reset[k] for k in ('exposure','analog','digital'))==(800,128,256)
        report.update(result='PASS_RUNTIME_CONTROL_CAPTURE_RESET',wrong_session_rejected=True,vm_image_preserved=True,real_face_tracking_tested=False)
    finally:
        if session:rpc(5,session)
        rpc(2)
        if owned:vm.call('imageRelease',owned)
        report['cleanup_images']=vm.call('imageCount');vm.close()
        a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);p.add_argument('--private-photos',type=Path);a=p.parse_args()
    if not a.execute:p.error('--execute required')
    main(a)
