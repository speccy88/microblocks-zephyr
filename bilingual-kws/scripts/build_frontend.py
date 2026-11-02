"""Compile the SAME pinned integer frontend as Zephyr into a host shared library."""
import argparse, hashlib, json, subprocess, sys
from pathlib import Path
from common import PROJECT, DATA, save, digest
REPO=PROJECT.parent
sys.path.insert(0,str(REPO/'tools'))
from prepare_p4_kws_frontend import prepare
C=['filterbank','frontend','frontend_util','log_lut','log_scale','log_scale_util','noise_reduction','noise_reduction_util','pcan_gain_control','pcan_gain_control_util','window','window_util']
CPP=['fft','fft_util','kiss_fft_int16']
def build(tflm):
 out=DATA/'native';out.mkdir(parents=True,exist_ok=True)
 checked,fix=prepare(tflm,out/'prepared')
 wrapper=PROJECT/'esp32p4/integration/frontend_host.c'
 files=[checked]+[tflm/f'tensorflow/lite/experimental/microfrontend/lib/{s}.c' for s in C]+[tflm/f'tensorflow/lite/experimental/microfrontend/lib/{s}.cc' for s in CPP]+[REPO/'common/kws/features.c',wrapper]
 objects=[]
 for i,path in enumerate(files):
  obj=out/f'{i}.o';cpp=path.suffix=='.cc'
  args=['c++' if cpp else 'cc','-std=c++17' if cpp else '-std=c11','-O2','-fPIC','-I'+str(tflm),'-I'+str(tflm/'third_party_static/kissfft'),'-I'+str(REPO/'common/kws')]
  if i<len(files)-2:args+=['-include',str(REPO/'common/kws/alloc_redirect.h')]
  subprocess.run(args+['-c',str(path),'-o',str(obj)],check=True);objects.append(str(obj))
 lib=out/'libkws_features.so';subprocess.run(['c++','-shared',*objects,'-lm','-o',str(lib)],check=True)
 canonical=(REPO/'common/kws/features.c').read_bytes().replace(b'\r\n',b'\n')
 save(DATA/'native/frontend.json',dict(library_sha256=digest(lib),adapter_sha256=digest(REPO/'common/kws/features.c'),adapter_lf_sha256=hashlib.sha256(canonical).hexdigest(),dependency_fix=fix))
 print(lib)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--tflm',type=Path,default=Path('/home/fred/microblocks-zephyr-work/optional/modules/lib/tflite-micro'));build(p.parse_args().tflm)
