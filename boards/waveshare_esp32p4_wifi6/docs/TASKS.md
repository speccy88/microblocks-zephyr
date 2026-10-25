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
- [x] Accurate source/evidence publication: native camera 0fb2aa74 on main;
  all three GitHub workflows passed.
- [x] Truthful image/DSP backend query.
- [ ] Native PPA transform measurement.
- [x] ES8311/I2S bounded PCM transport, DMA rate and lifecycle tests.
- [x] Controlled Windows speaker/P4 microphone acoustic-response test;
  correlation 0.7442, RMS rise 0.57 to 103.49, stopped and private PCM excluded.
- [x] Reuse prior Whistle C99 engine with native allocator/storage/worker.
- [x] Cross-build pinned C99 Whistle engine with 12 MiB bounded job arena,
  flash-mapped verified model and explicit native simple-boot partition map.
- [x] Native P4 fixture transcription, cancellation/reuse and memory metrics.
- [x] Native microphone handle to actual STT text and graphical example;
  experimental accuracy, scalar latency measured, no generic model runtime.
- [ ] Per-block expandable image snapshots and explicit audio playback;
  contract in INLINE_RESULTS.md, not implemented by the global camera panel.
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
