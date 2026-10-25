#!/usr/bin/env python3
"""Physical native Zephyr VM/PSRAM acceptance; no camera success claim."""
# SPDX-License-Identifier: MPL-2.0
import argparse,datetime,json,time
from pathlib import Path
from p4_serial import P4SerialVM,op,words
def test(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'physical native Zephyr SmallVM UART and PSRAM; no image capture','checks':{},'COM12_accessed':False}
 vm=None
 try:
  vm=P4SerialVM();report['version']=vm.version;vm.short(14,1);vm.short(15);time.sleep(.1)
  code=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0]);vm.upload(0,code)
  assert [vm.run_reporter(0) for _ in range(10)]==[12]*10
  edit=bytearray(code);edit[5]=17;vm.upload(0,edit);assert vm.run_reporter(0)==13;vm.upload(0,code)
  report['checks']['arithmetic_runs']=10;report['checks']['live_edit']=13
  stream=words([op(2,1),op(7,0),op(3,99),0,op(7,1),op(6,1),op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
  vm.upload(3,stream,1);start=len(vm.events);vm.short(3,3);vm.wait(lambda e:e[:2]==(17,3),seconds=20,after=start)
  assert [int(e[2][1:]) for e in vm.events[start:] if e[:2]==(20,254)]==list(range(1,51));report['checks']['ordered_outputs']=50
  large=words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0]);vm.upload(2,large,1,True);start=len(vm.events);vm.short(3,2);vm.wait(lambda e:e[:2]==(17,2),after=start);assert vm.variable(2)==42;report['checks']['fragmented_upload_bytes']=len(large)+7
  report['checks']['capabilities']=json.loads(vm.call('capabilities'));assert report['checks']['capabilities']['runtime']=='Zephyr'
  report['checks']['sensor_ids']=vm.call('sensorIDs');assert report['checks']['sensor_ids']=='IMX219=0219 OV5647=0000'
  h=vm.call('imageCreate',1280,720,2);assert h>0 and vm.call('imageBytes',h)==1843200
  small=vm.call('imageResize',h,160,90);gray=vm.call('imageGrayscale',small);assert min(small,gray)>0
  assert vm.call('imageWidth',gray)==160 and vm.call('imageHeight',gray)==90
  assert vm.image_request(2,gray,0,512)==bytes(512)
  for handle in [h,small,gray]:assert vm.call('imageRelease',handle) is True;assert vm.call('imageValid',handle) is False
  report['checks']['full_frame_psram_allocation_bytes']=1843200;report['checks']['native_resize_grayscale_and_bounded_export']=True
  for i in range(25):
   h=vm.call('imageCreate',32,32,1);assert h>0;assert vm.call('imageRelease',h) is True;assert vm.call('imageValid',h) is False
  report['checks']['physical_handle_reuse_cycles']=25
  assert vm.call('imageCreate',0,720,2)==0;assert vm.call('imageCreate',1281,720,2)==0;assert vm.call('imageRelease',-1) is False
  assert vm.call('imageCount')==0 and vm.call('imageMemory')==0
  report['checks']['camera_status']=vm.call('cameraStatus')
  vm.short(2,10);vm.close();vm=P4SerialVM();assert vm.run_reporter(0)==12;report['checks']['reconnect']=True
  vm.short(15);report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.call('imageReleaseAll');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('Current user authorization and --execute required')
 test(a)
