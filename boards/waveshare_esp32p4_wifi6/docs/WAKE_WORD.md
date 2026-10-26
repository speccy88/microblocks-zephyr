# Local wake word: native Zephyr contract and acceptance

Native Zephyr remains required. A keyword spotter is separate from Whistle
transcription and uses its own trained frontend and streaming model state.
The first candidate is the pinned English **Okay Nabu** model; arbitrary
phrases/French require an appropriate separately trained model. The verified
upstream license covers its weights and manifests under Apache-2.0.

## Model and preprocessing

The inspected model is 60,264 bytes, SHA256
`0689abe1912a95a3318a0d8cb2e67bad0cbcfe3e24dd6e050c75debddfb6f891`.
It has INT8 input `[1,3,40]`, UINT8 output `[1,1]`, two subgraphs, thirteen
operator types and six resource handles. It is not accepted by the existing
custom dense-only NN loader. Keep that loader's strict validation unchanged;
use a separately pinned builtin backend/resolver with bounded tensors,
resource-variable arena and model-hash/FlatBuffer checks.

PCM is signed 16-bit mono at 16 kHz. TFLM's Apache-licensed microfrontend
must match training: 30 ms window, 10 ms step, 40 filters, 125..7500 Hz;
noise smoothing bits10/even0.025/odd0.06/minimum0.05; PCAN enabled,
strength0.95/offset80/gain bits21; logarithmic scale shift6. Quantize
features using the trained frontend contract, not Whistle log-mel.
Read output using its actual quantization scale1/256 and zero point0;
do not substitute a generic dense or speech-transcription model.

The manifest's 26,080-byte arena is not total RAM. Account separately for
resource variables, frontend/FFT allocations, PCM/ring buffers, model mapping,
worker stack, event queue and existing camera/NN/Whistle reservations.
The upstream static frontend memmap writer does not serialize PCAN state;
do not use that writer as-is or disable PCAN to make it compile. Reuse the
portable frontend with an explicit bounded allocator and private diagnostics.

## User contract and lifecycle

The firmware default is microphone off. Editor connection and library import
do not start listening. Explicit start/stop blocks and Stop All own the session.
A user program can explicitly start listening from a when-started script; normal
MicroBlocks program startup semantics still apply.
The event hat should behave like a button event; confidence, phrase, status,
cooldown and overflow reporters explain current state. No cloud fallback,
audio upload or automatic physical actuation. Model selection exposes only
installed, compatible phrases. A blocked/unsupported backend never reports
a successful listener or fabricated detection.

One native worker owns model/frontend state; no GC pointers cross threads.
Share the existing PCM hardware path through explicit exclusive ownership,
not competing I2S configurations. Streaming uses a bounded ring and counts
overruns. Stop/cancel must stop I2S/DMA before releasing sample buffers;
close the session, invalidate stale events and release allocations safely.
Bound work between cancellation checks, model invocations and VM scheduling.
Do not leave a test listener running.

## Acceptance sequence

1. Pinned model metadata/license/hash inspected. Native TFLM reference backend,
   bounded microphone stream and genuine GP event hat implemented and tested.
2. Build portable frontend and trusted-model interpreter offline. Known
   synthetic positive/negative WAVs, silence/noise and split-buffer processing
   must produce repeatable features/scores. Fixtures stay local.
3. Run the same fixture on P4, compare scores/events, measure per-invocation
   latency, actual arena/frontend/stack use and VM responsiveness. Measure
   against the 30 ms model stride before promising continuous real-time use.
4. Implement actual native microphone stream and bounded event contract;
   verify start/stop/cancel/reuse, queue overflow and camera/audio coexistence.
   Use controlled short playback only when acoustically appropriate, never
   unprompted ambient recordings or a listener left active after tests.
5. Actual GP event/block workflow, screenshots, USB regression and separate
   station transport acceptance. The existing C6 station failure remains
   independent and does not justify an RTOS change or cloud substitution.

## Sources

- [Pinned model repository/license scope](https://github.com/esphome/micro-wake-word-models/tree/40ff33f57f8fc6ad71a75ef085abbf742495b225),
  [model manifest](https://github.com/esphome/micro-wake-word-models/blob/40ff33f57f8fc6ad71a75ef085abbf742495b225/models/v2/okay_nabu.json).
- [TFLM frontend and native streaming APIs](https://github.com/tensorflow/tflite-micro/tree/43b2a106a391dd8a099ac47f2ae858630a397264/tensorflow/lite/experimental/microfrontend/lib).
- ESPHome's preprocessing/streaming implementation is a functional reference;
  its GPL implementation/FreeRTOS integration is not copied into this port.

## Verified local increment (2026-10-26)

Native P4 and isolated host reference produced **identical int8 features and all
output scores**, not only the same final detection. The positive synthetic clip
produced one event at 2,210 ms in padded clip time, confidence 992/1000; the
unrelated phrase produced none. These short fixtures are not an accuracy or
false-positive-rate study. Model probabilities are not calibrated guarantees.

The real GP editor uploaded and ran both a single event handler and two
independent handlers: each fired once for the positive clip; neither fired for
the unrelated phrase. The example uses SmallVM's actual `sayIt` command.
The reserved internal broadcast `_p4.wake.OkayNabu` schedules native receiver
chunks; a running handler is not re-entered. Generic receive-any-message hats
can also observe that internal event. Do not use this reserved name in projects.

The runtime uses TFLM portable reference kernels, not ESP-NN/P4 PIE acceleration.
Measured on the initial final-size native profile:

| Resource or timing | Observed / reserved |
|---|---|
| Mapped model | 60,264 bytes in flash; not copied into PSRAM |
| Tensor/resource-variable arena | 19,396 bytes used / 32,768 reserved |
| Frontend allocator | 11,044 peak requested native bytes; allocator overhead separate |
| KWS worker stack | 16,384 reserved; minimum 12,916 unused in the measured suite |
| Permanent PCM message ring | 8,256 bytes, sixteen 256-sample entries |
| Model invocation | maximum 11.688 ms in that suite; model stride 30 ms |
| Frontend plus invocation work | maximum 12.833 ms in that suite |
| Concurrent VM roundtrip | maximum 32 ms in that suite |

Two one-second microphone sessions each delivered exactly 16,000 samples with
zero queue overflows. Stop/cancel/Stop All, repeat sessions and returning I2S to
ordinary recording passed. A captured clip remained valid for inference after
its source handle was released because the worker owned a bounded copy.
Codec stop, DMA DROP and slab release all reported success. No raw audio was
saved by this suite and no listener was left running.

Frontend ASan/UBSan tests cover all seventeen injected allocation failures,
cleanup, reset and chunk-boundary equivalence. A missing allocation check in
the pinned upstream filterbank helper is added to a verified generated copy;
the dependency checkout is not modified. Exact source/prepared hashes are in
`p4-kws-frontend.json`. Queue overflow and hardware stop-failure quarantine are
implemented, but deliberate hardware fault injection is **not yet tested**.
Concurrent heavy Whistle/NN workloads have not been benchmarked with listening;
queue overflow stops the listener rather than silently discarding samples.

Real acoustic wake detection remains **unverified**: the controlled playback
precheck found Windows output muted at 0%. No unmute, volume, endpoint or other
system setting was changed. The synthetic fixture does not prove the microphone
recognizes a spoken phrase. Continuous real-world false-trigger/CPU measurements,
other speakers/languages and other model phrases remain open.

## Reproduce without recording

Use the pinned workspace/TFLM sources from START_HERE and NEURAL_NETWORKS.
Download the model from the pinned source URL into ignored build artifacts;
`prepare_p4_kws.py` rejects a different size/hash before generating build inputs:

```bash
curl --fail --location https://raw.githubusercontent.com/esphome/micro-wake-word-models/40ff33f57f8fc6ad71a75ef085abbf742495b225/models/v2/okay_nabu.tflite -o "$P4_REPO/build-artifacts/p4-kws/okay_nabu.tflite"
west build -b esp32p4_wifi6/esp32p4/hpcore -s "$P4_REPO/boards/waveshare_esp32p4_wifi6/zephyr" -d build-p4-kws -- \
  -DEXTRA_CONF_FILE=profiles/neural.conf \
  -DP4_TFLM_SOURCE="$TFLM_SOURCE" -DZEPHYR_EXTRA_MODULES="$TFLM_SOURCE" \
  -DP4_KWS_MODEL="$P4_REPO/build-artifacts/p4-kws/okay_nabu.tflite"
python3 "$P4_REPO/tools/test_p4_kws_features.py" --tflm "$TFLM_SOURCE"
```

For the fixture tests, additionally supply `P4_KWS_POSITIVE` and
`P4_KWS_NEGATIVE` with explicitly chosen local 16 kHz mono signed-16 WAVs.
The compiler accepts at most six seconds per source and adds 1.2 seconds of
leading and 0.8 seconds of trailing silence. Use a clean "Okay Nabu" clip and
"The camera is ready" negative; keep all recordings out of Git. The measured
fixture was generated offline by the installed Windows SAPI voice. A different
speaker can produce different scores, so generate its own host reference first.
`tools/test_p4_kws_features.py --wav ... --features-output ...` exports the trained
features. Run `reference_p4_wake_word.py` in the separate LiteRT 2.3.0 environment
with `--expected-events 1` or `0`; retain its reference JSON locally.

After the approved COM5 revision-guarded flash, `test_p4_kws_usb.py --reference
build-artifacts/p4-kws --evidence <path>` checks fixtures without microphone use.
`--stream` explicitly enables the brief microphone lifecycle suite and never
exports audio. It must only be used within the microphone-test authorization.

In the real editor choose **Wake word: synthetic phrase (mic off)** and Start.
For live use, explicitly run **listen for Okay Nabu**, then use the event hat.
**Stop wake-word detection** or Stop All stops the session. The advanced start
accepts 100..300,000 ms (0 means until stopped), confidence 500..999/1000 and
cooldown 250..10,000 ms. One installed phrase is exposed; no custom-phrase field
pretends to train a model. The default small firmware without a supplied model
reports unavailable. USB and station packages include the same block library;
station association/HTTP remains blocked independently by the existing C6 issue.
