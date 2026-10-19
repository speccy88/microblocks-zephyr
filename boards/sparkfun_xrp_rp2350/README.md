# SparkFun production XRP RP2350 target

This target is for ROB-26619 with discrete RP2350B/RM2, not the Pico W beta.
Its primary schematic, part/pin checks and license hashes are recorded in
[`dependencies/xrp-production-reference.json`](../../dependencies/xrp-production-reference.json).
See the [feature parity and staged acceptance plan](../../docs/XRP_PARITY.md).

**Source-stage target; no physical XRP has been accessed or flashed.** The quiet
bring-up app only sets the eight motor inputs low (coast), reads the user button
and attempts one read-only IMU family-ID query. Servo outputs, RGB, ultrasonic
trigger and flash/settings are not driven or written. It is not SmallVM or an
XRPCode replacement. Firmware build status belongs in `hardware.json` and exact
build evidence; it is not a physical PASS.

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

The preview editor permits project editing/storage while its hardware Connect
path remains disabled. Full USB SmallVM/Arduino API, Wi-Fi live programming,
board-hosted GP and persistent configuration remain staged implementation work.
