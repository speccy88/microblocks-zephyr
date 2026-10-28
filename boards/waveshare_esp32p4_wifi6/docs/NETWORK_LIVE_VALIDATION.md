# Native station validation follow-up, 2026-10-27

## Latest checkpoint

The earlier failures below are retained as historical diagnostic evidence. The
HTTP poll-budget repair subsequently passed real graphical editor loading and
RAM create/edit/save/refresh/reopen over the board-hosted page. Byte-exact browser
download remains unverified because its permission/tool path stalled; it was
not retried through an alternate route.

The currently installed application is
`0a7045637b8e7bade0bd0f389711dffac31586df8e0e9ca7e9ef2dd6ca3b202d`.
It adds the native read-only SD worker to that repaired station profile. FAT32
card detection, raw capacity, bounded root-entry counting, cancellation/reuse
and concurrent hash-verified HTTP transfer passed on the physical P4. No SD
files were written or their contents read. The C6, settings and editor assets
remain unchanged. See [SD evidence](../../../evidence/2026-10-27/p4-sd-readonly-summary.json)
and [the implementation limits](../../../docs/SD_STORAGE_NATIVE.md).

The installed profile still gates saved-network association behind the
synthetic compatibility diagnostic; production reboot reconnection is not
validated. The SD library is packaged locally but not installed in the board's
existing editor assets. Full SD file-manager and write support are unavailable.

## Earlier station/HTTP diagnostic record

This local follow-up supersedes the earlier request-284 blocker. It is not a
claim that the complete graphical editor has passed on the board, nor a new
published release. Both the USB and station profiles remain separate builds.

## Physically observed

The factory C6 firmware was left unchanged. Supplying the missing default
threshold/PMF submessages produced response 540/status 0. Subsequent host-side
fixes increased the undersized system workqueue stack and separated Wi-Fi L2
and IPv4 L3 event callbacks. The real board associated with its approved saved
network, obtained DHCP and served its editor assets from P4 flash. The last
status read reported ready, error 0, connected, assets valid, AP disabled and
no programming controller. No Windows network/security changes were made.

Installed application SHA256:
`010d58b91f0dbb15365e5f2f40285663f8a5893ff4c51a298c955112a0aaf594`.
Its editor partition SHA256 is
`5db3dcb74201cb2617f47887da886c4810fe3edbb7421c2cbd63ba172cc28643`.
These are artifact identities, not a claim that current local source has
already been flashed or published.

- The actual Wi-Fi WebSocket ran SmallVM v417 uploads and a generated-image
  create/resize/grayscale pipeline. No new camera or microphone capture.
- The complete RAM acceptance passed 918 actual requests over Wi-Fi: Unicode
  and binary data, revisions/conflicts, replay/malformed recovery, cancellation,
  Stop All, full 64 KiB beside an independent 8.29 MB image allocation, 16
  full-size replacement cycles and WebSocket reconnect. Maximum observed RTT
  was 313 ms. Cleanup left zero RAM file bytes, eight slots and capture inactive.
- All 33 root runtime assets returned HTTP 200 and matched the packaged hashes
  when requested individually, including the complete 11,199,017-byte unpacked
  `gp_wasm.data`. Device Files assets are present and served.

## Still failing or unverified

Concurrent HTTP requests sometimes close without responses. A two-request
small-file run failed, a four-request run passed and a six-request run failed.
This does **not** establish a four-client-limit explanation. No client limits,
timeouts or security policies have been weakened. Asset-handler host tests do
not exercise the complete real TCP server and cannot override this failure.

The real graphical editor was observed stalled during loading. Its browser
inspection transport later closed; the uncertain reload was not repeated.
Complete GP rendering and Device Files edit/download through the board-hosted
page remain unverified. The existing interrupted download is not retried here.

The installed image is a gated diagnostic: one synthetic RAM-only C6 test at
boot, then one explicit approved saved-network attempt. Production automatic
reconnection after reboot has not been validated. Do not delete the encrypted
credential handoff or advertise standalone restart readiness yet.

## Local diagnostic prepared, not installed

`compat-diagnostic.conf` now optionally links an eight-record numeric HTTP
observation ring. Stage numbers are: 1 socket-send errno; 2 capacity deferral;
3 inactivity expiry; 4 no asset transfer slot; 5 flash read error; 6 asset
bounds error. Stage 7 is reserved. Only stage/result/uptime and saturating
counts are recorded; URLs, bodies, headers and credentials never enter it.
Diagnostic-only USB/network status operation 5 reads the snapshot. It does
not retry association, modify the filesystem or change credentials.

The instrumented station build reserves 383,824 internal bytes, leaving a
9,392-byte libc arena, 128 fewer bytes than the installed image. The existing
8,192-byte linker floor passes; this does not prove runtime headroom under all
loads. The 32 KiB system heap is unchanged. Shared DMA TX stays internal;
CPU-owned staging and HTTP buffers keep their audited PSRAM placement.

Host acceptance passed 4,000 concurrent numeric observations, saturation,
extreme output values and tiny buffers under ASan/UBSan. The actual asset
handler passed 99/102 checks and 400 concurrent transfers in each of four
internal/PSRAM and diagnostic-off/on combinations. Both native profiles build;
the application/model/editor/settings non-overlap checks pass.

Reproduce local C tests in the Linux/WSL development workspace with
`python tools/test_p4_http_diagnostics.py` and
`python tools/test_hosted_assets.py`. They do not connect to hardware.

The next hardware-dependent action is to install the separately staged,
guarded instrumented P4 application and compare numeric counters around one
bounded concurrent-fetch reproduction. Preserve the existing application
artifact; do not update C6, editor assets, credentials or settings for this test.
No new firmware write has been performed for this diagnostic.

## Newly inserted SD card

Fred reports a FAT32 card installed. The current MicroBlocks station image
disables slot 0 and has no disk/filesystem stack, so its capacity/content
cannot be queried through that firmware. No access, mount, format or file
write has been performed on the card in this follow-up.

An isolated [read-only SD diagnostic](../diagnostics/sd_readonly/README.md)
has local host-test and native-build acceptance. It is **not** the MicroBlocks
image and is not installed. It disables C6 and compiles out FatFs writes and
formatting, also enforcing no-format/read-only mount flags. SD/Wi-Fi coexistence,
actual card detection/capacity and MicroBlocks SD integration remain untested.
Do not replace the functioning station image with that separate diagnostic
without a deliberate installation/restoration plan.
