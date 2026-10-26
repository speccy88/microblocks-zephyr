# Ordered follow-through (2026-10-26)

New ideas are queued; they do not interrupt the current task or create another
hardware owner. Native Zephyr, COM5-only access, USB plus station-hosted targets,
AP disabled and preservation of saved credentials apply throughout.

1. Finish bounded station compatibility diagnostics. Verify association, DHCP,
   board-served editor assets, real WebSocket programming and USB ownership.
   If blocked, record the exact evidence and proceed to independent work.
   The official support question is ready, but connector submission returned
   HTTP 403; no issue was created and no new access grants were requested.
2. Complete a versioned hardware coverage audit for the actual P4-WIFI6
   revision: schematic/product revision, populated parts versus connectors
   versus SoC facilities, pins and conflicts, native drivers, block exposure,
   and linked end-to-end evidence. States: tested, implemented-unverified,
   missing, incompatible. A capability list alone is insufficient.
3. Initial portable I2C discovery/readings implementation verified; see
   I2C_DISCOVERY.md and p4-i2c-native.json. Extend the genuinely supported set
   only with tested adapters and hardware. Inspired by SparkFun's MIT-licensed
   Universal Auto-Detect source at 39b20cc3a9a1b1163f14fdfb8812c754926734c8.
   Explicit bus, bounded/cancellable operations and stable result lifecycle;
   address ACK, candidate and confirmed identity are distinct. Unknown devices
   expose addresses only. Registry names supported measurements, types and
   units; unsupported reads fail explicitly. Start with a small verified set,
   fixtures and safe available hardware. No blind configuration, reset, mux
   switching or foreign sensor probes at camera/codec addresses. Preserve
   third-party notices and inspect each reused driver's license.
4. Independent lightweight local wake-word detection using a compatible
   frontend/model/backend, explicit start/stop and event hat, bounded queues,
   confidence/cooldown, no default listener. Whistle remains separate.
   Native fixture parity, GP hats and bounded microphone lifecycle now pass;
   acoustic recognition waits for an audible Windows output. See WAKE_WORD.md.
5. Measured PPA/DSP/NN acceleration, then staged JPEG/H264 interfaces with
   accurate encode/decode directions and unsupported capability boundaries.
6. ESP-NOW portable blocks: capability/init, peer configuration, bounded typed
   send, receive event, sender/status, queue overflow/errors and teardown.
   P4 has no radio; current C6 support is unverified. Zephyr's direct-radio
   ESP32 sample does not establish a Hosted implementation. Espressif's open
   issue #19 tracks missing Hosted support. No channel change, broadcast,
   persistent keys, station disconnection or C6 flash without appropriate
   authority. RF proof requires a separately authorized available peer.
7. OpenRouter blocks after current native work: asynchronous model choice,
   prompt, response/status/error and bounded request/cancel lifecycle. Declare
   whether the request originates in the browser or board; never silently add
   a proxy or cloud fallback. First develop mocked transport tests. API keys
   must stay outside project serialization, source, logs and screenshots.
   Persistent API access and paid requests require specific approval; none
   has been supplied. The station blocker limits any board-originated path.
8. Continue measured board coverage and portable DSP, image processing,
   inference and audio increments using the support matrix. Keep each new
   feature independently tested and self-explanatory in the real editor.
9. Separate Chat API, typed Decision API (verified Jev provider contracts),
   and Agent libraries. Agents require explicit allowed tools, step/budget
   limits, status and cancellation; inference never authorizes actuation.
   OpenRouter Chat Completions and Jev Decisions are distinct interfaces.
10. Device storage aliases Flash, RAM and SD with a shared bounded service,
   explicit capacity/availability/volatility and safe paths. Keep credentials
   and firmware partitions inaccessible. No automatic format or erase.
   Explicit save/load for pictures, PCM, logs and transcriptions; browser
   preview, text edit and download through both Pages and board hosting.
   Files remain on the device. Verify real origin/permission/transport limits,
   MIME/nosniff behavior and safe partial-write/sync/rename/unmount semantics.
   Evaluate native Zephyr SQLite versus a lighter bounded database separately.
11. Audit use of Zephyr services; expose relevant timers, jobs, events and
   storage through understandable blocks. Separate portable logic, Zephyr
   adapters and board drivers; keep long inference off the system workqueue.
12. A bounded portable JSON library for parse/build, fields, arrays and easy
   get/set/add/remove. JSONata is a separate evaluated runtime: benchmark its
   correctness, memory and execution limits before claiming full native support.
13. A distinct GRAFCET-inspired library with steps, transitions, deterministic
   scans, visible active steps, timers and start/stop/reset. Test synthetic
   logic only; do not claim standards compliance or safety certification.
14. Separate MQTT and HTTP(S) libraries with asynchronous bounded operations,
   TLS verification, explicit status/cancellation and clear availability.
   MQTT includes publish/subscribe/events, QoS, retain, LWT and reconnect;
   HTTP includes methods, headers, JSON/binary bodies and timeout limits.
   No new broker credentials, cloud spending or security changes are approved.
15. A clock service and scheduling library: verify the actual board's RTC and
   power-loss retention, support NTP synchronization and clock-valid status,
   monotonic intervals, and calendar schedules with explicit timezone/DST
   and missed/duplicate firing policies. Do not assume an external RTC exists.

Hardware audit coverage includes CSI/IMX219/OV5647 and DSI attachments, ES8311
mic/speaker path, C6 Wi-Fi/Bluetooth, SD/storage, USB roles, exposed
GPIO/I2C/SPI/UART/I2S, buttons/LEDs/power, ISP/PPA/JPEG/H264 and compute
facilities only as verified on this exact schematic. Do not infer populated
Ethernet, displays, speakers or other loads from a generic P4 feature list.

Every library increment needs a usability pass: concise action/reporter labels,
named inputs/units, defaults/dropdowns, tooltips/help, small working examples,
native category colors/spacing, and explicit busy/empty/error/unsupported
states. Avoid backend jargon in the primary flow. Preserve the GP visual
language; check normal Windows viewport/scaling, long names, previews,
collapse/play, drag/cache, palette overlap and supported keyboard interaction.
Test USB and hosted UI separately. Return actual editor screenshots at coherent
milestones; a successful build does not prove visual polish or usability.

Primary references:
- https://github.com/sparkfun/SparkFun_Qwiic_Universal_Auto-Detect
- https://www.ti.com/lit/ds/symlink/tmp117.pdf
- https://docs.zephyrproject.org/latest/samples/boards/espressif/espnow/README.html
- https://github.com/espressif/esp-hosted-mcu/issues/19

## MQTT, HTTP, clock and scheduling libraries

Queued after the current wake-word increment. Audit and strengthen separate MQTT
and HTTP(S) libraries: bounded asynchronous publish/subscribe, receive events,
QoS/retain/LWT/reconnect; methods, headers, JSON/binary bodies, status, timeouts
and verified TLS. No new broker credentials, spending or security changes.

Add a shared valid-wall-clock service: RTC read/set and NTP sync/status, explicit
timezone/DST, calendar scheduling with missed/duplicate firing policies, and
monotonic interval timers. Verify populated RTC hardware and power-loss retention
on the exact board before advertising those capabilities.

Local follow-through: bounded portable JSON CRUD and separate `json:*` library
now pass host tests, both native profile builds and disconnected real-editor
rendering. Physical execution and publication remain held. See
[`docs/JSON.md`](../../../docs/JSON.md). JSONata is the next independent runtime
feasibility stage; initial candidate source review is in
[`docs/JSONATA.md`](../../../docs/JSONATA.md), without a native support claim.

Local scheduling follow-through: separate Clock & Timers and Steps & Transitions
libraries now have bounded portable cores, fake-clock sanitizer tests and both
native profile builds. The disconnected editor loads their logical-state
example. Calendar time is manual and uses an explicit fixed UTC offset; actual
RTC/NTP providers, automatic timezone/DST rules and physical timing validation
remain open. See [`docs/AUTOMATION.md`](../../../docs/AUTOMATION.md). Firmware
installation and publication remain held.

Local RAM-storage follow-through: a fixed-capacity service and separate Storage
library now pass host sanitizer tests, native profile builds and disconnected
GP rendering. This supports small text/binary records only: eight volatile
files of at most 8 KiB. Flash/SD, media streaming and DB remain open. The shared
browser file-manager frontend has a disconnected state and opt-in local fixture;
live device transport and revision guards remain open. See
[`docs/FILE_MANAGER.md`](../../../docs/FILE_MANAGER.md) and
[`docs/STORAGE.md`](../../../docs/STORAGE.md). No storage
formatting, physical file write or publication was performed in this stage.
