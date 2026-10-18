# Fruit Jam physical USB checkpoint

The owned Fruit Jam runs Zephyr and SmallVM v417 through its native USB port.
The user authorized firmware replacement. A complete original 16 MiB flash
backup remains private. The Pico 2 W probe uses GP2 SWCLK, GP3 SWDIO and GND;
its own DEBUG connector is not the target output connector.

## Measured results

- Authorized SWD backup/program/verify and cold reset pass at 4 MHz. The
  RP2350 reports chip ID 0x30004927, silicon revision 3 and 16 MiB Winbond flash.
- Binary CDC arithmetic, live editing, exactly 1..50 serial outputs, fragmented
  upload, partial-frame timeout, stop/variable inspection and reconnect pass.
- Four code CRCs and startup variable 9 = 42 survive cold reset and an updated
  peripheral firmware image. Arbitrary power loss during a save is untested.
- Real graphical MicroBlocks 2.5.8 calculates 12, then 13 after an input edit.
  Its 50-repeat example shows final count 50. Exact sequence evidence belongs
  to the serial test; a screenshot of 50 alone does not establish ordering.
- PIO1/base16 NeoPixel commands complete with seven brief 8/255 patterns and
  final off. After a requested repeat at 700 ms per step, the user confirmed
  all five positions, colors and extinction. Full-brightness load is untested.
- The three buttons returned released state. Actual presses, external ADC/PWM
  waveforms and other onboard peripherals remain unverified.

The original peripheral checkpoint ELF SHA256 is
`aa748a7e23712c63c8c270ac4c743b51425577b15bb6fb5fc84327bacfad7c75`.
The [canonical manifest](../boards/adafruit_fruit_jam/hardware.json) and
[evidence folder](../evidence/2026-10-18/fruit-jam/) define the exact scope.
Build-only reports retain `hardware_validation=false` and `flashed=false`
because compilation itself did neither; separate physical reports record the
subsequent installation and tests.

## Local real-IDE bridge

The bridge serves the pinned, hash-checked real editor on loopback only. It
requires Python with pyserial and websockets, one positively identified Fruit
Jam CDC and the existing pinned IDE source directory:

```sh
python tools/serve_fruit_jam_ide.py --ide-source /path/to/upstream-ide-2.5.8 --port COM8
```

Open `http://127.0.0.1:8768/`, select Connect Fruit Jam, then Board examples.
The bridge enforces the expected USB serial, same-origin WebSocket and one
controller. Disconnect the IDE before a direct serial test. It never flashes
firmware or probes I2C. This is host-assisted USB access. The standalone
AirLift endpoint is a separate [network stage](FRUIT_JAM_NETWORK.md).

SHT40/41 work was cancelled by the user. Historical failed attempts are retained
as failures; no sensor is polled automatically and no further test is pending.
No Waveshare firmware, COM4/COM5 access or credentials were used for this work.
