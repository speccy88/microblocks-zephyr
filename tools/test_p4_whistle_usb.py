#!/usr/bin/env python3
"""Real COM5 native inference; optional explicitly authorized speaker test.

No recording is exported or uploaded. Evidence contains metrics/text only.
"""
# SPDX-License-Identifier: MPL-2.0
import argparse,datetime,json,time
from pathlib import Path
from p4_serial import P4SerialVM

def wait_inference(vm):
 start=time.monotonic();roundtrips=0;previous='';max_rtt=0
 while vm.call('sttBusy'):
  tick=time.monotonic();assert vm.run_reporter(0)==12
  max_rtt=max(max_rtt,time.monotonic()-tick);roundtrips+=1
  state=json.loads(vm.call('sttStatus'))
  if state['phase']!=previous:print('native phase:',state['phase'],flush=True);previous=state['phase']
  if time.monotonic()-start>190:raise TimeoutError('Native inference exceeded worker deadline')
  time.sleep(.1)
 state=json.loads(vm.call('sttStatus'));text=vm.call('sttResult')
 assert state['phase']=='ready',(state,text)
 assert state['buffers_released'] is True
 assert 0<state['peak_requested_bytes']<state['reserved_arena_bytes']
 assert state['stack_unused_bytes']>=8192,'Insufficient measured inference stack margin'
 return dict(transcript=text,status=state,vm_roundtrips=roundtrips,max_vm_rtt_s=round(max_rtt,4),wall_s=round(time.monotonic()-start,3))

def main(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'runtime':'native Zephyr P4',
  'model_profile':'verified four-layer Whistle C99 int8 scalar','COM12_accessed':False,'raw_audio_exported':False}
 vm=None
 try:
  vm=P4SerialVM();report['firmware']=vm.version;assert vm.call('sttAvailable') is True
  vm.upload(0,bytes([9,0,2,11,2,15,50,2,35,0,127,0,240,0,0,0,0,0,0,0]))
  assert vm.call('sttRequest',123,0) is False
  assert vm.call('sttFixture',7) is False
  assert vm.call('sttFixture',0) is True
  assert vm.call('sttFixture',0) is False
  first=wait_inference(vm);report['fixture']=first
  assert first['transcript'].casefold()=='the camera is ready.',first
  assert first['vm_roundtrips']>0
  print('Native fixture:',first['transcript'],first['status'],flush=True)
  assert vm.call('sttFixture',0) is True;time.sleep(.25);vm.call('sttCancel')
  end=time.monotonic()+4
  while vm.call('sttBusy'):
   assert time.monotonic()<end,'Cancellation failed to quiesce'
   time.sleep(.05)
  cancelled=json.loads(vm.call('sttStatus'))
  assert cancelled['phase']=='error' and cancelled['buffers_released'] is True,cancelled
  report['cancel']=cancelled
  if a.acoustic_fixture:
   import winsound
   assert vm.call('audioRequest',4000) is True;time.sleep(.65)
   winsound.PlaySound(str(a.acoustic_fixture.resolve()),winsound.SND_FILENAME|winsound.SND_ASYNC|winsound.SND_NODEFAULT)
   end=time.monotonic()+6
   while vm.call('audioBusy'):
    assert time.monotonic()<end;time.sleep(.05)
   winsound.PlaySound(None,0)
   handle=vm.call('audioResult');assert vm.call('audioFrames',handle)==64000
   audio_status=vm.call('audioStatus')
   assert vm.call('sttRequest',handle,0) is True
   assert vm.call('audioRelease',handle) is True # Worker owns a PCM copy.
   acoustic=wait_inference(vm);acoustic['capture_status']=audio_status
   report['acoustic']=acoustic
   print('Native microphone:',acoustic['transcript'],acoustic['status'],flush=True)
   assert acoustic['transcript'].casefold()=='the camera is ready.',acoustic
  else:
   assert vm.call('sttFixture',0) is True
   repeat=wait_inference(vm);report['repeat']=repeat
   assert repeat['transcript']==first['transcript']
   assert repeat['status']['peak_requested_bytes']==first['status']['peak_requested_bytes']
  assert vm.call('audioCount')==0 and vm.call('audioMemory')==0
  report['result']='PASS'
 except BaseException as e:
  report.update(result='FAIL',error=type(e).__name__+': '+str(e))
  if vm and isinstance(e,RuntimeError) and 'Unframed' in str(e):
   # This test never requests PCM bytes; bounded control-stream diagnostic.
   raw=bytes(vm.buffer)+vm.serial.read(1024)
   private=Path(__file__).resolve().parents[1]/'boards/waveshare_esp32p4_wifi6/outputs/private/control-fault.log'
   private.parent.mkdir(parents=True,exist_ok=True);private.write_bytes(raw)
   report['control_fault_class']='instruction access fault' if b'Instruction Access fault' in raw else 'unframed control stream'
   report['error']='RuntimeError: unframed COM5 control stream; diagnostic kept private'
   print('Control-stream fault saved only in ignored private diagnostics',flush=True)
  raise
 finally:
  if a.acoustic_fixture:
   import winsound
   winsound.PlaySound(None,0)
  if vm:
   try:vm.call('sttCancel');vm.call('audioReleaseAll');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True)
  a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--execute',action='store_true');p.add_argument('--evidence',type=Path,required=True)
 p.add_argument('--acoustic-fixture',type=Path,help='Explicit authorization to play a brief known phrase at existing Windows volume is required')
 a=p.parse_args()
 if not a.execute:p.error('Current hardware authorization and --execute are required')
 main(a)
