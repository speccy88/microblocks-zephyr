#!/usr/bin/env python3
"""Offline CPU reference for pinned wake-word features, never a device fallback."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,math
from pathlib import Path

def run(a):
 import numpy as np
 from ai_edge_litert.interpreter import Interpreter,OpResolverType
 pin=json.loads((Path(__file__).resolve().parents[1]/'dependencies/p4-wake-word.json').read_text())
 model=a.model.read_bytes()
 if len(model)!=pin['model_bytes'] or hashlib.sha256(model).hexdigest()!=pin['model_sha256']:raise ValueError('Pinned wake-word model mismatch')
 data=a.features.read_bytes()
 if not 120<=len(data)<=32000 or len(data)%40:raise ValueError('Expected bounded trained int8 feature slices')
 interpreter=Interpreter(model_content=model,num_threads=1,experimental_op_resolver_type=OpResolverType.BUILTIN_REF)
 interpreter.allocate_tensors();input=interpreter.get_input_details()[0];output=interpreter.get_output_details()[0]
 if input['shape'].tolist()!=[1,3,40] or input['dtype']!=np.int8 or output['shape'].tolist()!=[1,1] or output['dtype']!=np.uint8:raise ValueError('Unexpected trusted model tensor contract')
 scale,zero=output['quantization']
 if (scale,zero)!=(1/256,0):raise ValueError('Unexpected probability quantization')
 x=np.frombuffer(data,dtype=np.int8);scores=[];events=[];history=[0]*5;last_event=-100000
 cutoff=math.ceil(0.97*5*256);peak=0
 for i in range(len(data)//120):
  interpreter.set_tensor(input['index'],x[i*120:(i+1)*120].reshape(1,3,40));interpreter.invoke()
  raw=int(interpreter.get_tensor(output['index'])[0,0]);scores.append(raw);history[i%5]=raw
  total=sum(history);peak=max(peak,total);at_ms=50+i*30
  if total>=cutoff and at_ms-last_event>=1000:
   events.append({'at_ms':at_ms,'confidence_milli':round(total*1000/(5*256))});last_event=at_ms;history=[0]*5
 report={'result':'PASS','scope':'host CPU reference only; synthetic features; no microphone or on-device claim',
  'runtime':'Google LiteRT 2.3.0 BUILTIN_REF, one thread','model_sha256':pin['model_sha256'],
  'feature_sha256':hashlib.sha256(data).hexdigest(),'invocations':len(scores),'raw_scores':scores,
  'max_probability_milli':round(max(scores)*1000/256),'max_average_milli':round(peak*1000/(5*256)),
  'events':events,'cutoff':0.97,'cooldown_ms':1000}
 if a.expected_events is not None and len(events)!=a.expected_events:raise AssertionError(f'Expected {a.expected_events} events, got {len(events)}')
 report['expected_events']=a.expected_events
 a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
 print(json.dumps({k:v for k,v in report.items() if k!='raw_scores'},indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--model',type=Path,required=True);p.add_argument('--features',type=Path,required=True);p.add_argument('--evidence',type=Path,required=True);p.add_argument('--expected-events',type=int);run(p.parse_args())
