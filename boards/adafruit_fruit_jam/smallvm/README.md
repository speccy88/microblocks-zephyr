# Fruit Jam initial USB/SmallVM application

**Source implementation only: not cross-compiled, flashed or physically tested.**
Compilation is deferred while another task runs timed GPU benchmarks. Build
instructions below are the planned command, not evidence of a successful build.

This is an out-of-tree `adafruit_fruit_jam/rp2350b/m33_0` target, pinned to Zephyr
`a915b2f12675b48b16d56653ea145dcd8f20cbbf` and verified SmallVM v417
`2071df569623ba9cdcd6f8106b61796e047df38b`. It uses internal SRAM; PSRAM is absent
from the memory map. No substitute board has been used.

## Initial behavior

- One native USB CDC port owns the official binary MicroBlocks protocol.
  Console, printk, shell and logging are disabled. Debugger-visible
  `fruit_jam_status` records startup errors. A host opening DTR does not restart
  the VM. Reconnection clears software transport buffers, preserving program
  state; overflow resets the partial protocol stream from the VM thread.
- The bounded interpreter runs `vmSlice(16)` then yields for 1 ms. The Fruit Jam
  build also checks digital opcode arity before accessing arguments.
- The actual pinned ArduinoCore-Zephyr module is linked, using a separate local
  prepared copy. Its safe variant and per-pin ADC/PWM mux repair leave the
  existing Waveshare checkout unchanged. No device-wide ADC/PWM reinitialization
  happens on pin changes. Boot pinctrl states for ADC/PWM are empty.
- MicroBlocks D0..D8 and Arduino D0..D8 map to GPIO6,7,10,40,41,42,43,44,45.
  Analog inputs 0..5 / Arduino A0..A5 map to GPIO40..45 (D3..D8), reporting
  0..1023. ADC pull modes return unsupported. PWM uses 1 kHz on the nine
  extension pins; moving back to digital/analog releases that pin's PWM.
- Button A/B read physical buttons 2/3 (GPIO4/5). Primitive
  `[fruitJam:buttonPressed]` accepts 1..3 for GPIO0/4/5. Button 1 also controls
  boot modes and is input-only. `[fruitJam:ioCapabilities]` reports pin mapping
  and the untested hardware boundary.
- Native I2C primitives use shared I2C0 GPIO20/21. Reads, writes and bounded
  deferred write/read transactions use the prior v417 adapter contract. There
  is no automatic scan, codec configuration or coprocessor reset. A library and
  VM script must not concurrently own an I2C transaction.
- The VM keeps a 64 KiB RAM code store. Two CRC-checked snapshots use a separate
  final 256 KiB flash partition, with a header written after payload. Saves are
  debounced for two seconds, restoring the prior valid generation after a
  partial write. Live variable values/task stacks are not persisted.

The mapped flash layout is: image-definition block `0x000000..0x0000ff`, app
`0x000100..0x3fffff`, program store `0xfc0000..0xffffff`. The intervening flash is
unassigned. Program-store data is not a loadable firmware section. ELF segment
bounds, actual flash writes, USB pauses during XIP flash writes and interrupted
save/reconnect behavior still require build/physical acceptance.

Display/HSTX, PIO USB host, PSRAM, AirLift Wi-Fi/BLE, SD, NeoPixels, audio and IR
are unavailable. The red LED shares GPIO29 with IR, so the initial application
does not drive it. Raw SPI returns unsupported; SD and AirLift buses are not
exposed as generic SPI. Arduino Serial is a stub with printk disabled, because
USB belongs to the VM; arbitrary serial-dependent libraries are not supported.
No audio, SD writes or GPIO22 reset occur at startup.

Extension numbers are logical, so D0 here is the socket's printed D6. Use this
mapping rather than treating a MicroBlocks number as an RP2350 GPIO number:

| Logical pin | MCU GPIO | Physical extension |
|---|---|---|
| D0 | 6 | JP3 pad15 (printed D6) |
| D1 | 7 | JP3 pad13 (printed D7) |
| D2 | 10 | JP3 pad7 (printed D10) |
| D3 / A0 | 40 | JST-PH analog input; absent from JP3 |
| D4 / A1 | 41 | JP3 pad25 |
| D5 / A2 | 42 | JP3 pad23 |
| D6 / A3 | 43 | JP3 pad21 |
| D7 / A4 | 44 | JP3 pad19 |
| D8 / A5 | 45 | JP3 pad17 |

## Prepare and build, after the benchmark window

The local workspace already contains the pinned Zephyr dependencies, Arm
toolchain and verified SmallVM source. The Arduino preparation command creates
a new directory and refuses to overwrite an existing prepared copy. It reads
only local sources/API blobs; it does not fetch or flash anything.

```sh
cd /home/fred/microblocks-zephyr-work
repo=/mnt/c/Users/fred_/Documents/Codex/2026-10-17/task-5/microblocks-zephyr
task=/mnt/c/Users/fred_/Documents/Codex/2026-10-17/task-5
export PATH="$PWD/.venv/bin:$PWD/tools/host/usr/bin:$PATH"
export ZEPHYR_BASE="$PWD/zephyr"
export ZEPHYR_SDK_INSTALL_DIR="$PWD/tools/zephyr-sdk-1.0.1"
export CMAKE_BUILD_PARALLEL_LEVEL=4
python "$repo/tools/prepare_fruit_jam_arduino.py" \
  --source references/arduino-api --output build/arduino-fruit-jam
west build -b adafruit_fruit_jam/rp2350b/m33_0 -d build/fruit-jam \
  "$repo/boards/adafruit_fruit_jam/smallvm" -- \
  -DZEPHYR_EXTRA_MODULES="$PWD/build/arduino-fruit-jam" \
  -DFRUIT_JAM_ARDUINO_DIR="$PWD/build/arduino-fruit-jam" \
  -DSMALLVM_SOURCE_DIR="$task/upstream-smallvm-v417-snapshot"
```

On this workstation the isolated Arduino copy has already been prepared; begin
with `west build` after coordination. Save exact logs and ELF/UF2 hashes. Inspect
the ELF load segments against the flash layout and verify real Arduino symbols.
Run the 32-bit protocol/I/O harness with the Fruit Jam adapter, then update the
manifest's compilation state. A successful compile still does not establish
physical USB, flash persistence, pin mux or peripheral operation.

Any later programming requires the user's separate authorization and a backup
of the positively identified target. See the [SWD guide](../../../docs/FRUIT_JAM_SWD.md).
