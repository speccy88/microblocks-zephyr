#!/usr/bin/env python3
"""Measure the authored tiny fixture in fresh optional CPU engine processes."""
# SPDX-License-Identifier: MIT
import argparse
import json
import math
import os
from pathlib import Path
import platform
import resource
import statistics
import subprocess
import sys
import time
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))

def check(backend,iterations):
 from linux.extensions.api import Context
 from linux.extensions.inference.extension import Extension
 catalog=json.loads((ROOT/'linux/extensions/inference/models/catalog.json').read_text(encoding='utf-8'))
 fixture=catalog['fixture'];extension=Extension({'demo_models':True,'threads':1},Context(Path('/tmp'),'linux-test'))
 before=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024
 metadata=extension.load({'model':'tiny-dense-v1','backend':backend})
 raw=[float(x) for x in extension.session.infer(fixture['input']).reshape(-1)]
 assert all(abs(a-b)<=fixture['absolute_tolerance'] for a,b in zip(raw,fixture['expected_float32']))
 args={'values':fixture['scaled_input'],'input_scale':fixture['input_scale'],'output_scale':fixture['output_scale']}
 first=extension.infer(args)
 for _ in range(5):extension.infer(args)
 kernel=[];operation=[]
 for _ in range(iterations):
  started=time.perf_counter_ns();result=extension.infer(args);operation.append((time.perf_counter_ns()-started)/1000);kernel.append(result['infer_us'])
  assert all(abs(a-b)<=1 for a,b in zip(result['values'],fixture['expected_scaled']))
 def stats(values):return {'median':statistics.median(values),'p95':sorted(values)[math.ceil(.95*len(values))-1],'min':min(values),'max':max(values)}
 version=next(v['version'] for v in extension.backend_list({})['backends'] if v['backend']==backend)
 report={'backend':backend,'engine_version':version,'provider':'CPU','engine_threads_requested':1,'npu_gpu_validated':False,
  'architecture':platform.machine(),'python':platform.python_version(),'libc':platform.libc_ver(),
  'model_sha256':metadata['sha256'],'model_bytes':(ROOT/'linux/extensions/inference/models'/('tiny-dense.'+metadata['format'])).stat().st_size,
  'model_load_us_including_import':metadata['load_us'],'float32_output':raw,'scaled_output':first['values'],
  'iterations':iterations,'warmup_calls':5,'engine_tensor_io_wall_us':stats(kernel),'whole_operation_wall_us':stats(operation),
  'process_peak_rss_before_load_bytes':before,'process_peak_rss_after_inference_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
  'actual_process_thread_count':len(list(Path('/proc/self/task').iterdir())),
  'scope':'Tiny 4->4 ReLU->3 integration fixture; fresh process per backend, CPU only. RSS includes Python/libraries; timings exclude VM/IPC and are not a representative performance benchmark.'}
 extension.close();return report

def main():
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path);parser.add_argument('--backend',choices=['onnx','litert']);parser.add_argument('--iterations',type=int,default=50);args=parser.parse_args()
 if sys.platform!='linux' or not 10<=args.iterations<=1000:raise SystemExit('Requires Linux and10..1000 bounded iterations')
 if args.backend:result=check(args.backend,args.iterations)
 else:
  reports=[];env={**os.environ,'OMP_NUM_THREADS':'1','OPENBLAS_NUM_THREADS':'1'}
  for backend in ['litert','onnx']:
   child=subprocess.run([sys.executable,'-B',str(Path(__file__)),'--backend',backend,'--iterations',str(args.iterations)],capture_output=True,text=True,env=env,timeout=30)
   if child.returncode:raise SystemExit(child.stderr[-1500:])
   reports.append(json.loads(child.stdout))
  result={'result':'PASS','engines':reports,'model_origin':'authored PyTorch CPU model; separate official LiteRT Torch and torch.onnx exports','hardware_or_network_operations':False}
 text=json.dumps(result,indent=2)+'\n'
 if args.output:args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(text,encoding='utf-8')
 print(text)
if __name__=='__main__':main()
