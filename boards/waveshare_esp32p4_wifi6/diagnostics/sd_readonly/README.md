# FAT32 card: isolated read-only diagnostic

Local build only. This is a peripheral bring-up image, not the MicroBlocks
application, and has not been installed or tested on the inserted card.
The working station/USB MicroBlocks image and its reserved editor/settings
partitions must remain preserved. Installing this diagnostic would temporarily
replace the P4 application and require a deliberate firmware-write decision.

## Contract before hardware testing

- Use the compact Waveshare ESP32-P4-WIFI6's native slot 0: CLK43, CMD44,
  D0..3 GPIO39..42, active-low power GPIO45. Slot 1/C6 is disabled here.
- Do nothing with the card until a `T` arrives on CH343 UART0 (115200 baud).
- Compile FatFs read-only. Compile out mkfs and mount-time formatting; also
  mount with `READ_ONLY | NO_FORMAT`. No file writes, deletes or content reads.
- Measure raw card capacity and count at most 32 root
  entries, with one extra read to detect truncation. Do not log file names,
  card serial numbers or private content. Always close/unmount after success
  and after later errors; report cleanup errors separately.
- Pinned Zephyr FatFs returns `ENOTSUP` for `statvfs` in strict read-only mode.
  Keep listing usable, report free space unavailable, and never present a zero
  placeholder as measured free space. Raw card capacity comes from read-only
  disk geometry IOCTLs, not from a guessed card size or file content.
- Reject impossible capacity arithmetic. All buffers stay bounded/internal;
  the probe allocates no heap, creates no thread, and never uses PSRAM for DMA.
- Preserve existing files. No format fallback, filesystem repair, partition
  change, automatic write test, or network/credential access.

## Acceptance tasks

1. Host tests: mount/stat/open/read/close/unmount failures, empty and long root
   directories, capacity validation, cleanup and repeated calls.
2. Cross-build the exact pre-v3 target with the pinned Zephyr/SDHC patch series.
   Inspect ELF/config to prove that format/write code is absent, slot 0 is
   selected, slot 1 is disabled and memory fits. This is not a physical pass.
3. Only after approved installation: verify actual card detection, FAT32 mount,
   capacity and cleanup. Record numeric results without private filenames.
4. Integrate with MicroBlocks only after runtime memory/resource budgeting.
   The SD card and C6 share a controller; its existing cross-slot mutex is
   necessary, but does not prove simultaneous SD/Wi-Fi operation. Test that
   separately, including card removal and ongoing programming traffic.

Command/data retries have finite driver limits. Mounting and listing
do not yet have an overall cancellation/deadline mechanism. They
run in this isolated application's main thread, never a MicroBlocks VM or
network/system workqueue. That is another prerequisite for later integration.

Build from the pinned WSL west workspace, substituting the repository path:

```
west build -b esp32p4_wifi6/esp32p4/hpcore \
  -s <repo>/boards/waveshare_esp32p4_wifi6/diagnostics/sd_readonly \
  -d build-p4-sd-readonly
```

The optional FatFs module must first be present at the revision in the pinned
Zephyr `west.yml`: `4f60a12c58c3de4246857ad87c40239ecd93349b`
from `https://github.com/zephyrproject-rtos/fatfs` (`west update fatfs`). Keep its
upstream license. Host tests: `python tools/test_p4_sd_readonly.py`.

No image in this directory should be mistaken for an upgraded MicroBlocks
release. A later write/readback test must use a unique new file, preserve all
existing files, leave the test file in place and report its path.
