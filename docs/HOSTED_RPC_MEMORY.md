# Bounded companion protobuf allocation (local only)

Feature expansion and all hardware/publication actions remain held.

## Contract before implementation

The companion transport limits each frame to 1600 bytes: 12-byte frame header,
12-byte SERIAL TLV, at most 1576 protobuf bytes. Decoded pointer fields can expand
far beyond wire length. One RPC is pending at a time, but a caller may still own
a response when the RX thread decodes another event. Therefore an arena reset
after each decode would invalidate retained response pointers.

Use an independent **65536-byte fixed pool** for the hosted profile's nanopb
allocations, backed by PSRAM and Zephyr sys_heap with a thread mutex. Realloc/free
retain normal ownership semantics across threads. Allocation failures reject
the entire protobuf message; no truncation, count clamp, schema or wire change.
Existing libc/system/external heaps, stacks, clients, DMA buffers and storage
session bounds remain unchanged. This new pool consumes static PSRAM, not the
existing external allocation heap. Ordinary BSS is used for native host tests.

Redirect only the pinned nanopb module's realloc/free hooks in this P4 hosted
build. Assert the expected target exists. The current image's nanopb consumer is
ESP-Hosted; USB does not enable this adapter. The pool is CPU-only: driver RX
frame buffers and transport DMA remain internal. Access happens in threads after
PSRAM startup, never in ISR/cache-disabled code. Lazy initialization occurs under
the same mutex as all allocator operations, and no shared arena reset is exposed.

Keep the decoder's existing ownership transfer and timeout behavior. Malformed
or exhausted messages are dropped whole; the matching caller may get its existing
bounded RPC timeout. Do not infer a trustworthy response UID from a partially
decoded message and wake the wrong caller. Add an independent 1576-byte entry
bound around the decode hook; retain the driver's existing frame/TLV validation.
The existing legacy receive path accepts zero checksums and does not validate RX
checksums; this increment does not change that transport compatibility policy.
Require response/event type and a matching message-ID/oneof-body tag after a full
decode, so a field-aligned truncated envelope cannot masquerade as a full RPC.

64 KiB is a finite aggregate budget, not support for every protobuf expansion.
It substantially exceeds the old shared 9488-byte arena without reducing any
previous protocol limit. Valid messages that exceed available pool space still
fail explicitly/atomically as they did under memory pressure; callers must retry
or handle failure. Unknown fields and wire order remain protobuf-compatible.
No silent message truncation or automatic radio retry is introduced.

Acceptance: actual Zephyr allocator plus pinned generated schema/decoder in a
native simulator; success, malformed/oversized data, partial allocation failure,
retained responses, overlap/reallocation, repeated decode/release and exhaustion
recovery; no leaks/cross-pool allocation. Both firmware builds, ELF/map placement,
full flash layout and affected HTTP/storage/editor/canonical regressions. Host
tests are not physical cache, timing, station or runtime-watermark evidence.

## Implementation and exact limits

`rpc_allocator.c` uses the real Zephyr `sys_heap` implementation, serialized by
`rpc_allocator_lock`. All allocator calls are thread-only. Initialization is
lazy under that mutex, after PSRAM initialization. Realloc failure preserves the
original pointer; free wipes the rounded usable block before recycling it. The
pool has no reset operation, no borrowing from libc or k_malloc, and no blocking
wait for capacity. Heap metadata reduces usable payload below 65536 bytes.

The actual pinned schema has exactly one `POINTER` field: the repeated
`ap_records` message array. Its RV32 element size is 128 bytes; other variable
fields are fixed-size or callback fields, with no callbacks installed by this
driver. The pool is shared by retained caller responses and any subsequent
decode. It does not reserve 64 KiB per message. A valid but extremely sparse
600-record reply fits the wire limit but exceeds this pool and is rejected whole.
Existing common replies and 64-record fixtures work. No claim is made that every
valid maximum-expansion protobuf message fits. This replaces the prior much
smaller shared allocator; it does not reduce frame size or silently cap counts.

The module-local forced include redirects only nanopb's allocator hooks in the
P4 hosted build. The new post-link check verifies the actual `allocate_field`
and `pb_release_single_field` calls target `p4_rpc_realloc`/`p4_rpc_free`, not a
shared allocator. It also requires the strong bounded decode hook, exact pool
size, external-memory placement and the existing 8192-byte libc floor.

`0006-esp-hosted-decode-ownership-hook.patch` adds a weak upstream-compatible
decode entry point; the application overrides it. It rejects zero/over-1576-byte
input, malformed protobuf, non-response/event envelopes and absent/mismatched
message-ID/body tags. Unknown protobuf fields remain supported. On error nanopb
releases partial allocations, the wrapper clears output, and no partial response
is handed to the caller. The existing driver then drops the message; a pending
RPC still uses its bounded timeout (normally 5 seconds), rather than receiving
an invented UID match or a false successful response. Precise resource errors
are not yet surfaced through the caller's RPC status API.

## Receive-parser bug found and fixed

The native AddressSanitizer test reproduced a heap-buffer-overflow in
`esp_hosted_mcu_process_frame` on a complete aggregate frame with missing alignment
padding. The old code dispatched the frame, rounded its stride beyond received
length, then underflowed an unsigned remaining-length check. This could inspect
bytes outside the validated receive span.

`0007-esp-hosted-partial-padding-bound.patch` checks the complete aligned stride
before dispatch and uses an addition-based bounds check. Incomplete padding is
carried with the frame for the next read; complete aligned and byte-tight frames
keep their existing semantics. No payload truncation or radio configuration
change is involved. The failing ASan log is retained locally as
`rpc-native-padding-before.log`; the reproducer passes after the fix.

## Verification

The offline `native_sim/native/64` application compiles the production allocator,
strong wrapper, generated schema and pinned nanopb with Zephyr mutexes,
semaphores and sys_heap. It also compiles the actual driver source, suppressing
only device registration. It never calls transport startup or touches a device.
AddressSanitizer and actual `CONFIG_SYS_HEAP_VALIDATE=y` checks are enabled.
No target timing is inferred from the simulator's virtual-time output.

Twelve test groups cover:

- Allocator realloc/shrink/free/oversize semantics and retained output contents.
- Two simultaneously live decoded responses, with semaphore-enforced overlap,
  400 decodes/releases and 200 actual RAM-store writes/readbacks.
- Failure at each of 32 successive allocation points, whole-message exhaustion,
  shared-pool exhaustion, automatic partial cleanup and recovery.
- 300 repeated decodes, 10000 malformed protobuf inputs and 2000 mutated frames.
- Overlong frame/TLV/decode bounds, partial frames, missing aggregate padding,
  matched/late responses, timeout-owner disarming and unknown-field compatibility.
- Zero remaining allocation and heap consistency after every test.

These exercise CPU memory ownership and parser behavior; they do not exercise
physical SDIO, cache-disabled execution or simultaneous HTTP over Wi-Fi. The
unchanged actual HTTP callback separately passes 99 checks and 400 concurrent
transfers in each placement mode under ASan/UBSan. Storage/dispatcher/VM-bridge
sanitizer regressions pass (49+10000, 23+10000, 12 scenarios), along with 47 Node
tests and 61 canonical repository regressions. Existing Windows CRLF/provenance
handling remains unchanged. Both native firmware profiles and full flash-layout
checks pass; the final station build also passes the new allocator link audit.

## Linked memory

| Measure | Before this increment | After |
|---|---:|---:|
| Station static internal SRAM |383728|383792|
| Station libc arena |9488|9424|
| Station linked external region including existing heap |17158128|17223696|
| USB static internal SRAM / libc arena |243856 /149360|unchanged|
| Station fixed internal stacks / system heap |140288 /32768|unchanged|
| External allocation heap |16777216|unchanged|

External addition is 65568 bytes: 65536-byte pool plus 28-byte state and alignment.
The mutex is 20 internal bytes; total static internal change including linker
layout/alignment is 64 bytes. This intentionally isolates allocation pressure
rather than enlarging or relocating general libc. Board configurations are
byte-identical and the USB binary is unchanged. Prior HTTP/storage buffers and
all DMA, client, file, revision and session limits remain intact.

Reproduction: `tests/p4_rpc_native` with `west build -b native_sim/native/64`,
passing `P4_RPC_GENERATED` as the existing pinned station-generated schema
directory; run its `zephyr/zephyr.exe` with a bounded timeout. Local exact wrapper
`build_rpc_native.sh` and logs are at task root. Evidence, source hashes, build
checks and before/after maps: `evidence/2026-10-25/p4-rpc-memory-local.json`.

**Remaining boundary:** no hardware was accessed or flashed. Native P4 cache,
PSRAM concurrency, stack watermarks, allocator latency and real companion
interoperability are unverified. The separate station request-284 problem is
unchanged. Pool exhaustion is contained, not made impossible; oversized valid
replies or retained responses can still cause bounded failures/timeouts. No
commit, push, publication, deployment, credential or network change occurred.

Follow-up: [authorized physical RAM acceptance](STORAGE_PHYSICAL.md) installed
the unchanged USB artifact and exercised RAM files alongside PPA/NN/Whistle.
That USB-only profile does not access C6 and does not contain the station decode
pool. The station runtime/cache/allocator/interoperability boundary above remains
open; the physical result must not be used as proof of that separate pool.
