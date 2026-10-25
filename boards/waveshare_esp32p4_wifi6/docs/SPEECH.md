# Native local speech and wake-word stages

Fred requested local Whistle speech-to-text, a separate wake-word event block,
and reuse of established NN/DSP optimizations on 2026-10-25. Camera bringup
remains the first milestone. No speech block is implemented or claimed yet.

## Existing work inspected

The earlier local package `whistle_esp32_s3_rlcd_v0.1.0/whistle-esp32` at
`9d4208c9fd2cb2f6705b4a5d369b3586eaaab10a` contains the actual RLCD port,
portable C99 engine, source/build documentation and physical English/French
acceptance evidence. It runs inference locally, with no transcription server.
Its four-layer model is 14,515,887 bytes; do not commit weights or borrow the
old board's ES7210 dual-mic/GPIO18 wiring for this ES8311 P4 board.

The Apache-2.0 C99 engine has scalar kernels as well as S3-only Xtensa PIE
paths. P4 is not intrinsically excluded by the absence of an official RV32
Cactus binary. The native port must override all allocation/time/platform
hooks and keep IDF/FreeRTOS application glue out of Zephyr. `nd_wh_encode`
accepts PCM and computes log-mel itself; its input is not an arbitrary mel
tensor. Preserve quantization scales and int32 accumulation when optimizing.

## Required behavior and gates

1. Verify ES8311 address and clocks against schematic and actual board.
   Schematic I2C SDA7/SCL8; MCLK13/BCLK12/LRCK10; codec ASDOUT to RX11,
   TX9 to DSDIN; amplifier enable53. Keep speaker off. Current native I2S
   driver supports standard/left/right-justified modes; no PDM support claim.
   No upstream ES8311 driver is established by an open pull request.
2. Explicit bounded recording block, at most eight seconds, 16 kHz mono PCM.
   Bounded sample handles, duration/RMS/peak metadata and explicit release.
   No automatic recording, upload or ambient listener at startup. User
   authorized a bounded mic test for this implementation; raw audio stays
   private locally and is excluded from Git/evidence.
3. Whistle worker consumes pinned native PCM, returns bounded UTF-8 text,
   timing/error metadata, cancellation and cleanup. Measure total weights,
   activations, KV/scratch, stack, audio pool and image coexistence. Choose
   flash/model placement explicitly; do not silently change partitions or
   claim that model size alone is the complete RAM requirement.
4. Independent lightweight keyword spotter; start/stop listening blocks and
   `when wake word detected` event semantics. Listener off by default and
   stopped after tests. Shared bounded PCM path, separate KWS/STT frontends.
   Initial candidate: Zephyr TFLM reference kernels plus microWakeWord model;
   fixed trained phrase selection, supported threshold/cooldown controls,
   bounded event queue and no arbitrary custom phrase guarantee.
5. Synthetic fixture tests first, then controlled known-phrase physical
   tests. Report whole-pipeline latency, memory, CPU and false-trigger test
   coverage. Neither recognition accuracy nor a performance number is
   inferred from another board's benchmark.
6. Evaluate upstream ESP-NN P4 PIE/QACC int8 and ESP-DSP P4 FFT/dot kernels
   selectively after reference correctness. Check Zephyr toolchain custom
   instructions and context saving. CMSIS-NN is ARM-specific; ESP-DL/ESP-SR
   IDF/prebuilt dependencies are not drop-in Zephyr support. Retain pinned
   versions/licenses and portable fallbacks; no inference-engine rewrite.

Sources: [Whistle engine](https://github.com/andrisgauracs/whistle-esp32),
[Zephyr TFLM](https://docs.zephyrproject.org/latest/samples/modules/tflite-micro/hello_world/README.html),
[microWakeWord model catalog](https://github.com/esphome/micro-wake-word-models),
[ESP-NN](https://github.com/espressif/esp-nn), [ESP-DSP](https://github.com/espressif/esp-dsp),
[board schematic](https://files.waveshare.com/wiki/ESP32-P4-WIFI6/ESP32-P4-WIFI6-datasheet.pdf).
