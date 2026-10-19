# SparkFun production XRP RP2350 target

This target is for ROB-26619 with discrete RP2350B/RM2, not the Pico W beta.
Its primary schematic, part/pin checks and license hashes are recorded in
[`dependencies/xrp-production-reference.json`](../../dependencies/xrp-production-reference.json).
See the [feature parity and staged acceptance plan](../../docs/XRP_PARITY.md).

**Both the quiet baseline and integrated non-actuating SmallVM app cross-build; neither has been installed on this XRP.**
A read-only USB/SWD check found COM10 and a responding RP2350 debug fabric; no
CPU halt, reset, flash probe or memory write was requested.
The baseline below remains available independently. The quiet
bring-up app only sets the eight motor inputs low (coast), reads the user button
and attempts one read-only IMU family-ID query. Servo outputs, RGB, ultrasonic
trigger and flash/settings are not driven or written. It is not SmallVM or an
XRPCode replacement. Firmware build status belongs in `hardware.json` and exact
build evidence; it is not a physical PASS. The baseline uses 40,188 flash bytes
and 18,656 linker-allocated RAM bytes. ELF/UF2 ARM Secure identity and all load
addresses were verified against the application partition. See
[the exact build/source evidence](../../evidence/xrp-bringup-build-verification-2026-10-19.json).

The target uses Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`, internal
SRAM and a separate RP2350B board definition. GPIO32..47 use `gpio0_hi` indices
0..15. I2C0 is GPIO4/5, I2C1/IMU GPIO38/39. The RM2 definition adapts the pinned
RP2350B Plus W PIO driver to power26/CS27/CLK28/shared DATA+IRQ29. PIO0 is
reserved for radio; RGB/encoder PIO resources must be allocated separately.
PSRAM CS47 is documented but PSRAM is not mapped. No BLE capability is claimed.

The production schematic uses dual-input DRV8411A control. Left34/35,
right32/33, motor3 20/21, motor4 10/11 must not use beta phase/enable code.
The overview calls the IMU LSM6DSO; the schematic says LSM6DSOX. Read-only
WHO_AM_I 0x6C establishes family compatibility only. Physical part/driver,
motor direction, servo limits and all sensor calibration remain unverified.

Build with the repository's pinned Zephyr SDK/workspace:

```sh
west build -b sparkfun_xrp/rp2350b/m33_0 -d build/xrp-bringup \
  /path/to/microblocks-zephyr/boards/sparkfun_xrp_rp2350/bringup
```

This command builds only; do not run a flash command against an unidentified
robot or another RP2350. Installing requires verified robot identity, private
backup/recovery and a separate concrete installation decision. Motion testing
also requires confirmed safe physical placement. Preserve existing Fruit Jam
and Waveshare images/programs. The current Fruit Jam CRC is `651a01da`.

The preview editor uses the actual pinned production `XRP.ubl` library (not
`XRP Beta.ubl`) and permits project editing/storage while its hardware Connect
path remains disabled. Its upstream motor/servo/sensor functions do not establish
Zephyr driver support. USB SmallVM/Arduino API, RM2/AIROC, board-hosted GP/WebSocket and common persistent
configuration now cross-build together in `smallvm/`. Runtime/hardware validation
remains pending; the Pages preview still rejects hardware connection.


## Integrated development image

The verified image uses **4,008,592 flash bytes** and **362,768 linker RAM bytes**.
It links 147 real GP assets occupying 3,511,116 flash bytes. These are cross-build
measurements, not a physical boot or performance result.

See [the integration contract](../../docs/XRP_INTEGRATION.md) and
[build/image evidence](../../evidence/xrp-smallvm-build-verification-2026-10-19.json).
The app uses internal SRAM, raw production GPIO numbering, default Wire/I2C1
GPIO38/39, ADC GPIO40..46, encoder interrupts and bounded ultrasonic echo capture.
Motor inputs stay low/coast; motor/servo writes fail through both the VM and
Arduino core. RGB, PSRAM and BLE remain unavailable. No actuator unlock exists.

Prepare a new isolated Arduino module and only the two verified external RM2
blobs, then build with the pinned Zephyr workspace/SDK (replace source paths):

```sh
python3 tools/prepare_xrp_arduino.py --source "$arduino_source" --output "$arduino_xrp"
python3 tools/prepare_xrp_radio.py --hal "$hal_infineon" --fetch
west build -b sparkfun_xrp/rp2350b/m33_0 -d build/xrp-smallvm \
  "$repo/boards/sparkfun_xrp_rp2350/smallvm" -- \
  -DZEPHYR_EXTRA_MODULES="$arduino_xrp" -DXRP_ARDUINO_DIR="$arduino_xrp" \
  -DSMALLVM_SOURCE_DIR="$smallvm_snapshot" -DIDE_SOURCE_DIR="$ide_source"
```

Wi-Fi joining/persistence runs off the VM thread. USER held at startup skips
saved-network joining without erasing the program/settings. MBNW v2 setup is
USB-only; no HTTP credential endpoint exists. Once joined, the same-origin
native editor uses `ws://<board-ip>/ws/vm`; USB preempts its single controller.
The native editor and setup flow have not been exercised on this XRP.

Before installation, preserve the existing full image and user files/settings,
verify recovery, select the deployment Wi-Fi country and confirm the RM2 radio
resource configuration. Installation still requires explicit authorization;
robot motion requires a later safe-placement/readiness decision. The detected
COM10 identity describes the existing image, not a presumed post-install port.
