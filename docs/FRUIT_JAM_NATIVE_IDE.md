# Fruit Jam native IDE acceptance

The real MicroBlocks GP 2.5.8 editor loads directly from Fruit Jam at
`http://192.168.1.7/` for the current association. Its real GP ready event,
Connect/Start/Stop controls and Fruit Jam category were verified through the
browser DOM, with the local USB bridge stopped. This was a software startup
check; no human visual/audio/device-presence confirmation was requested.

Installed source: `798bf16bdfea6eb434dbd8283cd1f55ba5cb6114`.
ELF SHA256: `fb2cd2fb6dcdc4a085072de1e0273db4997339ef3686977e4ebc19ac8ab0b411`.
The native build uses 3,626,928 bytes of its 4 MiB app partition and 253,784
bytes of internal RAM. PSRAM is not mapped. All 147 editor files retain source
verification and licenses; their flash representation uses 3,511,487 bytes.
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
| Current bootstrap-only update | Only HTML changed; its physical hash passes and other 146 raw/flash hashes and metadata are identical; `physical-native-bootstrap-html.json`, `native-bootstrap-asset-comparison.json` |
| Real browser GP startup from board flash | PASS, DOM readiness and full editor controls, host bridge stopped; `browser-bootstrap-attempt-02.json` |
| Focused current-image regression after browser startup | PASS, WebSocket arithmetic/reconnect, USB takeover/return, original CRC and USB arithmetic 12; `physical-native-bootstrap-smoke.json` |
| Offline repository validation | PASS, 17 tests |

Earlier HTTP/asset/VM failures remain in their numbered evidence files. The
current image's post-browser SPI protocol/first-error counters are zero. One
HTTP client timeout was recorded during browser startup; its request was not
captured. The editor nevertheless reached its actual ready event and the
post-startup VM/USB regression passed. This is recorded separately from the
resolved sustained-transfer SPI faults. Browser programming gestures were not
repeated; the earlier USB graphical baseline and full binary network sequence
remain separate measured results.

## Remaining boundaries

These results cover the current powered association. No RP2350 credential
storage or automatic boot-time NINA setup is implemented. An RP-only restart
requires explicit live identification/setup initialization; full C6 power loss
requires the secure local setup flow. C6-only reset/service recovery has not
been physically accepted on this image. The delivered Windows GUI keeps the
user's local Connect handoff and immutable attempt receipts; no background
vault replay is scheduled. No user action or approval is currently pending.

DVI, host USB, audio, SD, PSRAM and other peripheral limits remain in the board
manifest. Other boards/ports, cancelled SHT4x work and audible/light patterns
were not accessed during these reliability fixes. Builds used four jobs and
resource guards; no build, flash or debug operation remains active.

All referenced evidence is under `evidence/2026-10-18/fruit-jam/`. Pinned NINA
socket and Adafruit SPI references are under `dependencies/`; exact build
commands and source/artifact hashes accompany the build report.
