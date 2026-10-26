# Portable neural-network subsystem acceptance contract

Requested by Fred on 2026-10-25 after the native camera/audio/Whistle and
inline-result milestones. This document records required work; it does not
claim a generic runtime or model importer is installed.

## User-visible contract

- Model catalog with small actually tested examples and custom local import.
  Preserve source URL, license, exact hash, backend format and requirements.
- Inspect input/output names, shapes, dtypes, quantization and operator set
  before loading. Reject unsupported/dynamic shapes or operators explicitly.
- Typed tensors for sensor vectors, bounded image preprocessing and PCM/audio
  features. Do not conflate Whistle log-mel with another model's frontend.
- Explicit load, async run, busy/status/result, cancel and unload. Worker
  input owns native copies; no SmallVM GC pointer crosses a thread boundary.
- Memory limits include retained model, tensor arena, inputs/outputs, scratch
  and worker stack. Pressure and cancellation must release/reuse resources.
- Model bytes are data and never executable code, scripts or native plugins.
  Bound file length, parser traversal, tensor shapes and allocation products;
  verify structure again on the board, not only in the browser importer.
- Local inference outputs only. No robot movement or actuator command is
  implied, and no silent host/cloud fallback or model upload is allowed.

## Backend distinctions and stages

1. Verify actual RV32/native-Zephyr support for direct ONNX Runtime. If it
   requires unsupported OS/memory/operator infrastructure, record that gap.
2. Evaluate Zephyr's pinned TensorFlow Lite Micro module with reference CPU
   kernels and a minimal known model before adding model import. Label an
   ONNX-to-TFLite/other conversion as conversion, with its limitations.
3. Reuse the same verified backend for independent lightweight keyword
   spotting where frontend/model requirements match. Keep listener off until
   an explicit start block. Whistle remains a separate STT engine.
4. Adapt P4 ESP-NN INT8 kernels selectively after measuring reference output,
   total latency and memory. Verify toolchain instructions and register/context
   handling. ESP-DL/ESP-DSP are candidates, not assumed Zephyr drop-ins.
5. Preserve the portable block/tensor contract across compatible targets.
   Report backend/operation acceleration, software fallback and unsupported
   capability separately. Never promise arbitrary ONNX/YOLO models or all MCUs.

Research Arduino UNO Q, Tasmota and Microduck from their actual code and
documentation. The user's "ventuino uno" reference needs exact identification;
do not invent a board or runtime. Incoming independent research will be linked
to this contract before choosing dependencies.

## Research and first native evidence

The reference projects separate powerful Linux inference from microcontroller
control. Their UI and model-manifest patterns are useful; their Linux runtime
does not become an RV32 Zephyr runtime simply by sharing a block name.

- Microduck uses RK3566 Linux/aarch64 with Rust `ort`/ONNX Runtime. Its policy
  manifest documents float32 [1,61] observations to [1,14] actions, units,
  timing, output scaling and warm-up validation. Reuse that explicit contract,
  not implicit actuator access: [manifest](https://github.com/pollen-robotics/microduck/blob/main/docs/policy-manifest.md),
  [policy implementation](https://github.com/pollen-robotics/microduck/blob/main/duck-control/src/policy.rs).
- Arduino UNO Q and VENTUNO Q perform their application inference on Linux,
  with a Zephyr MCU control side. Their catalog's target/backend artifact
  separation is relevant: [Arduino model catalog](https://github.com/arduino/app-bricks-py/blob/main/models/models-list.yaml).
- Tasmota loads TFLite models through Berry and Espressif TFLM; it is not an
  ONNX Runtime port. Its GPL-3.0 implementation is a design reference rather
  than copied code: [Tasmota TFL](https://tasmota.github.io/docs/TFL/).
- The documented ONNX Runtime RISC-V build targets RV64 Linux/glibc, with
  `--rv64`, not this RV32 Zephyr board: [official build instructions](https://onnxruntime.ai/docs/build/inferencing.html#risc-v).
  Direct ORT execution on P4 remains unverified and unavailable.
- ESP-DL uses target-specific `.espdl` conversion from ONNX through ESP-PPQ
  and has IDF dependencies. TFLM reference kernels plus selective Apache-2.0
  [ESP-NN](https://github.com/espressif/esp-nn) P4 kernels form the initial
  native path. Conversion must preserve source and artifact hashes, and reject
  unsupported graph/operator/shape/quantization transformations explicitly.

The pinned Zephyr TFLM module has now been cross-built and physically run on
the revision 1.3 P4. Its Apache-2.0 INT8 sine fixture produced ten inference
outputs, maximum absolute error 0.063753 against sine, with stated test
tolerance 0.2. Model size is 2,488 bytes; the sample configures a 2,000-byte
arena. This is not a peak-memory measurement, generic importer or NN block.
See `dependencies/p4-tflm.json` and `evidence/2026-10-25/p4-tflm-native.json`.

Reproducible build (no global optional-group activation):

```sh
west update tflite-micro
west build -b esp32p4_wifi6/esp32p4/hpcore \
  -s zephyr/samples/modules/tflite-micro/hello_world -d build-p4-tflm-probe -- \
  -DZEPHYR_EXTRA_MODULES=/home/fred/microblocks-zephyr-work/optional/modules/lib/tflite-micro \
  -DCONFIG_ESP_SIMPLE_BOOT=y
```

Flash only under the existing P4 authorization, using the same revision guard
and COM5-only tool. The bounded `tools/test_p4_tflm_probe.py` validates the
embedded model bytes/hash and ten UART results, without recording, actuation,
camera capture or C6 firmware changes. Restore the normal SmallVM profile
after the standalone probe. Model lifecycle/tensor validation and catalog
integration remain the next implementation stage.

## Acceptance evidence

Known sensor-vector model with exact expected output; valid and malformed
custom files; dtype/shape/operator rejection; repeated load/run/unload;
arena exhaustion alongside image/audio/Whistle buffers; cancellation and VM
responsiveness; board/host comparison and latency/memory measurements. Model
catalog examples and block execution must pass in the genuine GP editor.
USB and board-hosted targets share the same model/tensor API and protocol;
successful Pages editing alone does not establish board execution or hosting.
