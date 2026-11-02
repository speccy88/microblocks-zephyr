# Bilingual TinyML command results

Selected artifact: **dscnn_retrain**. Model SHA256 `e17cbf03e00f5e673b8dd16209e62fb60515fab74c5af5f51732c5da4681b0e8`.

This report distinguishes trained host artifacts, pinned host TFLM execution, native Zephyr compilation and physical P4 acceptance. No board was flashed, reset or recorded during this task.

## Candidate comparison

| Candidate | Parameters | INT8 bytes | Human EN accuracy | Human FR accuracy | All clips accuracy | Macro-F1 (10) | Host TFLM arena | Host TFLM median / p95 | GPU training |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| tinyconv | 11,386 | 16,520 | 48.46% | 27.15% | 44.34% | 0.4516 | 28,528 B | 15.699 / 17.055 ms | 17.3 min |
| dscnn | 34,682 | 57,408 | 79.13% | 70.21% | 77.67% | 0.7411 | 55,968 B | 29.474 / 31.329 ms | 16.6 min |
| dscnn_retrain | 34,682 | 57,408 | 84.14% | 80.34% | 82.39% | 0.7938 | 32,608 B | 15.060 / 16.502 ms | 24.4 min |
| dscnn_lexical | 44,602 | 68,720 | 83.37% | 78.22% | 80.95% | 0.7714 | 33,056 B | 15.250 / 16.475 ms | 22.5 min |

These are optimized candidates, not a controlled architecture-only ablation. TinyConv uses uniform semantic sampling and the base corpus. DS-CNN adds 59 duration-eligible French phrase examples and more unknown sampling; its head retains coarse frequency position. The refined and lexical candidates use human-priority sampling, a larger training budget and first temporal stride 4. All reported candidates use the same final held-out evaluation cohort. Full regimes: `configs/experiments.yaml`.

| Candidate | Static MAC estimate / window | Sampled device-wide peak VRAM | Training epochs |
|---|---:|---:|---:|
| tinyconv | 2,027,520 | 6,696 MiB | 45 |
| dscnn | 3,462,800 | 1,110 MiB | 37 |
| dscnn_retrain | 1,802,240 | 501 MiB | 40 |
| dscnn_lexical | 1,812,140 | 505 MiB | 31 |

Selection criterion: mean en/fr HUMAN validation macro-F1 over supported classes; within 0.005 of best prefer fewer static MACs then smaller model; no test selection. INT8 validation accuracy loss on human speech must be <=2 percentage points, model <=150 KB, host TFLM arena <=128 KiB and host argmax agreement >=99%. The selected bilingual human validation macro-F1 is 0.7506.

The TinyConv device-wide VRAM peak includes overlapping conversion/synthesis processes; its own TensorFlow active-allocation peak is recorded separately. Device-wide peaks are sampled every second and can miss shorter excursions. MAC counts omit frontend, activation, Softmax and memory costs and do not establish P4 latency.

**Host arena and timings are x86_64 results, not P4 measurements.** Native pointer size, kernels, cache, scheduling, audio and PSRAM change the result. The firmware currently reserves 128 KiB for the voice arena.

## Corpus and leakage audit

Source records: 62,050; retained including generated non-speech: 60,147; duplicates removed: 9. Exclusions: `{"homophone_negative": 92, "longer_than_1.2s": 3582}`.

Original source speakers are partitioned together; synthetic preset voices are partitioned together; noise source files are partitioned together. The corpus check reports zero speaker-group overlap. Encoded and normalized-PCM duplicates are removed. Known homophone negatives are excluded because the same sound cannot be trained with conflicting labels.

| Action | Human EN train / val / test | Human FR train / val / test | Synthetic train / val / test |
|---|---:|---:|---:|
| UP | 2805 / 427 / 417 | 644 / 76 / 90 | 153 / 34 / 80 |
| DOWN | 5155 / 1553 / 1414 | 928 / 102 / 109 | 134 / 31 / 75 |
| LEFT | 5056 / 1304 / 1055 | 646 / 102 / 87 | 130 / 30 / 70 |
| RIGHT | 4998 / 1450 / 1290 | 621 / 93 / 87 | 101 / 24 / 65 |
| ANGRY | 478 / 87 / 72 | 20 / 5 / 5 | 60 / 14 / 37 |
| HAPPY | 2997 / 487 / 464 | 287 / 26 / 28 | 70 / 16 / 41 |
| TIRED | 557 / 87 / 95 | 149 / 15 / 13 | 51 / 13 / 34 |
| NORMAL | 501 / 98 / 78 | 130 / 18 / 23 | 55 / 12 / 33 |
| UNKNOWN | 7040 / 2128 / 2121 | 4010 / 479 / 545 | 1932 / 455 / 1065 |
| SILENCE | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |

The independent byte-level audit found 1 held-out all-zero procedural-silence duplicate. It is excluded from every final test metric; no speech clips, training labels or weights changed. Zero source-speaker overlap and zero cross-split PCM overlap hold for the resulting evaluation cohort. Original preparation metadata used pre-quantization float hashes for 1780 non-speech records; the audit instead hashes actual stored PCM16. The original training record file is retained for provenance.

Path-independent PCM/label/split digest: `c768323ea4a044710d9e06041c5a2c41c8ae867f11459dbd4080d7a15dd24219`. Speaker separation uses corpus-provided IDs; identity overlap between independently published corpora cannot be excluded.

### French alias coverage

| Alias | Human clips train / val / test | Human speaker groups train / val / test | TTS clips train / val / test | Test action recall: human / TTS |
|---|---:|---:|---:|---:|
| haut | 644 / 76 / 90 | 338 / 42 / 50 | 33 / 6 / 16 | 76.67% / 31.25% |
| en haut | 0 / 0 / 0 | 0 / 0 / 0 | 24 / 4 / 10 | unmeasured / 0.00% |
| bas | 928 / 102 / 109 | 455 / 58 / 53 | 19 / 4 / 12 | 74.31% / 25.00% |
| en bas | 0 / 0 / 0 | 0 / 0 / 0 | 19 / 3 / 9 | unmeasured / 0.00% |
| gauche | 646 / 102 / 87 | 356 / 57 / 54 | 17 / 1 / 11 | 95.40% / 54.55% |
| à gauche | 0 / 0 / 0 | 0 / 0 / 0 | 17 / 5 / 7 | unmeasured / 42.86% |
| droite | 621 / 93 / 87 | 331 / 52 / 50 | 1 / 0 / 6 | 91.95% / 100.00% |
| à droite | 0 / 0 / 0 | 0 / 0 / 0 | 4 / 0 / 7 | unmeasured / 0.00% |
| fâché | 20 / 5 / 5 | 20 / 4 / 4 | 9 / 2 / 7 | 100.00% / 71.43% |
| en colère | 0 / 0 / 0 | 0 / 0 / 0 | 3 / 0 / 6 | unmeasured / 0.00% |
| content | 129 / 8 / 15 | 87 / 7 / 13 | 3 / 0 / 6 | 86.67% / 33.33% |
| heureux | 158 / 18 / 13 | 103 / 14 / 12 | 19 / 4 / 11 | 92.31% / 0.00% |
| fatigué | 125 / 14 / 7 | 75 / 11 / 6 | 0 / 0 / 7 | 71.43% / 85.71% |
| fatiguée | 24 / 1 / 6 | 17 / 1 / 5 | 3 / 1 / 3 | 66.67% / 100.00% |
| normal | 60 / 10 / 14 | 52 / 9 / 11 | 3 / 0 / 6 | 100.00% / 100.00% |
| normale | 70 / 8 / 9 | 51 / 8 / 5 | 4 / 0 / 3 | 100.00% / 100.00% |

The `en colère` alias has only three training examples and no validation examples; all are synthetic. Complete utterances exceeding 1.2 seconds were excluded, not cropped through words. Faster complete-phrase synthesis improves coverage but does not establish natural long-phrase accuracy. Optional `look …` / `regarde …` samples are evaluated as phrases and remain exploratory. The attempted Gilles voice was rejected before training because its vocabulary lacked a required nasalization symbol; see `rejected-tts.json`.

Silence has separate source-file/procedural non-speech counts in the manifest. TTS and procedural audio are never counted as human speech. All corpus details and available-vs-retained counts are in `datasets/dataset_manifest.json`; the external private record manifest retains speaker IDs and segment provenance.

## Selected model: held-out performance

| Group | Clips | Speaker groups | Accuracy | Macro-F1 over represented classes |
|---|---:|---:|---:|---:|
| kind:human | 7,993 | 2008 | 83.67% | 0.7950 |
| human:en | 7,006 | 1730 | 84.14% | 0.8022 |
| human:fr | 987 | 288 | 80.34% | 0.7206 |
| kind:synthetic | 1,500 | 14 | 73.00% | 0.6289 |
| source:Piper | 805 | 9 | 71.80% | 0.6141 |
| source:Kokoro | 695 | 5 | 74.39% | 0.6487 |
| kind:non-speech | 359 | 2 | 93.04% | 0.9639 |

Kokoro is an entirely held-out synthesis engine. Piper and Kokoro Siwis are both excluded from training because they share a source voice. Preset-voice separation does not prove real human generalization. French-Canadian accent coverage is unverified.

| Class | Precision | Recall | F1 | Support (all test clips) |
|---|---:|---:|---:|---:|
| UP | 0.6909 | 0.8416 | 0.7588 | 587 |
| DOWN | 0.8166 | 0.8636 | 0.8394 | 1598 |
| LEFT | 0.8431 | 0.8465 | 0.8448 | 1212 |
| RIGHT | 0.8968 | 0.8315 | 0.8629 | 1442 |
| ANGRY | 0.6218 | 0.8509 | 0.7185 | 114 |
| HAPPY | 0.8243 | 0.8537 | 0.8387 | 533 |
| TIRED | 0.5749 | 0.8380 | 0.6819 | 142 |
| NORMAL | 0.5061 | 0.9254 | 0.6544 | 134 |
| UNKNOWN | 0.8573 | 0.7743 | 0.8137 | 3731 |
| SILENCE | 0.9201 | 0.9304 | 0.9252 | 359 |

### human:en: real speech per class

| Class | Precision | Recall | F1 | Clips |
|---|---:|---:|---:|---:|
| UP | 0.7119 | 0.9185 | 0.8021 | 417 |
| DOWN | 0.8501 | 0.8861 | 0.8677 | 1414 |
| LEFT | 0.8952 | 0.8417 | 0.8676 | 1055 |
| RIGHT | 0.9534 | 0.8256 | 0.8849 | 1290 |
| ANGRY | 0.6495 | 0.8750 | 0.7456 | 72 |
| HAPPY | 0.8843 | 0.8728 | 0.8785 | 464 |
| TIRED | 0.6754 | 0.8105 | 0.7368 | 95 |
| NORMAL | 0.4706 | 0.9231 | 0.6234 | 78 |
| UNKNOWN | 0.8304 | 0.7963 | 0.8130 | 2121 |
| SILENCE | 0.0000 | 0.0000 | 0.0000 | 0 |

human:en accuracy speaker-cluster bootstrap 95% interval (200 resamples): 82.64%–85.35%. Small per-command French supports remain a material limitation; aggregate accuracy does not establish each alias.

### human:fr: real speech per class

| Class | Precision | Recall | F1 | Clips |
|---|---:|---:|---:|---:|
| UP | 0.6832 | 0.7667 | 0.7225 | 90 |
| DOWN | 0.7105 | 0.7431 | 0.7265 | 109 |
| LEFT | 0.7615 | 0.9540 | 0.8469 | 87 |
| RIGHT | 0.9195 | 0.9195 | 0.9195 | 87 |
| ANGRY | 0.3571 | 1.0000 | 0.5263 | 5 |
| HAPPY | 0.4808 | 0.8929 | 0.6250 | 28 |
| TIRED | 0.5294 | 0.6923 | 0.6000 | 13 |
| NORMAL | 0.5111 | 1.0000 | 0.6765 | 23 |
| UNKNOWN | 0.9330 | 0.7670 | 0.8419 | 545 |
| SILENCE | 0.0000 | 0.0000 | 0.0000 | 0 |

human:fr accuracy speaker-cluster bootstrap 95% interval (200 resamples): 76.80%–83.23%. Small per-command French supports remain a material limitation; aggregate accuracy does not establish each alias.

### Clip rejection tradeoff

| Confidence threshold | Accepted-command precision | Known-command recall | UNKNOWN/SILENCE false accepts / negatives |
|---|---:|---:|---:|
| 0.70 | 90.34% | 73.34% | 353 / 4090 (8.63%) |
| 0.80 | 92.76% | 68.05% | 253 / 4090 (6.19%) |
| 0.85 | 93.99% | 63.29% | 201 / 4090 (4.91%) |
| 0.90 | 94.87% | 57.50% | 156 / 4090 (3.81%) |
| 0.95 | 96.62% | 47.62% | 86 / 4090 (2.10%) |
| 0.98 | 97.85% | 35.47% | 39 / 4090 (0.95%) |

These are threshold-only isolated-clip metrics. They neither include temporal filtering nor estimate events/hour. The firmware default of 0.85 is an explicit engineering setting, not a threshold optimized on this test set. Increasing it can reduce false accepts while missing more commands.

| Utterance form (human + TTS) | Clips | Accuracy | Macro-F1 over represented classes |
|---|---:|---:|---:|
| actions:single_word | 5607 | 85.66% | 0.8723 |
| actions:phrase | 155 | 58.71% | 0.5968 |

## Frontend, quantization and memory

The compiled existing native integer microfrontend prepares training, calibration and evaluation inputs. PCM is 16 kHz mono signed16, with a 1.2 s / 118x40 feature window. Parameters match the existing 30 ms / 10 ms frontend, including PCAN, filterbank, noise reduction and exact integer rounding. Training varies prior background context; clip evaluation uses 500 ms quiet context. Firmware runs continuously and has separate replay evaluation.

Input: `{'shape': [1, 118, 40, 1], 'dtype': 'int8', 'scale': 1.0, 'zero_point': 0}`. Output: `{'shape': [1, 10], 'dtype': 'int8', 'scale': 0.00390625, 'zero_point': -128}`. Tensor types: `['int32', 'int8']`. Operators: `['AVERAGE_POOL_2D', 'CONV_2D', 'DEPTHWISE_CONV_2D', 'FULLY_CONNECTED', 'RESHAPE', 'SOFTMAX']`. Calibration uses 844 training examples, including 445 human clips. No validation/test audio calibrates the graph.

Output semantics: direct ten-class Softmax. Validation float/INT8 argmax agreement: 98.45%; mean absolute probability error 0.002966; maximum 0.141164; human validation accuracy loss 0.152 percentage points.

Pinned host TFLM used 32,608 arena bytes. Maximum difference from desktop LiteRT was 0 INT8 LSB; argmax agreement 100.00%. This checks actual AllocateTensors/Invoke, not only operator names. The model is firmware mapped and not copied into the arena.

Training framework: TensorFlow 2.20.0; GPU NVIDIA GeForce RTX 2060 SUPER; sampled device-wide peak VRAM 501 MiB; TensorFlow active-allocation peak 327,341,056 bytes. The local WSL environment has two vCPUs and about 6 GB RAM. Float32 training was used for these small models.

TFLM arena use includes its kernel scratch. Additional runtime memory includes the 4,720-byte feature ring, 8,256-byte permanent PCM queue, 16,384-byte KWS stack, frontend allocations, synchronization/metrics and existing VM/media state. The offline frontend allocator test peaks at 11,056 requested bytes on x86_64. Host arena use is not total runtime RAM. Device pressure and stack high-water measurements remain pending.

## Semantic versus lexical classifier

The lexical-head experiment learns 30 individual word/language classes. A fixed one-hot integer FullyConnected layer sums the lexical Softmax probabilities into ten semantic probabilities in the exported model; the action mapping is embedded on-device, not performed by a PC. Its INT8 bilingual human validation macro-F1 is 0.7545. The same size, quantization and host TFLM gates apply to all four candidates. Different seeds and one run per regime limit architecture-level conclusions.

The selected artifact uses **direct ten-class Softmax**. Direct classifiers have a final ten-way Softmax; the lexical alternative has normalized sums after its finer Softmax. The simpler direct classifier is preferred within the stated validation near-tie rule.

## Continuous host replay

The same native frontend and C decision policy replayed 0.650 hours of constructed held-out human non-command audio: 40 events, 61.53 events/hour. This concatenated isolated-word corpus is not representative ambient conversation; real-world false positives/hour remain unmeasured.

Constructed-negative Poisson rate 95% interval: 43.95–83.78 events/hour. This interval only describes this constructed corpus and does not account for its mismatch with ambient audio.

Positive replay: 96/185 matched; 89 missed; 0 extra/wrong events. Audio-time delay relative to estimated speech-energy endpoint, detected commands only: median 371.5625 ms, p95 645.5 ms. This excludes P4 compute/queue/transport time and is not a physical end-to-end latency claim. Negative delay means a trigger before the estimated endpoint.

| Host replay candidate | Constructed negative events/hour | Matched human commands | Detected-only audio delay median / p95 |
|---|---:|---:|---:|
| dscnn_retrain | 61.53 | 96 / 185 | 371.6 / 645.5 ms |
| dscnn_lexical | 59.99 | 101 / 185 | 379.1 / 668.6 ms |

The lexical variant does not resolve the continuous-trigger problem. These test replays diagnose limitations after validation-based selection; they are not used to choose a new threshold or retrain on the test set. Neither candidate is recommended for unattended continuous operation.

## Native build and physical acceptance

Native Zephyr build: PASS (compiled only). See `reports/native-build.json` and `reports/native-build.txt` for exact command, base commits, source hashes and build result.

No physical microphone, firmware flash/reset, COM12 access, C6/network modification or display initialization occurred. P4 median/p95 inference, post-word latency, CPU use, total runtime RAM, acoustic accuracy, concurrent MicroBlocks responsiveness and sustained ambient false-trigger rate are **unmeasured for this new model**.

## Comparison with existing Whistle evidence

| Property | New command model | Existing Whistle reference |
|---|---|---|
| Model bytes | 57,408 | 14,515,887 |
| Output | Ten semantic scores | Free-form speech transcription |
| Arena | 128 KiB reserved; measured host use above | 12 MiB job arena reserved |
| P4 latency | Unmeasured | Historical controlled `happy`: 20.436 s after 2.5 s recording; 26.527 s TRANSCRIBING-to-Applied after 3 s recording in GP |
| Controlled same-input comparative benchmark | Pending | Pending |

Whistle numbers come from existing `boards/waveshare_esp32p4_wifi6/docs/WHISTLE_NATIVE.md`, `docs/VOICE_EYES.md` and the 2026-10-29 evidence. They use different inputs and timing boundaries; no new device speedup ratio is asserted.

## Deployment recommendation

Use `dscnn_retrain` as the host-validated firmware candidate because it won the stated validation ranking and passed the integer/host-runtime gates. Physical deployment readiness still requires the explicit acceptance session in `esp32p4/deployment.md`, especially French-Canadian speakers, rare French emotion words, continuous negatives and actual P4 timing/RAM. Targets of <50 ms invocation and <500 ms post-word response are not established by host execution.

Reproduction commands: `README.md`, `scripts/run_experiments.sh`, `esp32p4/build.sh`. Source/attribution: `reports/sources.md`. No main merge or GitHub push is performed by this task.

## Linked native artifact

The combined image is 15,250,032 bytes, including the existing 14,515,887-byte Whistle model. The 57,408-byte command model is mapped read-only at 0x40e384b0–0x40e464f0; its extracted ELF bytes match the selected TFLite SHA256. The offline revision-guarded image is `/mnt/c/Users/fred_/Documents/Codex/microblocks-zephyr/build-artifacts/bilingual-kws/zephyr-checked.bin`. It was not flashed.

| Linker region | Static used / reserved bytes | Capacity |
|---|---:|---:|
| FLASH | 15,218,116 | 33,554,176 |
| sram0_0_seg | 246,960 | 393,216 |
| lp_ram_seg | 36 | 30,944 |
| lp_reserved_seg | 0 | 24 |
| IDT_LIST | 0 | 8,192 |
| irom0_0_seg | 381,552 | 33,554,432 |
| drom0_0_seg | 15,087,044 | 33,554,432 |
| ext_dram_seg | 17,153,984 | 33,554,432 |

The external-DRAM reservation includes the existing 16 MiB heap. The command arena/frontend allocate from that heap; adding them again to linker PSRAM reservation would double-count. Flash DROM/IROM are mapped views and these rows must not be summed. Total live runtime RAM still needs physical measurement.

## Acceptance status

| Gate | Result |
|---|---|
| Actual local GPU training, checkpoint and INT8 artifact | Achieved |
| Human speech, speaker-group split and held-out TTS engine | Achieved for documented corpus; cross-corpus identity uncertainty remains |
| Eight bilingual action labels | Present and trained; per-alias recognition and French-Canadian robustness remain limited/unverified |
| Fully INT8, ten semantic scores and pinned host TFLM Invoke | Achieved; direct and lexical output semantics distinguished above |
| Model <100 KB / host arena <=128 KiB | Achieved for selected artifact |
| Native Zephyr compilation and linked-model hash | Achieved |
| MicroBlocks library/event integration and eye schematic | Implemented and packaged; no physical execution claim |
| Low continuous false-positive rate | Not established; constructed replay exposes unacceptable false triggers for unattended use |
| P4 <50 ms invocation / <500 ms post-word response | Unmeasured |
| P4 concurrent VM, CPU, total RAM and microphone acoustics | Unmeasured |
