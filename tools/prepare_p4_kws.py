#!/usr/bin/env python3
"""Prepare hash-pinned native KWS assets; fixtures are optional local build inputs."""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,subprocess,wave
from pathlib import Path
from prepare_p4_kws_frontend import prepare

def run(a):
 repo=Path(__file__).resolve().parents[1]
 pin=json.loads((repo/'dependencies/p4-wake-word.json').read_text())
 if subprocess.check_output(['git','-C',str(a.tflm),'rev-parse','HEAD'],text=True).strip()!=pin['TFLM_commit']:raise ValueError('TFLM source pin mismatch')
 model=a.model.read_bytes()
 if len(model)!=pin['model_bytes'] or hashlib.sha256(model).hexdigest()!=pin['model_sha256']:raise ValueError('Wake-word model hash mismatch')
 a.output.mkdir(parents=True,exist_ok=True);_,fix=prepare(a.tflm,a.output)
 assets={'model':model};fixtures=[]
 for name,path in [('positive',a.positive),('negative',a.negative)]:
  if not path:continue
  with wave.open(str(path),'rb') as w:
   if (w.getframerate(),w.getnchannels(),w.getsampwidth(),w.getcomptype())!=(16000,1,2,'NONE') or w.getnframes()>96000:raise ValueError('Fixture must be 16kHz mono signed16, at most six seconds')
   frames=w.getnframes();raw=w.readframes(frames)
   if len(raw)!=frames*2:raise ValueError('Truncated fixture PCM')
   pcm=bytes(38400)+raw+bytes(25600)
  assets[name]=pcm;fixtures.append({'name':name,'frames':len(pcm)//2,'sha256':hashlib.sha256(pcm).hexdigest()})
 if bool(a.positive)!=bool(a.negative):raise ValueError('Provide both fixtures or neither')
 assembly=['.section .rodata.p4_kws,"a"'];header=['#pragma once']
 for name,data in assets.items():
  path=(a.output/(name+'.bin')).resolve();path.write_bytes(data)
  assembly+=['.balign 16',f'.global p4_kws_{name}_start,p4_kws_{name}_end',f'p4_kws_{name}_start:', '.incbin '+json.dumps(path.as_posix()),f'p4_kws_{name}_end:']
  header+=[f'extern "C" const unsigned char p4_kws_{name}_start[],p4_kws_{name}_end[];']
 header+=['static const unsigned char p4_kws_digest[32]={'+','.join(str(x) for x in hashlib.sha256(model).digest())+'};']
 if fixtures:header+=['#define P4_KWS_FIXTURES 1']
 (a.output/'kws_assets.S').write_text('\n'.join(assembly)+'\n',newline='\n')
 (a.output/'kws_assets.h').write_text('\n'.join(header)+'\n',newline='\n')
 report={'model_sha256':pin['model_sha256'],'model_bytes':len(model),'fixtures':fixtures,'frontend_fix':fix}
 (a.output/'kws_assets.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n');print(json.dumps(report))
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__)
 for name in ['model','tflm','output']:p.add_argument('--'+name,type=Path,required=True)
 for name in ['positive','negative']:p.add_argument('--'+name,type=Path)
 run(p.parse_args())
