"""Add audit detail from SAVED predictions; no retraining or new inference."""
import argparse,json
import numpy as np
from common import DATA,PROJECT,save
from evaluate import selective,alias_metrics
def run(names):
 records=json.loads((DATA/'prepared/records.json').read_text())
 for name in names:
  for precision in ['float','int8']:
   for split in ['validation','test']:
    path=PROJECT/'reports'/f'{name}-{precision}-{split}.json'
    if not path.exists():continue
    data=np.load(DATA/f'prepared/{name}-{precision}-{split}-predictions.npz')
    meta=[records[i] for i in data['ids']];y=data['y'];scores=data['scores'];pred=data['pred']
    report=json.loads(path.read_text())
    report['threshold_only_clip_metrics']=selective(y,scores)
    report['alias_metrics']=alias_metrics(meta,y,pred)
    for lang in ['en','fr']:
     mask=np.array([r['language']==lang and r['kind']=='human' for r in meta])
     if mask.any():report['subgroups'][f'human:{lang}']['threshold_only_clip_metrics']=selective(y[mask],scores[mask])
    save(path,report)
    print(path.name)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('names',nargs='+');a=p.parse_args();run(a.names)
