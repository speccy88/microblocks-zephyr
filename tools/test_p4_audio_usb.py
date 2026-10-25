#!/usr/bin/env python3
"""Authorized bounded COM5 PCM transport/lifecycle test. No audio is saved."""
# SPDX-License-Identifier: MPL-2.0
import argparse,datetime,json,time,zlib,re
from pathlib import Path
from p4_serial import P4SerialVM

def test(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
  'scope':'native ES8311/I2S actual bounded PCM and SmallVM ownership; no recognition/acoustic-quality claim',
  'COM12_accessed':False,'raw_audio_saved':False,'checks':{}}
 vm=None
 try:
  vm=P4SerialVM();report['firmware']=vm.version
  vm.call('audioReleaseAll');assert vm.call('audioCodecID')==0x8311
  assert vm.call('audioRequest',0) is False and vm.call('audioRequest',8001) is False
  arithmetic=bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0]);vm.upload(0,arithmetic)
  clips=[];held=[]
  for ms in [100,250,1000]:
   if len(held)==2:
    assert vm.call('audioRequest',20) is False
    assert vm.call('audioRelease',held.pop(0)) is True
   assert vm.call('audioRequest',ms) is True
   assert vm.call('audioRequest',20) is False
   began=time.monotonic();polls=0
   while vm.call('audioBusy'):
    assert vm.run_reporter(0)==12;polls+=1
    if time.monotonic()-began>ms/1000+3:raise TimeoutError('Audio worker exceeded bounded deadline')
    time.sleep(.02)
   capture_poll_s=time.monotonic()-began
   status=vm.call('audioStatus');h=vm.call('audioResult');assert h>=0x20000000,(h,status)
   assert vm.call('audioResult')==0
   assert vm.call('audioFrames',h)==ms*16 and vm.call('audioRate',h)==16000
   assert vm.call('audioValid',h) is True and vm.call('imageValid',h) is False
   peak=vm.call('audioPeak',h);rms=vm.call('audioRMS',h)
   raw=bytearray()
   for offset in range(0,ms*32,100):raw.extend(vm.call('audioRead',h,offset,min(100,ms*32-offset)))
   assert len(raw)==ms*32
   assert 0<=rms<=peak<=32768
   blocks,us=map(int,re.search(r'(\d+) blocks, (\d+) us',status).groups())
   clock_rate=blocks*256*1000000/us
   if ms>=1000:assert 15600<clock_rate<16400,(clock_rate,status)
   clips.append({'milliseconds':ms,'frames':ms*16,'nominal_rate':16000,'peak':peak,'rms':rms,
    'dma_clock_rate_estimate':round(clock_rate,1),'capture_poll_s':round(capture_poll_s,3),
    'pcm_crc32':f'{zlib.crc32(raw):08x}','distinct_pcm_bytes':len(set(raw)),
    'vm_roundtrips_during_capture':polls,'elapsed_including_reporter_poll_s':round(time.monotonic()-began,3),'status':status})
   raw[:]=b'\0'*len(raw);held.append(h)
  for h in held:
   assert vm.call('audioRelease',h) is True and vm.call('audioValid',h) is False
   assert vm.call('audioRelease',h) is False
  assert vm.call('audioCount')==0 and vm.call('audioMemory')==0
  assert vm.call('audioRequest',1000) is True
  vm.call('audioReleaseAll');end=time.monotonic()+2
  while vm.call('audioBusy'):
   if time.monotonic()>end:raise TimeoutError('Audio cancel did not stop')
  assert vm.call('audioResult')==0
  assert vm.call('audioCount')==0 and vm.call('audioMemory')==0
  report['checks']={'codec_id':'0x8311','clips':clips,'two_slot_capacity_reuse_release':True,
   'cancel_cleanup':True,'final_status':vm.call('audioStatus'),'vm_still_runs':vm.run_reporter(0)==12}
  report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.call('audioReleaseAll');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True);a=p.parse_args()
 if not a.execute:p.error('Current authorization and --execute are required')
 test(a)
