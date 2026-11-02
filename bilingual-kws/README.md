# Bilingual TinyML commands for native Zephyr / ESP32-P4

This project trains an offline semantic classifier for UP, DOWN, LEFT, RIGHT,
ANGRY, HAPPY, TIRED, NORMAL, UNKNOWN and SILENCE. English and French aliases map
to the same action. See [the implementation contract](SPEC.md). Measurements
and deployment readiness are recorded in [reports/results.md](reports/results.md).

The trained artifacts and native integration are experimental. Held-out replay
exposes missed commands and false triggers; longer French aliases and
French-Canadian accents need further work. Use the measured results when
choosing a firmware candidate, and retain explicit activation.

The existing Okay Nabu frontend/PCM worker is reused. The generic dense-only
neural importer stays restricted. This is a trusted, firmware-embedded CNN with
a separate verified operator resolver. No microphone starts on import or boot.
No firmware is flashed by any command below.

## Environment and reproduction

Run from the repository root in WSL Ubuntu. A Python 3.12 environment avoids
the host's Python 3.14 framework compatibility constraints. Keep audio outside
Git, on the Linux filesystem. The default external corpus is
`/home/fred/bilingual-kws-data`; set `KWS_DATA` to override it.

```bash
python3.12 -m venv /home/fred/bilingual-kws-venv
source /home/fred/bilingual-kws-venv/bin/activate
pip install -r bilingual-kws/requirements.txt
python bilingual-kws/scripts/preflight.py
python bilingual-kws/scripts/build_frontend.py
python bilingual-kws/scripts/build_host_tflm.py --jobs 1
python bilingual-kws/scripts/download_datasets.py --dataset gsc
python bilingual-kws/scripts/download_datasets.py --dataset mswc --language fr
python bilingual-kws/scripts/download_datasets.py --dataset mswc --language en --target-shards
python bilingual-kws/scripts/audit_downloads.py
python bilingual-kws/scripts/generate_tts.py --engine piper --voices 24
python bilingual-kws/scripts/generate_tts.py --engine kokoro
python bilingual-kws/scripts/prepare_dataset.py
python bilingual-kws/scripts/repartition.py
python bilingual-kws/scripts/audit_corpus.py
python bilingual-kws/scripts/supplement_phrases.py
bash bilingual-kws/scripts/run_experiments.sh
```

The exact pinned TFLM checkout defaults to the existing workspace path. Supply
`--tflm /your/checkout` to the frontend and host build scripts elsewhere.
The optional `generate_tts.py --cuda` requires a CUDA-enabled ONNX Runtime
installation (`onnxruntime-gpu==1.23.2` used locally). CPU synthesis works too.
The phrase supplement is generated after base preparation and appended between
the TinyConv baseline and DS-CNN stage. The final held-out evaluation cohort is
shared by all candidates. `configs/experiments.yaml` records the distinct
training budgets, sampling policies and temporal strides. Set `KWS_RESUME=1`
when resuming the pipeline with completed training reports; fresh training is
the default. The selected architecture is retrained, then compared with a
lexical-head experiment. Test metrics never select a model.

Local execution may reuse verified CUDA 12 libraries rather than install another
copy. In that case prepend `KWS_CUDA_SITE=/path/to/site-packages bash
bilingual-kws/scripts/with_cuda.sh` to the Python command. The preflight must
execute on GPU; enumeration alone is insufficient. The environment's actual
versions and machine limits are retained in `reports/preflight.json` and the
training reports. The clean requirements route is independent of those local
shared-library paths.

For each trained candidate:

```bash
python bilingual-kws/scripts/quantize.py \
  --checkpoint bilingual-kws/models/tinyconv/best_checkpoint.keras \
  --output bilingual-kws/models/tinyconv_int8.tflite
python bilingual-kws/scripts/evaluate.py \
  --model bilingual-kws/models/tinyconv/best_checkpoint.keras --name tinyconv-float
python bilingual-kws/scripts/evaluate.py \
  --model bilingual-kws/models/tinyconv_int8.tflite --name tinyconv-int8
python bilingual-kws/scripts/build_host_tflm.py
python bilingual-kws/scripts/benchmark.py \
  --model bilingual-kws/models/tinyconv_int8.tflite --name tinyconv
python3 tools/validate.py
```

After all four candidates have completed, repeat the compact host timing probe
with training/build processes idle, then install the validation winner and make
the final report. This does not retrain or use test scores for selection:

```bash
for candidate in tinyconv dscnn dscnn_retrain dscnn_lexical; do
  python bilingual-kws/scripts/benchmark.py \
    --model bilingual-kws/models/${candidate}_int8.tflite --name "$candidate"
done
python bilingual-kws/scripts/compare.py \
  tinyconv dscnn dscnn_retrain dscnn_lexical --install
python bilingual-kws/scripts/benchmark_stream.py \
  --model bilingual-kws/models/voice_commands_int8.tflite
# Build/record the native image using esp32p4/deployment.md before reporting.
python bilingual-kws/scripts/finalize_report.py
```

`scripts/final_host_checks.sh` performs the final evaluation/timing/comparison
sequence above. The byte-level audit excludes a held-out all-zero procedural
silence duplicate from the final test cohort; it changes no speech or weights.
The baseline's `--exclude-fast-phrases` option preserves its original corpus
stage when retraining from a cache that already contains the phrase supplement.

## Corpus and evaluation contract

GSC v0.02 supplies real isolated English commands and negatives. MSWC 1.0
supplies forced-aligned real English/French word segments and original source
speaker IDs. Full metadata counts are audited before selection. Downloaded,
decoded, duration-eligible and retained counts are reported separately.
Single source speakers always remain in one split, including their negatives.
Rare human action/language cells receive deterministic speaker stratification
before training, so each has held-out validation and test speakers.
Duplicate encoded audio and identical normalized PCM are removed.

Piper MLS and LibriTTS presets supplement human samples. Voices are disjoint by
partition. Kokoro is held out as an entire synthesis engine. Siwis is excluded
from training because Piper Siwis and Kokoro French share a source speaker.
TTS is never counted as human speech. French-Canadian generalization needs
separate evidence; European-French TTS does not establish it.

Only silence/non-speech may omit a language. Every reported subgroup includes
sample support. Macro-F1 for all ten classes is distinguished from macro-F1
over classes represented in a subgroup. Model selection uses validation only;
test scores are for final evaluation. No clip metric is described as a
continuous real-world false-trigger study.

Audio is 16 kHz mono PCM16. The window is 1.2 seconds / 118 frames / 40 channels.
Training invokes the compiled firmware integer frontend and varies preceding
background context; validation uses 500 ms quiet preceding context. Firmware
maintains streaming state. All frontend parameters, integer rounding and PCAN
are unchanged. Clip and continuous-stream evaluation are separate scopes.
Waveform augmentation runs during training, before this frontend. The modest
resampling augmentation changes speed and pitch together; independent
phase-vocoder pitch stretching is not claimed.

## Firmware and blocks

See [deployment instructions](esp32p4/deployment.md) for the native build and
the explicit start/stop/event workflow. Import
`boards/waveshare_esp32p4_wifi6/integration/P4_Voice_Commands.ubl` and optionally
`esp32p4/microblocks/Voice_Eyes.ubl`. Eye state does not initialize any display.
`reports/eyes_preview.png` is a host schematic, not physical display evidence.

## Licenses

New training/integration code is MIT unless an individual SmallVM/editor file
states MPL-2.0. TFLM/frontend are Apache-2.0. GSC and MSWC are CC-BY-4.0;
Piper's selected MLS/LibriTTS/Siwis model cards name CC-BY-4.0 source data.
Kokoro weights/preset embeddings are Apache-2.0. Exact revisions, downloaded
cards, checksums and source references are retained. Raw public speech and
private source-speaker IDs stay outside Git. See `reports/sources.md` and the
repository `LICENSES.md` for attribution and inspected alternatives.
