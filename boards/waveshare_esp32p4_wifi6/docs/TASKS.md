# Native work ledger

- [x] Confirm exact Zephyr board target in pinned a915b2f tree.
- [x] Confirm IMX219 and ESP-Hosted-MCU SDIO drivers exist.
- [x] Identify upstream P4 CSI/ISP video integration gap.
- [x] Preserve tested IDF proof on separate local reference branch.
- [x] Reuse portable handle/image layer and camera library.
- [x] Native Zephyr SmallVM/UART/PSRAM build and physical tests.
- [x] Native sensor video control and P4 CSI/ISP endpoint.
- [x] Native real-frame capture/resize/grayscale/RGB888/export, three runs.
- [x] Graphical MicroBlocks browser camera-pipeline execution.
- [ ] Companion handshake, approved network configuration, board hosting.
- [ ] ArduinoCore-Zephyr variant compatibility verification.
- [ ] Accurate source/evidence publication.
- [x] Truthful image/DSP backend query.
- [ ] Native PPA transform measurement.
- [ ] ES8311/I2S bounded mic capture and PCM lifecycle tests.
- [ ] Reuse prior Whistle C99 engine with native allocator/storage/worker.
- [ ] Separate lightweight wake-word listener and MicroBlocks event contract.
- [ ] Measure compatible NN/DSP kernel optimizations against reference paths.

Native VM evidence: `evidence/2026-10-25/p4-zephyr-vm.json`. This establishes
actual UART programming, full-frame-sized PSRAM allocation, blank-image
preprocessing and safe handles. It does not establish sensor capture.

Receiver implementation: native video endpoint and sensor source,
dedicated Zephyr worker, bounded DMA completion polling, cache synchronization,
sensor stop and DMA abort/reset before release. HAL comes from the pinned
Zephyr Espressif module; ESP-IDF RTOS drivers are not linked. Three actual
IMX219 captures passed with live VM execution, transform/export and release,
recorded in `evidence/2026-10-25/p4-zephyr-camera.json`. Image quality is untuned.
