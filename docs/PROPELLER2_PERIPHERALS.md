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

## Environmental sensors (group 5)

`P2 Sensors` reuses the portable MicroBlocks BME680 library (as a hidden
implementation dependency), with explicit SDA/SCL and 0x76/0x77 address,
presence and chip-ID checks before configuration. Temperature is Celsius x10,
humidity percent x10, pressure mbar x10; gas is reported in ohms with 10-ohm
steps. The existing native gas-compensation primitive is reused.

The canonical portable source is `libraries/sensors/BME680.ubl`, derived from
the hash-verified pinned upstream asset with authorship/MPL notice preserved.
It corrects signed 8/16-bit endpoints, H1's low nibble, heater calibration's
malformed list update/premature return, signed gas-error nibble at register
0x04 and zero-based gas range. Pinned-parser register fixtures verify these
fields, including negative calibration values and range 15. These tests do
not establish sensor accuracy or validate every compensation/heater path.

DHT22 has a bounded native reader with a weak released line, 120-us pulse
timeouts, checksum, sign decoding and value bounds. It returns a list
`[temperature x10, humidity x10]`, or false on failure. One cached sensor slot
limits capture to once per two seconds, including failed attempts; changing
pins during that interval returns false. Allow two seconds after power-up.
Use an external pull-up to 3.3 V; never pull a P2 input up to 5 V. Each attempt
blocks the main interpreter for several milliseconds at most; IDE RX remains
separate. Host pulse fixtures execute production capture/decoding code for
valid, negative, invalid-checksum and stuck-line cases. Wire timing is untested.

`Examples/P2/environment.ubp` has separate click-only examples. Neither sensor
is confirmed connected, and no new firmware or sensor command was sent to the
board. All variants compile. The older upstream DHT11/DHT22 capture library
is not enabled by this work; use the new explicit P2 DHT22 block.

Protocol references: [Adafruit's DHT driver](https://github.com/adafruit/DHT-sensor-library/blob/master/DHT.cpp)
and Parallax Simple-Libraries `libbme680/bme680_begin.c` at the audited revision.

## Inertial sensors (group 6)

The portable `libraries/sensors/Inertial.ubl` supplies I2C LIS3DH and LSM9DS1
drivers. `P2 Sensors` wraps bus-pin selection and exposes their vector reads.
Importing the P2 library hides implementation palettes; the portable library
can also be imported directly. Register fixtures execute the production GP
parse trees with a simulated bus, not a real VM or sensor.

LIS3DH uses 50 Hz high-resolution mode, BDU, and selectable nominal 2/4/8/16 g
ranges. Read returns x/y/z in mg or false when uninitialized/not ready/read
fails. LSM9DS1 configures 119 Hz accelerometer/gyro at 2 g/245 dps, continuous
10 Hz 4-gauss magnetometer, BDU and register auto-increment. Acceleration is
mg, gyro millidegrees/second, magnetometer nT. Vector reads are six-byte bursts.
Offsets, alignment, scale error and hard/soft iron are not calibrated; no
orientation/fusion, FIFO, interrupt or tilt-compensation feature is claimed.

Tests cover wrong IDs without configuration writes, negative/positive axes,
LIS3DH range factors, all LSM9DS1 units, missing data and short bus reads.
The pinned editor imports dependencies and compiles all functions/examples
within the upload chunk limit. Native firmware is unchanged from group 5 and
compiles for all variants. Neither physical sensor was accessed.
`Examples/P2/inertial.ubp` runs only on explicit clicks.

Register and sensitivity references: ST [LIS3DH datasheet](https://www.st.com/resource/en/datasheet/lis3dh.pdf)
and [LSM9DS1 datasheet](https://www.st.com/resource/en/datasheet/lsm9ds1.pdf).

## IL3820 ePaper (group 7)

`P2 Displays` can select an IL3820 128x296 monochrome panel instead of the
SSD1331. This is specifically the Parallax reference full-update configuration
and 30-byte LUT, not a universal SSD16xx/ePaper driver. Confirm the controller,
panel dimensions and LUT compatibility before use. Partial refresh, alternate
panels, temperature LUT selection and sleep management are not implemented.
The reference sequence/LUT retain the Parallax 2018 MIT notice.

Explicit initialization uses six distinct user pins, with busy as input.
The buffer is 4736 bytes, white bits 1, MSB first within each row byte. Clear,
pixel, bounded Bresenham line and 5x7 text edit the buffer; explicit update
uploads 37 chunks of 128 bytes and yields between chunks. Reset delays and
busy polling are cooperative; 500 polls at 10 ms bound each busy wait. Update
returns false for timeout, stopped/reassigned pins or rejected transfers.
One external display is selected at a time; serialize display calls. Reusing
a display pin invalidates the configuration, and stop-all requires reinit.

Production C host tests check command/data flags, transfer bounds, busy-pin
configuration/reassignment and reserved/duplicate pins. Pinned-parser fixtures
verify framebuffer corners, line pixel count, glyph pixels, LUT length,
exact frame pages and busy/invalid-state timeout. All functions/examples
compile in the real pinned editor within chunk limits. No panel is confirmed
connected: waveform suitability, visible refresh, ghosting and update duration
remain untested. No board firmware was installed.

Use `Examples/P2/epaper.ubp` only with the documented matching panel and wiring.

## NMEA GPS (group 8)

The bundled upstream GPS-NEO7M library already supplied NMEA RMC/GGA/GSV,
fixed-point coordinates and freshness tracking. It is reused as canonical
portable `libraries/sensors/NMEA.ubl`, with original selectors/authorship kept.
The P2 wrapper uses the buffered UART, explicit RX/TX pins and 9600 8N1 on a
free cog. Import does not open the port. It shares the one secondary UART;
close GPS before another serial device. Call update regularly (example: 100 ms)
and check valid-position before reading coordinates. Coordinates are degrees
x1,000,000; altitude cm. Nothing compiles native code per project edit.

Integration fixes explicitly open the UART after setting pins, require exactly
two valid checksum hex digits, bound sentence length to 96 characters, reject
invalid coordinate digits/hemispheres/minutes/ranges, clear fix immediately on
GGA quality zero, and map two-digit dates using the 1980-2079 pivot. Existing
distance-expression syntax and a parameter-shadow warning were also corrected
so the full portable library compiles. Distance/geodesy accuracy is not tested.

Pinned-parser fixtures cover known RMC/GGA checksums, position/speed/altitude,
negative coordinates, malformed checksum/coordinates, no-fix and stale fix.
The real pinned editor loads dependencies and compiles all functions/examples.
Native UART changes compile for all variants. No GPS, antenna, time accuracy,
satellite reception or live board execution is verified.
`Examples/P2/gps.ubp` has explicit bounded receive/update/close steps.

## 4x4 keypad (group 9)

`P2 Peripherals` initializes four row pins and four column pins from lists,
with all eight unique user pins checked before any I/O. Init is inert. Scan
drives one row low, leaves inactive rows floating and uses weak column pull-ups;
it never drives an inactive row high against another pressed key. The result
is a row-major 16-bit mask, -1 for an ambiguous diode-less ghost rectangle,
or -2 when not initialized. Stop-all invalidates the configuration.

The convenience key reporter requires the same sampled mask for 30 ms, then
returns the first standard `123A456B789C*0#D` key, empty for none, or `?` for
an invalid/ambiguous mask. Use the raw mask for multi-key applications. The
passive matrix must have no other active driver on its eight wires.

Production C tests simulate the actual connectivity graph for all 16 keys,
empty state and a three-key ghost, checking floating rows, inert init,
reserved/duplicate pins and stop. GP fixtures test debounce and labels. The
editor compiles the library and click-only `Examples/P2/keypad.ubp`; all P2
variants compile. No physical keypad or live timing is verified.

## Shift registers (group 10)

`P2 Peripherals` supports 74HC595 output (data/clock/latch) and 74HC165 input
(serial data/clock/active-low parallel load). Transfers use 1-32 bytes with
per-byte MSB/LSB selection; the first byte goes first through the chain. Pins,
length, data and bit order are validated before any I/O. Output accepts a
list or ByteArray; input returns a ByteArray. This avoids the VM's 31-bit
integer limit and does not change the existing Smart Pin serial blocks.

Use compatible 3.3 V logic and the device's required OE/reset/clock-inhibit
wiring. The 595 latches once after the complete transfer. Its external
outputs remain latched when the VM stops; floating P2 pins does not clear
that separate device. Transactions are bounded; no background cog is used.

Production C pin fixtures verify asymmetric patterns in both orders, input
capture, one latch, invalid data/length and duplicate/reserved pins. Native
builds and actual editor library/example compilation pass. No external chips
or electrical timing were tested. `Examples/P2/shift-registers.ubp` contains
separate click-only wiring examples.

## PING))) and PIR (group 11)

The new single-wire PING reader provides a 5-us trigger, releases the line
and measures echo high time. The transaction has a 30-ms echo timeout plus
a 200-us quiet interval, rejects implausibly short/long pulses and returns -1
on failure. The mm convenience reporter assumes 343 m/s; it does not compensate
temperature or validate real ranging accuracy. Sampling should be deliberate,
as in the 100-ms interval in `Examples/P2/ping-pir.ubp`.

PIR already needed only normal digital input. The new convenience reporter
uses that existing implementation directly, with no background task. Allow
the actual module's power-up stabilization and configure its jumpers as needed.
Check both devices' actual interface voltage; never expose a P2 input to 5 V.
The PING guide describes a 5 V supply and bidirectional signal interface;
use an interface confirmed safe for the P2 rather than assuming supply equals
signal voltage compatibility.

Host fixtures execute the production PING trigger/echo code for valid, short,
stuck-low/high and reserved-pin cases, verifying timeout and released input.
Editor/ABI checks and all native variants pass. Neither physical device,
echo timing nor motion response was tested. PIR's GPIO capability pre-existed;
PING's native backend requires the candidate firmware update.

Reference: Parallax PING))) #28015 Product Guide v2.0 (2013-02-04), protocol
5-us typical trigger, echo 115 us-18.5 ms, minimum inter-measurement quiet time
200 us. No PING driver code was copied.

## DAC WAV playback (group 12)

`P2 Audio` streams a named user file to an explicit DAC pin on a free cog
2-7. A heap-free native consumer owns the DAC pin and a 1023-sample queue;
the ordinary VM reads and queues bounded 512-byte chunks, yielding while the
queue is full. Supported PCM is unsigned 8-bit or signed little-endian 16-bit,
mono/stereo (stereo mixed to mono), 8000-22050 samples/s. Volume is 0-100%,
default 25%. Finish drains queued samples; stop and pin reassignment join the
worker and float its pin. Only one audio stream is active at a time.

The portable `WAV PCM` header parser checks RIFF/WAVE, chunk boundaries,
unknown/odd-padded chunks, PCM format, frame alignment, byte rate and file
size (up to 8 MiB); unsupported/compressed/truncated files return false.
File access shares the single retained LittleFS reader, so serialize other
file operations during playback. Playback does not create or modify files.
The existing `dacInit`/`dacWrite` primitive names also use this backend for
the supported rate range; closed writes fail instead of polling forever.

The worker uses Smart Pin DAC dithering and explicit clock deadlines, without
DMA. The blocks report empty-queue underruns and delays over one sample
period; they do not promise gapless sound, a jitter bound or Hi-Fi quality.
The true playback result means that the validated file was consumed and its
queue drained. Check the diagnostic counters separately. Synchronous flash
reads and other workloads may cause underruns. This remains unmeasured.

Use a suitable AC-coupled, high-impedance amplifier input and common ground,
with the module's actual voltage requirements. Never drive a speaker directly
from a GPIO. `Examples/P2/audio.ubp` explicitly reads an existing `sound.wav`
file and uses P16/cog 3; importing it produces no output.

Production-C host tests cover PCM decoding, stereo mixing, volume/midscale,
ring wrap/full/empty, invalid pins/rates/alignment, finish/stop and the shared
DAC API. Actual editor parser fixtures cover file headers and cooperative
queue failure/timeouts. All three native variants compile, with a build guard
reserving at least 16 KiB beyond the image for the main native stack. No new
firmware was installed: real sample cadence, audio quality, underrun rate,
amplifier circuit and audible playback remain untested.

## Interactive workflow

All these libraries remain ordinary SmallVM projects and functions. A native
firmware update is needed once for new primitive backends. After that, normal
editor edits, sends, starts, stops and variable inspection use VM bytecode;
there is no BlocklyProp-style native compilation/firmware load per project.
Host C tests, ABI checks, actual editor compilation and protocol fixtures do
not substitute for live editor-to-new-firmware acceptance. That gate remains
pending because the existing board program must not be replaced without
approval. The stored 120 chunks have been left intact.

## Reference audit

Reviewed Parallax [Solo](https://github.com/parallaxinc/solo/tree/7f4644b95cf75115175ed0fe11ab9bbc8c66549a)
and [Simple-Libraries](https://github.com/parallaxinc/Simple-Libraries/tree/1cc167c103756e5772b533c833a0f34e6050f459).
Solo's generic categories include RGB LEDs, OLED/ePaper, serial, sensors,
storage, graphing and WAV. Robot-specific APIs are outside this port.
The Simple-Libraries WS2812 driver is MIT licensed, Propeller 1-specific and
starts a separate PASM cog. Its API/timing constants inform the audit; the P2
implementation here is newly written and uses the existing VM main cog.
No Simple-Libraries driver source is copied for group 1.
