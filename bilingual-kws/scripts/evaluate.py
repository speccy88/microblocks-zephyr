"""Held-out metrics with explicit subgroup support; absent cells are null."""
import os
os.environ.setdefault('TF_CPP_MIN_LOG_LEVEL','2')
import argparse,json,time
import numpy as np
from sklearn.metrics import accuracy_score,precision_recall_fscore_support,confusion_matrix
from common import DATA,PROJECT,LABELS,save
def metrics(y,p):
 if not len(y):return None
 precision,recall,f1,support=precision_recall_fscore_support(y,p,labels=np.arange(10),zero_division=0)
 return dict(samples=len(y),accuracy=float(accuracy_score(y,p)),macro_f1=float(np.mean(f1)),macro_f1_supported=float(np.mean(f1[support>0])),
  per_class=[dict(label=c,precision=float(precision[i]),recall=float(recall[i]),f1=float(f1[i]),support=int(support[i])) for i,c in enumerate(LABELS)],
  confusion=confusion_matrix(y,p,labels=np.arange(10)).tolist())
def selective(y,scores):
 """Threshold-only clip proxy; independent of temporal/continuous filtering."""
 pred=scores.argmax(1);confidence=scores.max(1);known=y<8;out=[]
 for threshold in [.7,.8,.85,.9,.95,.98]:
  accept=(pred<8)&(confidence>=threshold);correct=accept&(pred==y);false_accept=accept&~known
  out.append(dict(threshold=threshold,accepted=int(accept.sum()),correct=int(correct.sum()),
   command_precision=float(correct.sum()/accept.sum()) if accept.any() else None,
   known_command_recall=float(correct.sum()/known.sum()) if known.any() else None,
   negative_false_accepts=int(false_accept.sum()),negative_samples=int((~known).sum()),
   negative_false_accept_rate=float(false_accept.sum()/(~known).sum()) if (~known).any() else None))
 return out
def alias_metrics(meta,y,pred):
 out=[]
 cells=sorted({(r['language'],r['word'],r['kind'],r['label']) for r in meta if r['label'] in LABELS[:8]})
 for lang,word,kind,label in cells:
  mask=np.array([r['language']==lang and r['word']==word and r['kind']==kind for r in meta])
  out.append(dict(language=lang,text=word,kind=kind,label=label,samples=int(mask.sum()),
   speaker_groups=len({r['speaker'] for r,m in zip(meta,mask) if m}),
   action_recall=float(np.mean(y[mask]==pred[mask])),
   predicted_counts={LABELS[i]:int(n) for i,n in enumerate(np.bincount(pred[mask],minlength=10)) if n}))
 return out
def run(a):
 import tensorflow as tf
 for gpu in tf.config.list_physical_devices('GPU'):tf.config.experimental.set_memory_growth(gpu,True)
 data=np.load(DATA/f'prepared/{a.split}.npz');x=data['x'].astype(np.float32)[...,None];y=data['y'];ids=data['ids']
 exclusions=DATA/'prepared/evaluation-exclusions.json'
 excluded_count=0
 if exclusions.exists():
  audit=json.loads(exclusions.read_text())
  from common import digest
  if audit['records_sha256']!=digest(DATA/'prepared/records.json'):raise ValueError('stale evaluation exclusion IDs; rerun audit_corpus.py')
  keep=~np.isin(ids,audit['indices']);excluded_count=int((~keep).sum());x=x[keep];y=y[keep];ids=ids[keep]
 records=json.loads((DATA/'prepared/records.json').read_text());meta=[records[i] for i in ids]
 if a.model.suffix=='.tflite':
  interpreter=tf.lite.Interpreter(model_path=str(a.model),num_threads=2);interpreter.allocate_tensors();inp=interpreter.get_input_details()[0];out=interpreter.get_output_details()[0]
  scores=[];timings=[]
  for v in x:
   s,z=inp['quantization'];q=np.clip(np.round(v/s+z),-128,127).astype(np.int8)
   interpreter.set_tensor(inp['index'],q[None]);start=time.perf_counter_ns();interpreter.invoke();timings.append((time.perf_counter_ns()-start)/1e6)
   s,z=out['quantization'];scores.append((interpreter.get_tensor(out['index'])[0].astype(np.float32)-z)*s)
  scores=np.stack(scores)
 else:
  net=tf.keras.models.load_model(a.model);scores=net.predict(x,batch_size=64,verbose=0);timings=[]
  lexicon=a.model.parent/'lexicon.json'
  if lexicon.exists():
   lex=json.loads(lexicon.read_text());mapped=np.zeros((len(scores),10),np.float32)
   for j,action in enumerate(lex['actions']):mapped[:,action]+=scores[:,j]
   scores=mapped
 pred=scores.argmax(1);report=dict(model=str(a.model.name),split=a.split,evaluation_excluded_all_zero_duplicates=excluded_count,overall=metrics(y,pred),subgroups={})
 report['threshold_only_clip_metrics']=selective(y,scores)
 report['alias_metrics']=alias_metrics(meta,y,pred)
 report['overall']['speaker_groups']=len({r['speaker'] for r in meta})
 for field,values in [('language',['en','fr','none']),('kind',['human','synthetic','non-speech']),('source',sorted({r['source'] for r in meta}))]:
  for value in values:
   mask=np.array([r[field]==value for r in meta]);report['subgroups'][f'{field}:{value}']=metrics(y[mask],pred[mask])
   if mask.any():report['subgroups'][f'{field}:{value}']['speaker_groups']=len({r['speaker'] for r,m in zip(meta,mask) if m})
 for lang in ['en','fr']:
  mask=np.array([r['language']==lang and r['kind']=='human' for r in meta]);report['subgroups'][f'human:{lang}']=metrics(y[mask],pred[mask])
  if mask.any():
   result=report['subgroups'][f'human:{lang}'];speakers=sorted({r['speaker'] for r,m in zip(meta,mask) if m});result['speaker_groups']=len(speakers)
   result['threshold_only_clip_metrics']=selective(y[mask],scores[mask])
   matrices=np.zeros((len(speakers),10,10),np.int32);lookup={s:i for i,s in enumerate(speakers)}
   for j,r in enumerate(meta):
    if mask[j]:matrices[lookup[r['speaker']],y[j],pred[j]]+=1
   rng=np.random.default_rng(20261030);boot=[]
   for _ in range(200):
    weights=np.bincount(rng.integers(len(speakers),size=len(speakers)),minlength=len(speakers));cm=np.tensordot(weights,matrices,axes=1)
    boot.append(np.trace(cm)/cm.sum())
   result['accuracy_speaker_bootstrap_95_ci']=np.percentile(boot,[2.5,97.5]).tolist()
 for form in ['single_word','phrase']:
  mask=np.array([r['label'] in LABELS[:8] and ((' ' in r['word'])==(form=='phrase')) for r in meta])
  report['subgroups']['actions:'+form]=metrics(y[mask],pred[mask])
 if timings:report['host_litert_invoke_ms']=dict(median=float(np.median(timings)),p95=float(np.percentile(timings,95)),scope='x86 desktop LiteRT; NOT P4 or TFLM')
 save(PROJECT/'reports'/f'{a.name}-{a.split}.json',report)
 np.savez(DATA/f'prepared/{a.name}-{a.split}-predictions.npz',scores=scores,pred=pred,y=y,ids=ids)
 print(json.dumps({k:v for k,v in report.items() if k not in ['subgroups','overall']},indent=2));print('accuracy',report['overall']['accuracy'],'macro-F1',report['overall']['macro_f1'])
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--model',type=__import__('pathlib').Path,required=True);p.add_argument('--name',required=True);p.add_argument('--split',choices=['validation','test'],default='test');run(p.parse_args())
