#!/usr/bin/env python3
"""Build the portable trained audio frontend against pinned external TFLM."""
# SPDX-License-Identifier: MIT
import argparse,json,subprocess,tempfile,sys,wave
from pathlib import Path
from prepare_p4_kws_frontend import prepare

FRONTEND_C=['filterbank','filterbank_util','frontend','frontend_util','log_lut','log_scale','log_scale_util','noise_reduction','noise_reduction_util','pcan_gain_control','pcan_gain_control_util','window','window_util']
FRONTEND_CPP=['fft','fft_util','kiss_fft_int16']
def run(a):
 repo=Path(__file__).resolve().parents[1];dependency=a.tflm.resolve()
 pin=json.loads((repo/'dependencies/p4-tflm.json').read_text())['source_commit']
 actual=subprocess.check_output(['git','-C',str(dependency),'rev-parse','HEAD'],text=True).strip()
 if actual!=pin:raise ValueError('TFLM source commit differs from pin')
 source=dependency/'tensorflow/lite/experimental/microfrontend/lib';common=repo/'common/kws'
 with tempfile.TemporaryDirectory(prefix='p4-kws-features-') as folder:
  work=Path(folder);objects=[];checked_filterbank,fix=prepare(dependency,work/'prepared')
  for name,cpp in [(x,False) for x in FRONTEND_C]+[(x,True) for x in FRONTEND_CPP]+[('adapter',False),('test',False)]:
   path=source/(name+('.cc' if cpp else '.c')) if name not in ['adapter','test'] else common/'features.c' if name=='adapter' else repo/('tests/p4_kws_features_export.c' if a.wav else 'tests/p4_kws_features_test.c')
   if name=='filterbank_util':path=checked_filterbank
   obj=work/(name+'.o');cmd=['c++' if cpp else 'cc','-std=c++17' if cpp else '-std=c11','-g','-O1','-fsanitize=address,undefined','-fno-sanitize-recover=all','-fno-omit-frame-pointer','-I'+str(dependency),'-I'+str(dependency/'third_party_static/kissfft'),'-I'+str(common)]
   if name not in ['adapter','test']:cmd+=['-include',str(common/'alloc_redirect.h')]
   subprocess.run(cmd+['-c',str(path),'-o',str(obj)],check=True);objects.append(str(obj))
  binary=work/'test';subprocess.run(['c++','-fsanitize=address,undefined',*objects,'-lm','-o',str(binary)],check=True)
  args=[str(binary)]
  if a.wav:
   if not a.features_output:raise ValueError('--features-output is required for fixture export')
   with wave.open(str(a.wav),'rb') as w:
    if (w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getcomptype())!=(16000,1,2,'NONE') or w.getnframes()>128000:raise ValueError('Expected bounded 16kHz mono signed16 WAV')
    frames=w.getnframes();raw=w.readframes(frames)
    if len(raw)!=frames*2:raise ValueError('Truncated fixture PCM')
    pcm=bytes(38400)+raw+bytes(25600)
   if len(pcm)>256000:raise ValueError('Padded fixture exceeds eight seconds')
   raw=work/'fixture.pcm';raw.write_bytes(pcm);a.features_output.parent.mkdir(parents=True,exist_ok=True)
   args += [str(raw),str(a.features_output)]
  result=subprocess.run(args,capture_output=True,text=True)
  if result.returncode:
   print(result.stdout+result.stderr,file=sys.stderr);result.check_returncode()
  report=json.loads(result.stdout)
  report['TFLM_commit']=actual;report['dependency_fix']=fix
  if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',newline='\n')
  print(json.dumps(report,indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--tflm',type=Path,required=True);p.add_argument('--evidence',type=Path);p.add_argument('--wav',type=Path);p.add_argument('--features-output',type=Path);run(p.parse_args())
