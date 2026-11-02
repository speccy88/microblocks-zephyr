#!/usr/bin/env python3
"""Bounded, authorized COM5 preview/serial benchmark; saves numbers only."""
# SPDX-License-Identifier: MPL-2.0
import argparse
import json
from pathlib import Path
import secrets
import struct
import time
from p4_serial import P4SerialVM,primitive

def main(a):
    vm=P4SerialVM();sequence=0;session=0;owned=0
    report={'settings':[1156,195,3831],'private_images_saved':False,'transfers':[],'capture_sizes':[]}
    def rpc(op,client=0,values=(0,0,0)):
        nonlocal sequence
        sequence+=1;body=struct.pack('<4sBBHIIHHHH',b'P4CC',1,op,0,sequence,client,*values,0)
        start=len(vm.events);vm.send(bytes((251,213,0,25,0))+body+b'\xfe')
        response=vm.wait(lambda e:e[0]==213 and len(e[2])>=16 and int.from_bytes(e[2][8:12],'little')==sequence,after=start,seconds=6)[2]
        vm.events.clear();return response[6],response[7],json.loads(response[16:])
    def capture(width,height):
        nonlocal session
        session=secrets.randbelow(0x1ffffffe)+1;start=time.monotonic()
        assert rpc(3,session,(width,height,0))[0]==0
        while True:
            status,state,meta=rpc(4,session);assert status==0 and state!=3
            if state==2:break
            if time.monotonic()-start>8:raise TimeoutError('Camera capture')
            time.sleep(.02)
        assert (meta['width'],meta['height'])==(width,height)
        assert vm.call('imageValid',owned)
        return meta['handle'],time.monotonic()-start,meta
    def read(handle,width,height,capture_seconds=0):
        start=time.monotonic();raw=bytearray();size=width*height*2
        for offset in range(0,size,512):
            count=min(512,size-offset);part=vm.image_request(2,handle,offset,count);assert len(part)==count;raw.extend(part);vm.events.clear()
        duration=time.monotonic()-start
        row=dict(width=width,height=height,baud=vm.link_baud,bytes=size,transfer_ms=round(duration*1000),capture_and_transfer_ms=round((duration+capture_seconds)*1000))
        report['transfers'].append(row);print(json.dumps(row),flush=True)
        return bytes(raw)
    def release():
        nonlocal session
        assert rpc(5,session)[0]==0;session=0
    try:
        vm.short(15);assert rpc(1,values=tuple(report['settings']))[0]==0
        owned=vm.call('imageCreate',1,1,1);assert owned
        for size in [(15,90),(1281,720),(320,0),(0,180),(320,721),(16,15)]:assert rpc(3,123,(*size,0))[0]==1
        report['invalid_sizes_rejected']=True
        handle,captured,_=capture(320,180);reference=read(handle,320,180,captured)
        vm.negotiate_baud(921600);assert vm.link_baud==921600,vm.link_fallback
        report['baseline_vs_921600_identical']=read(handle,320,180)==reference;assert report['baseline_vs_921600_identical'];release()
        vm.negotiate_baud(460800);assert vm.link_baud==460800
        handle,captured,_=capture(320,180);reference=read(handle,320,180,captured)
        vm.negotiate_baud(921600);assert vm.link_baud==921600
        report['460800_vs_921600_identical']=read(handle,320,180)==reference;assert report['460800_vs_921600_identical'];release()
        for size in [(160,90),(192,108),(640,360),(1280,720)]:
            handle,captured,meta=capture(*size)
            report['capture_sizes'].append(dict(width=size[0],height=size[1],native_capture_ms=meta['capture_ms']))
            if size==(160,90):read(handle,*size,captured)
            release()
        for baud in (921600,460800,115200,921600):
            vm.negotiate_baud(baud);assert vm.link_baud==baud
            vm.upload(9,primitive('imageWidth',(owned,)),2,fragmented=True);assert vm.run_reporter(9)==1
        report['fragmented_crc_and_execution_each_rate']=True
        vm.serial.close() # deliberately bypass orderly close to verify native rate lease recovery
        time.sleep(5.2)
        vm=P4SerialVM();assert vm.link_baud==115200;assert vm.call('imageValid',owned)
        report['crashed_controller_recovers_115200']=True
        for _ in range(3):
            vm.negotiate_baud(921600);assert vm.link_baud==921600
            vm.close();vm=P4SerialVM();assert vm.link_baud==115200
        report['orderly_reconnect_cycles']=3
        assert rpc(0)[2]['baud']==115200
        report['result']='PASS'
    finally:
        if vm.serial.is_open:
            if session:rpc(5,session)
            if owned:vm.call('imageRelease',owned)
            report['cleanup_images']=vm.call('imageCount');vm.close()
        a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n')
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
    if not a.execute:p.error('--execute required')
    main(a)
