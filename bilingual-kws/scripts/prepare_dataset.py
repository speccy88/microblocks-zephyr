"""Normalize public audio, audit identity/hash leakage and prepare mmap PCM.

No sentence is relabeled as a one-word example. MSWC's supplied word segments
are used with their original labels. Raw voice/source IDs remain private.
"""
import argparse, collections, hashlib, json, math,concurrent.futures
import numpy as np
import soundfile as sf
from scipy.signal import resample_poly
from common import DATA,PROJECT,LABELS,WORDS,HOMOPHONE_NEGATIVES,rows,save,digest
from frontend import window_features
SAMPLES=19200;FRAMES=118
def read(path):
 x,sr=sf.read(path,dtype='float32',always_2d=True);x=x.mean(axis=1)
 return resample_poly(x,16000//math.gcd(sr,16000),sr//math.gcd(sr,16000))
def window(x):
 # Remove only very low energy padding. Never stretch/crop away phonemes.
 if np.max(np.abs(x),initial=0)>0.002:
  nonzero=np.flatnonzero(np.abs(x)>max(.002,np.max(np.abs(x))*.015))
  if len(nonzero):x=x[max(0,nonzero[0]-800):min(len(x),nonzero[-1]+801)]
 if len(x)>SAMPLES:return None
 start=(SAMPLES-len(x))//2;y=np.zeros(SAMPLES,np.float32);y[start:start+len(x)]=x
 return np.round(np.clip(y,-1,.999969)*32768).astype(np.int16)
def run():
 source=list(rows());seen={};speaker_split={};duplicates=0;rejected=collections.Counter();accepted=[]
 original_count=len(source)
 source=[r for r in source if not (r['label']=='UNKNOWN' and r['word'] in HOMOPHONE_NEGATIVES.get(r['language'],set()))]
 rejected['homophone_negative']=original_count-len(source)
 out=DATA/'prepared';out.mkdir(exist_ok=True)
 staging=out/'pcm-staging.npy'
 pcm=np.lib.format.open_memmap(staging,mode='w+',dtype=np.int16,shape=(len(source)+3000,SAMPLES))
 def decode(row):
  try:return row,window(read(row['path'])),None
  except Exception as e:return row,None,'decode:'+type(e).__name__
 def decoded_rows():
  with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
   for start in range(0,len(source),128):yield from pool.map(decode,source[start:start+128])
 for number,(row,x,decode_error) in enumerate(decoded_rows()):
  group=row['speaker'];part=row['split']
  if group in speaker_split and speaker_split[group]!=part:raise ValueError('speaker partition leak')
  speaker_split[group]=part
  if row['sha256'] in seen:
   old=seen[row['sha256']]
   if old['label']!=row['label']:raise ValueError('duplicate audio has conflicting labels')
   duplicates+=1;continue
  seen[row['sha256']]=row
  if decode_error:rejected[decode_error]+=1;continue
  if x is None:rejected['longer_than_1.2s']+=1;continue
  if np.max(np.abs(x.astype(np.int32)),initial=0)<3:rejected['empty_speech_clip']+=1;continue
  # Decoded PCM equality catches copies in different audio containers.
  h=hashlib.sha256(x.tobytes()).hexdigest()
  if h in seen:duplicates+=1;continue
  seen[h]=row;row=dict(row,pcm_sha256=h);accepted.append(row);pcm[len(accepted)-1]=x
  if number%10000==0:print('decoded',number,'/',len(source),flush=True)
 rng=np.random.default_rng(20261030)
 noise_paths=sorted((DATA/'noise').glob('*.wav'))
 noise=[]
 for i,path in enumerate(noise_paths):
  a=read(path);part='test' if i==0 else 'validation' if i==1 else 'train';noise.append((a,part,path.name))
  for j in range(180 if part!='train' else 220):
   offset=int(rng.integers(0,max(1,len(a)-SAMPLES)))
   y=a[offset:offset+SAMPLES]*rng.uniform(.01,.3)
   if len(y)!=SAMPLES:continue
   row=dict(path=str(path),label='SILENCE',word='',language='none',source='GSC background noise',
     kind='non-speech',speaker='noise:'+path.name,split=part,license='CC-BY-4.0',segment_start=offset,
     sha256=digest(path),pcm_sha256=hashlib.sha256(y.tobytes()).hexdigest())
   accepted.append(row);pcm[len(accepted)-1]=np.round(np.clip(y,-1,.999969)*32768).astype(np.int16)
   row['pcm_sha256']=hashlib.sha256(pcm[len(accepted)-1].tobytes()).hexdigest()
 for part in ['train','validation','test']:
  for j in range(180):
   y=rng.normal(0,rng.uniform(0,.003),SAMPLES).astype(np.float32)
   accepted.append(dict(label='SILENCE',word='',language='none',source='procedural quiet',kind='non-speech',
     speaker='procedural:'+part,split=part,seed=20261030,pcm_sha256=hashlib.sha256(y.tobytes()).hexdigest()))
   pcm[len(accepted)-1]=np.round(y*32768).astype(np.int16)
   accepted[-1]['pcm_sha256']=hashlib.sha256(pcm[len(accepted)-1].tobytes()).hexdigest()
 final_pcm=np.lib.format.open_memmap(out/'pcm.npy',mode='w+',dtype=np.int16,shape=(len(accepted),SAMPLES))
 for start in range(0,len(accepted),256):final_pcm[start:start+256]=pcm[start:min(start+256,len(accepted))]
 final_pcm.flush();del pcm;staging.unlink();pcm=final_pcm
 save(out/'records.json',accepted)
 cached=np.lib.format.open_memmap(out/'features.npy',mode='w+',dtype=np.int8,shape=(len(accepted),FRAMES,40))
 for i in range(len(accepted)):
  wave=pcm[i]
  cached[i]=window_features(wave)
  if i%5000==0:print('native frontend',i,'/',len(accepted),flush=True)
 cached.flush()
 # Validation/test are computed once, without training augmentation.
 for part in ['validation','test']:
  ids=[i for i,r in enumerate(accepted) if r['split']==part]
  x=np.asarray(cached[ids]);assert x.shape[1:]==(FRAMES,40)
  np.savez(out/f'{part}.npz',x=x,y=np.array([LABELS.index(accepted[i]['label']) for i in ids]),ids=ids)
  print(part,len(ids),flush=True)
 counts=collections.Counter((r['label'],r['language'],r['kind'],r['split']) for r in accepted)
 table=[dict(label=k[0],language=k[1],kind=k[2],split=k[3],samples=n,
   speakers=len({r['speaker'] for r in accepted if (r['label'],r['language'],r['kind'],r['split'])==k})) for k,n in sorted(counts.items())]
 inventory={p.stem:json.loads(p.read_text()) for p in (DATA/'inventory').glob('*available.json')}
 # Do not publish raw IDs or audio file paths.
 manifest=dict(schema_version=1,labels=LABELS,aliases=WORDS,window_samples=SAMPLES,frames=FRAMES,
  source_records=original_count,accepted_records=len(accepted),duplicates_removed=duplicates,rejected=dict(rejected),
  partition='SHA256 source speaker; synthetic preset voice; background file',speaker_overlap=0,
  corpus_sha256=digest(out/'records.json'),pcm_sha256=digest(out/'pcm.npy'),counts=table,available_metadata=inventory,
  limitations=['MSWC segments may contain alignment errors.','No verified French-Canadian accent labels.',
  'Acoustic homophones (right/write, haut/eau, bas/bat) cannot be reliably distinguished without context; excluded conflicting negatives.',
  'Clip evaluation uses 500 ms quiet frontend context. Streaming evaluation is separate.',
  'MSWC available counts are metadata counts; accepted counts above are retained decoded clips.',
  'Sentences longer than 1.2 seconds excluded; phrase coverage reported separately.'])
 save(PROJECT/'datasets/dataset_manifest.json',manifest)
 print('prepared',len(accepted),'rejected',dict(rejected),'duplicates',duplicates,flush=True)
if __name__=='__main__':run()
