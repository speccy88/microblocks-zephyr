# Hosted asset memory audit (local only)

## Plan and acceptance criteria before implementation

The station image has 1760 bytes in its automatic libc malloc arena. Preserve
all stack sizes, heap reservations, client counts, 2048-byte HTTP response chunks,
storage bounds/revisions/sessions and internal DMA/ISR buffers. Move only the
8240-byte CPU-owned asset transfer array to external BSS when PSRAM is enabled.
Use a single 512-byte internal flash scratch buffer under the existing transfer
mutex, copying to each client buffer only after flash_area_read returns. This
avoids adding the HAL's dynamic bounce-buffer demand to the system heap. Other
targets retain ordinary BSS placement. No hardware or publication actions.

The pinned HTTP/1 implementation calls the handler, consumes its response through
sendall_iov, then invokes the next callback/completion. Native sockets copy user
bytes into TCP-owned net_buf storage before returning; the C6/DMA path does not
retain the response pointer. The array must stay alive until that client's next
callback or terminal notification. A mutex protects slot lookup, updates and
scratch use; each active client retains a distinct response buffer. The HTTP
server serializes callbacks for one client. This is not a general concurrent
same-client API; no buffer may be reused while the socket is consuming it.

Flash scratch stays internal and is never exposed as a response. Main-flash HAL
disables cache during its internal read and restores it before returning. PSRAM
is touched only afterward, in thread context. No new direct DMA/ISR access or
cache flush is appropriate for this CPU copy path. Asset verification's existing
internal stack buffer remains unchanged. Keep HTTP/2 and socket offload disabled
for this verified ownership contract; re-audit before enabling another stack.

Add a final-link guard requiring the automatic libc arena to remain at least
8192 bytes in the hosted profile. This is a regression floor, NOT a proof of
worst-case allocation adequacy. The separate 32 KiB Zephyr heap is not part of
this arena. Explain actual allocation consumers and remaining unknowns below.

Acceptance: actual handler compiled with host stubs under ASan/UBSan; zero,
partial, exact and multi-chunk assets; four overlapping clients and fifth-client
exhaustion; completion/abort/read-error reuse; retained response bytes; malformed
asset bounds; concurrent different clients. Check guard rejection as well as
passing link, both real firmware profiles/maps and full affected regressions.
Do not claim cache/DMA/timing/stack/runtime evidence from host tests.

## Source trace and allocation budget

Reviewed the actual local sources used by the build (hashes in evidence), based
on Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf` and Espressif HAL
`b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`, including the existing local patches:

- `subsys/net/lib/http/http_server_http1.c:569-610`: GET callback -> synchronous
  dynamic response -> next callback -> COMPLETE. Error cleanup delivers ABORTED.
  Different clients retain their own slots; the mutex is not held across socket
  sending. Same-client concurrent/reentrant callbacks are outside this API.
- `http_server_core.c:1889-1940`: sendmsg loops over partially consumed iovecs;
  unsupported sendmsg falls back to sendall. It finishes copying before return.
- `subsys/net/lib/sockets/sockets_inet.c:718-763`, `subsys/net/ip/net_context.c`
  and `tcp.c:1919-1959,4117-4205`: native TCP appends into net_buf-owned storage.
  DMA sees the network/transport buffers, not the original asset buffer. HTTP/2
  and socket offload remain disabled and now cause configure failure if enabled.
- `drivers/flash/flash_esp32.c:139-158,370-436`: synchronous flash read under the
  flash semaphore; main flash calls esp_flash_read (or mapped encrypted read).
  HAL `esp_flash_api.c:934-1007` brackets the internal read with cache guards,
  copying any bounce data after `end`. `spi_flash_hal.c:163-168` disallows direct
  main-flash external destinations. The new explicit internal scratch avoids
  HAL `get_buffer_malloc`/k_malloc altogether for asset streaming.
- `soc/espressif/esp32p4/default.ld:1050-1064` collects external BSS;
  `soc/espressif/common/esp_psram.c:133-134` zeroes it after PSRAM initialization.
  Network worker verifies assets before starting HTTP. No ISR accesses slots.

HTTP staging is now fixed: 8240 bytes PSRAM (four RV32 slots), 512 bytes internal
scratch, unchanged mutex. Each full response chunk uses four bounded 512-byte
flash reads/copies. No new stack or malloc use; added flash-call overhead and
actual slow-client latency remain unmeasured. The existing asset-verification
4096-byte stack buffer stays internal and uses the unchanged station stack.

The station ELF's actual allocation calls distinguish two heaps:

- libc malloc/realloc: nanopb `allocate_field`; yyjson default allocator functions
  are linked, but the JSON service explicitly supplies its bounded arena.
  RV32 debug information gives `sizeof(wifi_ap_record)=128`, `sizeof(Rpc)=208`;
  the latter is stack/local state, not a compulsory heap allocation. Common
  association scalar responses and fixed SSID/MAC fields do not allocate a scan
  array. Decoded pointer fields and retained response/event overlap still matter.
- Zephyr system heap: flash HAL bounce fallback, PPA client/control objects and
  interrupt allocation. WebSocket masked-send allocation is linked, but this
  board server sends unmasked frames. Native TCP payload pools are fixed static
  reservations. None of these count as capacity in the libc arena.
- Media/inference use the separate, unchanged 16 MiB external heap. Speech can
  reserve 12 MiB; simultaneous camera/NN/preview demand and fragmentation remain
  unmeasured. Moving static bytes does not enlarge that heap.

Six synthetic tests compile the **actual generated scan-response schema and
pinned nanopb decoder** with an always-moving bounded realloc. Host records are
136 bytes; accounting explicitly uses the ELF-verified RV32 128-byte payload,
excluding allocator metadata. This is not a Zephyr allocator simulation:

| Synthetic records | Wire bytes | Payload budget | Outcome / peak payload |
|---|---:|---:|---|
|16|32|1760|exhaustion, cleanup /1664|
|16|32|8192|success /3968|
|32|64|8192|success /8064|
|64|128|9488|exhaustion, cleanup /9344|
|128|256|9488|exhaustion, cleanup /9344|
|16 after exhaustion|32|9488|success /3968|

Empty AP submessages deliberately expose wire-to-decoded expansion; no real
network names or scans are used. The driver currently requests all reported AP
records, rather than bounding that request to 16. A 1600-byte transport bound
therefore does **not** prove decoded data fits. Failed decode cleanup passed,
but runtime response ownership/allocator fragmentation still require measurement.

The 8192-byte floor is an engineering regression threshold: the concrete
16-record case needs 2048 bytes steady and up to 3968 payload bytes while moving
realloc; the floor leaves about another 4 KiB for allocator overhead/other work.
It is deliberately **not** a guarantee for 32 records, malformed maximum
expansion, concurrent responses or arbitrary future libc users. The old 1760
bytes cannot even hold 16 records steady. A future bounded decode policy or
allocator-specific measured budget is still needed before declaring station
memory adequate. No network driver behavior was changed in this increment.

## Result and verification

| Measure | Before | After |
|---|---:|---:|
| Station static internal SRAM |391456|383728|
| Station automatic libc arena |1760|9488|
| USB static internal SRAM |243856|243856|
| USB automatic libc arena |149360|149360|
| Station linked external region, including heap |17149888|17158128|
| Station fixed internal stacks |140288|140288|
| USB fixed internal stacks |104960|104960|
| Station / USB requested system heap |32768 /16384|unchanged|
| External heap reservation |16777216|unchanged|

Net saving: **7728 internal bytes**, 8240 added external bytes; 512 bytes retained
as the internal scratch. Generated configurations are byte-identical before and
after. USB binary is byte-identical. Four clients and 2048-byte HTTP body chunks
remain unchanged, as do storage limits, sessions/revisions, DMA buffers and
stack/heap reservations. Complete app/model/assets/settings layout passes.

- Handler ASan/UBSan: 99 checks and 400 four-client concurrent transfers in each
  of ordinary-BSS and PSRAM-section builds. Covers boundaries, busy, abort,
  completion, invalid arguments, read failure, reuse and retained body bytes.
  Flash/OS/network are synthetic; real production handler code is compiled.
- Exact production linker ASSERT: rejects 0/1760/8191, accepts 8192/9488/149360.
- Six actual-decoder synthetic allocation cases pass ASan/UBSan with no leaks.
- Storage 49 checks +10000 malformed inputs, dispatcher 23 scenarios +10000
  malformed packets, 12 actual VM-bridge scenarios pass ASan/UBSan.
- All 47 affected Node tests and 61 canonical repository regressions pass.
  Existing Windows FruitJam CRLF/provenance handling is unchanged.

Reproduce locally with `tools/test_hosted_assets.py`,
`tools/test_p4_rpc_memory.py --workspace <west-workspace>` (Zephyr Python with
pyelftools), and `tools/audit_p4_memory.py --workspace <west-workspace> --output
<report.json>`. Exact build commands/log hashes and reports are in
`evidence/2026-10-25/p4-hosted-memory-local.json`.

**Runtime risk remains open.** No hardware/cache-coherency stress test, HTTP
throughput measurement, concurrent allocator largest-free-block measurement,
speech/network stack watermark or live station/editor validation was performed.
Hardware, flash, commit, push, publication and deployment remain held. Feature
expansion stays paused; no credential, AP, C6, COM12, microphone or Windows
network/audio setting was touched.
