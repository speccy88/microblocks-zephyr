#!/usr/bin/env python3
"""Authorized Windows speaker/P4 mic same-PCM native/host comparison fixture.

One four-second recording, private local WAV only. No audio/model upload.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,datetime,hashlib,json,subprocess,time,wave
from pathlib import Path
from p4_serial import P4SerialVM
from test_p4_whistle_usb import wait_inference

def main(a):
 import winsound
 repo=Path(__file__).resolve().parents[1]
 target=a.private.resolve()/'same-pcm-camera-ready.wav'
 if not target.is_relative_to(repo) or subprocess.run(['git','-C',str(repo),'check-ignore','--quiet',str(target)],capture_output=True).returncode:
  raise ValueError('Private audio destination must be an ignored path inside this checkout')
 with wave.open(str(a.fixture),'rb') as w:
  if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000) or w.getnframes()>38400:
   raise ValueError('Use the controlled mono PCM16/16kHz phrase, at most 2.4 seconds')
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'scope':'explicitly authorized controlled speaker/microphone same-PCM diagnostic',
  'controlled_phrase':'The camera is ready.','raw_audio_uploaded':False,'COM12_accessed':False}
 vm=None
 try:
  vm=P4SerialVM();assert vm.call('sttAvailable') is True;vm.call('audioReleaseAll')
  vm.upload(0,bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0]))
  assert vm.call('audioRequest',4000) is True;time.sleep(.65)
  winsound.PlaySound(str(a.fixture.resolve()),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
  end=time.monotonic()+6
  while vm.call('audioBusy'):
   assert time.monotonic()<end;time.sleep(.05)
  winsound.PlaySound(None,0);h=vm.call('audioResult');assert vm.call('audioFrames',h)==64000
  report['capture_status']=vm.call('audioStatus');report['peak']=vm.call('audioPeak',h);report['rms']=vm.call('audioRMS',h)
  assert vm.call('sttRequest',h,0) is True
  pcm=bytearray();started=time.monotonic();calls=0
  for offset in range(0,128000,100):
   pcm.extend(vm.call('audioRead',h,offset,min(100,128000-offset)));calls+=1
  target.parent.mkdir(parents=True,exist_ok=True)
  with wave.open(str(target),'wb') as w:
   w.setnchannels(1);w.setsampwidth(2);w.setframerate(16000);w.writeframes(pcm)
  report['pcm_sha256']=hashlib.sha256(pcm).hexdigest();pcm[:]=b'\0'*len(pcm)
  report['pcm_export_vm_calls']=calls;report['pcm_export_s']=round(time.monotonic()-started,3)
  report['native_held']=wait_inference(vm)
  assert vm.call('sttRequest',h,0) is True;assert vm.call('audioRelease',h) is True
  report['native_released']=wait_inference(vm)
  report['copy_ownership_same_text']=report['native_held']['transcript']==report['native_released']['transcript']
  assert report['copy_ownership_same_text']
  assert report['native_released']['transcript'].casefold()=='the camera is ready.'
  report['result']='PASS'
 except BaseException as e:
  report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  winsound.PlaySound(None,0)
  if vm:
   try:vm.call('sttCancel');vm.call('audioReleaseAll');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--fixture',type=Path,required=True)
 p.add_argument('--private',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('Explicit current speaker/microphone test authorization and --execute are required')
 main(a)
