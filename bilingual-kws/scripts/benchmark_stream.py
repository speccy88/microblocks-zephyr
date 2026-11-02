"""Audio-time replay of constructed held-out public-speech streams, mic off.

This estimates decision behavior on concatenated corpus clips. It is NOT a
representative ambient acoustic trial or measured P4 end-to-end latency.
"""
import argparse,ctypes,json,subprocess,time
from collections import deque
from pathlib import Path
import numpy as np
from scipy.stats import chi2
from common import DATA,PROJECT,LABELS,save,digest
from frontend import Stream
class Decision(ctypes.Structure):
 _fields_=[('smooth',ctypes.c_uint16*10),('threshold',ctypes.c_uint16),('cooldown',ctypes.c_uint16),
  ('candidate',ctypes.c_uint8),('stable',ctypes.c_uint8),('release',ctypes.c_uint8),
  ('initialized',ctypes.c_bool),('armed',ctypes.c_bool),('has_event',ctypes.c_bool),('last_event',ctypes.c_uint32)]
def run(a):
 import tensorflow as tf
 lib=DATA/'native/libvoice_decision.so';subprocess.run(['cc','-shared','-fPIC','-O2','-I'+str(PROJECT/'esp32p4/integration'),str(PROJECT/'esp32p4/integration/decision.c'),'-o',str(lib)],check=True)
 policy=ctypes.CDLL(str(lib));policy.voice_decision_begin.argtypes=[ctypes.POINTER(Decision),ctypes.c_uint,ctypes.c_uint]
 policy.voice_decision_push.argtypes=[ctypes.POINTER(Decision),ctypes.POINTER(ctypes.c_uint16),ctypes.c_uint32];policy.voice_decision_push.restype=ctypes.c_int
 interpreter=tf.lite.Interpreter(model_path=str(a.model),num_threads=2);interpreter.allocate_tensors();inp=interpreter.get_input_details()[0];out=interpreter.get_output_details()[0]
 records=json.loads((DATA/'prepared/records.json').read_text());pcm=np.load(DATA/'prepared/pcm.npy',mmap_mode='r');rng=np.random.default_rng(20261030)
 negatives=[i for i,r in enumerate(records) if r['split']=='test' and r['label']=='UNKNOWN' and r['kind']=='human'];rng.shuffle(negatives);negatives=negatives[:a.negatives]
 positives=[]
 for lang in ['en','fr']:
  for label in LABELS[:8]:
   ids=[i for i,r in enumerate(records) if r['split']=='test' and r['label']==label and r['language']==lang and r['kind']=='human'];rng.shuffle(ids);positives+=ids[:12]
 def replay(ids,positive):
  stream=Stream();decision=Decision();policy.voice_decision_begin(ctypes.byref(decision),a.threshold,800)
  history=deque(maxlen=118);feature_count=0;samples=0;invocations=0;events=[];targets=[];invoke_ms=[]
  started=time.perf_counter()
  def push(wave):
   nonlocal samples,feature_count,invocations
   # Feed 100 ms chunks, with exact feature timestamps (first at 30 ms).
   for start in range(0,len(wave),1600):
    chunk=wave[start:start+1600];rows=stream.push(chunk);samples+=len(chunk)
    for row in rows:
     history.append(row);feature_count+=1
     if len(history)<118 or (feature_count-118)%10:continue
     s,z=inp['quantization'];x=np.clip(np.rint(np.asarray(history,np.float32)/s+z),-128,127).astype(np.int8)[None,...,None]
     interpreter.set_tensor(inp['index'],x);t=time.perf_counter_ns();interpreter.invoke();invoke_ms.append((time.perf_counter_ns()-t)/1e6)
     raw=interpreter.get_tensor(out['index'])[0];s,z=out['quantization'];scores=np.clip(np.rint((raw.astype(np.float32)-z)*s*1000),0,1000).astype(np.uint16)
     when=20+feature_count*10;action=policy.voice_decision_push(ctypes.byref(decision),scores.ctypes.data_as(ctypes.POINTER(ctypes.c_uint16)),when);invocations+=1
     if action>=0:events.append(dict(action=LABELS[action],at_ms=when))
  try:
   push(np.zeros(8000,np.int16))
   for i in ids:
    wave=pcm[i];begin=samples/16;active=np.flatnonzero(np.abs(wave.astype(np.int32))>max(64,np.max(np.abs(wave.astype(np.int32)))*.03))
    end=begin+(int(active[-1])+1)/16 if len(active) else begin+1200
    if positive:targets.append(dict(action=records[i]['label'],language=records[i]['language'],begin_ms=begin,end_ms=end,next_ms=begin+2600))
    push(wave);push(np.zeros(22400 if positive else 1600,np.int16))
  finally:stream.close()
  report=dict(samples=len(ids),audio_seconds=samples/16000,wall_seconds=time.perf_counter()-started,invocations=invocations,events=len(events),
    host_litert_invoke_ms_median=float(np.median(invoke_ms)),host_litert_invoke_ms_p95=float(np.percentile(invoke_ms,95)))
  if positive:
   delays=[];misses=0;early=0;cells={}
   for target in targets:
    key=target['language']+':'+target['action'];cell=cells.setdefault(key,dict(samples=0,matched=0));cell['samples']+=1
    hits=[e for e in events if e['action']==target['action'] and target['begin_ms']<=e['at_ms']<target['next_ms']]
    if not hits:misses+=1;continue
    cell['matched']+=1;delay=hits[0]['at_ms']-target['end_ms'];delays.append(delay);early+=delay<0
   report.update(matched_commands=len(delays),missed_commands=misses,detections_before_energy_endpoint=early,
    by_language_action=cells,extra_or_wrong_events=len(events)-len(delays),
    audio_time_delay_ms_median=float(np.median(delays)) if delays else None,audio_time_delay_ms_p95=float(np.percentile(delays,95)) if delays else None,
    delay_scope='audio timestamps after estimated energy endpoint, detected commands only; no P4 wall/CPU time')
  else:
   hours=report['audio_seconds']/3600;k=len(events)
   report.update(constructed_negative_events_per_hour=k/hours,poisson_rate_95_ci=[0 if k==0 else float(.5*chi2.ppf(.025,2*k)/hours),float(.5*chi2.ppf(.975,2*k+2)/hours)])
  return report
 result=dict(scope='host replay; continuous frontend and same C decision policy; concatenated held-out public corpus',model_sha256=digest(a.model),threshold_milli=a.threshold,
  negatives=replay(negatives,False),positives=replay(positives,True),representative_ambient_false_positives_per_hour=None,physical_p4_end_to_end_latency_ms=None)
 save(a.output,result);print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--threshold',type=int,default=850);p.add_argument('--negatives',type=int,default=1800)
 p.add_argument('--output',type=Path,default=PROJECT/'reports/stream-benchmark.json');run(p.parse_args())
