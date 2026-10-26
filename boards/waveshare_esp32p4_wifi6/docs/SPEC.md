# Native Zephyr / portable camera specification

Fred explicitly selected native Zephyr on 2026-10-25 for a cross-platform
software ecosystem and future ArduinoCore-Zephyr integration.

## Required architecture

SmallVM v417 runs in a Zephyr thread. Board services implement a stable C
camera/image interface through Zephyr video, I2C, DMA, clock, memory and
synchronization APIs. No FreeRTOS API shim or IDF runtime is presented as
native Zephyr. Reusing Espressif register/HAL code is permitted where adapted
to native resource ownership and licensed correctly.

The portable image layer owns at most four immutable generation-tagged
handles under an 8 MiB budget. GC owns only tagged integers and bounded
ByteArray copies; never a native pixel address. Resize/grayscale/RGB888
preprocessing, lifecycle and preview/export blocks keep the same semantics
across supported platforms. Platform capabilities explicitly distinguish
available, unavailable and physically untested operations.

## Acceptance gates

1. Pinned Zephyr exact-board build, silicon 1.00-1.99, 32 MiB flash/PSRAM.
2. Native VM over COM5: bytecode CRC, arithmetic/edit, 50 outputs, reconnect.
3. Native sensor identification: IMX219 0x0219/0x10 and retained OV5647
   0x5647/0x36 support, I2C0 GPIO7/8; no general pin probing.
4. Real P4 MIPI-CSI/ISP driver: genuine scene, bounded timeout, stream stop,
   native DMA/cache/memory ownership, repeated buffer reuse and cleanup.
5. Real browser compiler and camera block pipeline on that Zephyr image.
6. C6 SDIO version handshake before any proposed Wi-Fi configuration; new
   networking and companion firmware changes require exact authorization.
7. Board-hosted assets and live WebSocket programming, independently tested.

Retain two deployable native Zephyr build profiles: USB-only and C6 Wi-Fi
board hosting. The hosted profile also retains exclusive USB control/recovery.
The public Pages editor is a separate distribution surface. See
[the concrete network proposal and approval boundary](NETWORK_PLAN.md).

SmallVM core, image algorithms, .ubl library and browser protocol are reusable.
An IDF physical pass does not satisfy the native Zephyr camera acceptance gate.
Generic neural models are a separately requested subsystem with an explicit
format/backend contract; see [NEURAL_NETWORKS](NEURAL_NETWORKS.md). Direct
ONNX Runtime, converted ONNX and model-specific engines must be distinguished.

## Audio, local speech and editor results

Native PCM handles use a separate typed integer range, with explicit bounded
recording and release. The optional Whistle profile implements local C99
speech-to-text through copied PCM and an asynchronous Zephyr worker; no
default listener, cloud transcription, generic ONNX support or IDF task shim.
Storage, cancellation, measured stack and reserved/requested PSRAM limits are
specified in [WHISTLE_NATIVE](WHISTLE_NATIVE.md) and [SPEECH](SPEECH.md).

Native fixture and microphone-copy execution are physically verified, with
experimental accuracy and scalar latency of tens of seconds. The real GP
compiler executes the audio-to-text example. Latest camera scene contrast
remains a failed gate under current lighting, independently of frame-size,
transform/export and resource-lifetime checks.

Per-block image snapshots and explicit browser audio playback are required by
[INLINE_RESULTS](INLINE_RESULTS.md). The existing global camera panel does not
satisfy that requirement. PPA transforms, inline results and native wake-word fixture/events/microphone
lifecycle now have physical evidence. Acoustic wake recognition, native codecs
and actual C6 board hosting remain open gates; see WAKE_WORD and HARDWARE_SUPPORT.

## Portable neural-network blocks

Fred requested a model library and custom import for sensor, image, audio
and robotic inference. Implement typed tensors, model metadata and resource
validation, asynchronous run/cancel/status, safe unload and backend queries.
Inference outputs do not authorize physical actuation. No cloud inference or
automatic model/audio/image upload. A CPU fallback applies only to models,
operators and boards whose resources and runtime have been verified.

## Portable data and automation services

Keep JSON, clock/timers, steps/transitions and storage as distinct libraries
with portable C logic and thin native adapters. Preserve every existing
primitive-set index and append new sets. See the detailed contracts in
[JSON](../../../docs/JSON.md), [automation](../../../docs/AUTOMATION.md) and
[storage](../../../docs/STORAGE.md). Host/build/editor acceptance must remain
separate from physical acceptance while installation/publication is held.
Manual wall time is not RTC/NTP, fixed offsets are not automatic DST, logical
steps do not actuate hardware, and RAM files are not persistent Flash/SD.
