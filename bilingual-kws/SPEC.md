# Bilingual command recognizer acceptance contract

This work extends the dedicated native Zephyr KWS subsystem. It preserves the
restricted dense NN importer, Okay Nabu, ES8311 ownership, SmallVM and the
uncommitted camera/eyes changes present at base commit
`622c0c09fd0ad942f34048806629c0dd7a62c045`.

## Behavior

An explicitly started listener accepts 16 kHz mono PCM16. The pinned existing
TFLM integer microfrontend produces 40 channels with its existing 30 ms / 10 ms
window/hop, PCAN, noise reduction and quantization unchanged. A static window
classifier yields UP, DOWN, LEFT, RIGHT, ANGRY, HAPPY, TIRED, NORMAL, UNKNOWN,
SILENCE, in that order. English and French aliases share semantic labels.
Inference and recording are offline. A single bounded worker owns the frontend
and microphone; temporal decisions reject unknown/silence and require confidence,
stability, cooldown and release before retriggering. Stop All cancels listening,
invalidates events and clears samples. The microphone remains off on boot/import.
Eyes consume semantic state independently of display initialization.

## Non-goals and boundaries

No firmware flashing, reset, C6/network changes, COM12 access, private recordings,
voice cloning, cloud inference, arbitrary CNN importing or automatic main merge.
Device timing, accuracy, RAM and CPU results require actual measurement. A host
or native build is never physical acceptance. Public corpus audio stays outside
Git. No claim of French-Canadian coverage without identified evidence.

## Dependencies and experiment gates

Pinned TFLM `43b2a106a391dd8a099ac47f2ae858630a397264`, existing checked
microfrontend allocator, local RTX 2060 SUPER, isolated Python 3.12 TensorFlow
CUDA environment, GSC v2 / MLCommons MSWC human audio and licensed local TTS.
Use source-speaker partitions; MSWC clips share source sentence identities and
must not leak across partitions. Synthetic voices are partitioned independently;
hold out an engine where feasible. Report missing words and empty test cells.

## Testable acceptance

1. Actual GPU operations and training logs/checkpoints for TinyConv and DS-CNN;
   reproducible seeds, validation selection, early stopping and LR scheduling.
2. Corpus counts by source/class/language/split, distinct speakers, hashes and
   leakage checks; human and synthetic metrics reported separately.
3. Exact native frontend used to prepare training inputs; chunk equivalence and
   allocation-failure tests reused. Augmentation precedes feature extraction.
4. Fully INT8 static `[1,T,40,1]` input and `[1,10]` Softmax output; no float/hybrid
   tensors; calibration uses training data only, including real human audio.
5. Float/INT8 comparison, per-class and per-language metrics, confusion and
   curves; quantization loss <=2 percentage points on the held-out human set.
6. Exact pinned host TFLM AllocateTensors/Invoke, bounded arena measurement and
   score comparison; native Zephyr build with exact command, commit and log.
   Numerical comparison uses desktop BUILTIN_REF kernels: max <=8 output LSB,
   mean <=0.25 LSB and >=99% argmax agreement. Differences are reported rather
   than described as bit-exact; this is a host gate, not physical acceptance.
7. Blocks for start/stop/event/command/confidence/scores/status; decision-policy
   lifecycle tests and a display-independent eye preview/controller.
8. Targets: <100 KB model preferred, <150 KB ceiling, <=128 KiB arena; <50 ms
   P4 invocation and <500 ms post-word response measured only on authorized
   hardware. False positives/hour requires continuous held-out negatives.
9. `python3 tools/validate.py` completes; existing functionality remains intact.

The final report records each gate as achieved, failed or unmeasured. A trained
research candidate with coverage gaps is not declared deployment-ready.
