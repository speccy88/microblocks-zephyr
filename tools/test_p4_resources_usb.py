#!/usr/bin/env python3
"""Native P4 PSRAM pressure/recovery and camera lifetime; no scene-quality pass."""
# SPDX-License-Identifier: MPL-2.0
import argparse,datetime,json,time
from p4_serial import P4SerialVM
from pathlib import Path

def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'scope':'native image/Whistle resource pressure, recovery and camera lifetime only; separate scene-content gate remains required',
  'COM12_accessed':False,'raw_images_or_audio_exported':False}
 vm=None
 try:
  vm=P4SerialVM();vm.call('imageReleaseAll');vm.call('audioReleaseAll')
  images=[vm.call('imageCreate',1280,720,3) for _ in range(3)]
  assert min(images)>0 and vm.call('imageMemory')==8294400
  assert vm.call('sttFixture',0) is True
  end=time.monotonic()+3
  while vm.call('sttBusy'):
   assert time.monotonic()<end;time.sleep(.02)
  pressure=json.loads(vm.call('sttStatus'))
  assert pressure['phase']=='error' and 'PSRAM budget' in pressure['message']
  assert pressure['buffers_released'] is True and vm.call('imageCount')==3
  report['pressure_error']=pressure;report['images_preserved_on_error']=True
  for h in images:assert vm.call('imageRelease',h) is True
  assert vm.call('sttFixture',0) is True;end=time.monotonic()+60
  while vm.call('sttBusy'):
   assert time.monotonic()<end;time.sleep(.1)
  assert vm.call('sttResult').casefold()=='the camera is ready.'
  report['inference_after_pressure']=json.loads(vm.call('sttStatus'))
  assert report['inference_after_pressure']['buffers_released'] is True
  again=[vm.call('imageCreate',1280,720,3) for _ in range(3)]
  assert min(again)>0;vm.call('imageReleaseAll')
  report['image_reallocation_bytes']=8294400
  if a.camera_lifecycle:
   assert vm.call('cameraRequest') is True;vm.call('imageReleaseAll')
   end=time.monotonic()+5
   while vm.call('cameraBusy'):
    assert time.monotonic()<end;time.sleep(.02)
   assert vm.call('cameraResult')==0
   assert vm.call('cameraRequest') is True;end=time.monotonic()+5
   while vm.call('cameraBusy'):
    assert time.monotonic()<end;time.sleep(.02)
   h=vm.call('cameraResult');assert h>0
   assert vm.call('imageWidth',h)==1280 and vm.call('imageHeight',h)==720
   report['camera_status']=vm.call('cameraStatus')
   assert vm.call('imageRelease',h) is True
  else:report['camera_lifecycle']='not run; separate scene/lighting check required'
  assert vm.call('imageCount')==0 and vm.call('audioCount')==0
  assert vm.call('audioBusy') is False and vm.call('sttBusy') is False
  report['result']='PASS_RESOURCE_LIFECYCLE_ONLY'
 except BaseException as e:
  report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.call('sttCancel');vm.call('audioReleaseAll');vm.call('imageReleaseAll');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--camera-lifecycle',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('Current hardware authorization and --execute are required')
 main(a)
