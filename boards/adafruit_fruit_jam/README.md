# Adafruit Fruit Jam target specification

Product 6200: RP2350B, 16 MiB flash, 8 MiB PSRAM. The owned board is available.
The [initial target source](smallvm/README.md) now includes the board definition,
USB transport, SmallVM, an isolated Arduino variant, extension I/O and program
snapshots. **Physical SWD programming, binary USB, arithmetic/editing, 50 ordered
serial outputs, stop/variable inspection, reconnect and reboot/autostart pass.**
The real graphical IDE passes arithmetic/editing and final count 50 through a
loopback USB bridge. It is not yet hosted by Fruit Jam over Wi-Fi.
Do not flash another RP2350 board or either connected Waveshare port as a substitute.
Waveshare source, installed firmware and evidence remain unchanged.

The development branch starts at `8616af6`. The selected development route is
[Pico 2 W SWD programming](../../docs/FRUIT_JAM_SWD.md), with a specifically
adapted probe image. The user authorized replacement, the original 16 MiB flash
was backed up privately, and corrected GP2/GP3 probe wiring programs and verifies
the board at 4 MHz. See the [physical installation evidence](../../evidence/2026-10-18/fruit-jam/physical-installation.json).

## Software target requirements

- Use the pinned Zephyr RP2350B Cortex-M33 support, a new out-of-tree board
  definition and the existing verified SmallVM v417 preparation/runtime.
- First deliver binary MicroBlocks over native USB CDC with a separate logging
  path. Never mix debug text into the VM stream. Bound VM work as on Waveshare.
- Link the actual pinned ArduinoCore-Zephyr module with a schematic-derived
  variant; do not import Arduino-Pico firmware as if it were a Zephyr module.
- Reserve onboard pins; extension I/O may only use GPIO6/7/10 and GPIO40..45.
  GPIO8/9 are shared with the ESP32-C6 UART. ADC A0 is GPIO40 on the JST-PH
  connector; the other five ADCs are GPIO41..45. GPIO numbers above 31 require
  the RP2350B high GPIO bank, not ESP32-style GPIO access.
- Keep boot quiet, with no automatic audio, SD formatting, coprocessor firmware
  replacement or unrequested reset of the shared Wi-Fi/audio reset signal.
- Separate app/program-storage partitions. Add a local software BOOTSEL request
  only after the USB/persistence lifecycle is defined; SWD remains recovery.

## Hardware support matrix at this checkpoint

“Driver available” means source exists in pinned Zephyr; it is not a build or
physical PASS for Fruit Jam. The canonical [manifest](hardware.json) records
the narrower measured scope for each feature.

| Hardware | Verified connection/reference | Current software boundary |
|---|---|---|
| RP2350B / flash / SWD | Cortex-M33, 16 MiB flash; dedicated JST-SH SWCLK/GND/SWDIO | Backup/program/verify pass; historical four-chunk/autostart-42 checks passed. Current saved arithmetic chunk 0 survives coprocessor restoration |
| Native USB-C | MCU native USB, device/power/ROM boot | Exclusive binary VM CDC and real IDE bridge pass; no console mixed into the protocol |
| 8 MiB PSRAM | Shared XIP bus, second chip select GPIO47 | No Fruit Jam PSRAM integration; begin with internal SRAM |
| DVI output | HSTX GPIO12..19 | No matching display driver found in pinned Zephyr; new HSTX/DMA integration needed |
| TLV320DAC3100 speaker/headphones | I2S data24/MCLK25/BCLK26/WS27; IRQ23; reset22 | Codec driver family exists; no matching RP2350 I2S driver found; audio remains missing/quiet |
| ESP32-C6 AirLift | SPI1 MISO28/SCK30/MOSI31, CS46, BUSY3, BOOT9/IRQ23, reset22; UART8/9 | Official NINA 3.3.0 restored; version/MAC/status queries pass. MAC text order needs correction; association and socket service pending |
| Two USB-A ports / CH334F hub | PIO host D+1/D-2, power11; third hub port on header | Generic hub support alone is insufficient; no matching PIO USB host controller found |
| microSD | SPI0 SCK34/MOSI35/MISO36/CS39, detect33; SDIO37/38 | SPI/FatFS building blocks exist; board integration and bounded read-only acceptance pending |
| Five NeoPixels | GPIO32 | Dedicated PIO1/base16 driver; five positions, red/green/blue and off confirmed by the user after a brief 8/255 pattern |
| Three buttons | GPIO0/4/5; button1 also RP2350 USB boot; C6 BOOT9 is GPIO23 | Input-only primitives return released state; actual press acceptance pending |
| Red LED / IR receiver | Shared GPIO29; LED active low | Modes must be mutually exclusive; no IR decoder claimed |
| STEMMA QT / codec I2C | I2C0 SDA20/SCL21 | Native adapter compiled; no successful physical transaction claimed. External SHT4x investigation cancelled; no automatic access |
| Extension / JST-PH analog | GPIO6/7/10; ADC0..5 on GPIO40..45 | Safe variant and GPIO/ADC/PWM cross-built; per-pin mux source reviewed, physical tests pending; no DAC |
| Power / reset / debug | On/off switch, USB supply, main RUN separate from GPIO22 | Documented; do not treat power switch as GPIO or periph-reset as MCU reset |

The guide has a contradictory SD detect line (GPIO34, also SD clock). The official
Adafruit firmware pin table says GPIO33; the schematic is the authority for the
new board. The guide also discusses the early A2 E9 input erratum. The owned chip reports
silicon revision 3; no marketing stepping is inferred from that number here.

## Staged acceptance

1. Cross-build board baseline, USB transport, Arduino API and SmallVM. Save exact
   dependencies, command, ELF/UF2 hashes and resource usage. Run the 32-bit VM
   harness without claiming USB or peripheral physical results.
2. When hardware is available and replacement is authorized, identify both USB
   devices, preserve current firmware/settings and validate the SWD probe at low
   speed. Load the Fruit Jam image with verification; test USB ping/arithmetic,
   one 50-output run, stop, reconnect and program persistence.
3. Validate buttons/LED sharing, ADC and extension I/O with deliberate wiring;
   NeoPixels off/low brightness, then one at a time. Read SD without formatting
   or writes. Verify I2C only against documented devices/registers.
4. Develop/test missing HSTX, PIO USB host, PSRAM and I2S paths separately. Audit
   AirLift protocol before networking; shared reset requires Wi-Fi setup before
   codec setup. Audio listening and actual display/keyboard behavior need human
   observations and traces, not a successful build alone.

The coordinated first cross-build is complete; no compilation remains running
from this task. No Ollama/GPU process was controlled here.
The prepared Arduino module is a separate local clone, so the existing Waveshare
module and its source outputs remain unchanged. See the initial target README
for exact executed build commands, pin numbers, unsupported features and storage
boundaries. The separate cross-build evidence establishes compilation; source checks alone do not establish hardware operation.

## Primary references

- [Adafruit product](https://www.adafruit.com/product/6200)
- [Official guide and pinout](https://learn.adafruit.com/adafruit-fruit-jam/pinout)
- [Official schematic revision 252dc094](https://github.com/adafruit/Adafruit-Fruit-Jam-PCB/tree/252dc09456ee447b3d7eeb4fa99877898503e81a)
- [Official CircuitPython pin table](https://github.com/adafruit/circuitpython/blob/main/ports/raspberrypi/boards/adafruit_fruit_jam/pins.c)
- Pinned local Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`: Metro RP2350B board,
  Pico GPIO/ADC/PWM/USB/PIO drivers and TLV320DAC310x codec sources.
