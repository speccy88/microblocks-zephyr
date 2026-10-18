# Fruit Jam native IDE acceptance

The real MicroBlocks GP 2.5.8 editor loads directly from Fruit Jam at
`http://192.168.1.7/microblocks.html` for the current association. Use the complete
HTML path for the upstream Copy project URL command. Its real GP ready event,
Connect/Start/Stop controls and Fruit Jam category were verified through the
browser DOM, with the local USB bridge stopped. Native graphical editing,
execution, reconnect and saved-program readback after
an RP-only reset now pass as well. No human visual/audio/device-presence
confirmation was requested.

Installed source: `37f1fc22c50b0c639622f0e77d9a4e000da80b1a`.
ELF SHA256: `58770eadbdbb27472e32fb0e02e46cd756908e56fa0886866a50d63618b08df5`.
The native build uses 3,627,708 bytes of its 4 MiB app partition and 253,808
bytes of internal RAM. PSRAM is not mapped. All 147 editor files retain source
verification and licenses; their flash representation uses 3,511,861 bytes.
No ELF load segment overlaps VM snapshots. SWD programming/verification and
private pre-update backups passed; original chunk 0 retains CRC `297d191b`.

## Implementation and reliability corrections

Complete SPI command/reply operations and diagnostic cleanup share a mutex.
The restored stock NINA 3.3.0 has six socket slots: one listener, up to four
HTTP streams and one VM controller. Fixed request/frame/queue bounds, partial
send handling, deadlines, Host/Origin/key/version checks and USB DTR priority
remain in force. Network clients cannot submit Wi-Fi credentials.

Radio modem sleep is disabled when the listener starts. Socket-write response
preparation permits ten seconds, matching the pinned reference's ready budget;
select acknowledgement and ordinary query limits remain bounded separately.
The first socket error/command/phase is latched. On a socket error, at most two
read-only version probes restore framing; failed writes and credential commands
are never replayed. A read-only version probe can consume an exact stale error
reply and submit that identification query once more. This recovered the prior
fault while keeping association, without a C6 reset or vault read.

Native packaging sequences startup CSS/images and scripts to avoid the
browser's eager connection burst. It preserves blocking/inline order followed
by deferred order, loads the actual GP runtime last, checks resource origins
and reports load failures with a reload message. The USB bridge's verified
packaging stays unchanged. The queue harness executes the actual JavaScript
with asynchronous mock resource events; actual browser startup is separately
verified by the real GP event.

## Measured acceptance

| Check | Result and evidence |
|---|---|
| Native build, ARM Secure ELF/UF2 and app bounds | PASS; `network-build-verification.json` |
| C HTTP/WebSocket/SPI protocol harness | PASS, 2,308 checks; `network-parser-harness.json` |
| Real VM harness | PASS, arithmetic, 50 ordered outputs, fragmentation and control isolation; `network-vm-harness.json` |
| Native bootstrap queue harness | PASS, sequential scheduling/order, failure stop and origin guard; `native-bootstrap-queue-harness.json` |
| Live AirLift association | PASS, NINA 3.3.0, MAC `58:e6:c5:f5:a3:58`, IP `192.168.1.7`; `physical-native-bootstrap-identification.json` |
| Full physical VM network sequence | PASS on source `6109239`: 10 arithmetic runs, edit 13, 50 ordered outputs, fragmentation, stop/variable, reconnect, second-controller rejection, USB takeover and setup-path rejection; `physical-network-vm-attempt-03.json` |
| Largest real IDE asset | PASS on `aa63f96`, 2,180,174 wire bytes / 10,895,070 decoded bytes with both SHA256 values exact, 45.875 seconds; `physical-network-largest-asset-attempt-03.json` |
| Complete HTTP asset integrity | PASS, all 147 files / 17,278,833 decoded bytes on `aa63f96`; `physical-network-assets-attempt-02.json` |
| Initial queued bootstrap on source 798bf16 | Only HTML changed; its physical hash passes and other 146 raw/flash hashes and metadata are identical; `physical-native-bootstrap-html.json`, `native-bootstrap-asset-comparison.json` |
| Real browser GP startup from board flash | PASS, DOM readiness and full editor controls, host bridge stopped; `browser-bootstrap-attempt-02.json` |
| Focused 798bf16 regression after browser startup | PASS, WebSocket arithmetic/reconnect, USB takeover/return, original CRC and USB arithmetic 12; `physical-native-bootstrap-smoke.json` |
| Current packaged assets on source 37f1fc2 | New HTML physically hash-verified, other 146 assets identical; `retained-boot-asset-comparison.json` |
| Current retained-association boot and timeout classification | PASS; physical-retained-boot-and-http-timeouts.json |
| Real graphical edit, reconnect, board persistence and file export/import | PASS with alternate export; direct IAB download unconfirmed; physical-graphical-save-readback.json |
| Original complete VM-store restoration and automatic HTTP resume | PASS; physical-graphical-cleanup-and-boot.json |
| Current-image final transport regression after cleanup | PASS, arithmetic, reconnect, USB takeover/return and original CRC; physical-retained-boot-final-smoke.json |
| Offline repository validation | PASS, 17 tests |

Earlier numbered HTTP/asset/VM failures remain as historical evidence. The
current source adds a delayed read-only identity/status/IP probe at RP2350
boot, with one retry after a failed probe. A queued explicit user operation
supersedes it. It never resets the C6, submits a join, requests an SSID/key or
reads the Windows vault. Two RP-only resets resumed HTTP automatically with
probe generation 1, operation 0 and reset_requested false.

Controlled empty-TCP and partial-header connections expired at 5.016 and
5.031 seconds respectively, with separate bounded counters and byte counts.
The subsequent real browser load added one empty-TCP expiration, zero send
and zero WebSocket timeouts. The historical startup timeout had no captured
request and cannot be retrospectively classified. The current socket protocol
and latched first-error counters remain zero; one exact stale-error reply was
consumed by the existing read-only framing recovery at boot.

The real editor ran 5 + 7 = 12, changed 7 to 8 and returned 13, then returned
13 again after graphical reconnect. The edited CRC 806c9e21 survived the
verified application update and RP-only reset. A fresh native browser session
used Project > Open from board before Connect, recovered return (5 + 8), and
returned 13. This path avoids uploading a blank workspace to the board.

Project Save exposes a visible link to the actual GP-serialized .ubp in page
memory. IAB did not confirm delivery through either the upstream synthetic
Save or the visible blob link. This is an unresolved embedded-browser download
limitation, with no security denial observed. The official Copy project URL
command works at /microblocks.html; its DOM copy field supplied the serialized
project when IAB's clipboard service returned empty. Removing its URL-only
projectName header and normalizing trailing whitespace produced
[graphical-readback-5-plus-8.ubp](../evidence/2026-10-18/fruit-jam/graphical-readback-5-plus-8.ubp).
That actual file was reopened through the editor's Computer picker and ran 13
on the Fruit Jam. Direct IAB download delivery remains unconfirmed.

The full original 256 KiB program store, including metadata, is restored from
the private pre-test snapshot and verified by physical SHA256 readback. Original
CRC 297d191b and USB arithmetic 12 are restored. The exported test and post-test
store backup remain available separately. See physical-graphical-save-readback,
physical-graphical-cleanup-and-boot and physical-retained-boot-and-http-timeouts
JSON evidence under the folder below.

## Remaining boundaries and user decision

Retained C6 association now resumes automatically after an RP2350-only reset.
A full C6 reset or power loss still requires secure local setup; that case was
not triggered while the user was away. No RP2350 credential persistence,
automatic join or vault replay was added. The delivered Windows GUI retains
its physical local Connect handoff and immutable attempt receipts.

The remaining user decision is whether to keep that manual secure Connect
step after full power loss, or explicitly approve a separate design for
persistent credentials and automatic association. No credential action or
approval is currently pending. Direct embedded-browser file download behavior
also remains a documented limitation, despite the verified export/import
round trip above.

DVI, host USB, audio, SD, PSRAM and other peripheral limits remain in the board
manifest. Other boards/ports, cancelled SHT4x work and audible/light patterns
were not accessed during these reliability fixes. Builds used four jobs and
resource guards; no build, flash or debug operation remains active.

All referenced evidence is under `evidence/2026-10-18/fruit-jam/`. Pinned NINA
socket and Adafruit SPI references are under `dependencies/`; exact build
commands and source/artifact hashes accompany the build report.
