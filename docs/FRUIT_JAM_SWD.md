# Fruit Jam: unattended programming with a Pico 2 W

Status: software preparation only. Neither board is present. No probe or target
has been flashed, connected, reset or physically tested for this work.

Use permanent SWD wiring for development. Normal updates program the Fruit Jam
ELF through CMSIS-DAP/OpenOCD, independently of the target's running USB firmware.
BOOTSEL is only needed once to install the probe firmware on the Pico 2 W.

## Exact probe support

Reviewed official debugprobe revision:
`262f9625d75a2bad8d76cc228ee5e21ca3a64d3a`, with Pico SDK 2.3.0
`98a542c1a62fb549ffb5d66a3e5892b06276b670`.

The upstream README documents Pico and Pico 2. The current board selector tests
`RASPBERRYPI_PICO` / `RASPBERRYPI_PICO2`, while the SDK's `pico2_w` profile defines
`RASPBERRYPI_PICO2_W`. Thus an unmodified `PICO_BOARD=pico2_w` is rejected. Published
v2.3.1 images include Pico and Pico 2, but no Pico 2 W-specific image. Do not use
the RP2040/Pico 1 binary on this RP2350 board.

`tools/prepare_debugprobe_pico2w.py` verifies the reviewed revision and header
hashes, prepares a separate source copy, accepts the W define and disables the
GPIO25 status LED. GPIO25 is wireless CS on Pico 2 W; its LED is on the wireless
chip. This probe does not initialize wireless. Its USB product name and fixed
version identify the adaptation. Original upstream sources/licenses are retained.
This is a reviewed local adaptation, not an official prebuilt W release.

The cross-build passed for `PICO_BOARD=pico2_w`. Official picotool file inspection
identifies RP2350 Arm secure code and the correct W board. The 95,744-byte UF2 is
SHA-256 `d5b2ffa66e31f79f7fc8b9d990b70e6d6bb669d86c825e6719052c6d48543591`.
The GPIO25 LED is absent from the actual compiler preprocessor output. Build,
binary inspection and timing records are in
[`evidence/2026-10-18/fruit-jam`](../evidence/2026-10-18/fruit-jam/).
This verifies software preparation; it does not verify USB or SWD hardware.

## Reproduce the probe build

Clone the reviewed debugprobe revision with its pinned submodules and Pico SDK
2.3.0 with TinyUSB initialized. Run the source preparation helper from this repo.
The following is the successful build command, using the private tools in this
workstation's WSL workspace. Paths are illustrative variables pointing to those
existing directories; no system compiler, driver or package was installed.

```sh
repo=/mnt/c/Users/fred_/Documents/Codex/2026-10-17/task-5/microblocks-zephyr
work=/home/fred/microblocks-zephyr-work
cd "$work"
export PATH="$work/.venv/bin:$work/tools/host/usr/bin:$PATH"
export LD_LIBRARY_PATH="$work/tools/host/usr/lib/x86_64-linux-gnu${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
python "$repo/tools/prepare_debugprobe_pico2w.py" \
  --source /mnt/c/Users/fred_/Documents/Codex/2026-10-17/task-5/upstream-references/debugprobe \
  --output "$work/build/debugprobe-pico2w-src"
cmake -S build/debugprobe-pico2w-src -B build/debugprobe-pico2w -G Ninja \
  -DPICO_BOARD=pico2_w -DPICO_SDK_PATH="$work/references/pico-sdk-2.3.0" \
  -DPICO_TOOLCHAIN_PATH="$work/tools/zephyr-sdk-1.0.1/gnu/arm-zephyr-eabi" \
  -DPICO_GCC_TRIPLE=arm-zephyr-eabi \
  -Dpioasm_DIR="$work/tools/pico-host-2.3.1/pioasm" \
  -Dpicotool_DIR="$work/tools/pico-host-2.3.1/picotool" \
  -DCMAKE_PROJECT_debugprobe_INCLUDE="$repo/cmake/pico_prebuilt_pioasm.cmake" \
  -DPICO_PREBUILT_PIOASM="$work/tools/pico-host-2.3.1/pioasm/pioasm" \
  -DCMAKE_EXPORT_COMPILE_COMMANDS=ON
cmake --build build/debugprobe-pico2w -j4
```

`pioasm_DIR` was ignored by the SDK in this configuration; the project hook
supplies the imported prebuilt pioasm executable instead. On a host with a native
C++ compiler, the SDK can build its own pioasm without that hook. Official Pico
host tools here are release `v2.3.1-0`; GCC is Zephyr SDK 1.0.1's Arm GCC 14.3.0.
The largest recorded Ninja invocation ended at 7,722 ms, using four build jobs;
peak CPU/RAM were not measured. No compilation remains running. The UF2/ELF are
local build artifacts and are excluded from Git.

## One-time physical setup, after authorization

1. Identify and back up the Pico 2 W's existing contents as needed. Boot that
   probe into BOOTSEL once and install the specifically built
   `debugprobe_on_pico2_w.uf2` after reviewing the software checks above. Then
   verify probe USB enumeration before attaching the target.
2. With power disconnected while wiring, connect the three SWD signals below.
   The Fruit Jam socket is JST-SH, 1 mm, three pins. Verify connector numbering
   against the schematic/board orientation; do not infer it from wire colors.
3. Power the Pico 2 W and Fruit Jam through their own USB connectors. Both use
   3.3 V debug logic. The three-pin debug connector supplies no target power;
   do not join USB 5 V or the boards' 3.3 V outputs.

| Pico 2 W probe | Fruit Jam DEBUG connector |
|---|---|
| GP2, physical header pin 4 | Pin 1, SWCLK |
| GND, physical header pin 3 | Pin 2, GND |
| GP3, physical header pin 5 | Pin 3, SWDIO |

The Pico's own SWD pads are its debug **input**, not the generated probe outputs.
Use GP2/GP3 as above. Optional external reset: probe GP1 (physical pin 2) to
Fruit Jam main `RST` / RP2350 `/RUN` (schematic JP3 pin 26). The upstream probe
emulates open drain by driving low and releasing to input. This is distinct
from **GPIO22 PERIPH_RESET**, which resets the Wi-Fi coprocessor and audio DAC.
The default RP2350 OpenOCD target uses SYSRESETREQ over SWD; the fourth wire is
not required for normal programming and needs separate recovery validation.
Source inspection also confirms `probe_gpio_init()` calls `gpio_init(GP1)` when
SWD connects, switching GP1 from the startup diagnostic UART to SIO input with a
cleared output latch. Consequently picotool's UART0-RX metadata on that pin does
not describe its active reset mode. Do not use GP1 as a probe UART connection.

## Normal unattended update

Use Raspberry Pi's OpenOCD distribution containing `target/rp2350.cfg` and its
RP2xxx flash driver. An older generic OpenOCD package or `rp2040.cfg` is not a
substitute. Select the positively identified probe by its USB serial when more
than one CMSIS-DAP device is present. Example, not executed against hardware:

```sh
openocd -f interface/cmsis-dap.cfg -f target/rp2350.cfg \
  -c "adapter speed 1000" \
  -c "program build/fruit-jam/zephyr/zephyr.elf verify reset exit"
```

This loads an **ELF**, not a UF2 drag-and-drop. Keep code/program-storage partitions
separate and back up the actual target before its first firmware replacement.
No full-chip erase or OTP operation belongs to the ordinary update procedure.

For a hung application, SWD can normally halt/reprogram it without cooperation
from its USB stack. The official RP2350 configuration also has a `RESCUE` path
which resets cores into boot ROM through the debug access port. Physical recovery,
reset wiring and fault cases remain to be tested; loss of power or a hung probe
can still require a power cycle. Do not promise recovery from every failure.

## Windows and WSL routes

Prefer native Windows OpenOCD for this workstation, using the official Raspberry
Pi tool bundle (also distributed with its Pico VS Code extension). The probe
exposes CMSIS-DAP plus a separate UART CDC interface. Upstream USB descriptors
provide WinUSB-compatible discovery; actual Windows driver binding remains a
physical acceptance item. Do not replace unrelated serial/device drivers.

WSL is suitable for building. To run OpenOCD inside WSL, explicitly pass the
identified **probe** USB device using usbipd-win (one-time administrator binding,
then attachment to WSL). Windows cannot simultaneously own that passed-through
USB device. Fruit Jam's separate USB cable can remain on Windows for power and
its own serial protocol. No USB binding/driver change has been performed here.

## Software BOOTSEL as a convenience

`picotool -f` works only with running firmware implementing the compatible Pico
SDK USB reset interface. Generic Zephyr CDC is not that interface. A 1200-baud
touch likewise needs an explicit firmware hook; neither recovers a broken USB
stack. For the target port, plan an explicit local USB bootloader request,
handled from the VM/work thread after quiescing outputs and flushing saved
program data, calling the RP2350 boot-ROM reset API. A compatible vendor reset
interface can follow. This remains separate from SWD recovery and is not yet
claimed implemented or physically tested.

## Primary sources

- [Official debugprobe source and Pico 2 build instructions](https://github.com/raspberrypi/debugprobe)
- [Reviewed board selector](https://github.com/raspberrypi/debugprobe/blob/262f9625d75a2bad8d76cc228ee5e21ca3a64d3a/include/board_config.h)
- [Probe output/reset pin configuration](https://github.com/raspberrypi/debugprobe/blob/262f9625d75a2bad8d76cc228ee5e21ca3a64d3a/include/board_pico_config.h)
- [Pico 2 W SDK board definition](https://github.com/raspberrypi/pico-sdk/blob/2.3.0/src/boards/include/boards/pico2_w.h)
- [Fruit Jam pinout and debug connector](https://learn.adafruit.com/adafruit-fruit-jam/pinout#debug-port)
- [Official schematic, revision 252dc094](https://github.com/adafruit/Adafruit-Fruit-Jam-PCB/blob/252dc09456ee447b3d7eeb4fa99877898503e81a/Adafruit%20Fruit%20Jam.sch)
- [RP2350 OpenOCD target and rescue reset](https://github.com/raspberrypi/openocd/blob/master/tcl/target/rp2350.cfg)
- [Raspberry Pi Debug Probe documentation](https://www.raspberrypi.com/documentation/microcontrollers/debug-probe.html)
- [Picotool force/reset requirements](https://github.com/raspberrypi/picotool)
