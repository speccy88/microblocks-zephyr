#!/usr/bin/env python3
"""Physical P4 trusted wake-word fixture comparison; never starts a microphone."""
# SPDX-License-Identifier: MIT
import argparse,datetime,json,time
from pathlib import Path
from p4_serial import P4SerialVM

def run(a):
 report={'tested_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),'scope':'native P4 TFLM reference kernels and trained frontend, synthetic flash fixtures','microphone_started':False,'speaker_used':False,'COM12_accessed':False,'checks':{}}
 vm=None
 def status():return json.loads(vm.call('kwsStatus'))
 def wait():
  end=time.monotonic()+65;polls=0;maximum=0
  while vm.call('kwsBusy'):
   before=time.monotonic();vm.call('imageCount');maximum=max(maximum,time.monotonic()-before);polls+=1
   if time.monotonic()>end:raise TimeoutError(status())
  return {'VM_roundtrips_while_busy':polls,'max_VM_roundtrip_ms':round(1000*maximum,3)}
 def fixture(index,name):
  reference=json.loads((a.reference/(name+'-reference.json')).read_text())
  features=json.loads((a.reference/(name+'-features.json')).read_text())
  assert vm.call('kwsFixture',index) is True,status()
  assert vm.call('kwsFixture',index) is False,'Concurrent native job accepted'
  responsiveness=wait();result=status();assert result['phase']=='ready',result
  assert result['listening'] is False
  assert result['feature_fnv1a']==features['feature_fnv1a'],result
  assert result['features']==features['features'] and result['frames']==features['frames']
  assert result['invocations']==reference['invocations'],result
  scores=[]
  for offset in range(0,result['invocations'],64):scores.extend(vm.call('kwsScores',offset,min(64,result['invocations']-offset)))
  differences=[abs(x-y) for x,y in zip(scores,reference['raw_scores'])]
  # Same reference int8 graph: require exact scores, not merely a detection.
  assert scores==reference['raw_scores'],{'max_score_difference':max(differences),'native':scores,'reference':reference['raw_scores']}
  expected=1 if index==1 else 0
  assert result['events']==expected,(result,reference['events'])
  if expected:
   assert result['event_ms']==reference['events'][0]['at_ms']
   assert result['confidence_milli']==reference['events'][0]['confidence_milli']
  result.update(responsiveness);result['raw_scores_equal_host_reference']=True
  report['checks'].setdefault(name,[]).append(result)
 try:
  vm=P4SerialVM();vm.short(15);time.sleep(.1)
  assert vm.call('kwsAvailable') is True
  assert vm.call('kwsFixture',0) is False and vm.call('kwsFixture',3) is False
  assert vm.call('kwsClip',0) is False
  fixture(1,'positive');fixture(2,'negative');fixture(1,'positive')
  for i in range(3):
   assert vm.call('kwsFixture',1) is True
   time.sleep(.15);before=time.monotonic()
   if i==1:vm.short(15)
   else:vm.call('kwsCancel')
   responsiveness=wait();result=status();assert result['phase']=='idle',result
   report['checks'].setdefault('cancel',[]).append({'elapsed_ms':round(1000*(time.monotonic()-before),3),'status':result,**responsiveness})
  fixture(2,'negative');assert vm.call('imageCount')==0 and vm.call('audioCount')==0
  if a.stream:
   report['microphone_started']=True
   report['scope']+='; explicitly bounded microphone lifecycle, no audio saved'
   for args in [(-1,970,1000),(50,970,1000),(1000,499,1000),(1000,1000,1000),(1000,970,249),(1000,970,10001)]:assert vm.call('kwsListen',*args) is False
   for repetition in range(2):
    assert vm.call('kwsListen',1000,970,1000) is True,status()
    end=time.monotonic()+3
    while not vm.call('kwsListening'):
     assert vm.call('kwsBusy') and time.monotonic()<end,status()
    assert vm.call('audioRequest',100) is False
    assert vm.call('kwsListen',1000,970,1000) is False
    responsiveness=wait();result=status()
    assert result['phase']=='ready' and result['frames']==16000 and result['invocations']==32,result
    assert not result['ring_overflows'] and not result['quarantined'] and not result['listening']
    detail=vm.call('audioStatus');assert 'drop=0 slab=0 off=0' in detail,detail
    assert vm.call('audioCount')==0
    report['checks'].setdefault('bounded_streams',[]).append({**result,**responsiveness,'audio_status':detail})
   for use_stop_all in [False,True]:
    assert vm.call('kwsListen',1000,970,1000) is True
    time.sleep(.15);before=time.monotonic()
    if use_stop_all:vm.short(15)
    else:vm.call('kwsCancel')
    wait();result=status();assert result['phase']=='idle' and not result['listening'],result
    detail=vm.call('audioStatus');assert 'drop=0 slab=0 off=0' in detail,detail
    report['checks'].setdefault('stream_cancel',[]).append({'stop_all':use_stop_all,'elapsed_ms':round(1000*(time.monotonic()-before),3),'audio_status':detail})
   # Verify exclusive ownership returns to ordinary finite recording.
   assert vm.call('audioRequest',100) is True
   end=time.monotonic()+3
   while vm.call('audioBusy'):assert time.monotonic()<end
   clip=vm.call('audioResult');assert clip>0 and vm.call('audioFrames',clip)==1600
   assert vm.call('kwsClip',clip) is True
   assert vm.call('audioRelease',clip) is True
   wait();result=status();assert result['phase']=='ready' and result['frames']==1600,result
   report['checks']['released_source_clip_owned_copy']=result
   assert vm.call('audioCount')==0 and not vm.call('kwsListening')
  report['result']='PASS'
 except BaseException as e:report.update(result='FAIL',error=type(e).__name__+': '+str(e));raise
 finally:
  if vm:
   try:vm.call('kwsCancel');vm.short(15)
   except Exception:pass
   vm.close()
  a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--reference',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--stream',action='store_true',help='Explicitly authorized short microphone lifecycle tests; no recording saved');run(p.parse_args())
