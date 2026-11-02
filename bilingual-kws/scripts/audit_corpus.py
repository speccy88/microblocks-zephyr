"""Post-preparation independent leakage, class/language and phrase coverage audit."""
import collections,json,hashlib
import numpy as np
from common import PROJECT,DATA,save,digest
def run():
 records=json.loads((DATA/'prepared/records.json').read_text());speaker_parts=collections.defaultdict(set);hash_parts=collections.defaultdict(set);lexical=collections.Counter();lex_speakers=collections.defaultdict(set)
 pcm=np.load(DATA/'prepared/pcm.npy',mmap_mode='r');actual_hashes=[];legacy_mismatches=collections.Counter()
 for i,r in enumerate(records):
  actual=hashlib.sha256(pcm[i].tobytes()).hexdigest();actual_hashes.append(actual)
  if actual!=r['pcm_sha256']:
   if r['kind']!='non-speech':raise ValueError('prepared speech PCM differs from recorded hash')
   # Early preparation recorded pre-quantization FLOAT hashes for generated
   # non-speech. Preserve that original training manifest, audit stored PCM.
   legacy_mismatches[r['kind']]+=1
  speaker_parts[r['speaker']].add(r['split']);hash_parts[actual].add(r['split'])
  if r['label'] not in ['UNKNOWN','SILENCE']:
   key=(r['label'],r['word'],r['language'],r['kind'],r['split']);lexical[key]+=1;lex_speakers[key].add(r['speaker'])
 speaker_leaks=sum(len(v)>1 for v in speaker_parts.values());hash_leaks=sum(len(v)>1 for v in hash_parts.values())
 excluded=[];groups=collections.defaultdict(list)
 for i,h in enumerate(actual_hashes):groups[h].append(i)
 for h,indices in groups.items():
  if len(hash_parts[h])<=1:continue
  if not all(records[i]['kind']=='non-speech' and records[i]['label']=='SILENCE' and not np.any(pcm[i]) for i in indices):
   raise ValueError('Unexpected cross-split PCM duplicate; investigate before evaluation')
  # Canonical digital zero can occur after quantizing very quiet procedural
  # audio. Keep its training occurrence; exclude matching held-out occurrences.
  preferred=min(indices,key=lambda i:({'train':0,'validation':1,'test':2}[records[i]['split']],i))
  excluded.extend(i for i in indices if i!=preferred and records[i]['split']!='train')
 if speaker_leaks:raise ValueError('prepared speaker leakage')
 save(DATA/'prepared/evaluation-exclusions.json',dict(indices=sorted(excluded),records_sha256=digest(DATA/'prepared/records.json'),reason='held-out all-zero PCM duplicate of training silence; no speech or labels changed'))
 canonical=sorted((h,r['label'],r['language'],r['split'],r['kind']) for i,(h,r) in enumerate(zip(actual_hashes,records)) if i not in excluded)
 result=dict(records=len(records),evaluation_records=len(records)-len(excluded),evaluation_excluded_all_zero_duplicates=len(excluded),records_sha256=digest(DATA/'prepared/records.json'),canonical_pcm_label_split_sha256=hashlib.sha256(json.dumps(canonical,separators=(',',':')).encode()).hexdigest(),speaker_overlap=speaker_leaks,pcm_hash_overlap_raw=hash_leaks,pcm_hash_overlap_after_evaluation_exclusions=0,
  hash_scope='SHA256 of actual stored PCM16 bytes, not only preparation metadata',legacy_prequantization_hash_fields=dict(legacy_mismatches),
  lexical_counts=[dict(label=k[0],text=k[1],language=k[2],kind=k[3],split=k[4],samples=v,speakers=len(lex_speakers[k])) for k,v in sorted(lexical.items())])
 save(PROJECT/'reports/corpus-audit.json',result);print(json.dumps({k:v for k,v in result.items() if k!='lexical_counts'},indent=2))
if __name__=='__main__':run()
