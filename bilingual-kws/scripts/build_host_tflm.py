"""Reproducible exact-pin host kernel and probe build (external checkout)."""
import argparse,subprocess
from pathlib import Path
from common import PROJECT,DATA
def run(tflm,jobs):
 actual=subprocess.check_output(['git','-C',str(tflm),'rev-parse','HEAD'],text=True).strip()
 if actual!='43b2a106a391dd8a099ac47f2ae858630a397264':raise ValueError('TFLM pin mismatch')
 gen=DATA/'native/tflm-size-gen'
 subprocess.run(['make','-f','tensorflow/lite/micro/tools/make/Makefile','microlite',f'-j{jobs}','OPTIMIZE_KERNELS_FOR=KERNELS_OPTIMIZED_FOR_SIZE','BASE_GENDIR='+str(gen)],cwd=tflm,check=True)
 downloads=tflm/'tensorflow/lite/micro/tools/make/downloads'
 args=['c++','-std=c++17','-O2','-DTF_LITE_STATIC_MEMORY','-I'+str(tflm)]
 args += ['-I'+str(downloads/p) for p in ['flatbuffers/include','gemmlowp','ruy']]
 DATA.joinpath('native').mkdir(exist_ok=True)
 args+=['-DKERNELS_OPTIMIZED_FOR_SIZE']
 subprocess.run(args+[str(PROJECT/'esp32p4/integration/tflm_host.cc'),str(gen/'linux_x86_64_default_gcc/lib/libtensorflow-microlite.a'),'-lpthread','-lm','-o',str(DATA/'native/tflm_host')],check=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--tflm',type=Path,default=Path('/home/fred/microblocks-zephyr-work/optional/modules/lib/tflite-micro'));p.add_argument('--jobs',type=int,default=2);a=p.parse_args();run(a.tflm,a.jobs)
