#!/usr/bin/env python3
"""Check hosted firmware over COM5 without taking a picture or recording audio."""
# SPDX-License-Identifier: MIT
import argparse,datetime,json,time
from pathlib import Path
from p4_serial import P4SerialVM

def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'hosted native image, real SmallVM over COM5','camera_captured':False,'microphone_recorded':False,'Windows_network_changed':False,'COM12_accessed':False}
 vm=None
 try:
  vm=P4SerialVM();report['firmware']=vm.version
  start=time.monotonic()
  while True:
   state=json.loads(vm.call('networkStatus'))
   if state.get('phase')!='checking editor assets':break
   assert time.monotonic()-start<10;time.sleep(.1)
  report['network']=state;report['c6']=json.loads(vm.call('c6Status'))
  assert state['wifi_driver_ready'] and state['assets_valid'],state
  assert not state['station_association'] and not state['internet_sharing']
  if a.runtime_only:report['AP_acceptance']='not claimed; this run checks USB/runtime only'
  elif a.require_ap:assert state['ap_running'],state
  else:assert not state['credentials_saved'] and not state['ap_running'],state
  vm.upload(0,bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0]))
  assert [vm.run_reporter(0) for _ in range(10)]==[12]*10
  assert not vm.call('cameraBusy') and not vm.call('audioBusy')
  vm.call('imageReleaseAll');vm.call('audioReleaseAll')
  first=vm.call('imageCreate',128,64,3);small=vm.call('imageResize',first,64,32);gray=vm.call('imageGrayscale',small)
  assert min(first,small,gray)>0
  assert vm.call('imageWidth',gray)==64 and vm.call('imageHeight',gray)==32 and vm.call('imageBytes',gray)==2048
  for handle in [first,small,gray]:assert vm.call('imageRelease',handle) is True
  assert vm.call('imageCount')==0 and vm.call('audioCount')==0
  report['generated_image_pipeline']='PASS';report['stt_available']=vm.call('sttAvailable');assert report['stt_available'] is True
  if a.whistle:
   from test_p4_whistle_usb import wait_inference
   assert vm.call('sttFixture',0) is True;result=wait_inference(vm)
   assert result['transcript'].casefold()=='the camera is ready.';report['whistle_fixture']=result
  # Let the USB activity lease expire, then ensure parser reset preserves code.
  vm.close();vm=None;time.sleep(6);vm=P4SerialVM();assert vm.run_reporter(0)==12
  report['usb_reconnect_after_lease']='PASS';report['final_network']=json.loads(vm.call('networkStatus'));report['result']='PASS'
 except BaseException as e:
  report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))

if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--execute',action='store_true');expect=p.add_mutually_exclusive_group();expect.add_argument('--require-ap',action='store_true');expect.add_argument('--runtime-only',action='store_true');p.add_argument('--whistle',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('--execute required for COM5 test')
 main(a)
