# P2 optional peripherals: implementation and acceptance

This work adds focused, opt-in P2 LEDs, Displays, Peripherals, Storage,
Sensors and Audio libraries. The existing five automatic P2 libraries and
their saved selectors remain compatible. Shared MicroBlocks libraries are
preferred to duplicate sensor/math/protocol implementations.

## Contract

The published installer deliberately remains pinned to the hardware-validated
revision-8 source `ac4fce0a118761b2d75add8147e946e0e43aa4ca` and exact image
hashes. New optional peripherals are **candidate firmware**, compiled separately
in CI and not installed or packaged as validated images. Their library
descriptions and `optional-peripherals.json` disclose this dependency. Building
the current checkout produces a candidate; installing it requires the owner's
approval and preservation of their program/storage. Do not infer a new hardware
PASS from the older revision-8 acceptance records.

Work proceeds in this order: WS2812; SSD1331; buffered full-duplex UART;
general LittleFS files and SD feasibility; BME680/DHT22; LIS3DH/LSM9DS1;
IL3820; NMEA GPS; 4x4 keypad; shift registers; PING/PIR; DAC WAV playback.
Examples accompany implemented groups. Firmware changes must compile for
Eval, original Edge and Edge32. Editor tests must load optional libraries
normally and compile their public blocks with the pinned JavaScript editor.
Protocol and data conversion tests use known inputs, malformed inputs and
timeouts; compilation and simulated buses are not physical acceptance.

Every pin path rejects module-reserved pins (Edge32 P40-57, all P58-63).
IDE UART, boot flash and PSRAM remain reserved. Long operations have bounds
or cooperative/background progress; worker cogs do not directly call
unaudited heap or peripheral primitives. Shared buses need explicit pins.
No automatic output or hardware probing occurs merely by importing a library.

The owner's latest instruction supersedes previous flash permission: do not
replace programs or perform destructive flash operations without approval.
Before any device operation, inspect storage/project state non-destructively.
Normal editor connect synchronizes and can replace stored code; RAM firmware
loading can format incompatible LittleFS volumes. Neither is a safe default
hardware test. Missing peripherals are recorded as untested and do not block
software implementation of later groups. No firmware install, project upload,
flash erase or format is authorized by this development task.

Out of scope: robot-specific additions, USB Smart Pin modes, DMA enhancements
and external-clock acquisition. SD boot-pin sharing must never bypass the
reserved-pin policy. Third-party code retains its license and attribution.

## Baseline audit

The native FlexC port already implements raw/friendly Smart Pins, independent
UART TX/RX pins, synchronous serial words, I2C/SPI, calibrated ADC/DAC,
capture and physical worker cogs. Standard serial and external NeoPixel
primitives are currently stubs. The bundled upstream BME680 library already
uses the native gas compensation primitive. More detailed acceptance and
remaining gaps are recorded below as each group is completed.

## WS2812 (group 1)

`P2 LEDs` is an optional library (Libraries / P2), not another automatic
palette. It provides initialization, one-based individual pixels, fill,
non-destructive brightness 0-255 and explicit update. One strip of 1-128
RGB LEDs is supported; RGBW is rejected. Initialization does not drive pins.
The existing shared `NeoPixel` library also uses this backend. Stop-all
invalidates the configured strip and floats outputs through normal VM cleanup.
The update is a short bounded synchronous operation; the IDE receiver remains
on its separate cog. Timing-critical bits use cached PASM, not interpreted C.

Use a suitable logic-level shifter for a 5 V strip, common ground, and an
external supply sized for the LEDs; do not power a strip from a GPIO. Start
with low brightness. `Examples/P2/leds.ubp` requires explicit clicking and
assumes DIN P8, avoiding the owner's P0-7 loopback pairs.

Acceptance: all three FlexC variants compile. Host tests execute production C
for GRB ordering, full/half brightness without color loss, fill, shared API,
invalid ranges, all Edge32 reserved pins and stop cleanup. The pinned editor
loads the optional library normally and compiles the example. No LED or
oscilloscope is connected: electrical behavior and pulse widths are unverified.
The installed Edge32 is still the previous firmware; these new primitives
require installing a new image after the owner approves preservation/replacement.

The 2026-11-05 read-only preflight found v405 Edge32, 120 stored code chunks,
and matching repeated CRCs. Reset, upload, execution and flash writes were not
requested; other filesystem contents remain unknown.

## SSD1331 (group 2)

`P2 Displays` adds a 96x64 SSD1331 OLED with five explicit distinct pins,
zero-based pixels, RGB24 colors, hardware lines and outlined/filled rectangles,
and cooperative ASCII text (5x7 shared font, opaque 6x8 cells). The text block
yields between characters and stops at the right/bottom boundary. The OLED
uses its own SPI output pins, independently of the generic I2C/SPI defaults.
Initialization has no effect until the block is explicitly run. Stop-all
invalidates the display; initialize again before drawing.

`Examples/P2/oled.ubp` uses P8-12 and requires clicking. Confirm breakout
voltage requirements and common ground before connecting. No framebuffer or
large allocation is added. Only SSD1331 96x64 RGB mode is implemented here;
other controllers, rotations and readback are not implied.

All variants compile; production C host tests verify initialization commands,
RGB565 pixel data, line/rectangle color bytes, glyph layout, coordinate limits,
invalid/duplicate/reserved pins and cleanup. The real pinned editor imports
and compiles the library and example. A physical OLED is unavailable, so
display appearance and SPI electrical timing remain unverified. Firmware was
not installed on the owner's P2.

The initialization sequence adapts the MIT Parallax reference; attribution
and its full license are retained under `third_party/parallax-peripherals/`.

## Buffered UART (group 3)

`P2 Peripherals` opens one full-duplex 8N1 UART on explicit RX/TX pins and a
free physical cog 2-7. Baud is conservatively bounded to 3000-115200 because
the Smart Pin integer period must fit 16 bits at 180 MHz. Each direction has
a 255-byte usable ring. The producer and consumer publish aligned HUB indices
after byte access; no VM objects or allocation occur in the worker. The
software RX overflow reporter counts dropped newest bytes. It cannot detect
bytes lost before polling the hardware receive buffer, or establish framing
error rates. Physical throughput and concurrent-VM timing remain untested.

Queue-byte returns false when full; next-byte returns -1 when empty. Close
discards queued output and input. Reassigning either pin stops the owning cog
and waits for it to float both pins before the main cog configures them.
Stop-all also closes it. Reserved pins and duplicate RX/TX are rejected before
touching any pins. Failure to acquire a cog returns false.

The shared standard `serial:open/close/setPins/read/readInto/write/writeBytes`
API uses the same backend; explicit setPins is required before open. Existing
unbuffered P2 Serial blocks retain their behavior. MIDI/DUELink are still
unsupported. The optional UART example uses P8/P9 and has no start hat.
Tests execute production ring, conversion and validation code through several
wraps, simultaneous independent RX/TX queues, overflow, backpressure, binary
0/255 bytes, offset writes, pin reassignment and close. Native cog/Smart Pin
code is separately compiled for all variants; no new firmware is installed.

## General files (group 4)

`P2 Storage` exposes readiness, append, size, open/read/close and delete.
The existing shared `Files` primitive names use the same backend, including
line/byte reads, seek and file listing. One read cursor is retained; opening
another file closes it. Binary append/read calls are bounded to 512 bytes;
line reads return at most 255 bytes. Append does not truncate existing data.
Missing files/read failures return false or -1; callers should check results.

Flat user names (1-48 ASCII letters/digits/dot/underscore/hyphen) map only to
`/flash/user-<name>`. Traversal, slashes, backslashes, drive names and leading
dots are rejected. Even the name `ublockscode` maps to a separate user file.
Program storage, boot firmware and raw flash are not exposed. The candidate
mount disables automatic formatting; an incompatible or absent LittleFS
volume is unavailable. There is deliberately no format block. The reviewed
revision-8 installer remains unchanged and retains its existing flash warning.

Production C host tests exercise binary append/read, repeated appends, cursor
retention, EOF continuation, size limits, mount failure, deletion and program
file isolation using disposable host files. Real LittleFS flash persistence,
capacity exhaustion and power-loss behavior remain untested for this API.
`Examples/P2/files.ubp` only reads an existing file and does not write/delete.

SD is not exposed. The toolchain's SD convenience API defaults to reserved
P58-61, and there is no confirmed external SD module on four user pins. A
future SD adapter needs explicit user-pin validation, non-formatting FAT mount,
bounded transfer/timeouts and a new resource/physical test; default boot-pin
sharing is prohibited. No SD device or card data was touched.

## Reference sources

Reviewed Parallax [Solo](https://github.com/parallaxinc/solo/tree/7f4644b95cf75115175ed0fe11ab9bbc8c66549a)
and [Simple-Libraries](https://github.com/parallaxinc/Simple-Libraries/tree/1cc167c103756e5772b533c833a0f34e6050f459).
Solo's generic categories include RGB LEDs, OLED/ePaper, serial, sensors,
storage, graphing and WAV. Robot-specific APIs are outside this port.
The Simple-Libraries WS2812 driver is MIT licensed, Propeller 1-specific and
starts a separate PASM cog. Its API/timing constants inform the audit; the P2
implementation here is newly written and uses the existing VM main cog.
No Simple-Libraries driver source is copied for group 1.
