# Fruit Jam initial USB/SmallVM application

**Cross-build, mock VM and the physical USB/VM baseline pass.**
The native network/IDE image was programmed and verified with authorized SWD access.
Its linker allocation is 3,625,484 bytes of flash and 253,768 bytes of internal
RAM; runtime usage has not been measured. Graphical arithmetic/editing work
through the local USB bridge. The native service and 147 real editor assets
compile; standalone acceptance is pending after network timeouts. See
[the measured checkpoint](../../../docs/FRUIT_JAM_NATIVE_IDE.md).
ELF and UF2 inspection identify RP2350 ARM Secure images.
See the [build evidence](../../../evidence/2026-10-18/fruit-jam/target-build-verification.json).

This is an out-of-tree `adafruit_fruit_jam/rp2350b/m33_0` target, pinned to Zephyr
`a915b2f12675b48b16d56653ea145dcd8f20cbbf` and verified SmallVM v417
`2071df569623ba9cdcd6f8106b61796e047df38b`. It uses internal SRAM; PSRAM is absent
from the memory map. No substitute board has been used.

## Initial behavior

- One native USB CDC port and the bounded WebSocket path share the binary
  MicroBlocks protocol with one controller. USB DTR takes priority.
  Console, printk, shell and logging are disabled. Debugger-visible
  `fruit_jam_status` records startup errors. A host opening DTR does not restart
  the VM. Reconnection clears software transport buffers, preserving program
  state; overflow resets the partial protocol stream from the VM thread.
- The bounded interpreter runs `vmSlice(16)` then yields for 1 ms. The Fruit Jam
  build also checks digital opcode arity before accessing arguments.
- The actual pinned ArduinoCore-Zephyr module is linked, using a separate local
  prepared copy. Its safe variant and per-pin ADC/PWM mux repair leave the
  existing Waveshare checkout unchanged. No device-wide ADC/PWM reinitialization
  happens on pin changes. A small C bridge keeps Pico SDK headers out of the
  minimal C++ library. Boot pinctrl states for ADC/PWM are empty.
- MicroBlocks D0..D8 and Arduino D0..D8 map to GPIO6,7,10,40,41,42,43,44,45.
  Analog inputs 0..5 / Arduino A0..A5 map to GPIO40..45 (D3..D8), reporting
  0..1023. ADC pull modes return unsupported. PWM uses 1 kHz on the nine
  extension pins; moving back to digital/analog releases that pin's PWM.
- Button A/B read physical buttons 2/3 (GPIO4/5). Primitive
  `[fruitJam:buttonPressed]` accepts 1..3 for GPIO0/4/5. Button 1 also controls
  RP2350 USB boot and is input-only. ESP32-C6 BOOT9 is on GPIO23.
  `[fruitJam:ioCapabilities]` reports pin mapping
  and the untested hardware boundary.
- Native I2C primitives use shared I2C0 GPIO20/21. Reads, writes and bounded
  deferred write/read transactions use the prior v417 adapter contract. There
  is no automatic scan, codec configuration or coprocessor reset. A library and
  VM script must not concurrently own an I2C transaction.
- The VM keeps a 64 KiB RAM code store. Two CRC-checked snapshots use a separate
  final 256 KiB flash partition, with a header written after payload. Saves are
  debounced for two seconds, restoring the prior valid generation after a
  partial write. Live variable values/task stacks are not persisted.

The mapped flash layout is: app `0x000000..0x3fffff`, including the SoC linker’s
RP2350 image-definition block, and program store `0xfc0000..0xffffff`. The intervening flash is
unassigned. Program-store data is not a loadable firmware section. ELF segment
bounds exclude the program store. Actual flash writes, USB pauses during XIP
flash writes have physical reboot/CRC evidence; arbitrary power-loss timing
during a save remains untested.

NeoPixels use an isolated PIO1/base16 implementation. The user confirmed the
five positions, red/green/blue and final off after brief 8/255 patterns.
All three buttons pass isolated press/release checks. Native AirLift SPI
identification and user-triggered association/DHCP pass after official NINA
3.3.0 restoration; the canonical MAC formatter is corrected and physically
verified. [USB-local setup](../../../docs/FRUIT_JAM_WIFI_SETUP.md) keeps
credentials outside VM bytecode and snapshots. USB arithmetic, reconnect and
the current program CRC remain intact during and after association.
Display/HSTX, PIO USB host, PSRAM, BLE, SD, audio and IR remain unavailable.
AirLift TCP/HTTP/WebSocket service and real editor assets are compiled and
installed; one HTTP status response passed, but subsequent timeouts leave
standalone acceptance pending. Read-only `networkStatus` exposes progress.
The explicitly requested coprocessor restoration is
tracked in [the restoration record](../../../docs/FRUIT_JAM_AIRLIFT_RESTORE.md).
SHT4x source is dormant, its library blocks removed, and further
sensor diagnosis is cancelled. The red LED shares GPIO29 with IR, so the initial application
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

## Reproduce the verified build

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
  --source references/arduino-api --output build/arduino-fruit-jam-cbridge
west build -b adafruit_fruit_jam/rp2350b/m33_0 -d build/fruit-jam \
  "$repo/boards/adafruit_fruit_jam/smallvm" -- \
  -DZEPHYR_EXTRA_MODULES="$PWD/build/arduino-fruit-jam-cbridge" \
  -DFRUIT_JAM_ARDUINO_DIR="$PWD/build/arduino-fruit-jam-cbridge" \
  -DSMALLVM_SOURCE_DIR="$task/upstream-smallvm-v417-snapshot" \
  -DIDE_SOURCE_DIR="$task/upstream-ide-2.5.8"
```

On this workstation the isolated Arduino copy already exists. Exact logs,
resource samples, dependency hashes and ELF/UF2 hashes are retained in the
evidence folder. The actual Arduino Wire, pinMode and analogRead symbols are
linked. The 32-bit harness passes ten arithmetic runs, 50 ordered outputs,
fragmentation/timeout recovery and 83 I/O checks (32 bulk-I2C checks included).
These use simulated hardware, not Zephyr USB/GPIO drivers.

```sh
python "$repo/tools/test_fruit_jam_vm.py" \
  --source "$task/upstream-smallvm-v417-snapshot" \
  --wasi-sdk "$PWD/tools/wasi/opt/wasi-sdk" \
  --evidence "$repo/evidence/2026-10-18/fruit-jam/vm-harness.json"
```

The [physical USB baseline](../../../evidence/2026-10-18/fruit-jam/physical-usb-baseline.json)
and [peripheral-update persistence](../../../evidence/2026-10-18/fruit-jam/physical-peripheral-update-persistence.json)
record actual hardware results. Compile and mock results alone do not establish
peripheral operation. Native HTTP assets and VM WebSocket checks now pass, with
[exact network acceptance](../../../docs/FRUIT_JAM_NATIVE_IDE.md) and separate
boot/credential limits. HSTX, host USB, audio and other missing features remain
as listed above.

Any later programming requires the user's separate authorization and a backup
of the positively identified target. See the [SWD guide](../../../docs/FRUIT_JAM_SWD.md).
