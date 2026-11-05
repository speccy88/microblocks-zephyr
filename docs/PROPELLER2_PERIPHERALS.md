# P2 optional peripherals: implementation and acceptance

This work adds focused, opt-in P2 LEDs, Displays, Peripherals, Storage,
Sensors and Audio libraries. The existing five automatic P2 libraries and
their saved selectors remain compatible. Shared MicroBlocks libraries are
preferred to duplicate sensor/math/protocol implementations.

## Contract

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

## References and licensing

Reviewed Parallax [Solo](https://github.com/parallaxinc/solo/tree/7f4644b95cf75115175ed0fe11ab9bbc8c66549a)
and [Simple-Libraries](https://github.com/parallaxinc/Simple-Libraries/tree/1cc167c103756e5772b533c833a0f34e6050f459).
Solo's generic categories include RGB LEDs, OLED/ePaper, serial, sensors,
storage, graphing and WAV. Robot-specific APIs are outside this port.
The Simple-Libraries WS2812 driver is MIT licensed, Propeller 1-specific and
starts a separate PASM cog. Its API/timing constants inform the audit; the P2
implementation here is newly written and uses the existing VM main cog.
No Simple-Libraries driver source is copied for group 1.
