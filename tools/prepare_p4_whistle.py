#!/usr/bin/env python3
"""Verify local licensed Whistle inputs and generate native Zephyr wrappers.

No download, model/audio upload, or hardware access. Outputs belong in build/.
"""
# SPDX-License-Identifier: MIT
import argparse,hashlib,json,shutil,wave
from pathlib import Path
from p4_whistle_permutations import adapt_source, header, permutations

def prepare(sources,model,output,fixture=None):
 repo=Path(__file__).resolve().parents[1]
 manifest=json.loads((repo/'dependencies/p4-whistle.json').read_text())
 for item in manifest['files']:
  raw=(sources/item['path']).read_bytes()
  if hashlib.sha256(raw).hexdigest()!=item['sha256']:raise ValueError('Source hash: '+item['path'])
 data=model.read_bytes();spec=manifest['model']
 if len(data)!=spec['bytes'] or hashlib.sha256(data).hexdigest()!=spec['sha256']:raise ValueError('Model size/SHA256 mismatch')
 output.mkdir(parents=True,exist_ok=True)
 tables=permutations(data)
 adapted=adapt_source((sources/'engine/src/nd_whistle.c').read_bytes())
 (output/'nd_whistle_p4.c').write_text(adapted,encoding='utf-8',newline='\n')
 (output/'whistle_permutations.h').write_text(header(tables),encoding='utf-8',newline='\n')
 target=output/'whistle_d4.cact';target.write_bytes(data)
 sections=['.section .rodata.p4_whistle,"a",@progbits','.balign 64',
  '.global p4_whistle_model_start, p4_whistle_model_end','p4_whistle_model_start:',
  '.incbin "'+target.resolve().as_posix()+'"','p4_whistle_model_end:']
 frames=0
 if fixture:
  with wave.open(str(fixture),'rb') as w:
   if (w.getnchannels(),w.getsampwidth(),w.getframerate())!=(1,2,16000):raise ValueError('Fixture must be PCM16 mono 16kHz')
   frames=w.getnframes()
   if not 1600<=frames<=64000:raise ValueError('Fixture must be 0.1..4 seconds')
   pcm=w.readframes(frames)
  target=output/'fixture.pcm';target.write_bytes(pcm)
  sections+=['.balign 64','.global p4_whistle_fixture_start, p4_whistle_fixture_end',
   'p4_whistle_fixture_start:','.incbin "'+target.resolve().as_posix()+'"','p4_whistle_fixture_end:']
 (output/'whistle_assets.S').write_text('\n'.join(sections)+'\n',newline='\n')
 for name in ['nd_cact','nd_quant','nd_tokenizer','nd_ledcmd','nd_whistle']:
  path=output/'nd_whistle_p4.c' if name=='nd_whistle' else sources/'engine/src'/(name+'.c')
  (output/(name+'_zephyr.c')).write_text('#include "whistle_port.h"\n#include "'+path.resolve().as_posix()+'"\n',encoding='utf-8',newline='\n')
 report={'source_commit':manifest['source_commit'],'model_bytes':len(data),'model_sha256':spec['sha256'],
  'fixture_frames':frames,'backend':'native Zephyr portable C99 int8; model mapped flash; 12MiB bounded PSRAM arena',
  'const_permutations':{'bytes':4096,'generated_source_sha256':hashlib.sha256(adapted.encode()).hexdigest(),
   'header_sha256':hashlib.sha256(header(tables).encode()).hexdigest(),'runtime_model_equality_check':True}}
 (output/'inputs.json').write_text(json.dumps(report,indent=2)+'\n',newline='\n')
 return report
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--sources',type=Path,required=True);p.add_argument('--model',type=Path,required=True)
 p.add_argument('--output',type=Path,required=True);p.add_argument('--fixture',type=Path);a=p.parse_args()
 print(json.dumps(prepare(a.sources,a.model,a.output,a.fixture)))
