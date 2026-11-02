"""Create the requested source-backed Markdown report and static figures."""
import json,math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from common import PROJECT,DATA,LABELS,save,digest
def read(path):return json.loads(path.read_text())
def pct(x):return 'unmeasured' if x is None else f'{100*x:.2f}%'
def run():
 reports=PROJECT/'reports';comparison=read(reports/'candidate-comparison.json');selected=comparison['selected'];rows=comparison['candidates'];best=next(r for r in rows if r['name']==selected)
 test=read(reports/f'{selected}-int8-test.json');manifest=read(PROJECT/'datasets/dataset_manifest.json');model=read(PROJECT/'models/model_manifest.json')
 train=read(reports/f'{selected}-training.json');host=read(reports/f'{selected}-tflm.json')
 # Static images are requested artifacts; plot inspected counts directly.
 cm=np.array(test['overall']['confusion']);fig,ax=plt.subplots(figsize=(10,8));im=ax.imshow(cm,cmap='Blues')
 ax.set_xticks(range(10),LABELS,rotation=45,ha='right');ax.set_yticks(range(10),LABELS);ax.set_xlabel('Predicted');ax.set_ylabel('True');ax.set_title(f'{selected} INT8: held-out test clips (counts)')
 for i in range(10):
  for j in range(10):ax.text(j,i,str(cm[i,j]),ha='center',va='center',fontsize=8,color='white' if cm[i,j]>cm.max()*.5 else 'black')
 fig.colorbar(im,ax=ax,label='Clips');fig.tight_layout();fig.savefig(reports/'confusion_matrix.png',dpi=160);plt.close(fig)
 fig,axes=plt.subplots(2,2,figsize=(12,8));axes=axes.ravel()
 for r in rows:
  h=read(reports/f'{r["name"]}-training.json')['history'];epochs=np.arange(1,len(h['loss'])+1)
  for ax,metric in zip(axes,['accuracy','val_accuracy','loss','val_loss']):ax.plot(epochs,h[metric],label=r['name'])
 for ax,label in zip(axes,['Training accuracy','Validation accuracy','Training cross entropy','Class-weighted validation cross entropy']):ax.set_ylabel(label)
 for ax in axes:ax.set_xlabel('Epoch');ax.grid(alpha=.25);ax.legend(fontsize=8)
 fig.suptitle('CUDA training history; lexical head uses finer labels than direct action heads');fig.tight_layout();fig.savefig(reports/'training_curves.png',dpi=160);plt.close(fig)
 if digest(PROJECT/'models/voice_commands_int8.tflite')!=model['model_sha256']:raise ValueError('selected model hash mismatch')
 lines=['# Bilingual TinyML command results','',f'Selected artifact: **{selected}**. Model SHA256 `{model["model_sha256"]}`.',
  '', 'This report distinguishes trained host artifacts, pinned host TFLM execution, native Zephyr compilation and physical P4 acceptance. No board was flashed, reset or recorded during this task.',
  '', '## Candidate comparison','', '| Candidate | Parameters | INT8 bytes | Human EN accuracy | Human FR accuracy | All clips accuracy | Macro-F1 (10) | Host TFLM arena | Host TFLM median / p95 | GPU training |',
  '|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|']
 for r in rows:lines.append(f'| {r["name"]} | {r["parameters"]:,} | {r["model_bytes"]:,} | {pct(r["human_en_test_accuracy"])} | {pct(r["human_fr_test_accuracy"])} | {pct(r["test_accuracy"])} | {r["test_macro_f1"]:.4f} | {r["host_tflm_arena_used_bytes"]:,} B | {r["host_tflm_median_ms"]:.3f} / {r["host_tflm_p95_ms"]:.3f} ms | {r["training_seconds"]/60:.1f} min |')
 lines += ['', 'These are optimized candidates, not a controlled architecture-only ablation. TinyConv uses uniform semantic sampling and the base corpus. DS-CNN adds 59 duration-eligible French phrase examples and more unknown sampling; its head retains coarse frequency position. The refined and lexical candidates use human-priority sampling, a larger training budget and first temporal stride 4. All reported candidates use the same final held-out evaluation cohort. Full regimes: `configs/experiments.yaml`.',
  '', '| Candidate | Static MAC estimate / window | Sampled device-wide peak VRAM | Training epochs |', '|---|---:|---:|---:|']
 for r in rows:lines.append(f'| {r["name"]} | {r["estimated_macs"]:,} | {r["peak_vram_mib"]:,} MiB | {read(reports/(r["name"]+"-training.json"))["epochs"]} |')
 lines += ['',f'Selection criterion: {comparison["selection_metric"]}. INT8 validation accuracy loss on human speech must be <=2 percentage points, model <=150 KB, host TFLM arena <=128 KiB and host argmax agreement >=99%. The selected bilingual human validation macro-F1 is {best["human_validation_bilingual_macro_f1"]:.4f}.',
  '', 'The TinyConv device-wide VRAM peak includes overlapping conversion/synthesis processes; its own TensorFlow active-allocation peak is recorded separately. Device-wide peaks are sampled every second and can miss shorter excursions. MAC counts omit frontend, activation, Softmax and memory costs and do not establish P4 latency.',
  '', '**Host arena and timings are x86_64 results, not P4 measurements.** Native pointer size, kernels, cache, scheduling, audio and PSRAM change the result. The firmware currently reserves 128 KiB for the voice arena.',
  '', '## Corpus and leakage audit','',f'Source records: {manifest["source_records"]:,}; retained including generated non-speech: {manifest["accepted_records"]:,}; duplicates removed: {manifest["duplicates_removed"]:,}. Exclusions: `{json.dumps(manifest["rejected"],sort_keys=True)}`.',
  '', 'Original source speakers are partitioned together; synthetic preset voices are partitioned together; noise source files are partitioned together. The corpus check reports zero speaker-group overlap. Encoded and normalized-PCM duplicates are removed. Known homophone negatives are excluded because the same sound cannot be trained with conflicting labels.',
  '', '| Action | Human EN train / val / test | Human FR train / val / test | Synthetic train / val / test |', '|---|---:|---:|---:|']
 def counts(label,kind,lang=None):return [sum(r['samples'] for r in manifest['counts'] if r['label']==label and r['kind']==kind and (lang is None or r['language']==lang) and r['split']==s) for s in ['train','validation','test']]
 for label in LABELS:lines.append(f'| {label} | {" / ".join(map(str,counts(label,"human","en")))} | {" / ".join(map(str,counts(label,"human","fr")))} | {" / ".join(map(str,counts(label,"synthetic")))} |')
 audit=read(reports/'corpus-audit.json')
 lines += ['', f'The independent byte-level audit found {audit.get("evaluation_excluded_all_zero_duplicates",0)} held-out all-zero procedural-silence duplicate. It is excluded from every final test metric; no speech clips, training labels or weights changed. Zero source-speaker overlap and zero cross-split PCM overlap hold for the resulting evaluation cohort. Original preparation metadata used pre-quantization float hashes for {sum(audit.get("legacy_prequantization_hash_fields",{}).values())} non-speech records; the audit instead hashes actual stored PCM16. The original training record file is retained for provenance.']
 lines += ['',f'Path-independent PCM/label/split digest: `{audit["canonical_pcm_label_split_sha256"]}`. Speaker separation uses corpus-provided IDs; identity overlap between independently published corpora cannot be excluded.',
  '', '### French alias coverage','', '| Alias | Human clips train / val / test | Human speaker groups train / val / test | TTS clips train / val / test | Test action recall: human / TTS |', '|---|---:|---:|---:|---:|']
 for action,words in manifest['aliases']['fr'].items():
  for word in words:
   def lexical(kind,field):return [sum(r[field] for r in audit['lexical_counts'] if r['language']=='fr' and r['text']==word and r['kind']==kind and r['split']==s) for s in ['train','validation','test']]
   accuracy=[next((r['action_recall'] for r in test.get('alias_metrics',[]) if r['language']=='fr' and r['text']==word and r['kind']==kind),None) for kind in ['human','synthetic']]
   lines.append(f'| {word} | {" / ".join(map(str,lexical("human","samples")))} | {" / ".join(map(str,lexical("human","speakers")))} | {" / ".join(map(str,lexical("synthetic","samples")))} | {" / ".join(map(pct,accuracy))} |')
 lines += ['', 'The `en colère` alias has only three training examples and no validation examples; all are synthetic. Complete utterances exceeding 1.2 seconds were excluded, not cropped through words. Faster complete-phrase synthesis improves coverage but does not establish natural long-phrase accuracy. Optional `look …` / `regarde …` samples are evaluated as phrases and remain exploratory. The attempted Gilles voice was rejected before training because its vocabulary lacked a required nasalization symbol; see `rejected-tts.json`.']
 lines += ['', 'Silence has separate source-file/procedural non-speech counts in the manifest. TTS and procedural audio are never counted as human speech. All corpus details and available-vs-retained counts are in `datasets/dataset_manifest.json`; the external private record manifest retains speaker IDs and segment provenance.',
  '', '## Selected model: held-out performance','', '| Group | Clips | Speaker groups | Accuracy | Macro-F1 over represented classes |', '|---|---:|---:|---:|---:|']
 for key in ['kind:human','human:en','human:fr','kind:synthetic','source:Piper','source:Kokoro','kind:non-speech']:
  r=test['subgroups'].get(key)
  if r:lines.append(f'| {key} | {r["samples"]:,} | {r.get("speaker_groups","—")} | {pct(r["accuracy"])} | {r["macro_f1_supported"]:.4f} |')
 lines += ['', 'Kokoro is an entirely held-out synthesis engine. Piper and Kokoro Siwis are both excluded from training because they share a source voice. Preset-voice separation does not prove real human generalization. French-Canadian accent coverage is unverified.',
  '', '| Class | Precision | Recall | F1 | Support (all test clips) |','|---|---:|---:|---:|---:|']
 for r in test['overall']['per_class']:lines.append(f'| {r["label"]} | {r["precision"]:.4f} | {r["recall"]:.4f} | {r["f1"]:.4f} | {r["support"]} |')
 for key in ['human:en','human:fr']:
  lines += ['',f'### {key}: real speech per class','', '| Class | Precision | Recall | F1 | Clips |', '|---|---:|---:|---:|---:|']
  for r in test['subgroups'][key]['per_class']:lines.append(f'| {r["label"]} | {r["precision"]:.4f} | {r["recall"]:.4f} | {r["f1"]:.4f} | {r["support"]} |')
  r=test['subgroups'][key];ci=r.get('accuracy_speaker_bootstrap_95_ci')
  if ci:lines += ['',f'{key} accuracy speaker-cluster bootstrap 95% interval (200 resamples): {pct(ci[0])}–{pct(ci[1])}. Small per-command French supports remain a material limitation; aggregate accuracy does not establish each alias.']
 lines += ['', '### Clip rejection tradeoff','', '| Confidence threshold | Accepted-command precision | Known-command recall | UNKNOWN/SILENCE false accepts / negatives |', '|---|---:|---:|---:|']
 for r in test.get('threshold_only_clip_metrics',[]):lines.append(f'| {r["threshold"]:.2f} | {pct(r["command_precision"])} | {pct(r["known_command_recall"])} | {r["negative_false_accepts"]} / {r["negative_samples"]} ({pct(r["negative_false_accept_rate"])}) |')
 lines += ['', 'These are threshold-only isolated-clip metrics. They neither include temporal filtering nor estimate events/hour. The firmware default of 0.85 is an explicit engineering setting, not a threshold optimized on this test set. Increasing it can reduce false accepts while missing more commands.',
  '', '| Utterance form (human + TTS) | Clips | Accuracy | Macro-F1 over represented classes |', '|---|---:|---:|---:|']
 for key in ['actions:single_word','actions:phrase']:
  r=test['subgroups'].get(key)
  if r:lines.append(f'| {key} | {r["samples"]} | {pct(r["accuracy"])} | {r["macro_f1_supported"]:.4f} |')
 lines += ['', '## Frontend, quantization and memory','',
  'The compiled existing native integer microfrontend prepares training, calibration and evaluation inputs. PCM is 16 kHz mono signed16, with a 1.2 s / 118x40 feature window. Parameters match the existing 30 ms / 10 ms frontend, including PCAN, filterbank, noise reduction and exact integer rounding. Training varies prior background context; clip evaluation uses 500 ms quiet context. Firmware runs continuously and has separate replay evaluation.',
  '', f'Input: `{model["input"]}`. Output: `{model["output"]}`. Tensor types: `{model["all_tensor_dtypes"]}`. Operators: `{model["operators"]}`. Calibration uses {model["calibration_samples"]} training examples, including {model["calibration_human_samples"]} human clips. No validation/test audio calibrates the graph.',
  '',f'Output semantics: {model["output_semantics"]}. Validation float/INT8 argmax agreement: {pct(best["float_int8_validation_argmax_agreement"])}; mean absolute probability error {best["float_int8_validation_mean_abs_probability_error"]:.6f}; maximum {best["float_int8_validation_max_abs_probability_error"]:.6f}; human validation accuracy loss {100*best["validation_quantization_accuracy_loss"]:.3f} percentage points.',
  '', f'Pinned host TFLM used {host["arena_used_bytes"]:,} arena bytes. Maximum difference from desktop LiteRT was {host["max_output_lsb_difference"]} INT8 LSB; argmax agreement {pct(host["argmax_agreement"])}. This checks actual AllocateTensors/Invoke, not only operator names. The model is firmware mapped and not copied into the arena.',
  '', f'Training framework: TensorFlow {train["tensorflow"]}; GPU {train["gpu_details"].get("device_name")}; sampled device-wide peak VRAM {train["sampled_device_wide_peak_vram_mib"]} MiB; TensorFlow active-allocation peak {train["gpu_memory"]["peak"]:,} bytes. The local WSL environment has two vCPUs and about 6 GB RAM. Float32 training was used for these small models.',
  '', 'TFLM arena use includes its kernel scratch. Additional runtime memory includes the 4,720-byte feature ring, 8,256-byte permanent PCM queue, 16,384-byte KWS stack, frontend allocations, synchronization/metrics and existing VM/media state. The offline frontend allocator test peaks at 11,056 requested bytes on x86_64. Host arena use is not total runtime RAM. Device pressure and stack high-water measurements remain pending.']
 lexical=next((r for r in rows if r['name'].endswith('_lexical')),None)
 if lexical:
  lex_train=read(reports/(lexical['name']+'-training.json'))
  lines += ['', '## Semantic versus lexical classifier','',f'The lexical-head experiment learns {lex_train["lexical_classes"]} individual word/language classes. A fixed one-hot integer FullyConnected layer sums the lexical Softmax probabilities into ten semantic probabilities in the exported model; the action mapping is embedded on-device, not performed by a PC. Its INT8 bilingual human validation macro-F1 is {lexical["human_validation_bilingual_macro_f1"]:.4f}. The same size, quantization and host TFLM gates apply to all four candidates. Different seeds and one run per regime limit architecture-level conclusions.',
   '',f'The selected artifact uses **{model["output_semantics"]}**. Direct classifiers have a final ten-way Softmax; the lexical alternative has normalized sums after its finer Softmax. The simpler direct classifier is preferred within the stated validation near-tie rule.']
 if (reports/'stream-benchmark.json').exists():
  stream=read(reports/'stream-benchmark.json');neg=stream['negatives'];pos=stream['positives']
  if stream['model_sha256']!=model['model_sha256']:raise ValueError('stale stream report for a different model')
  lines += ['', '## Continuous host replay','',f'The same native frontend and C decision policy replayed {neg["audio_seconds"]/3600:.3f} hours of constructed held-out human non-command audio: {neg["events"]} events, {neg["constructed_negative_events_per_hour"]:.2f} events/hour. This concatenated isolated-word corpus is not representative ambient conversation; real-world false positives/hour remain unmeasured.',
   '',f'Constructed-negative Poisson rate 95% interval: {neg["poisson_rate_95_ci"][0]:.2f}–{neg["poisson_rate_95_ci"][1]:.2f} events/hour. This interval only describes this constructed corpus and does not account for its mismatch with ambient audio.',
   '',f'Positive replay: {pos["matched_commands"]}/{pos["samples"]} matched; {pos["missed_commands"]} missed; {pos["extra_or_wrong_events"]} extra/wrong events. Audio-time delay relative to estimated speech-energy endpoint, detected commands only: median {pos["audio_time_delay_ms_median"]} ms, p95 {pos["audio_time_delay_ms_p95"]} ms. This excludes P4 compute/queue/transport time and is not a physical end-to-end latency claim. Negative delay means a trigger before the estimated endpoint.']
  if (reports/'dscnn_lexical-stream.json').exists():
   other=read(reports/'dscnn_lexical-stream.json')
   if other['model_sha256']!=digest(PROJECT/'models/dscnn_lexical_int8.tflite'):raise ValueError('stale lexical replay report')
   lines += ['', '| Host replay candidate | Constructed negative events/hour | Matched human commands | Detected-only audio delay median / p95 |', '|---|---:|---:|---:|']
   for name,s in [(selected,stream),('dscnn_lexical',other)]:
    n=s['negatives'];p=s['positives'];lines.append(f'| {name} | {n["constructed_negative_events_per_hour"]:.2f} | {p["matched_commands"]} / {p["samples"]} | {p["audio_time_delay_ms_median"]:.1f} / {p["audio_time_delay_ms_p95"]:.1f} ms |')
   lines += ['', 'The lexical variant does not resolve the continuous-trigger problem. These test replays diagnose limitations after validation-based selection; they are not used to choose a new threshold or retrain on the test set. Neither candidate is recommended for unattended continuous operation.']
 build=read(reports/'native-build.json') if (reports/'native-build.json').exists() else None
 if build and build['model_sha256']!=model['model_sha256']:raise ValueError('native image uses a different model')
 lines += ['', '## Native build and physical acceptance','',
  ('Native Zephyr build: '+('PASS (compiled only)' if build.get('compiled') else '**not compiled**')+'. See `reports/native-build.json` and `reports/native-build.txt` for exact command, base commits, source hashes and build result.') if build else '**not compiled**: no successful native build report is present yet.',
  '', 'No physical microphone, firmware flash/reset, COM12 access, C6/network modification or display initialization occurred. P4 median/p95 inference, post-word latency, CPU use, total runtime RAM, acoustic accuracy, concurrent MicroBlocks responsiveness and sustained ambient false-trigger rate are **unmeasured for this new model**.',
  '', '## Comparison with existing Whistle evidence','', '| Property | New command model | Existing Whistle reference |','|---|---|---|',
  f'| Model bytes | {model["model_bytes"]:,} | 14,515,887 |',
  '| Output | Ten semantic scores | Free-form speech transcription |',
  '| Arena | 128 KiB reserved; measured host use above | 12 MiB job arena reserved |',
  '| P4 latency | Unmeasured | Historical controlled `happy`: 20.436 s after 2.5 s recording; 26.527 s TRANSCRIBING-to-Applied after 3 s recording in GP |',
  '| Controlled same-input comparative benchmark | Pending | Pending |',
  '', 'Whistle numbers come from existing `boards/waveshare_esp32p4_wifi6/docs/WHISTLE_NATIVE.md`, `docs/VOICE_EYES.md` and the 2026-10-29 evidence. They use different inputs and timing boundaries; no new device speedup ratio is asserted.',
  '', '## Deployment recommendation','',f'Use `{selected}` as the host-validated firmware candidate because it won the stated validation ranking and passed the integer/host-runtime gates. Physical deployment readiness still requires the explicit acceptance session in `esp32p4/deployment.md`, especially French-Canadian speakers, rare French emotion words, continuous negatives and actual P4 timing/RAM. Targets of <50 ms invocation and <500 ms post-word response are not established by host execution.',
  '', 'Reproduction commands: `README.md`, `scripts/run_experiments.sh`, `esp32p4/build.sh`. Source/attribution: `reports/sources.md`. No main merge or GitHub push is performed by this task.']
 if build and build.get('compiled'):
  lines += ['', '## Linked native artifact','',f'The combined image is {build["image_bytes"]:,} bytes, including the existing 14,515,887-byte Whistle model. The {build["voice_model_bytes"]:,}-byte command model is mapped read-only at {build["voice_model_start"]}–{build["voice_model_end"]}; its extracted ELF bytes match the selected TFLite SHA256. The offline revision-guarded image is `{build["guarded_image"]}`. It was not flashed.',
   '', '| Linker region | Static used / reserved bytes | Capacity |', '|---|---:|---:|']
  for name,r in build.get('linker_memory_regions',{}).items():lines.append(f'| {name} | {r["linker_used_bytes"]:,} | {r["region_bytes"]:,} |')
  lines += ['', 'The external-DRAM reservation includes the existing 16 MiB heap. The command arena/frontend allocate from that heap; adding them again to linker PSRAM reservation would double-count. Flash DROM/IROM are mapped views and these rows must not be summed. Total live runtime RAM still needs physical measurement.']
 lines += ['', '## Acceptance status','', '| Gate | Result |', '|---|---|',
  '| Actual local GPU training, checkpoint and INT8 artifact | Achieved |',
  '| Human speech, speaker-group split and held-out TTS engine | Achieved for documented corpus; cross-corpus identity uncertainty remains |',
  '| Eight bilingual action labels | Present and trained; per-alias recognition and French-Canadian robustness remain limited/unverified |',
  '| Fully INT8, ten semantic scores and pinned host TFLM Invoke | Achieved; direct and lexical output semantics distinguished above |',
  '| Model <100 KB / host arena <=128 KiB | Achieved for selected artifact |',
  '| Native Zephyr compilation and linked-model hash | '+('Achieved' if build and build.get('compiled') else 'Not compiled')+' |',
  '| MicroBlocks library/event integration and eye schematic | Implemented and packaged; no physical execution claim |',
  '| Low continuous false-positive rate | Not established; constructed replay exposes unacceptable false triggers for unattended use |',
  '| P4 <50 ms invocation / <500 ms post-word response | Unmeasured |',
  '| P4 concurrent VM, CPU, total RAM and microphone acoustics | Unmeasured |']
 (reports/'results.md').write_text('\n'.join(lines)+'\n')
 save(reports/'benchmarks.json',dict(candidates=rows,selected=selected,host_tflm=host,stream=read(reports/'stream-benchmark.json') if (reports/'stream-benchmark.json').exists() else None,lexical_stream=read(reports/'dscnn_lexical-stream.json') if (reports/'dscnn_lexical-stream.json').exists() else None,native_build=build,physical_p4=None))
 print(reports/'results.md')
if __name__=='__main__':run()
