"""Download licensed public corpora; bounded selected extraction, no tar extractall.

MSWC metadata is read before any labels are assigned. Shards are processed one
at a time per worker; only selected audio is retained. Full metadata inventory
and available counts differ from actual selected/downloaded counts.
"""
import argparse, collections, concurrent.futures, csv, io, json, tarfile, time
from pathlib import Path
import requests
from common import DATA, MSWC, MSWC_PIN, WORDS, label, split, save, digest

def download(url,path):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 if path.exists():return path
 for attempt in range(5):
  try:
   with requests.get(url,stream=True,timeout=(30,180)) as r:
    r.raise_for_status()
    with path.with_suffix(path.suffix+'.part').open('wb') as out:
     for b in r.iter_content(1<<20):out.write(b)
   path.with_suffix(path.suffix+'.part').replace(path)
   return path
  except requests.RequestException:
   if attempt==4:raise
   time.sleep(2**attempt)

def gsc():
 url='https://storage.googleapis.com/download.tensorflow.org/data/speech_commands_v0.02.tar.gz'
 archive=download(url,DATA/'downloads/gsc-v2.tar.gz')
 out=DATA/'manifests/gsc.jsonl';out.parent.mkdir(parents=True,exist_ok=True)
 counts=collections.Counter();available=collections.Counter();word_counts=collections.Counter();seen=set()
 with tarfile.open(archive,'r:gz') as tar,out.open('w') as manifest:
  for m in tar:
   p=Path(m.name)
   if not m.isfile() or p.suffix!='.wav':continue
   word=p.parent.name; action=label(word,'en');available[word]+=1
   if word=='_background_noise_':
    dest=DATA/'noise'/p.name;dest.parent.mkdir(exist_ok=True)
    dest.write_bytes(tar.extractfile(m).read());continue
   speaker=p.stem.split('_nohash_')[0];partition=split('gsc:'+speaker)
   key=(action,partition)
   cap=6500 if action=='UNKNOWN' and partition=='train' else 1800 if action=='UNKNOWN' else 3000
   if counts[key]>=cap:continue
   if action=='UNKNOWN' and word_counts[(word,partition)]>=(180 if partition=='train' else 60):continue
   raw=tar.extractfile(m).read();h=__import__('hashlib').sha256(raw).hexdigest()
   if h in seen:continue
   seen.add(h);counts[key]+=1;word_counts[(word,partition)]+=1;dest=DATA/'audio/gsc'/word/p.name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
   manifest.write(json.dumps(dict(path=str(dest),label=action,word=word,language='en',
    source='Google Speech Commands v0.02',kind='human',speaker='gsc:'+speaker,
    split=partition,sha256=h,license='CC-BY-4.0',sample_rate=16000))+'\n')
 save(DATA/'inventory/gsc.json',dict(available_words=dict(available),selected={str(k):v for k,v in counts.items()},url=url,sha256=digest(archive)))
 print('GSC selected',sum(counts.values()),flush=True)

def mswc(lang,workers=3,max_shards=None,target_shards=False):
 archive=download(f'{MSWC}/splits/{lang}/splits.tar.gz',DATA/f'downloads/{lang}-splits.tar.gz')
 selected={};available=collections.Counter();speakers=collections.defaultdict(set);quotas=collections.Counter()
 # Count complete metadata, keep capped records only; same speaker always in
 # one partition across words and languages (original Common Voice IDs).
 with tarfile.open(archive,'r:gz') as tar:
  for m in tar:
   if not m.name.endswith('.csv'):continue
   for row in csv.DictReader(io.TextIOWrapper(tar.extractfile(m),encoding='utf-8')):
    if row['VALID'].lower()!='true' or not row['SPEAKER']:continue
    word=row['WORD'];action=label(word,lang);speaker='mswc:'+row['SPEAKER'];partition=split(speaker)
    if action!='UNKNOWN':available[word]+=1;speakers[word].add(speaker)
    key=(action,partition)
    cap=6500 if action=='UNKNOWN' and partition=='train' else 1500 if action=='UNKNOWN' else 2200
    # Spread unknown selection over vocabulary rather than first alphabetic words.
    if action=='UNKNOWN' and int(__import__('hashlib').sha256(row['LINK'].encode()).hexdigest()[:8],16)%500:continue
    if quotas[key]>=cap:continue
    name=row['LINK'].replace('/','_');quotas[key]+=1
    selected[name]=dict(label=action,word=word,language=lang,source='MLCommons MSWC 1.0',
     kind='human',speaker=speaker,split=partition,license='CC-BY-4.0',
     source_sentence=row['LINK'].split('/')[-1].split('.')[0],sample_rate=48000)
 save(DATA/f'inventory/mswc-{lang}-available.json',dict(pin=MSWC_PIN,metadata_sha256=digest(archive),
  counts=dict(available),speakers={k:len(v) for k,v in speakers.items()},
  missing=[w for a in WORDS[lang].values() for w in a if not available[w]],
  requested_selection=len(selected),sampling='valid entries; capped metadata order, unknown SHA subsample; speaker SHA partition'))
 found=[]
 def shard(args):
  original,n=args;path=download(f'{MSWC}/opus/{lang}/{original}/audio/{n}.tar.gz',DATA/f'downloads/mswc-{lang}-{original}-{n}.tar.gz')
  local=[]
  with tarfile.open(path,'r:gz') as tar:
   for m in tar:
    name=Path(m.name).name
    if name not in selected:continue
    raw=tar.extractfile(m).read();h=__import__('hashlib').sha256(raw).hexdigest()
    dest=DATA/f'audio/mswc/{lang}'/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    local.append(dict(selected[name],path=str(dest),sha256=h,original_split=original,shard=n))
  print('MSWC',lang,original,n,'selected',len(local),flush=True)
  return local
 jobs=[]
 for original in ['train','dev','test']:
  n=int(requests.get(f'{MSWC}/opus/{lang}/{original}/n_files.txt',timeout=60).text)
  jobs += [(original,i) for i in range(min(n,max_shards) if max_shards else n)]
 if target_shards:
  # Audio shards are sorted by flattened word filename. Probe only their
  # first tar member over a bounded HTTP stream, then download every shard
  # spanning any target word. Retain negatives encountered in these shards.
  def first_word(job):
   original,n=job;url=f'{MSWC}/opus/{lang}/{original}/audio/{n}.tar.gz'
   with requests.get(url,stream=True,timeout=(30,60)) as r:
    r.raise_for_status()
    with tarfile.open(fileobj=r.raw,mode='r|gz') as tar:
     for m in tar:
      if m.isfile():return job,Path(m.name).name.split('_common_voice_')[0]
   raise ValueError('empty shard')
  with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
   starts=dict(pool.map(first_word,jobs))
  target_words=sorted({w for words in WORDS[lang].values() for w in words if ' ' not in w})
  chosen=[]
  for original,n in jobs:
   lo=starts[(original,n)];hi=starts.get((original,n+1),'\U0010ffff')
   if any(lo<=w<=hi for w in target_words):chosen.append((original,n))
  save(DATA/f'inventory/mswc-{lang}-shard-selection.json',dict(starts={str(k):v for k,v in starts.items()},
    selected=[list(j) for j in chosen],reason='all shards spanning target words; negatives retained from those shards'))
  jobs=chosen
  print('Target-bearing shards',lang,len(jobs),jobs,flush=True)
 out=DATA/f'manifests/mswc-{lang}.jsonl';out.parent.mkdir(parents=True,exist_ok=True)
 # Save each completed shard immediately so interrupted downloads are recoverable.
 with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool,out.open('w') as f:
  for local in pool.map(shard,jobs):
   found.extend(local)
   for row in local:f.write(json.dumps(row,ensure_ascii=False)+'\n')
   f.flush()
 wanted_targets={k for k,v in selected.items() if v['label']!='UNKNOWN'}
 found_names={Path(r['path']).name for r in found}
 missing_targets=sorted(wanted_targets-found_names)
 save(DATA/f'inventory/mswc-{lang}-selected.json',dict(samples=len(found),shards=len(jobs),complete=max_shards is None,target_shards_only=target_shards,
  requested_target_clips=len(wanted_targets),found_target_clips=len(wanted_targets&found_names),missing_target_clips=len(missing_targets)))
 if missing_targets and not max_shards:raise ValueError(f'{len(missing_targets)} selected target clips missing; shard coverage incomplete')

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--dataset',choices=['gsc','mswc'],required=True);p.add_argument('--language',default='fr',choices=['en','fr']);p.add_argument('--workers',type=int,default=3);p.add_argument('--max-shards',type=int);p.add_argument('--target-shards',action='store_true')
 a=p.parse_args();gsc() if a.dataset=='gsc' else mswc(a.language,a.workers,a.max_shards,a.target_shards)
