#!/usr/bin/env bash
# Final consistent evaluation/idle host timing; no training or device access.
set -euo pipefail
kws_project="$(cd "$(dirname "$0")/.." && pwd)"
kws_python="${KWS_PYTHON:-/home/fred/bilingual-kws-venv/bin/python}"
kws_data="${KWS_DATA:-/home/fred/bilingual-kws-data}"
run_python() { bash "$kws_project/scripts/with_cuda.sh" "$kws_python" "$@"; }
cd "$(dirname "$kws_project")"
for candidate in tinyconv dscnn dscnn_retrain dscnn_lexical; do
  run_python "$kws_project/scripts/evaluate.py" --model "$kws_project/models/$candidate/best_checkpoint.keras" --name "$candidate-float" --split test > "$kws_data/logs/$candidate-final-float-test.txt" 2>&1
  run_python "$kws_project/scripts/evaluate.py" --model "$kws_project/models/${candidate}_int8.tflite" --name "$candidate-int8" --split test > "$kws_data/logs/$candidate-final-int8-test.txt" 2>&1
done
# Timing probes run consecutively, with training/native compiler jobs idle.
for candidate in tinyconv dscnn dscnn_retrain dscnn_lexical; do
  run_python "$kws_project/scripts/benchmark.py" --model "$kws_project/models/${candidate}_int8.tflite" --name "$candidate" > "$kws_data/logs/$candidate-final-tflm.txt" 2>&1
done
run_python "$kws_project/scripts/compare.py" tinyconv dscnn dscnn_retrain dscnn_lexical --install
