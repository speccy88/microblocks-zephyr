#!/usr/bin/env bash
# Reproducible bounded experiment sequence. Never accesses a device/serial port.
set -euo pipefail
kws_project="$(cd "$(dirname "$0")/.." && pwd)"
kws_repo="$(dirname "$kws_project")"
kws_python="${KWS_PYTHON:-/home/fred/bilingual-kws-venv/bin/python}"
kws_data="${KWS_DATA:-/home/fred/bilingual-kws-data}"
mkdir -p "$kws_data/logs"
cd "$kws_repo"
run_python() { bash "$kws_project/scripts/with_cuda.sh" "$kws_python" "$@"; }
evaluate_candidate() {
  local name="$1"
  run_python "$kws_project/scripts/quantize.py" --checkpoint "$kws_project/models/$name/best_checkpoint.keras" --output "$kws_project/models/${name}_int8.tflite" > "$kws_data/logs/$name-quantize.txt" 2>&1
  for partition in validation test; do
    run_python "$kws_project/scripts/evaluate.py" --model "$kws_project/models/$name/best_checkpoint.keras" --name "$name-float" --split "$partition" > "$kws_data/logs/$name-float-$partition.txt" 2>&1
    run_python "$kws_project/scripts/evaluate.py" --model "$kws_project/models/${name}_int8.tflite" --name "$name-int8" --split "$partition" > "$kws_data/logs/$name-int8-$partition.txt" 2>&1
  done
  run_python "$kws_project/scripts/benchmark.py" --model "$kws_project/models/${name}_int8.tflite" --name "$name" > "$kws_data/logs/$name-tflm.txt" 2>&1
}
if [[ ! -f "$kws_data/prepared/features.npy" ]]; then
  run_python "$kws_project/scripts/prepare_dataset.py" > "$kws_data/logs/prepare.txt" 2>&1
fi
run_python "$kws_project/scripts/repartition.py" > "$kws_data/logs/repartition.txt" 2>&1
run_python "$kws_project/scripts/audit_corpus.py" > "$kws_data/logs/corpus-audit.txt" 2>&1
for architecture in tinyconv dscnn; do
  echo "Training $architecture on local CUDA"
  unknown_probability=.22
  [[ "$architecture" == tinyconv ]] && unknown_probability=.10
  training_args=()
  [[ "$architecture" == tinyconv ]] && training_args+=(--exclude-fast-phrases)
  if [[ "${KWS_RESUME:-0}" != 1 || ! -f "$kws_project/reports/$architecture-training.json" ]]; then
    run_python "$kws_project/scripts/train.py" --arch "$architecture" --name "$architecture" --epochs 45 --steps 180 --unknown-probability "$unknown_probability" "${training_args[@]}" > "$kws_data/logs/$architecture-training.txt" 2>&1
  fi
  echo "Exporting/evaluating $architecture"
  evaluate_candidate "$architecture"
  if [[ "$architecture" == tinyconv && -f "$kws_data/manifests/tts-piper-phrases.jsonl" ]]; then
    run_python "$kws_project/scripts/append_phrases.py" > "$kws_data/logs/append-phrases.txt" 2>&1
    run_python "$kws_project/scripts/audit_corpus.py" > "$kws_data/logs/corpus-audit.txt" 2>&1
    evaluate_candidate tinyconv
  fi
done
run_python "$kws_project/scripts/compare.py" tinyconv dscnn > "$kws_data/logs/initial-comparison.txt"
architecture="$("$kws_python" -c "import json,pathlib; p=pathlib.Path('$kws_project/reports/candidate-comparison.json'); d=json.loads(p.read_text()); print(next(x['architecture'] for x in d['candidates'] if x['name']==d['selected']))")"
name="${architecture}_retrain"
echo "Retraining selected architecture: $architecture"
if [[ "${KWS_RESUME:-0}" != 1 || ! -f "$kws_project/reports/$name-training.json" ]]; then
  run_python "$kws_project/scripts/train.py" --arch "$architecture" --name "$name" --human-priority --time-stride 4 --seed 20261031 --epochs 70 --steps 240 --patience 12 > "$kws_data/logs/$name-training.txt" 2>&1
fi
evaluate_candidate "$name"
run_python "$kws_project/scripts/compare.py" tinyconv dscnn "$name" --install > "$kws_data/logs/final-comparison.txt"
echo "Training, INT8 export and host TFLM experiments complete"

# Controlled lexical-head comparison on the same corpus and selected backbone.
name="${architecture}_lexical"
echo "Lexical classifier experiment: $architecture"
if [[ "${KWS_RESUME:-0}" != 1 || ! -f "$kws_project/reports/$name-training.json" ]]; then
  run_python "$kws_project/scripts/train.py" --arch "$architecture" --name "$name" --lexical --human-priority --time-stride 4 --seed 20261030 --epochs 70 --steps 240 --patience 12 > "$kws_data/logs/$name-training.txt" 2>&1
fi
evaluate_candidate "$name"
run_python "$kws_project/scripts/compare.py" tinyconv dscnn "${architecture}_retrain" "$name" --install > "$kws_data/logs/final-comparison.txt"
echo "Lexical mapping experiment complete"
