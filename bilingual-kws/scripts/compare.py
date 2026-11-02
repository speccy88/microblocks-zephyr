"""Select by bilingual HUMAN validation macro-F1, subject to measured host gates.

Test metrics never participate in ranking. Keep real/synthetic denominators
separate; null device measurements remain null.
"""
import argparse,json,shutil
import numpy as np
from common import PROJECT,save,digest,LABELS
def read(path):return json.loads(path.read_text())
def run(a):
 rows=[]
 for name in a.names:
  report=PROJECT/'reports';model=PROJECT/'models'/f'{name}_int8.tflite'
  val=read(report/f'{name}-int8-validation.json');flo=read(report/f'{name}-float-validation.json')
  test=read(report/f'{name}-int8-test.json');train=read(report/f'{name}-training.json');host=read(report/f'{name}-tflm.json');manifest=read(model.with_suffix('.json'))
  keys=['human:en','human:fr']
  if any(val['subgroups'][k] is None for k in keys):raise ValueError('missing bilingual human validation support')
  score=sum(val['subgroups'][k]['macro_f1_supported'] for k in keys)/2
  loss=flo['subgroups']['kind:human']['accuracy']-val['subgroups']['kind:human']['accuracy']
  float_scores=np.load(__import__('common').DATA/f'prepared/{name}-float-validation-predictions.npz')['scores']
  int_scores=np.load(__import__('common').DATA/f'prepared/{name}-int8-validation-predictions.npz')['scores']
  eligible=loss<=.02 and manifest['model_bytes']<=150000 and host['arena_used_bytes']<=131072 and host['argmax_agreement']>=.99
  rows.append(dict(name=name,architecture=train['architecture'],parameters=manifest['parameters'],model_bytes=manifest['model_bytes'],
   human_validation_bilingual_macro_f1=score,validation_quantization_accuracy_loss=loss,eligible=eligible,
   estimated_macs=manifest.get('estimated_multiply_accumulates'),
   float_int8_validation_argmax_agreement=float(np.mean(float_scores.argmax(1)==int_scores.argmax(1))),
   float_int8_validation_mean_abs_probability_error=float(np.mean(np.abs(float_scores-int_scores))),
   float_int8_validation_max_abs_probability_error=float(np.max(np.abs(float_scores-int_scores))),
   test_accuracy=test['overall']['accuracy'],test_macro_f1=test['overall']['macro_f1'],
   human_test_accuracy=test['subgroups']['kind:human']['accuracy'],human_en_test_accuracy=test['subgroups']['human:en']['accuracy'],
   human_fr_test_accuracy=test['subgroups']['human:fr']['accuracy'],synthetic_test_accuracy=test['subgroups']['kind:synthetic']['accuracy'],
   host_tflm_arena_used_bytes=host['arena_used_bytes'],host_tflm_median_ms=host['invoke_ms_median'],host_tflm_p95_ms=host['invoke_ms_p95'],
   training_seconds=train['training_seconds'],peak_vram_mib=train['sampled_device_wide_peak_vram_mib'],
   native_p4_arena=None,native_p4_median_ms=None,native_p4_p95_ms=None))
 ranked=sorted([r for r in rows if r['eligible']],key=lambda r:r['human_validation_bilingual_macro_f1'],reverse=True)
 if not ranked:raise ValueError('No candidate meets quantization/host compatibility gates')
 frontier=[r for r in ranked if r['human_validation_bilingual_macro_f1']>=ranked[0]['human_validation_bilingual_macro_f1']-.005]
 best=min(frontier,key=lambda r:(r['estimated_macs'] or float('inf'),r['model_bytes'],-r['human_validation_bilingual_macro_f1']))
 save(PROJECT/'reports/candidate-comparison.json',dict(selection_metric='mean en/fr HUMAN validation macro-F1 over supported classes; within 0.005 of best prefer fewer static MACs then smaller model; no test selection',candidates=rows,selected=best['name']))
 if a.install:
  name=best['name'];source=PROJECT/'models'/f'{name}_int8.tflite'
  shutil.copyfile(source,PROJECT/'models/voice_commands_int8.tflite')
  shutil.copyfile(source.with_suffix('.json'),PROJECT/'models/voice_commands_int8.json')
  shutil.copyfile(PROJECT/'models'/name/'best_checkpoint.keras',PROJECT/'models/best_checkpoint.keras')
  lexicon=PROJECT/'models'/name/'lexicon.json'
  if lexicon.exists():shutil.copyfile(lexicon,PROJECT/'models/lexicon.json')
  elif (PROJECT/'models/lexicon.json').exists():(PROJECT/'models/lexicon.json').unlink()
  manifest=read(source.with_suffix('.json'));manifest['selected_candidate']=name;manifest['selection']=best
  training_report=PROJECT/'reports'/f'{name}-training.json'
  manifest['training_report_sha256']=digest(training_report)
  manifest['training_records_sha256']=read(training_report)['dataset_sha256']
  manifest['evaluation_canonical_pcm_label_split_sha256']=read(PROJECT/'reports/corpus-audit.json')['canonical_pcm_label_split_sha256']
  manifest['evaluation_report_sha256']=digest(PROJECT/'reports'/f'{name}-int8-test.json')
  save(PROJECT/'models/model_manifest.json',manifest);save(PROJECT/'models/labels.json',LABELS)
 print(json.dumps(dict(selected=best['name'],architecture=best['architecture'],score=best['human_validation_bilingual_macro_f1']),indent=2))
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('names',nargs='+');p.add_argument('--install',action='store_true');run(p.parse_args())
