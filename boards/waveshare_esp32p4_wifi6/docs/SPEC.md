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
ONNX/YOLO remains future work through an explicit preprocessing/model contract.
