"""Append prepared supplemental phrases without recalculating 60k native inputs."""
import collections,hashlib,json,os
import numpy as np
from common import DATA,PROJECT,save,digest
from prepare_dataset import read,window,SAMPLES,FRAMES
from frontend import window_features
from repartition import run as repartition
def run(source=None):
 source=source or DATA/'manifests/tts-piper-phrases.jsonl';marker=DATA/'prepared'/('phrase-supplement.json' if source.stem=='tts-piper-phrases' else source.stem+'-prepared.json')
 if marker.exists():return
 records=json.loads((DATA/'prepared/records.json').read_text());known={r['pcm_sha256'] for r in records};parts={r['speaker']:r['split'] for r in records}
 added=[];audio=[];excluded=duplicates=0;incoming=[json.loads(s) for s in source.read_text().splitlines()]
 for r in incoming:
  if r['speaker'] in parts and parts[r['speaker']]!=r['split']:raise ValueError('voice split changed')
  pcm=window(read(r['path']))
  if pcm is None:excluded+=1;continue
  h=hashlib.sha256(pcm.tobytes()).hexdigest()
  if h in known:duplicates+=1;continue
  known.add(h);r['pcm_sha256']=h;added.append(r);audio.append(pcm)
 old_n=len(records);records.extend(added)
 for name,shape,dtype in [('pcm',(SAMPLES,),np.int16),('features',(FRAMES,40),np.int8)]:
  target=DATA/f'prepared/{name}.npy';old=np.load(target,mmap_mode='r');temp=target.with_suffix('.next.npy');new=np.lib.format.open_memmap(temp,mode='w+',dtype=dtype,shape=(len(records),*shape))
  for start in range(0,old_n,512):new[start:min(start+512,old_n)]=old[start:min(start+512,old_n)]
  for i,pcm in enumerate(audio):new[old_n+i]=pcm if name=='pcm' else window_features(pcm)
  new.flush();del old,new;os.replace(temp,target)
 save(DATA/'prepared/records.json',records)
 manifest=json.loads((PROJECT/'datasets/dataset_manifest.json').read_text());manifest['source_records']+=len(incoming);manifest['accepted_records']=len(records);manifest['duplicates_removed']+=duplicates;manifest['rejected']['longer_than_1.2s']+=excluded;manifest['pcm_sha256']=digest(DATA/'prepared/pcm.npy')
 supplement=dict(source=source.name,source_samples=len(incoming),retained=len(added),excluded_too_long=excluded,complete_utterances=True,speeds=sorted({r['speed'] for r in incoming}))
 manifest.setdefault('supplements',[]).append(supplement)
 save(PROJECT/'datasets/dataset_manifest.json',manifest);repartition();save(marker,supplement);print(json.dumps(supplement,indent=2))
if __name__=='__main__':
 import argparse
 from pathlib import Path
 p=argparse.ArgumentParser();p.add_argument('--source',type=Path);run(p.parse_args().source)
