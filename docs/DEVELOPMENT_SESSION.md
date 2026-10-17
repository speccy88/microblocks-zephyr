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

Graphical acceptance is unfinished: the browser displays Loading and reports
`Module is not defined`; a concurrent HTTP asset audit observed a connection
closed without a response. These are web-serving/loading failures to diagnose,
not failures of the passing VM protocol test. Do not claim graphical editing,
run/stop/debug or a browser request-trace pass yet. Earlier failed diagnostic
test files remain as evidence of the investigation.
