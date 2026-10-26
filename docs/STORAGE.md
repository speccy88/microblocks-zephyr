# Device storage: bounded RAM stage

Storage is a separate portable service and MicroBlocks library. Files stay on
the device. This first backend is **volatile RAM**, for small text/JSON/logs and
binary records. It is not yet the full photo/audio archive. The shared web file
manager and RAM blocks are now physically verified over the local USB bridge;
see [physical acceptance](STORAGE_PHYSICAL.md). Board-hosted Wi-Fi remains blocked.
Flash and SD are unavailable; no filesystem is mounted, formatted or erased.
The current flash map has no user-files partition. Adding one requires an
explicit layout/migration plan that preserves firmware, assets and credentials.
An isolated [Flash service/LittleFS experiment](FLASH_STORAGE_LOCAL.md) is tested
separately on simulated media. It is not linked to the P4 firmware or the blocks;
the physical RAM profile and Flash-unavailable capability remain unchanged.

## Contract decided before implementation

- Eight files, at most 8192 bytes each, fixed storage and one 8192-byte staging
  buffer. The maximum payload capacity is 65536 bytes; free file slots and the
  per-file limit matter as well as bytes used. No allocator or heap fallback.
- Absolute paths use `/RAM/` plus 1-4 ASCII components, at most 63 bytes total.
  Components contain letters, digits, `_`, `-` or `.`, start with a letter,
  digit or underscore, and never contain empty, `.` or `..` components.
  Backslashes, URL escapes, drive prefixes, NUL and control characters are
  rejected. `/Flash/` and `/SD/` return unavailable, never route to host files.
- Explicit writes have a generation-checked job reference, declared size,
  sequential chunks of at most 1024 bytes, finish, poll/commit and cancellation.
  A replace flag is required to overwrite. Readers see the previous complete
  contents until commit. Incomplete, invalid or cancelled writes preserve them.
  Only one write job exists. Mutations while receiving/ready return busy.
- The portable service is single-owner. The Zephyr adapter runs on the VM
  thread, copies input before returning and keeps no pointer to a GC object.
  Poll commits at most one 8 KiB file; no background hardware or system worker.
  Cancellation works before commit, not after a completed write. Stop All
  cancels a pending write but preserves completed RAM files until reboot.
- Read/list/size/delete are explicit and bounded. Text uses strict UTF-8 with
  no embedded NUL; binary data is a copied ByteArray. Missing files, capacity,
  conflicts, invalid paths, unsupported backends and stale jobs are distinct.
  List output includes canonical paths; directory components are virtual.
- No timestamps are invented while the clock is invalid. No auto-save,
  recording, capture, network request, secret access or physical output occurs.

## Acceptance sequence

1. Host sanitizer tests for empty/binary/UTF-8 data, full slots/size, traversal,
   chunk ordering, all-or-nothing replacement, cancellation/Stop All, stale
   references, delete/reuse and deterministic malformed inputs.
2. Separate `storage:*` namespace, existing primitive IDs preserved; real GP
   library/example, local USB/station builds and disconnected editor screenshot.
3. Authorized P4 USB installation and physical storage/reconnect/restart tests
   passed on 2026-10-26; general GC/heap watermarks remain unmeasured.
4. Later: bounded media streaming,
   LittleFS Flash/FatFs SD adapters, capacity/attachment/power-loss checks and
   optional database. No automatic formatting or host/cloud storage substitute.

The first text example uses `/RAM/note.txt`; it writes only when explicitly
run. A program stop does not delete completed files. Power loss does.

## Earlier local result

The portable service passes ASan/UBSan host tests: 49 named checks, 10,000
malformed path/text inputs, atomic replacement/cancellation, binary and UTF-8
data, capacity, stale jobs, padded VM strings and delete/reuse. Fixed host
state originally occupied 74,352 bytes; revision guards increase it to 74,396
bytes on the host, including staging. This is reserved capacity,
not measured runtime peak. VM read results allocate bounded copied objects.

Separate Storage blocks use primitive set 25; JSON 22, clock 23, steps 24 and
all previous sets retain their indices. The service uses a separate bounded
extension217 protocol, rather than the unimplemented upstream file commands.
Both native Zephyr USB/station profiles build, with the full hosted flash map
checked. The actual disconnected GP editor loads the library and RAM-file
example at normal 1280 x 720 zoom. Save refuses an existing file; the separate
Replace block explicitly permits replacing it. Neither operation was executed
on hardware during this local stage.

Reproduce host checks with `python3 tools/test_storage.py` under Linux GCC.
Use the local packaging/native build commands in the P4
[START_HERE](../boards/waveshare_esp32p4_wifi6/START_HERE.md), then select
**RAM text file (temporary, new firmware required)** in Projects & board.
That earlier stage's evidence is recorded in
`evidence/2026-10-25/p4-storage-*.json`. The approved USB firmware installation
and physical tests have since passed. See the [release boundaries](P4_RELEASE_2026_10_26.md). Flash, SD,
media archives and database remain separate
open stages. The shared [file-manager frontend](FILE_MANAGER.md) now has a local
browser-fixture contract and UI. The [revision/session dispatcher](STORAGE_DISPATCH.md)
and frame adapter are implemented and host-tested. The
[controller integration](STORAGE_CONTROLLER.md) now uses the real generated
editor adapter and VM routing, with explicit Connect files and session cleanup.
Those hooks are now installed in the local USB profile. The 2026-10-26 physical
record covers 918 file requests, actual GP edits, independent byte readback,
resource-pressure regressions and reset volatility. Browser download completion
and network-hosted transfer remain unverified; Flash/SD are unavailable.
