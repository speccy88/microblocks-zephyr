# Request-284 compatibility experiment

Independent hypothesis tested: SDIO signal/timing margin. Official
`docs/getting-started-mcu.md` recommends initial bring-up near 5 MHz before
raising the clock. The optional `profiles/station-sdio-slow.overlay` changes
only the host maximum clock from 20 MHz to 5 MHz. Build from the restored
reviewed patch series; preserve station credentials, AP disabled and the prior
image. Test once, record actual initialization/control/address results, then
stop if the same failure persists. Result on 2026-10-26: native build/model/
whole-flash layout passed; 12 KiB of changed application sectors were written
only after the installed baseline digest matched. The complete new digest
matched. VM remains responsive, but request 284 still has no response 540,
the last received RPC is station-start event 773 and SDHC reports -116.
Driver ready, assets valid, credentials saved, no station address, AP false.
This is not a fix. No further identical trial is scheduled. The configured
maximum is 5 MHz; the physical clock was not measured with an instrument.

The installed diagnostic image SHA-256 is
ce1ddca9b027538a0da761e2d3d5a1c8e3a9409126eee346d6b3e518a074643d.
See `p4-station-slow-flash.json` and `p4-station-slow-status.json` under
`evidence/2026-10-25/`. Counter values after bus errors are not evidence of
actual zero device credits: failed reads can leave zero placeholders.

Status: native build and full flash layout passed, and COM5 flash hash was
verified. The resulting image did not answer the VM version query, including
a bounded passive wait. The ROM digest warning also occurs in earlier boots
and is not a demonstrated cause. No valid request-284 result was obtained.
The experiment is quarantined under `zephyr/experiments/`; it is excluded from
the normal patch series, which has been restored in the SDK. The previous
validated application was restored and its flash hash verified. The VM answers
again, sees saved station credentials and valid assets, and reports request 284
with no response followed by SDHC -116. Camera/audio are idle. Assets and NVS
were not changed. The complete reviewed five-patch SDK series is restored.

An official support question was attempted once through the GitHub connector.
GitHub returned HTTP 403, `Resource not accessible by integration`; no issue
was created. See ESP_HOSTED_SUPPORT_DRAFT.md for the exact sanitized draft.
No new access grant or C6 firmware replacement has been requested or applied.

Baseline 9d34a516: WifiInit, legacy MAC queries, SetMode(STA), WifiStart
and the station-start event succeed. The following WifiSetConfig (284)
has no response, followed by SDHC -116. There is no DHCP address. Saved
credentials were independently verified by NVS write/readback; do not request
them again. The C6 firmware version remains unknown. No C6 flash is authorized.

Primary comparison: Espressif release/v2.x host RPC serializer,
`host/drivers/rpc/core/rpc_req.c`, blob
7f7e4e73e1537c93ee1bc2653054d88dcbbbb660. It always allocates the station
threshold and PMF messages and copies the fixed SAE-H2E identifier array.
The pinned Zephyr serializer omits threshold, PMF on WPA2, and the empty
identifier field. Request IDs and nested field tags match the official v2
schema. Current official companion handlers guard absent submessages; this
does not establish the behavior of the unidentified installed firmware.

Test hypothesis: complete the station configuration wire representation to
match the official host. Include threshold/PMF submessages, retain WPA2-PSK
as the minimum authentication type, use the conventional -127 RSSI threshold,
and send the bounded zero-filled SAE identifier. PMF is not required; no new
AP, destination, credentials, radio band or Windows setting is introduced.
Only the opt-in station profile changes. One new physical attempt is justified
by this source difference; do not repeat identical failures.

Before flashing: exact pinned patch-series check, native build and full
application/model/assets/NVS layout validation. Preserve the previous verified
image as a local build artifact, not a firmware readback. After boot, use the
already-saved credentials; do not decrypt/reprovision or erase NVS. Read only
status and sanitized request/counter metadata. Never record payloads, SSID,
password or their checksum. If association works, verify DHCP, actual HTTP
assets, same-origin GP/WebSocket and USB ownership. Otherwise record the exact
new response/failure and advance a different evidence-backed diagnostic.

Camera/PCM capture and listeners remain off. Run non-capture media/NN and
synthetic Whistle regressions as appropriate. This experiment does not prove
a C6 firmware replacement is necessary.

Sources:
- https://github.com/espressif/esp-hosted-mcu/blob/release/v2.x/host/drivers/rpc/core/rpc_req.c
- https://github.com/espressif/esp-hosted-mcu/blob/main/common/serializers/eh_proto_v2/src/proto/rpc_v2.proto
- https://github.com/espressif/esp-hosted-mcu/blob/release/v2.x/slave/main/slave_wifi_std.c
