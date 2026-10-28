# P4 large HTTP transfers

## Bounded investigation plan (before implementation)

Preserve native application 5e692377 and editor 3b29bdfa, automatic saved Wi-Fi,
the confirmed volatile power-save-off policy, SD contents and browser drafts.
No C6 flash, router/security/credential change, file mutation or timeout increase.
The copied local compiled baseline is the rollback; no board dump is needed.

Initial raw HTTP/1.1 reads, with a strict 5-second receive bound and 90-second
total bound, verify gzip decoding and the manifest SHA-256. The baseline sends
2,195,829 bytes in 21.907 seconds (98.447 KiB/s after headers); decoded bytes
are 11,235,169. JS/Wasm are 115.312/125.578 KiB/s. Chunk arrival medians are
15..16 ms. Decoding takes 46 ms and cannot explain the body transfer time.

Trace the pinned HTTP/1 synchronous callback -> gathered native sendmsg ->
TCP-owned copies before changing any ownership. Add optional numeric timing
observations around actual flash reads, deliberate yield and gaps between
callbacks, exposed read-only. First measure this unchanged behavior on P4.
Choose the smallest fix supported by those observations. Preserve four-client
ownership, internal flash scratch and native network DMA buffers; no arbitrary
network-pool, stack, heap or TCP-window increases.

Acceptance: actual-handler host sanitizer regressions, root validate, exact
native build and memory/layout/model audits, guarded revision 1.3 image, full
baseline/final device digest checks, identical asset hashes, before/after
throughput with strict bounds, concurrent VM liveness and read-only SD listing.
Report unmeasured energy, power-cycle, AP and long-duration behavior explicitly.
Keep changes isolated for Pi/main coordination; do not apply to old folders.

## Diagnosis and chosen experiment

The unchanged-handler diagnostic image 8f9cab45 passed full device digests.
Its actual large transfer took 23.623 s: flash reads 338,346 us (4,289 reads),
deliberate yield 1,415,258 us, and callback gaps 21,745,438 us. Flash is about
1.4% and the gap before the next callback about 92.5% of handler wall time.
The gap includes synchronous native socket sending; it is not a radio trace.
No bus or malformed-header errors were observed in the diagnostic snapshots.

The pinned MCU transport drains queued RX frames, then waits for DAT1 with a
20 ms fallback. Its Kconfig explicitly documents that this SDIO coprocessor
reports pending data in a register without driving DAT1, making that fallback
the ordinary receive cadence. TCP's 4096-byte send window then waits for ACKs.
Source trace: drivers/misc/esp_hosted_mcu/{esp_hosted_mcu.c:541-590,
esp_hosted_mcu_sdio.c:405-439,Kconfig:119-135}; TCP/socket trace in the build
workspace is unchanged. Exact local-source hashes belong in the evidence.

Chosen bounded change: only the already explicit wifi-low-latency.conf sets
CONFIG_ESP_HOSTED_MCU_EVENT_TASK_POLL_MS=5. Other profiles retain the default
20 ms. Keep 2048-byte body chunks, 512-byte internal scratch, all client/pool/
heap/stack/window sizes, timeouts and C6 firmware unchanged. Compare actual
throughput, callback gaps and idle polling after a digest-checked installation.
At idle this requests about four times as many status checks/wakeups, roughly
200/s rather than 50/s; actual cadence and energy must be distinguished. No
battery-life or current-consumption improvement is claimed.

The pinned HTTP/1 dynamic GET loop sends one full response synchronously.
Other HTTP work/new handshakes may wait behind it; yielding the CPU does not
make that loop schedule other HTTP clients. Existing WebSocket traffic has a
separate worker and must be checked during the bulk transfer. Rewriting HTTP
scheduling and claiming simultaneous four-client radio throughput are outside
this bounded polling experiment.

## Verified result

PASS_WITH_LIMITS on the native P4 rev1.3. The same instrumented handler and
unchanged editor sent 2,195,829 compressed bytes (11,235,169
decoded, SHA-256 verified) in 23.623s before and
10.236s after (2.31x for this controlled pair).
Body throughput was 91.3 -> 211.4 KiB/s.
Earlier uninstrumented baseline samples were 20.740..21.907s. These are bounded
single-board/AP samples; no universal throughput or statistical confidence claim.
Residual receive pauses reached about0.6s and the first TCP connection0.52s;
their lower-level cause remains untraced. Steady small-packet liveness passed.

Handler callback gaps fell from 21.745s to
8.393s. Flash time was
0.338s -> 0.339s;
the flash-read path and intentional 1ms yield were unchanged. Idle status checks
were about 54.1/s -> 174.5/s in two-second
observations. This measures cadence, not energy. C6 receiver wakefulness from
the prior policy and extra P4 polling may consume more power; battery life and
current have not been measured. Default profiles keep 20ms polling.

Concurrent existing WebSocket/VM pings passed the unchanged 3s bound
(36 replies, maximum
238.3ms) during a hash-verified bulk GET.
Native SD listing and a bulk GET also passed together; no SD file was written.
The retained real board-hosted editor reconnected and its fresh SD session/list
passed. Browser drafts were preserved. No cold-browser load or download claim.

Installed application `fe01c3fb2ac57262cbbd87cbd7d07d073cd72092fab37f6e7354fa14e8f5d60d` (15,378,064 bytes at0x2000), editor
`3b29bdfa5f086a51b2e769af244c347328379499db02449f79007e744a9a9e5a` (3,570,589 bytes at0xfe0000). Full baseline and final device
digests passed, then reset at 2026-10-27T17:59:32.920566+00:00; COM5 closed. Guarded compiled
5e692377 and 8f9cab45 rollback images remain local. No raw board dump, C6 flash,
settings/credential/router/security change or denied action repetition occurred.

All90 root checks pass. Actual-handler ASan/UBSan variants pass99/99/102/102/
109/109 checks and400 concurrent synthetic transfers each; actual policy28 and
transport12 checks pass sanitizers. Native VM/RPC/layout/model/DMA audits pass.
Compared with the diagnostic baseline, configuration differs only in the poll
value and the libc arena remains 10336 bytes. The
diagnostic recorder adds64 internal bytes versus the original5e image; default
non-diagnostic builds omit it. This arena floor does not prove worst-case RPC
allocation adequacy. Body chunks2048, internal scratch512 and all stack/heap/
network-pool/window/client reservations remain unchanged.

Reproduce the read-only benchmark with tools/benchmark_p4_http.py --host <P4-IP>
--manifest <matching-assets-manifest.json> --output <new-result.json>. It enforces
5s receives,90s total, bounded headers/chunks/decompression and manifest hashes.
Optional P4ST12 is a USB-only, read-only numeric last-transfer snapshot; it
records no content/path/peer and changes no network state.

Full power removal, multiple APs, long-duration/energy behavior and writes on
this final pair remain unverified. Existing earlier exclusive-file SD-write
evidence remains historical. Pi/main are untouched; use the isolated source
patch after checking current refs and prior unpublished SD/C6, saved-boot,
loss-retry, editor-timing and PS-policy prerequisites. See sanitized
evidence/2026-10-27/p4-http-throughput-summary.json for exact bounds.
