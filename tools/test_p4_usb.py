#!/usr/bin/env python3
"""Authorized COM5 physical VM and camera acceptance; no other port is opened."""
# SPDX-License-Identifier: MPL-2.0
import argparse,datetime,json,time,zlib
from pathlib import Path
from p4_serial import P4SerialVM,primitive,op,words
def test(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'physical COM5, native SmallVM bytecode and IMX219 still pipeline','checks':{},'graphical_browser_test':False,'COM12_accessed':False}
 vm=None
 try:
  vm=P4SerialVM();report['version']=vm.version;vm.short(14,1);vm.short(15);time.sleep(.2)
  arithmetic=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0])
  vm.upload(0,arithmetic);assert [vm.run_reporter(0) for _ in range(10)]==[12]*10
  edit=bytearray(arithmetic);edit[5]=17;vm.upload(0,edit);assert vm.run_reporter(0)==13;vm.upload(0,arithmetic)
  report['checks']['arithmetic_10_runs_and_live_edit']=True;print('Physical arithmetic/edit PASS',flush=True)
  stream=words([op(2,1),op(7,0),op(3,99),0,op(7,1),op(6,1),op(2,3),op(8,0),op(6,0),op(78,1),op(26,-5),0])
  vm.upload(3,stream,1);start=len(vm.events);vm.short(3,3);vm.wait(lambda e:e[:2]==(17,3),seconds=20,after=start)
  outputs=[int(e[2][1:]) for e in vm.events[start:] if e[:2]==(20,254)];assert outputs==list(range(1,51));report['checks']['ordered_outputs']=50
  large=words([op(21)]*500+[op(2,85),op(7,2),0,0,0,0]);vm.upload(2,large,1,True);start=len(vm.events);vm.short(3,2);vm.wait(lambda e:e[:2]==(17,2),after=start);assert vm.variable(2)==42
  report['checks']['fragmented_upload_bytes']=len(large)+7
  assert vm.call('imageCount')==0;assert vm.call('imageMemory')==0;assert vm.call('imageRelease',-1) is False
  captures=[]
  for attempt in range(3):
   assert vm.call('cameraRequest') is True;assert vm.call('cameraRequest') is False
   began=time.monotonic();polls=0
   while vm.call('cameraBusy'):
    assert vm.run_reporter(0)==12;polls+=1
    if time.monotonic()-began>20:raise TimeoutError('Camera worker exceeded deadline')
    time.sleep(.05)
   status=vm.call('cameraStatus');handle=vm.call('cameraResult');assert handle>0,(status,handle)
   assert vm.call('cameraResult')==0;assert vm.call('imageWidth',handle)==1280;assert vm.call('imageHeight',handle)==720
   assert vm.call('imageFormat',handle)=='RGB565'
   small=vm.call('imageResize',handle,160,90);gray=vm.call('imageGrayscale',small);tensor=vm.call('imageRGBTensor',small,96,96);assert min(small,gray,tensor)>0
   assert vm.call('imageResize',handle,1,1)==0 # all four slots occupied
   assert vm.call('imageGrayscale',-1)==0
   assert vm.call('imageResize',handle,-1,90)==0
   assert vm.call('imageWidth',gray)==160 and vm.call('imageHeight',gray)==90
   assert vm.call('imageBytes',gray)==14400 and vm.call('imageBytes',tensor)==27648
   meta=json.loads(vm.image_request(1,gray));raw=bytearray()
   for offset in range(0,meta['bytes'],512):raw.extend(vm.image_request(2,gray,offset,min(512,meta['bytes']-offset)))
   assert len(raw)==14400 and len(set(raw))>10
   a.private.mkdir(parents=True,exist_ok=True)
   if attempt==0:
    from PIL import Image
    Image.frombytes('L',(160,90),bytes(raw)).save(a.private/'camera-gray.png')
   for h in [small,gray,tensor,handle]:assert vm.call('imageRelease',h) is True;assert vm.call('imageValid',h) is False
   assert vm.call('imageRelease',handle) is False;assert vm.call('imageCount')==0;assert vm.call('imageMemory')==0
   captures.append(dict(width=1280,height=720,gray_width=160,gray_height=90,gray_crc32=f'{zlib.crc32(raw):08x}',gray_range=[min(raw),max(raw)],vm_roundtrips_during_capture=polls,status=status))
   print('Physical camera pipeline',attempt+1,'PASS',flush=True)
  report['checks']['captures']=captures
  # Explicit discard is safe both while capture is running and after READY.
  assert vm.call('cameraRequest') is True
  vm.call('imageReleaseAll');deadline=time.monotonic()+5
  while vm.call('cameraBusy'):
   if time.monotonic()>deadline:raise TimeoutError('Cancel did not quiesce capture')
   time.sleep(.02)
  assert vm.call('cameraResult')==0
  assert vm.call('imageCount')==0 and vm.call('imageMemory')==0
  assert vm.call('cameraRequest') is True
  while vm.call('cameraBusy'):
   if time.monotonic()>deadline:raise TimeoutError('Post-cancel capture did not finish')
   time.sleep(.02)
  handle=vm.call('cameraResult');assert handle>0
  assert vm.call('imageRelease',handle) is True
  report['checks']['discard_and_recapture']=True
  # Reallocate almost the entire image budget after repeated DMA cleanup.
  # This also catches gross capture-buffer leaks in the 16 MiB PSRAM heap.
  large_handles=[vm.call('imageCreate',1280,720,3) for _ in range(3)]
  assert min(large_handles)>0
  assert vm.call('imageMemory')==8294400
  for handle in large_handles:assert vm.call('imageRelease',handle) is True
  report['checks']['post_capture_psram_reallocation_bytes']=8294400
  report['checks']['capabilities']=json.loads(vm.call('capabilities'))
  assert report['checks']['capabilities']['camera_receiver'] is True
  report['checks']['dsp_backends']=json.loads(vm.call('dspCapabilities'))
  vm.call('imageReleaseAll');vm.short(15);report['checks']['final_camera_status']=vm.call('cameraStatus');assert not vm.call('cameraBusy')
  for chunk in [2,3,10]:vm.short(2,chunk)
  report['checks']['saved_crc32']={str(k):f'{v:08x}' for k,v in vm.all_crcs().items()};time.sleep(2)
  vm.close();vm=P4SerialVM();assert vm.run_reporter(0)==12;report['checks']['usb_reconnect']=True
  report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.call('imageReleaseAll');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);p.add_argument('--private',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('Current authorization and --execute required')
 test(a)
