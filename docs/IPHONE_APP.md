# iPhone wireless editor — first slice

## Behavior and acceptance contract (2026-11-01)

Build on `codex/js-editor-migration-20261027` and its exact official JS pin
`5564b1e42d6790360450ebf11c9eb33a1c6877f2`. Preserve the independent GP/SFC
branch. This profile does not upgrade firmware or import the Linux primitive
map into microcontroller programs.

The local compiler overlay maps `rlcd`, `fruitJam` and `xrp` to the canonical
ports' `IOPrims` index 3. It copies the compiler map without changing the
shared upstream table. Unknown named sets fail before upload instead of the
stock compiler's fallback to set zero. The existing RLCD and Fruit Jam
libraries are available in `Libraries/Zephyr`; custom matrix/media/SFC slots
remain outside this slice. Compiling a board primitive does not prove its
physical peripheral works.

The first app bundles the real editor for offline editing and uses a native
`URLSessionWebSocketTask` bridge for station-mode Wi-Fi programming. A user
enters the board's private IPv4 address and explicitly connects. The socket
uses `/ws/vm`, the board's existing exact HTTP Origin, and its `ready` marker.
The original Origin check remains unchanged. No proxy, cloud relay, login,
credential provisioning, discovery scan or automatic reconnect is introduced.

Acceptance criteria:

1. Upstream engine blobs retain their manifest hashes. The separate iPhone
   package contains its own overlay, source notices and deterministic receipt.
2. A native link accepts only private IPv4 addresses, bounded binary frames
   and the exact initial `ready` marker. Queues have fixed limits; late events
   from an old session cannot corrupt a new connection. Close, error, timeout
   and backgrounding discard queued input and output.
3. The existing compiler and connection parser perform programming. Tests must
   exercise ping/version, a compiled arithmetic chunk, CRC acknowledgement,
   run/stop and reconnect through the iPhone adapter. A test fixture is clearly
   labeled; it is not physical-board evidence.
4. The phone layout provides at least 44 CSS-pixel controls, a collapsible
   block palette, a full scripts workspace, portrait/landscape resizing and
   an accessible connection sheet. Connected status requires a recent VM ping
   and version, not just an open socket. Native project export uses the iOS
   share sheet; Files import uses the editor's normal picker.
5. A macOS CI job generates and builds an unsigned iOS Simulator app. Windows
   tests alone cannot establish that the app compiles or runs on an iPhone.

## Board scope

The canonical board manifests remain the source of hardware capability. The
app's small selector links back to those manifests and records app acceptance
separately; wireless silicon is not proof of a working programming server.

| Target | Initial path | Limit |
|---|---|---|
| Waveshare ESP32-S3 RLCD | Native Wi-Fi `/ws/vm` | Existing board firmware has physical wireless evidence; this iPhone app has not been tested on the board |
| SparkFun XRP RP2350 | Native Wi-Fi `/ws/vm` | Existing wireless protocol evidence; iPhone and graphical acceptance pending; actuator restrictions remain |
| Fruit Jam | Native Wi-Fi `/ws/vm` | Existing networking/GP evidence; association/power-cycle limitations remain; iPhone acceptance pending |
| ESP32-P4 WIFI6 | Unavailable in this slice | Manifest records C6 request-284/hosting failure; do not advertise Wi-Fi programming as ready |
| Propeller 2 | Desktop USB serial | Native FlexC VM is independent of Zephyr; no iPhone USB serial or built-in wireless path is implemented |
| micro:bit / stock BLE boards | Next native CoreBluetooth adapter | Stock MicroBlocks service/characteristic UUIDs are in the pinned source; no BLE support is claimed by this slice |
| UNO Q / Pi / MicroDuck | Separate adapters/acceptance required | Do not infer this board-server contract from a reference repository or a local Linux bridge |

## Build on macOS

Requires Xcode with an iOS 17+ SDK, Python 3, Git and XcodeGen. Fetch the exact
editor pin into a source cache using verified Git transport, then:

```sh
python3 tools/package_iphone_editor.py --source /path/to/smallvm-git --output ios/MicroBlocks/Editor
cd ios
xcodegen generate
xcodebuild -project MicroBlocks.xcodeproj -scheme MicroBlocks -sdk iphonesimulator -configuration Debug CODE_SIGNING_ALLOWED=NO build
```

The generated editor directory and Xcode project are ignored. Open the generated
project to select your own signing team for an actual phone. No paid membership,
App Store submission, device deployment or signing configuration is performed
by this task. The local-network permission prompt must be accepted on the phone.
The app has a scoped `NSAllowsLocalNetworking` ATS declaration for existing
plain-HTTP LAN firmware; it does not enable arbitrary internet loads. Transport
is not encrypted: use the board on the intended trusted local network. A future
WSS firmware path needs its own certificate/identity design.

## Evidence and remaining gates

See `evidence/2026-11-01/iphone/validation.json` for actual executed checks.
Implementation commit `496b904ad65ad11db3ef56e26916f06667851e70` passes all
four workflows. The [native iPhone CI run](https://github.com/speccy88/microblocks-zephyr/actions/runs/41331343970)
builds the unsigned app with Xcode 16.4, passes two endpoint unit tests, and
passes the actual Simulator UI test: bundled editor, on-screen keypad entry,
real WebKit-to-native validation response, close/reopen and rotation. The
public test address is rejected before any network request. This verifies
the bridge without contacting a board. The final evidence-only receipt does
not change the tested app code.

The [portrait workspace](../evidence/2026-11-01/iphone/portrait.png),
[block palette](../evidence/2026-11-01/iphone/portrait-blocks.png) and
[landscape view](../evidence/2026-11-01/iphone/landscape.png) are captures of the
real pinned editor under desktop Chromium mobile emulation. Trusted touch
events moved an existing block and added one from the palette; the workspace
expanded after the drop. Export cancellation and successful serialization/
reparse were checked with explicit synthetic native-share responses.

The CI also builds the actual pinned native SmallVM under ASan/UBSan and runs
the iPhone JS adapter through the existing loopback WebSocket/PTY bridge. The
real compiler uploads a chunk with CRC acknowledgement; the actual interpreter
returns 42, then stop/reconnect and retained CRC readback pass. Only the native
socket API is modeled by a Node test shim in this check. This does not test
`URLSession`, iOS local-network permissions or a physical board's radio.

Simulator compilation, desktop graphical QA and synthetic protocol checks are
separate from physical iPhone acceptance. Before calling this ready, test on
an iPhone: local-network permission denial/retry, first connection, block drag
and numeric keyboard, import/export, 50 ordered outputs, large uploads, CRC,
stop, Wi-Fi loss, background/resume, reconnect and retained program readback.
Board-specific custom slots, P4 media, SFC, native BLE, Bonjour and first-flash
provisioning are later slices, not implied by this initial app.

Primary platform references: [Apple WebKit](https://developer.apple.com/documentation/webkit),
[URLSessionWebSocketTask](https://developer.apple.com/documentation/foundation/urlsessionwebsockettask),
[local-network privacy](https://developer.apple.com/documentation/bundleresources/information-property-list/nslocalnetworkusagedescription),
[CoreBluetooth](https://developer.apple.com/documentation/corebluetooth).
