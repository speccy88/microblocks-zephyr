"""Run the exact pinned host TFLM and compare integer output with desktop LiteRT.

Host arena usage is measured for x86_64 (pointer sizes differ on RV32). Native
P4 arena/latency remain unmeasured until authorized hardware execution.
"""
import argparse,json,subprocess,time
from pathlib import Path
import numpy as np
from common import DATA,PROJECT,save,digest
def run(a):
 import tensorflow as tf
 data=np.load(DATA/'prepared/test.npz');rng=np.random.default_rng(20261030);chosen=[]
 for label in range(10):
  ids=np.flatnonzero(data['y']==label);rng.shuffle(ids);chosen.extend(ids[:max(1,a.samples//10)].tolist())
 chosen=np.array(chosen[:a.samples]);raw=data['x'][chosen]
 i=tf.lite.Interpreter(model_path=str(a.model),num_threads=2,experimental_op_resolver_type=tf.lite.experimental.OpResolverType.BUILTIN_REF);i.allocate_tensors()
 inp=i.get_input_details()[0];out=i.get_output_details()[0];s,z=inp['quantization']
 x=np.clip(np.round(raw.astype(np.float32)/s+z),-128,127).astype(np.int8)
 path=DATA/'native/probe-input.i8';path.write_bytes(x.tobytes());output=DATA/'native/probe-output.i8'
 command=[str(DATA/'native/tflm_host'),str(a.model),str(path),str(output),'131072']
 p=subprocess.run(command,capture_output=True,text=True)
 if p.returncode:raise RuntimeError(p.stdout+p.stderr+f' TFLM exited {p.returncode}')
 # TFLM diagnostics may precede the machine-readable final line.
 result=json.loads(p.stdout.strip().splitlines()[-1]);actual=np.frombuffer(output.read_bytes(),np.int8).reshape(-1,10)
 expected=[]
 for v in x:
  i.set_tensor(inp['index'],v[None,...,None]);i.invoke();expected.append(i.get_tensor(out['index'])[0])
 expected=np.stack(expected);diff=np.abs(actual.astype(np.int16)-expected.astype(np.int16))
 result.update(model_sha256=digest(a.model),input_sha256=digest(path),max_output_lsb_difference=int(diff.max()),
   test_classes_present=sorted(np.unique(data['y'][chosen]).tolist()),
   mean_output_lsb_difference=float(diff.mean()),argmax_agreement=float(np.mean(actual.argmax(1)==expected.argmax(1))),
   tflm_commit='43b2a106a391dd8a099ac47f2ae858630a397264',
   invoke_ms_median=float(np.median(result['invoke_us'])/1000),invoke_ms_p95=float(np.percentile(result['invoke_us'],95)/1000),
   native_p4=dict(compiled=None,compilation_evidence='separate reports/native-build.json; require matching model hash',arena_used_bytes=None,inference_ms_median=None,inference_ms_p95=None,
      end_to_end_ms_median=None,end_to_end_ms_p95=None,cpu_usage=None,concurrent_microblocks=None),
   limitations=['Host TFLM arena allocation is not an RV32 RAM measurement.',
    'No physical microphone, P4 timing, false positives/hour or concurrent VM benchmark in this host probe.'])
 result.pop('invoke_us')
 result['desktop_comparison']='TensorFlow Lite BUILTIN_REF; same INT8 bytes; host kernels use SIZE policy matching native non-SPEED build'
 result['bit_exact']=result['max_output_lsb_difference']==0
 result['numerical_tolerance']=dict(max_output_lsb=8,mean_output_lsb=.25,min_argmax_agreement=.99)
 if result['max_output_lsb_difference']>8 or result['mean_output_lsb_difference']>.25 or result['argmax_agreement']<.99:raise ValueError('TFLM numerical compatibility gate failed: '+str(result))
 save(PROJECT/'reports'/f'{a.name}-tflm.json',result);print(json.dumps(result,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',type=Path,required=True);p.add_argument('--name',required=True);p.add_argument('--samples',type=int,default=256);run(p.parse_args())
