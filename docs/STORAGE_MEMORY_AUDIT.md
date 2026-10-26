# Storage-scoped P4 memory audit

This is a local-only audit of the two linked images, their maps and pinned
Zephyr allocator source. It does not establish runtime heap/stack safety.
Hardware, installation and publication remain held. Feature expansion is paused.

## Decision before the bounded change

The station image uses 391488 of 393216 internal SRAM bytes. The remaining 1728
bytes are also `_libc_heap_size`: with `CONFIG_COMMON_LIBC_MALLOC_ARENA_SIZE=-1`,
the common C library creates its malloc arena between aligned `_end` and
`_heap_sentry`. This is not spare capacity in the independently reserved
32768-byte Zephyr system heap. Source: pinned Zephyr
`lib/libc/common/source/stdlib/malloc.c`, lines89-115 and `Kconfig`, lines57-79.

Only 46 bytes of storage objects remain internal: 40-byte controller, 4-byte
last-error value and two initialization flags. Its 74396-byte file store,
1712-byte codec workspace and 640-byte reply buffer already occupy PSRAM. The
112-byte primitive table is already read-only flash; adding `const` would save
nothing. No storage capacity, revision/session guard or queue limit will shrink.

Move just the 40-byte controller beside the existing CPU-only transfer state in
PSRAM. Its entry points run exclusively on the VM thread after initialization;
there is no ISR/DMA use, new allocation, retained GC pointer or new lifetime.
Keep the initialization guard internal. Verify placement and exact linker delta
in both profiles, run native sanitizer and application regressions, and preserve
all unrelated stack/heap/network/DMA reservations.

This can only yield a small reduction. A substantial increase requires work
outside storage: investigate measured stack use or CPU-only hosted buffers and
their flash/cache lifetime. Do not move interrupt/DMA buffers, relocate the
general malloc heap or shrink speech/network stacks on speculation.

## Result

| Linked reservation | Before | After | Change |
|---|---:|---:|---:|
| USB static internal SRAM | 243888 | 243856 | -32 bytes |
| USB automatic libc arena | 149328 | 149360 | +32 bytes |
| Station static internal SRAM | 391488 | 391456 | -32 bytes |
| Station automatic libc arena | 1728 | 1760 | +32 bytes |
| Storage internal object bytes | 46 | 6 | -40 bytes |
| External static region plus reserved heap | 17149840 | 17149888 | +48 bytes |

Linker alignment accounts for the difference between object-size and region-size
deltas. The controller is now in `.ext_ram.data`. No file count/size, packet
limit, generation, revision, session, expiry, queue, worker stack, system heap
or DMA allocation changed. Both generated `.config` files are byte-identical
before/after. The remaining six internal storage bytes are last-error and two
initialization flags. There is no kilobyte-scale storage-only saving left.

The station-versus-USB difference remains 147600 internal bytes. This is a profile
comparison, not a reconstructed history of every feature. Section deltas are
91472 bytes of `.dram0.noinit`, 39968 bytes of `.dram0.bss`, 5980 bytes of initialized
data and 9068 bytes of IRAM code, plus small tables/alignment. The network profile
adds 35328 bytes of fixed stack reservations and 16384 bytes of system heap.

The largest actual station reservations include:

- Fixed internal stacks total 140288 bytes, including speech 65536, VM 16384,
  station worker 12288, camera 8192, audio 8192, HTTP 6144 and WebSocket 6144.
  This excludes tiny diagnostic scalars named `stack_unused` and the separate
  external-memory inference stacks. Reserved sizes are not stack high-water marks.
- System heap backing 32852 bytes (32768 requested plus allocator overhead).
- Network RX/TX packet payload pools 16384/12288 bytes, UART ISR receive ring 8192,
  TCP connection slab 6800, HTTP server context 13944 and HTTP asset transfers 8240.
- Audio DMA slab 6144 and SDIO/driver buffers remain internal and unchanged.

The automatic libc arena is separate from the system heap and has allocator
overhead; 1760 bytes is not a claim that an allocation of that size can succeed.
No runtime free/largest-block values, concurrent worst-case demand, allocation
failure rate or current stack watermarks were measured. Historical successful
camera/STT tests do not validate this changed combined station image.

## PSRAM constraints

The configured external heap remains 16777216 bytes, with the heap start/end
shifted by 48 bytes due to added static metadata. It serves dynamic camera/audio,
previews and inference allocations; the speech engine can reserve 12 MiB within
it. The board's 32 MiB PSRAM does not mean every unoccupied byte is available from
that configured 16 MiB heap. The complete linked external region is 17149888 bytes;
the remaining physical address space is not automatically another allocation pool.

The moved metadata is CPU-only, initialized before first use, never referenced
by an ISR or DMA engine, and only accessed by the VM thread after normal Zephyr
startup. It follows the existing file-store/transfer placement. It must not be
accessed during cache-disabled execution. No cache policy, DMA descriptors,
interrupt stack, general malloc allocator or persistent flash region was moved.

## Verification and remaining decision

Both native profiles and full model/app/assets/settings layout checks pass.
Native ASan/UBSan suites pass 49 storage checks + 10000 malformed inputs, 23
dispatcher scenarios + 10000 malformed packets, and 12 actual VM-bridge scenarios.
All 47 affected Node tests and 61 canonical repository regressions pass. The latter
preserves the known unchanged Windows FruitJam CRLF/provenance workaround.

Reproduce the read-only linked audit with the existing Zephyr Python environment:
`python tools/audit_p4_memory.py --workspace <west-workspace> --output <report.json>`.
It reads both existing build directories, ELF symbols/sections, maps and selected
non-secret Kconfig settings; it neither builds nor contacts a board. Full evidence:
`evidence/2026-10-25/p4-storage-memory-local.json`.

**Memory risk remains unresolved.** Keep feature expansion paused. A next local
review can examine the 8240-byte CPU-side HTTP asset transfer array, proving the
pinned flash-read/cache and asynchronous response lifetime before any relocation.
Another option is a measured stack/allocator budget after hardware testing is
authorized. Neither reduction is included here. No hardware, flash, commit,
push, publication, deployment, credential or network/security change occurred.
