"""Deterministic GROUP stratification for rare human action/language cells.

The original speaker hash happened to put no French ANGRY speaker in test.
Reserve held-out speakers BEFORE model selection; move all utterances from
each such speaker together. Never choose a split using predictions.
"""
import collections,hashlib,json
import numpy as np
from common import DATA,PROJECT,LABELS,save,digest
def stratify(records):
 cells=collections.defaultdict(set)
 for r in records:
  if r['kind']=='human' and r['label'] in LABELS[:8]:cells[(r['language'],r['label'])].add(r['speaker'])
 overrides={};summary=[]
 for (lang,label),speakers in sorted(cells.items()):
  if len(speakers)>=60:continue
  ranked=sorted(speakers,key=lambda s:hashlib.sha256(('rare-cell-v1:'+s).encode()).digest())
  n=max(1,min(4,len(ranked)//5))
  for i,s in enumerate(ranked):overrides[s]='test' if i<n else 'validation' if i<2*n else 'train'
  summary.append(dict(language=lang,label=label,speakers=len(speakers),held_out_test_speakers=n,held_out_validation_speakers=n))
 moved=0
 for r in records:
  if r['speaker'] in overrides:
   target=overrides[r['speaker']]
   if r['split']!=target:r.setdefault('initial_speaker_hash_split',r['split']);r['split']=target;moved+=1
 return dict(method='deterministic rare-cell speaker stratification; move every utterance in the group',cells=summary,utterances_moved=moved,utterances_with_recorded_split_override=sum('initial_speaker_hash_split' in r for r in records))
def run():
 path=DATA/'prepared/records.json';records=json.loads(path.read_text());audit=stratify(records);save(path,records)
 cached=np.load(DATA/'prepared/features.npy',mmap_mode='r')
 for part in ['validation','test']:
  ids=np.array([i for i,r in enumerate(records) if r['split']==part]);np.savez(DATA/f'prepared/{part}.npz',x=np.asarray(cached[ids]),y=[LABELS.index(records[i]['label']) for i in ids],ids=ids)
 manifest=json.loads((PROJECT/'datasets/dataset_manifest.json').read_text());counts=collections.Counter((r['label'],r['language'],r['kind'],r['split']) for r in records)
 manifest['counts']=[dict(label=k[0],language=k[1],kind=k[2],split=k[3],samples=n,speakers=len({r['speaker'] for r in records if (r['label'],r['language'],r['kind'],r['split'])==k})) for k,n in sorted(counts.items())]
 manifest['partition']='source speaker hash, then deterministic rare human cell group stratification; synthetic voices/noise files held out'
 manifest['corpus_sha256']=digest(path);manifest['rare_cell_stratification']=audit;save(PROJECT/'datasets/dataset_manifest.json',manifest);save(PROJECT/'reports/split-stratification.json',audit);print(json.dumps(audit,indent=2))
if __name__=='__main__':run()
