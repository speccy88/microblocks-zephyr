# P4 static SRAM reduction and Pi service checkpoint

2026-10-28, isolated migration branch based on 06f0a8c. No flash, deployment, push,
main/GP/SFC change, protected P4 access or robot command. Fred later authorized
one Pi reboot; [its separate evidence](../pi-user-service/REBOOT.md) records
automatic VM startup, saved code and graphical reconnect plus session disruption.

## Measured linker allocation

| Item | Before | After |
|---|---:|---:|
| Internal SRAM region |393,216 B|393,216 B|
| Static occupied |382,880 B (97.37%)|378,784 B (96.33%)|
| Reserved libc arena |10,336 B|14,432 B|
| Mutable permutation tables |4,096 B internal|0 B internal;4,096 B const flash|
| Whistle native stack |65,536 B|65,536 B|
| Main / HTTP stacks |16,384 /6,144 B|16,384 /6,144 B|

The [ELF inventory](memory.json) and preserved linker-map archive identify the
allocation, rather than treating the percentage as runtime heap consumption.
70,512 B of IRAM code,1,308 B loader code,230,728 B `.dram0.noinit`,24,028 B `.dram0.data`
and 49,376 B BSS contribute to the new allocation, along with object tables and
alignment. The largest internal objects include the 65,536 B inference stack,
32,852 B system heap including metadata,16,384 B RX pool,16,384 B main stack,
13,944 B server context,12,288 B TX pool and12,288 B station worker stack.
These heaps/pools are already counted in static occupancy. The remaining libc
arena is a reservation, not measured current free memory.

The adaptation generates two const int32 index tables from the exact verified
D4 model. The raw pinned Apache-2.0 source stays unchanged; only a generated copy
is adapted, with strict source-hash/anchor checks. Runtime model equality is
checked before inference. Table flash addresses are0x40e79220 and0x40e78a20.
The post-link guard compares all bytes with the model and rejects writable RAM
placement. CPU inference already reads the model in mapped flash; no ISR/DMA
buffer or critical stack is moved. All stacks, pool sizes, Kconfig and DTS remain
unchanged. Earlier physical stack evidence recorded 43,964 B used and corruption
with the former 24 KiB allocation, so shrinking that stack was rejected.

## Validation and outputs

Six bounded-reader regressions cover FP16/FP32, geometry, truncation, metadata,
payload bounds, integer/range/duplicate checks and unreviewed source rejection.
The [independent C oracle](oracle-receipt.json) uses the original upstream loader:
all 1,024 table values and 1,024 synthetic encoder floats are byte-identical;
changed permutation data fail with -13. Combined output SHA256:
`e6ca0476891952052f9ed36b37544b7f101f8e95730e67aae14721db6ec2999e`.
This is host numerical equivalence using synthetic samples, not speech accuracy
or P4 execution. The mutation fixture was corrected from an FP16 assumption to
handle the observed FP32 data; final positive evidence is retained separately.

The full station/neural/Whistle/KWS/SD/saved-boot profile recompiles and links.
All four actual-image checks pass: VM/stack placement, isolated RPC pool,
flash/model/assets layout, and Whistle model/const table integrity. The new raw
image is15,312,496 B, SHA256
`c40bfcc8bea56ee9f063b6c2f56aa8da341e622a03cf2c1fa69ac482072774d7`.
ELF SHA256 is
`3111e23af8acf4a52d14cb0370bf7861293eda7a4bd74cbf11ec71e09c869640`.
It remains an unguarded local build, not an installable release or exact owner
image. Its unchanged config/DTS hashes and four check results are in the
[receipt](build-receipt.json). Build commands/configuration/logs/maps, original
source provenance, preparation hashes and synthetic oracle are in
[raw audit evidence](raw-sram-evidence.zip); no firmware/model/recording is committed.

The build wrapper failed only after compiler/linker completion while obtaining
Git metadata: Linux Git cannot resolve this Windows worktree's `.git` path.
The completed output was preserved without recompilation and all four guards
were independently rerun successfully. That receipt-wrapper error is not hidden
as a compiler success status. Existing compiler warnings about conversions,
indentation and deprecated network APIs remain; this does not resolve them.

Complete unchanged-validator results and frozen source hashes are recorded in
[full validation](full-validation-receipt.json). The tested installer's actual
Pi service lifecycle and safe cleanup are documented [separately](../pi-user-service/README.md).

## Readiness

The extra 4 KiB is useful margin; 96.33% static occupancy remains a risk. No runtime
allocator margin, fragmentation, stack guard, contention, timing or P4 boot
result follows. Physical worst cases, silicon/image reconciliation, clean-model
acquisition, release guarding and hosted-CI/publication gates are itemized in
[the acceptance inventory](../../../docs/DEPLOYMENT_ACCEPTANCE_20261028.md).
The live site, GP fallback, P4 owner firmware and paused SFC remain unchanged.
