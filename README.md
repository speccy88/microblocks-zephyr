# MicroBlocks on Zephyr

A multi-board development project to run **MicroBlocks SmallVM and the Arduino API
alongside Zephyr RTOS**, with board-aware blocks for displays, sensors, buses, storage,
wireless connectivity and other peripherals.

**Status: experimental hardware port.** Zephyr, the actual Arduino API and SmallVM
v417 compile together, and standalone images containing the real graphical IDE
have been flashed on COM4. Sensor reads, LCD transfers, protected Wi-Fi,
DHCP, HTTP and binary WebSocket arithmetic have physical evidence. Full graphical
editor behavior, repeated wireless editing and reboot persistence are not yet validated.
The production protocol test now passes reconnect, stop/variable inspection and
code CRC/start-block checks across reboot. The graphical editor currently stops
at Loading; browser asset delivery is still being repaired. Protocol results
are not a substitute for graphical acceptance.
See the [development record](docs/DEVELOPMENT_SESSION.md) and
[standalone goal](docs/STANDALONE_GOAL.md) for exact limitations.

## Supported and planned boards

| Board | Zephyr integration | SmallVM | Arduino API | Hardware tests |
|---|---|---|---|---|
| [Waveshare ESP32-S3-RLCD-4.2](boards/waveshare_esp32s3_rlcd_4_2/README.md) | Pinned build and physical boot | v417 linked; interpreter harness passes | Real module compiled; library tests pending | Sensors/LCD transfer/AP association; full acceptance pending |
| [Arduino UNO Q](https://github.com/speccy88/uno-q-microblocks) | Separate working project | Verified in reference repo | Reference port | Prior physical tests, not validated in this repo |
| RP2350 | Candidate | Not started | Not started | None |

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
created private. Active hardware integration lives on `development/waveshare-rlcd`.
Preserve existing branches and history when pushing further changes.

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

- [Waveshare hardware/examples](https://github.com/waveshareteam/ESP32-S3-RLCD-4.2)
- [Zephyr official board](https://github.com/zephyrproject-rtos/zephyr/tree/main/boards/waveshare/esp32s3_rlcd_4_2)
- [BeagleBoard MicroBlocks-Zephyr](https://github.com/beagleboard/microblocks-zephyr)
- [ArduinoCore-Zephyr](https://github.com/arduino/ArduinoCore-zephyr)
- [Existing UNO Q port](https://github.com/speccy88/uno-q-microblocks)
- [SmallVM](https://codeberg.org/MicroBlocks/smallvm)

New code is principally MIT, with an MPL-2.0 SmallVM adapter. See
[LICENSE](LICENSE) and [LICENSES.md](LICENSES.md); upstream components retain
their own licenses. No third-party firmware or proprietary blobs are included.
