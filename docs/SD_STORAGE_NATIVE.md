# Native SD integration

## Bounded write increment

An optional `P4_SD_FILES` profile uses exclusive FatFs creation inside
`/SD:/MBFILES`, without format or replacement fallback. Names are uppercase
8.3 only and each file is at most 8 KiB. The first acceptance is a uniquely
named, non-sensitive test file: write, sync, close, reopen and compare every
byte. Removing it is a separate explicit operation, permitted only for the
worker's successful creation snapshot and after another exact-content check.
No automatic cleanup deletes a partial file. The card must remain powered
through completion; FAT32 does not offer power-loss atomicity for these writes.
The native worker must serialize these jobs with read-only probes and bounce
PSRAM data through internal buffers. Mount/close/unmount and cancellation/error
paths require host tests before installation. The physical results below
distinguish the tested native operations from graphical acceptance.

## Read-only profile and earlier baseline

This opt-in profile adds SD detection, FAT mount, raw capacity and a count of
at most32 root entries to the existing native MicroBlocks application. It
does not expose file contents/names, support SD file editing, or write a test
file. RAM and Flash services remain separate. SD file-manager availability
stays false until the actual file protocol supports it.

Use the exact compact ESP32-P4-WIFI6 board's slot0 CLK43/CMD44/D0..3 GPIO39..42,
active-low power45. C6 remains on slot1 CLK18/CMD19/D0..3 GPIO14..17/reset54.
Append profiles/sd-readonly.overlay after the station overlays. The pinned
SDHC driver uses a shared transaction mutex and restores per-slot clocks;
this is necessary but does not prove simultaneous SD/Wi-Fi works on hardware.

The SD library appends storage:* primitives without moving existing indices:
sdAvailable, sdProbe, sdBusy, sdCancel, sdStatus, sdPhase, sdReady, sdMiB and
sdEntries. sdAvailable means
the configured controller is ready, not that a card/filesystem was detected.
Probe only starts explicitly. Stop All requests cooperative cancellation.

The worker owns its data, mount/directory lifecycle and internal4096-byte
dynamic stack. Allocation failure returns an explicit error. Poll joins the
terminated thread before freeing its stack/job. No VM/GC pointer survives a
primitive and no lengthy operation runs on the VM/system/network workqueue.
Its30-second deadline and cancellation are checked between blocking calls;
an in-progress SD driver call may overrun it. Never abort a DMA/lock owner.
Existing station SDIO timeout/retry settings are preserved. Measure elapsed
time, responsiveness, cleanup and stack watermark physically before claiming
bounded wall-clock behavior.

FatFs is compiled read-only, mkfs/mount-format disabled and mount flags require
READ_ONLY|NO_FORMAT. DMA buffers and the FatFs sector window remain internal;
CPU-only report state can use PSRAM. The SD stack's aligned-buffer fast path
does not bounce aligned PSRAM, so moving a sector window to PSRAM is unsafe.
Pinned read-only FatFs lacks free-space queries: report unavailable, never0
as measured free space. Always close/unmount after failures. No card names,
serial numbers, private file names or contents are logged.

Acceptance: host cancellation/deadline/cleanup tests; both native builds and
whole-flash/memory guards; inspect ELF for no FAT write/format code. Only after
safe installation, prove actual card detection/capacity/mount, repeated probe,
cancellation/cleanup and simultaneous Wi-Fi editor/HTTP. Do not format on
failure or modify current files. A later write test needs a separate RW
backend decision and one unique dedicated file left in place after exact
readback; this read-only implementation cannot perform that write.

## Measured local installation, 2026-10-27

The COM5-only candidate0a7045637b8e7bade0bd0f389711dffac31586df8e0e9ca7e9ef2dd6ca3b202d
was flashed and checksum-verified. Original application1a40ca46 remains a
preserved compiled artifact; no MCU backup was taken. Editor assets/settings
and C6 firmware were not written. Both USB and station builds pass, with
whole-image/model/layout guards.

Initial station+FAT32 static growth left only6016 libc bytes and correctly
failed the unchanged8192-byte audit floor. A source audit of the pinned
v417 interpreter/runtime/GC shows the5240-byte Task array is owned by the VM
and contains its operand/state records. The P4 preparation step places it
in initialized PSRAM, preserving Task layout/count and all native stack sizes.
A new ELF guard verifies that placement and internal native stacks. Final
static internal use381968, libc arena11248, system heap32768; the SD job needs
at least4504 temporary kernel-heap bytes including its4096-byte stack, plus
allocator/alignment overhead. The FatFs sector window576 and SD card state768
remain internal and DMA-capable. Runtime overall heap watermarks are not measured.

Actual results: FAT32, raw card31299993600 bytes (29850 whole MiB), six root
entries without truncation or private names/content. Each ordinary probe took
about1110–1112ms, with13 arithmetic VM roundtrips while busy. Close/unmount
errors were0; measured unused worker stack2852–2876 bytes. An overlapping
2194999-byte compressed editor asset transferred/hash-verified in17.672s.
Cancellation returned native picolibc ECANCELED140 and cleaned up; subsequent
probe/reuse succeeded. A first host assertion incorrectly expected Linux125;
that evidence is preserved, and remaining checks were completed without reset,
reflash or reassociation.200 status reporters and a generated resize/grayscale
pipeline passed; SDIO invalid-header/bus-error counters stayed0 and Wi-Fi stayed
connected. Free space remains explicitly unavailable (native ENOTSUP134).

205 probe checks and97 worker lifecycle checks pass with ASan/UBSan; canonical
regressions65 pass. Those host tests remain separate from physical evidence.
The root-entry bound is33 calls to fs_readdir, not33 underlying sector reads.
See [curated physical evidence](../evidence/2026-10-27/p4-sd-readonly-summary.json).

The SD Card library is authored/embedded in local packages, but its actual GP
palette/graphical execution is not yet checked or installed in board assets.
The local preview hit a browser error-page URL-policy block and was isolated,
without alternate browser/navigation routes. The known browser-download
permission loop was never restarted. Installed SD file-manager support is
still unavailable. Production automatic Wi-Fi reconnect after reboot remains
unverified because this installed profile is diagnostically gated.

FatFs dependency: pinned Zephyr module4f60a12c58c3de4246857ad87c40239ecd93349b;
upstream ChaN/module notices are retained unchanged. To reproduce the optional
build, append profiles/sd-readonly.conf and profiles/sd-readonly.overlay to the
existing station build (the latter after c6-sdio/hosted overlays). Default
profiles use the explicit unsupported SD service stub.

## SD file profile installed and native acceptance, 2026-10-27

The independent continuation task compiled and installed the matching native
application `4de3ae8ca235f814344d84b494b0fb70ba99341494ea4d46057c45c5dfcccaf4`
and editor assets `44fb73224ad225eeb62375b1e37690078fdadb30c3e2a1bc03c36f239188c977`.
Full old-application and old-asset digests matched before writing; both complete
new digests matched afterward. C6 and settings were preserved. Compiled rollback
artifacts were retained; no device backup was read. The station build retains
a 10,608-byte libc arena, unchanged 32 KiB system heap, internal native stacks
and both internal FatFs sector windows. Format/mkfs/fdisk symbols are absent.

An exclusively created random test name in MBFILES held 8,192 known bytes.
Sync, close, reopen and exact readback passed in 1.234 seconds. A simultaneous
HTTP 200 editor data transfer matched its hash in about 20.34 seconds. The host
harness then blocked without VM pings while waiting for HTTP, causing the known
five-second native peer timeout and file-lease invalidation. That incomplete
receipt is preserved. No creation was repeated: a fresh lease reopened the
same file, matched every byte again, and removed only that creation using its
retained native ownership snapshot. Final removal returned error 0; the worker
was idle with 2,188 unused stack bytes. Existing SD files were not changed.

The new [bounded SD file-manager contract](SD_FILE_MANAGER.md) documents the
protocol, UI and limits. Actual graphical acceptance is recorded separately.
This was the local diagnostic installation before the bounded saved-boot
follow-up below.

The final UI-corrected application is
`bbaba6feb0ea872b957e67b12988fe5e9e4d60e81ffaed5c047bab28a097cfdc`, with assets
`30ef126cdbc1ff67ccc5b34e59089afea0680490f4d1d4f1541a758383d0cfe1`.
Both were installed after complete old-image digest checks and verified in full
afterward. Real browser acceptance on this final pair created a unique 60-byte
UTF-8 text file, refreshed the list and reopened the same accented text exactly.
An independent COM5 lease reread all 60 bytes and removed only that owned test
file, with error 0 and 2,188 unused worker stack bytes. No test files remain.
The startup-order and active-backend-banner fixes have 42 passing JavaScript
tests. See [curated final evidence](../evidence/2026-10-27/p4-sd-files-summary.json).

## Saved Wi-Fi boot follow-up, 2026-10-27

The application is now
`cc533266f45f1b76be5606ef6608a74611f7f87a919e7630775c6ccd87849ec3`,
with the same `30ef126c...` editor assets and unchanged SD backend. Three warm
boots automatically connected without a host station command, and each passed
read-only MBFILES listing during a hash-verified HTTP asset transfer plus
wireless VM arithmetic/editing. This follow-up performed no SD writes, format,
credential provisioning or C6 flash. The compiled prior `bbaba6fe...` image is
retained for rollback. Full power removal and later network-loss recovery remain
outside the tested bound; see [exact boot evidence and policy](P4_SAVED_WIFI_BOOT.md).

The later normal loss-retry image is `a4e49b75d390a4c24ca011662b5c80972d6b1c3447f69d5d33cecae1df1cad56`,
with unchanged editor assets and SD backend. Its boot/read-only SD/HTTP/VM
acceptance passes; the diagnostic also passed those operations after one local
link loss. No additional SD file write was made. Initial TCP intermittence
remains a limitation in [recovery acceptance](P4_WIFI_LOSS_RETRY.md).
