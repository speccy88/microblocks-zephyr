# Two native Zephyr targets and network approval proposal

Fred explicitly requested both USB and board-self-hosted MicroBlocks targets
on 2026-10-25. GitHub Pages is a third distribution surface, not board hosting.
The default USB image remains available without the network stack or C6.
Both images share SmallVM, camera/image/audio primitives and portable handles.

## Companion identification before network changes

The exact board schematic identifies ESP32-C6-MINI-1-N4, using SDIO D0..D3
GPIO14..17, CLK18, CMD19 and CHIP_PU GPIO54. Use the pinned Zephyr
`esp_hosted_mcu` SDIO transport core first, with no Wi-Fi consumer, Bluetooth,
scan, association, AP or credential RPC. Read the companion boot/version event
or GetCoprocessorFwVersion RPC. A version mismatch is evidence, not permission
to flash the C6. Its firmware is separate from the authorized P4 replacement.

The core's host protocol expects major 3. Existing firmware may differ. First
test enumeration and version without changing it; document the actual result.
No C6 flashing is authorized yet. If required, prepare exact source/version,
artifact hash, access method and recovery steps for separate approval.

## Approved initial self-hosted configuration (startup currently failing)

Fred approved the password-protected standalone AP proposal on 2026-10-25
at 20:47 UTC, including saving its unique password on board for reuse.
This does not authorize C6 firmware replacement or Windows network changes.
The unique key is privately generated and stored on P4 for reuse, absent from
source, logs and evidence. SDHC/SDIO initialization
now passes after freeing unused AXI DMA interrupt vectors; the current version
RPC still has no reply. Bounded tracing now verifies a current-numbered V1
private frame and `RPCEvt` boot event 769, no SDIO/decode errors, and transmit
credits replenished after host writes. A read-only MAC-query RPC returned
response 513 in 12 ms with `ESP_ERR_WIFI_NOT_INIT` (0x3001), before driver
initialization; the address was not retained. This establishes a responding
basic control path even though the version RPC is unavailable. It is not
evidence that C6 replacement is required or that networking is already up.
Next use the approved AP-only configuration through compatible native control
requests, with no automatic station association or saved foreign credentials.

The native hosted image and all 154 verified editor assets are now flashed.
Safe initialization passes, including C6 Wi-Fi init, compatible post-init MAC
queries, USB programming/reconnect, generated-image transforms and Whistle.
AP enable currently fails: SetMode request 260 receives response 516, followed
by configuration request 284 without a response and SDHC timeouts (-116).
Zero counter fields on failed register reads are placeholders, not proof of
a reset or actual zero credits. The underlying cause remains unresolved.
Disabling the documented `sta_disconnected_pm` flag reproduced the same
failure, so it is not claimed as a fix. See `p4-hosted-pm-result.json` and
`p4-hosted-pm-runtime.json` under `evidence/2026-10-25/`.
No C6 replacement is justified by this result alone. The AP has not passed
radio/DHCP/browser tests and must not be presented as working self-hosting.

The power flag is documented in the official
[ESP32-C6 Wi-Fi API](https://docs.espressif.com/projects/esp-idf/en/v5.5.1/esp32c6/api-reference/network/esp_wifi.html#_CPPv418wifi_init_config_t).
The official control implementation copies AP beacon/DTIM fields directly;
their documented defaults are 100/1, rather than the uninitialized zero values
in the pinned Zephyr driver. The opt-in AP patch supplies those defaults:
[coprocessor configuration source](https://github.com/espressif/esp-hosted-mcu/blob/0e8d0e3f0c2723deaf15441200cb4d8c53fea230/slave/main/slave_wifi_std.c),
[wire schema](https://github.com/espressif/esp-hosted-mcu/blob/0e8d0e3f0c2723deaf15441200cb4d8c53fea230/common/proto/esp_hosted_rpc.proto).
This reference version is not asserted to be the unknown installed C6 build.
The nonzero timing-default trial also reproduced the same request-284/SDHC
failure (`p4-hosted-timing-result.json`). Further AP retries are paused; USB,
generated images and local speech remain independently usable. No Windows
association is requested while there is no working AP to test. C6 firmware
replacement is neither performed nor established as necessary. Resolving the
remaining transport/companion failure needs additional diagnostic evidence;
it is not an unanswered permission request.

Recommended for an independent board and phone/tablet use:

- Create a new 2.4 GHz access point named `MicroBlocks-P4`, channel 6.
- Require WPA2-PSK with a newly generated unique 16-character password. Keep
  it in an ignored local private file; do not print it or put it in Git,
  evidence, browser storage or URLs. The AP provisioning was approved. If saved
  for autonomous boot it is stored on board flash; no flash encryption/eFuse
  changes are proposed. A RAM-only test can precede persistence.
- Board address `192.168.4.1/24`, DHCP clients beginning at `.10`, at most two
  clients. No routing, internet sharing, DNS interception or captive portal.
- Serve the actual GP editor and its assets from P4 flash at
  `http://192.168.4.1/`, with binary VM WebSocket `/ws/vm` on port 80. Permit
  only a matching browser Origin and one programming controller at a time.
- Anyone who has the AP password and connects can program this board through
  that local service, including invoking its camera/audio blocks. No separate
  application account/login is proposed. No internet exposure or cloud proxy.
- Preserve USB programming in the hosted image with exclusive transport
  ownership; do not let simultaneous USB/WS byte streams mix. The separate
  USB-only image remains reproducible and testable.
- No Windows Wi-Fi association, firewall, network-security or OS credential
  changes. Fred chooses whether to connect a phone/computer to this AP.

Alternative: station-only mode on a specific existing 2.4 GHz SSID supplied by
Fred, DHCP, the same HTTP/WS service available to that LAN, no new AP. Credentials
are entered privately over USB, never inferred or uploaded. Initial connection
uses RAM-only credentials; saving them for autonomous boot is a separate
explicit choice. Any LAN peer with access to the service can program the board.

The approved choice is AP mode with saved board credentials and the service
scope above. Station mode remains an alternative requiring a separate choice.
Independent USB/camera/audio work continues during protocol bringup.

## Implementation and acceptance

Reuse the repository's native Zephyr HTTP service/WebSocket architecture and
pinned GP packager, with bounded 2 KiB asset chunks and transport queues.
Package P4 library/example/preview locally in flash. No runtime CDN. Keep the
existing same-origin checks and deterministic disconnect/Stop All cleanup.
Measure image/audio/DMA coexistence, controller transitions and idle heap.

Test both images: VM arithmetic/edit/fragmentation/reconnect; actual camera
pipeline; all hosted asset hashes/headers under VM traffic; a genuine browser
loaded from the board; power-cycle behavior according to the approved saved
configuration. A localhost bridge or Pages deployment is not physical hosted
acceptance. Do not claim speech, wake-word, generic ONNX or YOLO support from
network success.
