# MicroBlocks on Zephyr

The [JavaScript editor migration](docs/JS_EDITOR_MIGRATION.md) is now staged
separately, with a local `gp` preservation branch, an independently pinned
upstream editor and a Linux compatibility layer. Existing GP/runtime pins
remain available. This is experimental staging, not a published main migration.

A multi-board development project to run **MicroBlocks SmallVM and the Arduino API
alongside Zephyr RTOS**, with board-aware blocks for displays, sensors, buses, storage,
wireless connectivity and other peripherals.

**Status: experimental hardware port.** Zephyr, the actual Arduino API and SmallVM
v417 compile together and run on the Waveshare board. Wireless validation covers
arithmetic/editing, ordered output, code CRCs, fragmented uploads, stop/variable
inspection, reconnect and reboot/autostart checks.
Basic physical checks now default to 50 outputs; the earlier 500-output results
remain historical evidence. HTTP assets stream in bounded 2 KiB chunks.
An earlier user-shortened 689.703-second workload completed 22 cycles with
zero observed reset, WebSocket error, asset abort or settled heap loss; this is
not a 30-minute stability result. The final graphical follow-up emitted exactly
1..50. See [targeted acceptance](evidence/2026-10-18/targeted-http-acceptance.json).
The actual MicroBlocks 2.5.8 graphical editor now loads entirely from board flash,
with all 148 assets passing a concurrent content/header audit. The real editor
passes graphical arithmetic/editing, ordered outputs, variable
inspection, stop/reconnect, saved-program readback and reboot/autostart. Four
fresh browser loads passed; runtime heap samples are recorded. Sensor reads and
LCD transfers have physical evidence; display appearance and button presses
still require observation.
See the [development record](docs/DEVELOPMENT_SESSION.md) and
[standalone goal](docs/STANDALONE_GOAL.md) for exact limitations.

The [direct local access](docs/LOCAL_ACCESS.md) mode requested by the user has no
application login or connection code. Wi-Fi credentials and protected recovery
AP remain. [Speaker output](docs/AUDIO.md) adds asynchronous tone, busy, stop
and diagnostic blocks. Silent hardware timing and stop tests pass; audible
confirmation is pending. The latest [bounded checkpoint](evidence/2026-10-18/audio-direct-access-checkpoint.json)
includes direct connection, reboot persistence, one fresh graphical load and
50 outputs, with the original program and Wi-Fi retained.

[Generic I/O](docs/GENERIC_IO.md) now implements the native I2C register,
SPI send/receive and analog read/write blocks, plus SPI setup/exchange. Analog
input is A0/A1; output is 1 kHz PWM on D2. SPI3 uses D0/D1/D2 without automatic
CS. The [current checkpoint](evidence/2026-10-18/generic-io-checkpoint.json)
records real graphical I2C readback, 50 ordered outputs, asset/reconnect/reset
checks and preserved original CRCs. External SPI/PWM waveforms and ADC accuracy
remain unverified; writes and transfers have software-driver simulations.
The advanced Comm category also supports I2C List/ByteArray read, bounded write
and single-address presence helpers. The usual `write(..., false)` then read
pattern uses one atomic transaction; see [its exact bounds](docs/GENERIC_IO.md).

## Supported and planned boards

| Board | Zephyr integration | SmallVM | Arduino API | Hardware tests |
|---|---|---|---|---|
| [Waveshare ESP32-S3-RLCD-4.2](boards/waveshare_esp32s3_rlcd_4_2/README.md) | Pinned build and physical boot | v417 linked; interpreter harness passes | Real module compiled; library tests pending | Sensors/LCD transfer/AP association; full acceptance pending |
| [Waveshare ESP32-P4 WIFI6](boards/waveshare_esp32p4_wifi6/START_HERE.md) | Native Zephyr CSI/ISP, PCM, Whistle and bounded TFLM | v417 USB, graphical media and NN catalog/custom import pass | Future integration; not linked | Untuned IMX219; PCM/local STT and static dense NN verified. Station/board-hosted editor and bounded FAT32 SD file manager verified; opt-in saved boot passes warm resets. One controlled link loss recovered; powered low-latency and faster SDIO polling pass bounded HTTP/VM/SD checks; energy and full power removal remain unverified. PPA transforms and KWS fixture/event/mic lifecycle tested; acoustic KWS and codecs pending. |
| [Arduino UNO Q](https://github.com/speccy88/uno-q-microblocks) | Separate working project | Verified in reference repo | Reference port | Prior physical tests, not validated in this repo |
| [Adafruit Fruit Jam RP2350B](boards/adafruit_fruit_jam/README.md) | Pinned ARM build and physical boot | v417 USB/graphical calculations, reconnect and reboot persistence pass | Real module/variant compiled | SWD/USB, NeoPixels, three buttons and user-triggered Wi-Fi, native graphical edit/save/readback and retained-association boot verified; full-power Wi-Fi and remaining peripherals pending |
| [SparkFun XRP production RP2350B](boards/sparkfun_xrp_rp2350/README.md) | Integrated Canada image installed and verified | v417 USB and Wi-Fi arithmetic/edit,50 outputs,fragmentation,reconnect and retained boot pass | Real isolated module linked; ADC/I2C reads pass | All 147 HTTP assets pass during VM traffic; IMU ID and raw ADC verified; graphical acceptance pending; motors/servos locked |

## Native Propeller 2

The [P2 port](boards/propeller2/README.md) runs the recovered native FlexC
SmallVM over USB Web Serial in the same portal, with P2 hardware and Smart Pin
blocks. It runs directly on P2; it does not use Zephyr, ArduinoCore-Zephyr,
Wi-Fi or board-hosted HTTP. Select the exact Eval/original Edge/EC32MB image
when installing firmware. Physical acceptance and limits are recorded in its
[capability manifest](boards/propeller2/hardware.json).

## Linux ARM64 and MicroDuck development checkpoint

The [native ARM64 SmallVM](linux/arm64/README.md) now builds and executes on a
real Raspberry Pi 5, using 32-bit arena offsets while native addresses remain
native pointers. Pi interpreter, installer and isolated session-recovery tests
have evidence. The separately pinned JavaScript editor also connects, executes,
serializes/reopens, reconnects and reads programs back on the Pi; the latest
[readback lifecycle](docs/JS_PI_READBACK_SPEC.md) preserves existing VM slots.
The standalone Pi target requires no robot services.

The separate MicroDuck RK3566 target remains an experimental offline placeholder.
Its typed simple and advanced libraries coexist in one project, with real Pi
VM/graphical tests against fictional daemon sources. Physical robot, live motion,
camera commissioning and secure BLE provisioning remain unverified. Actual BLE
PIN/Wi-Fi secrets remain blocked until confidentiality is established. No ARM64
release or installer URL is published by this development checkpoint.

## Start here: Waveshare ESP32-S3-RLCD-4.2

Read **[hardware inventory, Zephyr installation, flashing precautions, and
diagnostic instructions](boards/waveshare_esp32s3_rlcd_4_2/README.md)**.

```sh
# Offline, runs on any computer with Python 3; does NOT build or flash firmware
python3 tools/validate.py
```

Once the pinned Zephyr workspace from the board README is installed:

```sh
west build -b esp32s3_rlcd_4_2/esp32s3/procpu \
  boards/waveshare_esp32s3_rlcd_4_2/bringup -p always
```

Preserve the board's current flash unless the user explicitly requests erase
without a backup. This firmware replaces
the existing application. The bring-up shell is not the MicroBlocks binary protocol;
they need separate serial endpoints or mutually exclusive transport modes.

## Layout

```text
boards/
  waveshare_esp32s3_rlcd_4_2/
    hardware.json              Board capability inventory and reserved pins
    bringup/                   Compiled, physically exercised diagnostics
    arduino_smoke/             Actual Arduino API compile/smoke target
    smallvm/                   Bounded SmallVM v417 recovery/test target
    standalone/                Board-hosted graphical IDE and binary WebSocket
    integration/               Linked primitives and Waveshare .ubl blocks
    docs/                      Physical acceptance checklist
    README.md                  Board-specific setup and safety
docs/
  ARCHITECTURE.md              Cross-board API and runtime design
  ROADMAP.md                   Scope, milestones and acceptance criteria
tests/                         Offline source/manifest checks
tools/                         Source verification, editor packaging and validators
dependencies/                  Pinned sources and per-file hashes
web/                           Board transport and saved Wi-Fi setup page
common/                        Portable setup decoder/journal, not yet linked into board images
evidence/                      Build and physical observations, no credentials
.github/workflows/             Offline CI only — not a firmware build
```

## What has to exist to call a board fully supported?

1. A reproducible, pinned Zephyr build for the board with hardware-specific drivers.
2. SmallVM executes official MicroBlocks bytecode and passes reconnection/CRC tests.
3. A verified Arduino API integration with representative libraries; API parity is
   not assumed from Zephyr board support alone.
4. A capability manifest reflects **tested** features, not just Devicetree nodes.
5. Physical tests for every advertised device (LCD, I²C, buttons, battery,
   microSD, Wi-Fi, BLE, microphone, audio output, power management).

Follow [ARCHITECTURE.md](docs/ARCHITECTURE.md),
[ROADMAP.md](docs/ROADMAP.md), and [AGENTS.md](AGENTS.md).

## GitHub repository

The repository is [speccy88/microblocks-zephyr](https://github.com/speccy88/microblocks-zephyr),
initially created private. All accepted Fruit Jam and Waveshare development
is now integrated on `main`; further work uses `main` only. Existing history
is preserved. The owner approved public visibility with the audited technical
diagnostic metadata on 2026-10-19.

The [browser portal](https://speccy88.github.io/microblocks-zephyr/) is built
by the Browser portal workflow from `main`. See [portal acceptance and current
limitations](docs/PAGES_PORTAL.md) and [website source/license review](docs/SITE_DESIGN_LICENSES.md).
Build success alone does not establish deployment or physical USB acceptance.

The common USB Wi-Fi provisioning work has a tested portable decoder and
two-slot flash-record format; [board integration remains pending](docs/COMMON_WIFI_SETUP.md).
No persistent configuration capability is claimed for either current image
on the strength of synthetic storage tests.

For a separate new repository only:

The GitHub connector used to inspect the sources cannot create repositories.
After reviewing the files, from a machine with authenticated [GitHub CLI](https://cli.github.com/):

```sh
gh auth login
bash tools/publish-github.sh private
```

This validates the offline tests, initializes a local Git commit with **your** configured
Git identity, and creates/pushes `speccy88/microblocks-zephyr`. The script
refuses to overwrite an existing repository with branches. For manual creation,
[create an empty repository](https://github.com/new?owner=speccy88&name=microblocks-zephyr)
with **no** initial README, license or `.gitignore`, then run the same script.
The repository's visibility is an explicit choice; this script never publishes
without `public` or `private` being supplied.

## References and licenses

The [native Linux ARM64 port](linux/arm64/README.md) now executes official
SmallVM v417 bytecode on Raspberry Pi 5, including real graphical IDE uploads
through a loopback SSH tunnel. ARMv8-A builds, persistence, installation lifecycle
and browser save/restore/reconnect have recorded evidence. Full OS reboot and
release publication remain pending. The portal adds Pi 5 and MicroDuck profiles;
installation copying stays disabled until an actual reviewed release exists.
[MicroDuck BLE](docs/MICRODUCK_PROTOCOL.md) and the
[optional Unix gateway](linux/microduck/README.md) have mock coverage; physical
robot validation remains pending. The native adapter and block library pass
real Pi execution against an explicitly simulated robot backend.

The production [XRP integration](boards/sparkfun_xrp_rp2350/README.md) is a
separate non-actuating SmallVM/Arduino/RM2 application. Its physical release
gates and current evidence are recorded with that board; existing Fruit Jam
and Waveshare firmware are preserved.

- [Waveshare hardware/examples](https://github.com/waveshareteam/ESP32-S3-RLCD-4.2)
- [Zephyr official board](https://github.com/zephyrproject-rtos/zephyr/tree/main/boards/waveshare/esp32s3_rlcd_4_2)
- [BeagleBoard MicroBlocks-Zephyr](https://github.com/beagleboard/microblocks-zephyr)
- [ArduinoCore-Zephyr](https://github.com/arduino/ArduinoCore-zephyr)
- [Existing UNO Q port](https://github.com/speccy88/uno-q-microblocks)
- [SmallVM](https://codeberg.org/MicroBlocks/smallvm)

New code is principally MIT, with an MPL-2.0 SmallVM adapter. See
[LICENSE](LICENSE) and [LICENSES.md](LICENSES.md); upstream components retain
their own licenses. No third-party firmware or proprietary blobs are included.
