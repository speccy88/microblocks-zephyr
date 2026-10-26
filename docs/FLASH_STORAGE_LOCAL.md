# Flash backend: local-only acceptance contract

This increment is separate from the physically verified RAM service and SD.
No board access, flash/erase/format, credentials, commit or publication is allowed.
The current P4 firmware, editor capability and partition overlays stay unchanged.

## Layout decision before implementation

The pinned station map reserves app/model `[0x2000,0xfe0000)`, assets
`[0xfe0000,0x1fe0000)` and settings `[0x1fe0000,0x2000000)` on 32 MiB NOR.
The USB profile reserves the same tail as a single region. It is not free space.
The current asset blob ends at `0x1345f5d`, but its partition reserves 16 MiB;
the settings region contains approved station credentials. Neither may be
reused by a filesystem. Application image slack is also not a user partition.

A deployable backend needs a separately named, erase-aligned partition, a
reviewed migration plan and updated guards for BOTH profiles and packaging,
plus explicit authority to initialize that partition. No proposed migration
is applied here. Blank or corrupt media must fail mounting without formatting.

## Bounded local deliverable

- A portable Flash record service and a separate Zephyr VFS/LittleFS adapter,
  exercised in native_sim against a dedicated simulated flash area only.
- Eight logical `/Flash/...` files, each at most 8192 payload bytes, 65536-byte
  aggregate payload quota. ASCII path grammar matches RAM, with a distinct
  root. No host path, firmware/settings directory or arbitrary physical key.
- One single-owner synchronous operation at a time. Future integration must
  dispatch through a dedicated bounded worker, not block the VM/system queue.
  No new blocks or availability claims before that integration and a partition.
- Fixed workspace, bounded metadata and copied read chunks; no owned GC pointers.
  Backend physical storage includes headers, allocation and filesystem metadata;
  logical quota and `statvfs` free bytes are distinct, not interchangeable.
- Revision-checked create/replace/delete/read. A durable sequence is reserved
  before each file replacement; gaps after failure are allowed, revision reuse
  across remount/delete/recreate is forbidden. Counter exhaustion fails closed.
- Separate bounded record with revision/path/length/CRC; CRC detects accidental
  corruption, not malicious modification. Unknown or invalid records fail closed
  without erasing or silently repairing user data.
- LittleFS temp write, sync, close and same-filesystem rename are the commit
  path. All short writes and errors are surfaced. A mutation failure leaves the
  service unavailable until remount/reconciliation, with no automatic replay.
  Temp records are ignored on mount and replaced only by an explicit new write.
- No production format API or automatic filesystem initialization. Test-only
  fixtures explicitly format simulated storage, never a P4 partition.

## Acceptance gates

Use the actual pinned Zephyr filesystem API and LittleFS, not only an in-memory
mock: blank/corrupt/no-format, normal mount/unmount, empty/text/binary, quota/
capacity, revisions, delete/recreate, simulated restart persistence, malformed
records, injected short writes/sync/close/rename errors and recovery. Fault tests
must distinguish old/new atomic outcomes from real power-cut proof. Verify
production P4 source/config/ELF hashes and memory maps remain unchanged; report
prototype workspace/stack/filesystem costs separately, without extrapolating
native host ABI totals into a P4 runtime guarantee.

Source basis: pinned Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`,
`include/zephyr/fs/{fs,littlefs}.h`, `subsys/fs/littlefs_fs.c` and its native tests.
Zephyr's [VFS documentation](https://docs.zephyrproject.org/latest/services/storage/file_system/index.html)
describes independent mount points and filesystem adapters. In this pinned
driver, `FS_MOUNT_FLAG_NO_FORMAT` prevents the default format-on-mount-failure
path. LittleFS rename/delete durability still needs real-board power-loss tests
after any later authorized migration.

## Implementation and reproduction

`common/storage/flash/flash_store.{c,h}` implements the portable record service.
`zephyr_flash.{c,h}` implements fixed-key Zephyr VFS operations; logical user
paths never become filesystem paths. It supports mount/unmount, bounded list,
stat/read, conditional put/delete and logical/physical capacity reporting.
The synchronous API is only an experiment for a future single-owner worker;
it does not yet expose staging/cancellation or route existing VM/file commands.
LittleFS is external, pinned by the existing Zephyr manifest at
`e9a8638fc228e43a3156ed3ac602229af3e3c1d5` (BSD-3-Clause).

The `tests/flash_native` CMake project refuses non-native_sim boards. Its
256 KiB flash fixture has no P4 addresses. Only that test source calls `fs_mkfs`.
Production adapter mount always sets `FS_MOUNT_FLAG_NO_FORMAT`. Mount scans
fixed sequence/slot/temp names and rejects unknown files or directories without
deleting them. A record has an 80-byte header, payload and 4-byte CRC; the
separate 16-byte sequence record survives deleting every user file. The single
temp file is synced and closed before rename. Reserving a sequence and changing
a file are two durable writes, so gaps and write amplification are intentional;
this is unsuitable for per-sample logging without later batching/wear analysis.

From the existing pinned west workspace (fetch the manifest-pinned `littlefs`
module if absent), with the installed Zephyr SDK selected:

```sh
west build -b native_sim/native/64 -d build-p4-flash-native -s <repo>/tests/flash_native
build-p4-flash-native/zephyr/zephyr.exe --flash=<workspace>/flash-native-test.img --test='flashlocal::*'
build-p4-flash-native/zephyr/zephyr.exe --flash=<workspace>/flash-native-test.img --test='persist::test_seed'
build-p4-flash-native/zephyr/zephyr.exe --flash=<workspace>/flash-native-test.img --test='persist::test_verify'
```

Use only a disposable workspace image: the test suite intentionally formats it.
The last two commands are separate processes sharing that simulated image.
This verifies restart persistence, not real electrical power-loss durability.
No board, serial port, host user files, live partition or credentials are accessed.

## Memory boundary

The portable state is 8868 bytes under the actual P4 RV32/ilp32f compiler ABI;
its standalone optimized object has 3013 text bytes and zero static data/BSS.
This excludes VFS/LittleFS code, controller integration, worker stack and caches.
On the native64 simulator, the state is 8880 bytes. Mount read/program caches
are 256 bytes each with a 32-byte lookahead, plus a dedicated 512-byte file-cache
heap and one file/directory slab. The default 288-byte cache heap produced
`-ENOMEM` with native64 metadata; a bounded explicit 512-byte pool resolved it.
These host pool/slab costs must not be assumed identical on RV32.

Both production ELF/config/map/bin hashes remain identical to the physical RAM
acceptance baseline: USB internal/libc 243856/149360 bytes; station
383792/9424 bytes. Before/after static delta is zero because no prototype object
is linked. Putting the core state in station internal SRAM would leave only
556 bytes before the additional filesystem/worker costs and violate the existing
allocator floor. Deployment therefore requires an audited PSRAM placement and
cache-safe flash I/O plan, bounded worker resources and real runtime evidence.
No existing stack/heap reserve was reduced, and no DMA memory was moved.

## Completed local evidence, 2026-10-26

Ten native Zephyr/LittleFS test groups pass with AddressSanitizer, including
10,000 malformed paths, all eight files at full quota, 16 full-size replacement
cycles, stale revisions, delete/recreate, busy guards and corrupt/unknown/
duplicate record rejection. Twelve injected sequence/data mutation failures
cover short write, write/full, sync, close and before/after rename. Failed
mutations require remount; the recovered record is the complete old or new
version. Real simulated-filesystem exhaustion preserves the previous file.
Blank and corrupt simulated media remain byte-identical after mount failure.
Separate seed and verification processes pass persistence with a shared test
image. No sanitizer diagnostics were reported. Native virtual-clock test times
are not performance measurements, and the busy guard is not multi-owner testing.

Existing RAM suites pass unchanged: 49 checks plus 10,000 malformed inputs;
23 dispatcher groups plus 10,000 malformed packets; 12 controller/VM bridge
scenarios. Canonical repository validation passes 65 tests with the existing
unchanged-FruitJam CRLF/provenance handling. `git diff --check` passes.

Evidence: `evidence/2026-10-26/p4-flash-local.json` and
`p4-flash-local-memory.json`. Source/log hashes and exact profile identities are
included. The previously installed RAM artifact remains preserved with SHA-256
`b46a58136e264d54ab7944471f8cfc5ae918d29f9e5ca3dca620ca34c8beb065`.
There is no new Flash palette entry, editor screenshot or board capability:
the prerequisite partition/memory/integration work is intentionally not implied
by the simulator result. No hardware, C6, COM12, credentials, live formatting,
commit, push, publication or deployment was accessed or performed.
