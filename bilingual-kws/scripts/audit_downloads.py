"""Independent metadata-to-retained-clip coverage check for target-bearing shards."""
import collections,csv,io,json,tarfile
from pathlib import Path
from common import DATA,PROJECT,label,split,save
def run():
 report={}
 for lang in ['en','fr']:
  expected=set();counts=collections.Counter()
  with tarfile.open(DATA/f'downloads/{lang}-splits.tar.gz','r:gz') as tar:
   for m in tar:
    if not m.name.endswith('.csv'):continue
    for r in csv.DictReader(io.TextIOWrapper(tar.extractfile(m),encoding='utf-8')):
     if r['VALID'].lower()!='true' or not r['SPEAKER']:continue
     action=label(r['WORD'],lang)
     if action=='UNKNOWN':continue
     key=(action,split('mswc:'+r['SPEAKER']))
     if counts[key]>=2200:continue
     counts[key]+=1;expected.add(r['LINK'].replace('/','_'))
  actual={Path(json.loads(line)['path']).name for line in (DATA/f'manifests/mswc-{lang}.jsonl').open()}
  missing=expected-actual
  report[lang]=dict(expected_selected_target_clips=len(expected),found_selected_target_clips=len(expected&actual),missing=len(missing),
    scope='every metadata-selected target; class/split caps 2200; not all available source clips')
  if missing:raise ValueError(f'{lang} incomplete target coverage: {len(missing)}')
 save(PROJECT/'reports/download-audit.json',report);print(json.dumps(report,indent=2))
if __name__=='__main__':run()
