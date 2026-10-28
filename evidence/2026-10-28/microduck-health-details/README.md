# Additional typed MicroDuck health and coexisting abstraction layers

The normal read-only robotd adapter now supplies **27 health selectors**: the
previous 21 plus motors.hottest and cpu_throttle.level, max_level, khz, max_khz,
and throttled. Source: pinned official API 44 commit
96b89d8613f06722c1d64ce75ab0d7124fed9d8f, duck-ipc-proto/src/lib.rs,
HealthResult/MotorThermal/CpuThrottle. No upstream source or protocol pin changed.

Missing optional CPU sections/keys remain not_reported; present zero/false are
known. The derived predicate follows upstream level>0 or max_khz>0 and
khz<max_khz, and requires its three source operands. These clocks are ceilings,
not instantaneous frequencies. Exact u32 values are decimal text with count64
or kHz64 units across the signed31 VM boundary. The native decoder rejects
wrong units/types, forged defaults, negative/noncanonical/overflow strings and
cross-source markers. Hottest names retain bounded UTF8 text. Existing raw
18-field health decoding and all 21 primitive indices are unchanged.

Six named advanced Robot blocks accompany two simple helpers for board
temperature and reported health verdict. Both layers share capture/read/release
and typed records in one project. Normal import: 6 modules/146 functions;
optional Starter Lab: 10 modules/186 functions. Real JS parser/compiler/source
reopen is tested, and all 186 compiled functions are uploaded to the actual local
native VM. A faithful Unix robotd fixture supplies the data. The new simple
temperature returned 41250 mC, reported verdict degraded, and advanced clock
ceiling 408000 as exact decimal text; snapshot stores were empty afterward.

Fresh native build and self-test passed with AddressSanitizer and
UndefinedBehaviorSanitizer on **local x86-64 Linux**, using pinned VM 417.
Binary SHA256: f4b88494482e795d4ee13542f0bb00ee2c9120320ae6900be9853c7855a38e58.
The final full unchanged validator passed **534 tests**, zero failures/skips;
wrapper elapsed 295.331 s. All 2,383 repository
source hashes matched both original and replica after validation. Exact input
and native build manifests accompany this note. Evidence was added afterward.

The earlier 534-test run had three failures from obsolete 140/141/144 library
count expectations. All native and new health/helper assertions passed in that
run. The expected counts were updated to 146/147/150 for the added functions;
no deadline, exclusion, transport gate or behavior assertion was weakened.
The final run reuses the fresh sanitized binary only after checking every port
source hash and its manifest/binary hash against final sources.

This checkpoint has **no new Pi, graphical MicroDuck or physical robot test**.
Earlier Pi evidence applies to the earlier selectors. No robot movement,
credentials, BLE transfer, service/network/security changes, SDK modification,
P4 hardware access, publication or deployment occurred. GP/live/main and paused
SFC are preserved. Remaining gaps include typed missing-servo IDs, model geometry,
commissioned live control/continuous streams and production camera integration.
Mediad audio remains unsupported without a reviewed upstream interface.
