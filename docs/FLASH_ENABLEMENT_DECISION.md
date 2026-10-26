# Build-only Flash enablement decision

No hardware or production layout change is authorized. This review preserves
both known-good profiles and describes an optional, non-activating candidate.
The candidate has not been built; the publication checkpoint below explains
the memory blocker. This document cannot authorize formatting or flashing.

## Candidate layout and constraints

32 MiB NOR and P4 rev1.3 are established by the existing ROM/flash evidence.
Simple ROM boot loads at 0x2000; there is no MCUboot secondary slot/OTA scheme.
Whistle weights are inside the mapped app image. MicroBlocks program storage is
currently volatile; the port does not own an additional persistent program area.
Station settings use NVS at 0x1fe0000..0x2000000. C6 has separate firmware and is
not part of this map. No credentials or live partition bytes will be read.

Current app/model region 0x2000..0xfe0000 is unchanged. The asset blob currently
ends at 0x1345f5d, within the 0xfe0000..0x1fe0000 asset reservation. There is no
unallocated file partition. Candidate only: reduce assets to 15 MiB ending at
0x1ee0000 and allocate the following 1 MiB through 0x1fe0000 to user files.
Keep settings exactly at its existing offset/size. This avoids all known image
bytes but does NOT prove the live candidate region is empty or disposable.
USB would adopt the same explicit tail regions instead of its broad reservation.

An eventual migration must inspect the intended live region without exporting
credentials, refuse unknown existing data, and request explicit authorization
before erasing/formatting exactly that user-file area. Asset packaging and BOTH
profile guards must enforce the smaller asset limit. Downgrades or old packages
that can fill the former 16 MiB asset region are unsafe after migration. No OTA
or retained VM-program feature is implied by this file partition.

## Resource hypothesis before building

Retain the current stacks/heaps and 8192-byte hosted libc regression floor.
Place only portable record state and future copied job/reply payloads in PSRAM.
Keep LittleFS metadata/caches, file-cache heap, fixed 256-byte I/O bounce buffer,
worker stack/control and flash-driver objects internal. No DMA allocation moves.
The VFS adapter copies between PSRAM and internal bounce storage outside fs calls;
this avoids relying on HAL's external-pointer temporary-buffer allocation path.
The pinned HAL explicitly handles cache-off DRAM requirements. This source
reasoning does not prove every P4/cache/concurrent-driver interaction.

The optional build must retain the backend, filesystem and a conservative
4096-byte unused worker-stack reservation, without starting a worker, mounting
or initializing media. It is a footprint probe, not an exposed storage backend.
If the station build violates its existing guard, stop activation work and report
the measured shortfall; do not lower the guard or shrink existing reserves.

Acceptance: candidate interval/size/alignment and negative-overlap tests;
separate USB/station compile/link attempts, exact memory maps and PSRAM symbol
locations; known-good artifact hashes unchanged; native LittleFS fault tests
and affected regressions pass. Physical runtime/persistence remains unverified.

## Publication checkpoint — proposal only

The optional candidate profile and link attempts above have NOT been implemented
or run. This audit is checkpointed before publication of the already-tested RAM,
KWS, JSON and automation work. Neither a new layout nor PSRAM cache placement is
enabled by this document. The tested Flash prototype remains isolated.

The existing station libc arena is 9424 bytes; its guard requires at least 8192,
leaving only 1232 bytes of static growth above that floor. A 4096-byte worker
stack alone would leave 5328 bytes, a shortfall of 2864 before filesystem caches,
control or I/O bounce storage. That is a quantified blocker to the proposed
dedicated-worker design, not a measured optional-profile link result. USB has
149360 bytes of libc arena, so it does not share this particular static limit.
No reserves or guard have been reduced to make the candidate appear viable.

The pinned `flash_esp32.c` calls `esp_flash_read`/`esp_flash_write`. HAL
`esp_flash_api.c` explicitly checks direct DRAM buffers; external reads may need
an internal temporary allocation, and external writes are copied before entering
cache-disabled operations. A future fixed internal bounce buffer avoids relying
on that extra allocation, while the portable record state can be considered for
PSRAM. That adapter change and full driver/callback/stack audit remain pending.

Next choice: retain the current two profiles and first redesign/share the bounded
worker resources with measured concurrency limits, or develop a separate USB-only
Flash experiment while station enablement remains blocked. Neither choice grants
authority to initialize the proposed region, flash a new image or drop station
support from the product.
