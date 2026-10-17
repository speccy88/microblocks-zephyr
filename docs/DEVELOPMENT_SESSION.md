# Waveshare development session — 2026-10-17

## Scope and acceptance criteria

Start from `e07e6f9e6752f7722a8fa3f790c14f59c515de63` on
`development/waveshare-rlcd`. First compile the pinned upstream hello-world
application, then the board diagnostic application, then integrate SmallVM in
a separate application, then move production transport to binary WebSocket
and serve the actual graphical IDE from the board (see STANDALONE_GOAL.md).

The user explicitly authorized full flash erase and replacement on the
Waveshare connected as COM4, without a firmware backup. No backup is to be
made. This session-specific instruction overrides the starter's generic
backup recommendation. It does not authorize eFuse or security changes,
writing another board, or changing repository visibility.

Diagnostic acceptance requires compiler logs and live serial observations for
the exact binary hash. Device readiness alone is not physical validation.
Display appearance and button presses require human observation when no
independent measurement is available. Initial tests exclude SD writes, radios,
audio output and unrestricted GPIO. SmallVM acceptance requires real binary
protocol connection, arithmetic and ordered output, not merely a linked image.

## Target identity before modification

- Windows USB Serial/JTAG interface: COM4, VID 303A, PID 1001, interface 00.
- ROM reports ESP32-S3, revision v0.2; crystal 40 MHz; embedded 8 MB PSRAM.
- Read-only flash identification reports 16 MB flash, 3.3 V quad interface.
- Read-only security report: secure boot disabled; flash encryption disabled.
- Existing application explicitly identifies Waveshare ESP32-S3-RLCD-4.2,
  ST7305 300×400 and SHTC3 at 0x70. Its observations are identity evidence,
  not validation of this project's drivers.
- Opening Windows serial caused a USB serial reset despite DTR/RTS being
  deasserted. No firmware backup was taken. Application/network/token lines
  were excluded from retained evidence.
- COM5 was absent during inventory and is outside this session's write scope.

## Source references

- [Waveshare board documentation](https://docs.waveshare.com/ESP32-S3-RLCD-4.2)
- [Waveshare schematic and datasheets](https://docs.waveshare.com/ESP32-S3-RLCD-4.2/Resources-And-Documents)
- [Vendor examples](https://github.com/waveshareteam/ESP32-S3-RLCD-4.2)
- [Pinned Zephyr source](https://github.com/zephyrproject-rtos/zephyr/tree/a915b2f12675b48b16d56653ea145dcd8f20cbbf)
- [Zephyr board documentation](https://docs.zephyrproject.org/latest/boards/waveshare/esp32s3_rlcd_4_2/doc/index.html)
- [SmallVM upstream](https://codeberg.org/MicroBlocks/smallvm)
- [BeagleBoard reference integration](https://github.com/beagleboard/microblocks-zephyr)
- [ArduinoCore-Zephyr](https://github.com/arduino/ArduinoCore-zephyr)

## Build environment

Use an isolated Linux workspace on the WSL ext4 filesystem, not `/tmp`
(which is RAM-backed on this host). Limit Ninja to four jobs. The WSL VM has
approximately 6 GB RAM and 2 GB swap; the Windows host has approximately 16 GB
RAM. Serial access stays on Windows so no USB reassignment is required.
Dependencies and test results are recorded as they are verified below.

## Results

Pinned Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`
(4.5.0-rc2) and SDK 1.0.1 / GCC 14.3.0 compiled upstream hello-world and
the corrected diagnostic image. Python 3.12.15, west 1.5.0, CMake 4.4.4 and
Ninja 1.13.2 were used. The diagnostic linker reports 216,756 bytes FLASH,
61,484 bytes IRAM and 98,592 bytes DRAM, plus the board's PSRAM reservation.
All nine offline tests pass on Linux.

Build logs and module revisions are saved under `evidence/2026-10-17/`.
The first erase request was denied before execution by automatic review.
After the exact user confirmation authorizing erase without backup was
forwarded, the same request was retried once and succeeded. The diagnostic
image was flashed and verified by esptool. No backup was made, and no eFuse
or security settings were changed.

Live results in `diagnostic-live.txt`: LCD, SHTC3, RTC, button devices, ADC,
I2C and SPI were ready. Temperature was approximately 36.2 C and humidity
26.4%; battery raw ADC was 1291 with an uncalibrated 4158 mV estimate.
RTC returned ENODATA (clock unset). Both button inputs were released.
A checkerboard transfer succeeded. Display appearance and physical button
presses remain unverified.

Official SmallVM stable source was inspected at
`e614320450bc3c14cd95b4be4e7b74819ad8d13c` (VM v411, MPL-2.0).
Its existing Zephyr persistence backend assumes directly addressable flash
offsets; it must not be used unchanged for the ESP32-S3 memory map. A first
runtime should use an explicit RAM code store or a bounded, correctly mapped
partition backend. The existing ArduinoCore-Zephyr loader model also requires
an actual ESP32-S3 variant/integration; Zephyr board support alone does not
establish Arduino API compatibility.

## Combined runtime checkpoint

The actual Arduino API module (`af5b8610f9be6d7b962e2ba6dd8e6859697c44ff`)
and checksum-verified ArduinoCore-API 1.5.2 compile for this target. The smoke
target exercises Serial, GPIO and Wire at source/build level. Physical library
acceptance is still pending.

SmallVM v417 (`2071df569623ba9cdcd6f8106b61796e047df38b`) is linked from
verified files in the existing UNO Q snapshot. Preparation patches bound
scheduling, repair partial-frame expiry, reject malformed lengths, and use
a 64 KiB RAM code store in PSRAM. The standalone target adds alternating
CRC-checked flash snapshots; reboot persistence still needs hardware testing.

The real 32-bit interpreter passed a WASI harness with simulated transport
and peripherals: ten 5+7 reporters returned 12, a 1019-byte fragmented upload
executed, timeout and invalid-length recovery passed, and all 500 outputs
arrived in order while writes were restricted to seven bytes. These are
interpreter/adapter tests, not browser or board transport passes.

The standalone image packages the real MicroBlocks 2.5.8 GP editor/compiler
with about 3.51 MB of local compressed assets. Combined images compiled and
were flashed with esptool hash verification. Boot logs confirm PSRAM, LCD
text transfer, AP startup and HTTP startup return success. Windows detected
and connected to the protected AP, and the board reported its client event.
The bounded background probe at 18:43 UTC obtained DHCP address 192.168.4.10,
authenticated the binary WebSocket, received a VM ping and uploaded/executed
5+7 with result 12. No firmware fatal error was observed. HTTP returned assets,
but missing Content-Encoding headers exposed compressed bytes to the client;
the response-header fix is compiled and awaiting re-test. Full graphical
browser behavior and persistence remain unvalidated. The PC's original Wi-Fi
profile was restored after each probe.

Focused logging also revealed that upstream Arduino Wire.begin directly calls
the Zephyr device initializer, allocating its I2C IRQ a second time. The pinned
Wire preparation fix reuses the initialized device, implements available() as
the buffered byte count, and implements setClock for supported bus rates. This
fix is compiled; peripheral reads under the combined runtime need re-testing.

The simple-boot image emits a ROM SHA comparison warning before proceeding;
its esptool image checksum and flash write verification pass. This packaging
warning remains unresolved.

## Production wireless acceptance

The production build disables the USB console and logging, keeps station Wi-Fi
awake, and uses the supported 2-second DHCP initial-delay limit. Its physical
test ran without a serial reader. `wireless-production.json` records PASS for
ten arithmetic reporters, bytecode editing (12 to 13), real temperature/humidity
and battery primitives, released buttons, LCD transfer, 500 ordered outputs,
source-matching code CRCs, a 1019-byte fragmented upload, partial-frame timeout
recovery, stop/variable inspection, and reconnect (0.156 seconds). After a COM4
recovery reset, all tested code CRCs matched, arithmetic returned 12, and a
saved start-hat block automatically set a variable to 42. Wi-Fi settings also
survived reboot. This is reset testing, not a physical unplug/replug test.

The board is provisioned on the regular Wi-Fi network at `192.168.1.69`; the
network password was reused privately from the Windows profile, sent only to
the authenticated board settings endpoint, and never written into Git or logs.
The local editor/compiler is MicroBlocks 2.5.8, including the real GP WASM engine,
GP filesystem package, local scripts, styles, fonts, images and embedded libraries.
Generated asset hashes are in `standalone-assets-manifest.json`. The response
policy restricts runtime connections to the board and blocks external resources.

## HTTP and graphical loading repair

A temporary diagnostic build captured `poll failed (-12)` followed by server
restarts as soon as two clients were active. The default `CONFIG_ZVFS_POLL_MAX=3`
was insufficient for the HTTP listener, stop event and client descriptors.
Setting it to 16 removed those resets. A remaining concurrent request expired
because the GP package took 13.16 seconds on the measured link while accepted
clients had a 10-second inactivity timer. The production timeout is now 60
seconds, and asset responses close connections after use. Buffer sizes also
accommodate browser headers and concurrent packets.

`http-browser-assets.json` records 148/148 assets passing with four concurrent
clients, including content hashes, gzip, MIME types and board-only response
policies. Earlier failed and sequential audits are retained. A controlled
browser reload captured 156 network events, no failures or truncation, and only
`http://192.168.1.69` as a request origin. The actual GP WASM editor and Waveshare
library rendered. The test temporarily removed the old page's unconditional
leave-page handler because the in-app browser automatically cancelled that
confirmation; the freshly loaded page reinstated the original handler.

Native `prompt()` is unsupported in the in-app browser. Pairing now uses a DOM
password dialog, with an optional local JSON import that reads only its `pair`
field and never uploads the file. The temporary pairing-only file imported
successfully and the value stayed redacted. The import tool call took 4,334
seconds to return; no build or flash was running during that wait. Pairing submit
and graphical edit/run/stop/variable/reconnect tests remain pending at this
checkpoint. Forwarding an approval was not treated as approval.

`wireless-browser-firmware.json` records the full production regression after
the final HTTP/pairing build: ten arithmetic runs, editing, 500 ordered outputs,
CRC checks, 1019-byte fragmented upload, timeout recovery, stop/variable checks,
reconnect in 0.14 seconds, and matching code/autostart behavior after reset.
The firmware SHA-256 is
`332068fbe8b78280c4a6fa1af908a257821d7a3e54be549f10235c4952d338f9`.
See `storage-capacity.json` for exact flash and linker allocations. Runtime
free heap under browser-plus-VM load has not yet been measured.

## Final standalone graphical acceptance

This section supersedes the earlier pending graphical and heap checkpoints.
The final app-only image is 4,184,804 bytes, SHA-256
`1c6589145155f5c3e205ad92d53dab32cee2ceac79e2ac58b914915bef265506`.
The exact final build and hash-verified COM4 flash logs are
`production-keepalive-build.txt` and `production-keepalive-flash.txt`.
No further full erase was performed; program/settings partitions were preserved.

Forced asset `Connection: close` responses were an interim change, not the final
configuration. The tested final combination uses normal HTTP keep-alive, eight
HTTP clients/backlog, 24 network contexts/connections, poll capacity 16 and a
60-second client timeout. A proposed all-context diagnostic sampler was removed;
it could block the HTTP thread. Four final fresh actual-browser loads each
completed 39/39 requests with status 200, no pending/failed requests or off-board
origins. The last two used six connections with 33 reused responses and no JS
errors. The final four-worker content/header audit passed 148/148 assets while
the authenticated editor remained open. These are bounded samples, not a
24-hour stability claim. Earlier failed audits remain for diagnosis.

GP engine startup is deferred until its head dependencies and local English
catalog are ready; the board adapter waits for IDE initialization. Category
labels are now clean and the Board menu keeps native controls visible. The
actual GP WASM/compiler UI paired, displayed a graphical SHTC3 result 26093 milliC,
ran 5+7=12, changed the second input to 8 and returned 13. Its counter emitted
exactly 1..500. A one-million-iteration count/say script was observed running
at 8578; individual script stop retained 10643 in two separated inspections.
Global Stop uses upstream softReset and deliberately clears variables.
Disconnect/reconnect required no new pairing prompt and ran another 500 values.

After the GUI program had been saved, read-only queries and a COM4 reset
confirmed count 500, saved generation 28 and all three CRCs unchanged. A fourth
fresh load, Project > Open from board, then Connect reconstructed one variable
and three chunks; Start emitted 500 ordered numeric values. The separate id 255
Memory cleared diagnostic was excluded from program numeric output. Use Open
from board before Connect when retrieving a saved program: ordinary Connect
synchronizes the current editor project to the board. Readback preserves logic
and variable names, not original positions/comments/full project metadata.

The final binary WebSocket regression also passes ten arithmetic runs, live
editing, real peripherals, 500 outputs, source CRCs, fragmented 1019-byte upload,
timeout recovery, stop/variables, reconnect (0.188 s), persistence and autostart.
See `wireless-keepalive-firmware.json`, `graphical-acceptance.json`,
`graphical-final-reboot.json` and `browser-fresh-loads.json`.

Ten allocator samples were taken while the real graphical counter was active.
Common libc malloc retained 46,876 free bytes; kernel heap retained 22,604 free
bytes with 42,732 allocated and 43,444 peak. Uptime increased without reboot.
These statistics cover allocator pools; they exclude static arrays, stacks,
unassigned PSRAM and free objects inside the fixed 64 KiB VM object arena.
The ESP-IDF heap_caps free-size port returns a stub zero, so the endpoint uses
the real locked Zephyr common-libc/kernel heap statistics instead.

The earlier PSRAM estimate was incorrect: the linker ext_dram span 5,242,896 B
contains 4,063,232 B of virtual mapping padding. The actual external data/reserved
heap section is 1,179,664 B: 131,088 B static VM buffers/other BSS plus a 1,048,576 B
reserved heap. The remaining 7,208,944 B of physical 8 MiB capacity is not a measured
or guaranteed allocatable free heap. Current common-libc malloc uses internal
DRAM, not that reserved external heap. Do not sum IRAM/DRAM aliases or count the
internal linker remainder again on top of the measured malloc pool.
`storage-capacity.json` corrects the earlier estimate and separates these values.
The final image leaves 9,446,684 B in its 13 MiB application partition. IDE assets
occupy 3,513,201 B compressed flash, expand to 17,284,911 B in the PC browser and use
no microSD. VM storage is 256 KiB (two 128 KiB slots, 64 KiB payload cap); settings 64 KiB;
the flash tail beyond those partitions is 2,818,048 B.

Display appearance/orientation, physical button presses, calibrated voltage,
RTC setter/retention, SD, BLE, audio, power/sleep and external library/pin tests
remain incomplete. Startup fallback exists; mid-session station-loss fallback
does not. The simpleboot ROM comparison warning remains an upstream packaging
limitation; no eFuse/security settings were changed. No COM5 access occurred.
