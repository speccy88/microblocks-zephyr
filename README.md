# MicroBlocks on Zephyr

A multi-board, open development project to run **MicroBlocks SmallVM and the Arduino API
alongside Zephyr RTOS**, with board-aware blocks for displays, sensors, buses, storage,
wireless connectivity and other peripherals.

**Status: experimental scaffolding — no flashable SmallVM firmware has been built
or validated for this new repository.** Start with the Waveshare hardware-diagnostic
application; the UNO Q implementation remains an independent, physically tested reference.

## Supported and planned boards

| Board | Zephyr integration | SmallVM | Arduino API | Hardware tests |
|---|---|---|---|---|
| [Waveshare ESP32-S3-RLCD-4.2](boards/waveshare_esp32s3_rlcd_4_2/README.md) | Upstream board target exists | Adapter draft, not linked | Not integrated | No device tests |
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

**Back up the board's current flash before `west flash`.** This firmware replaces
the existing application. The bring-up shell is not the MicroBlocks binary protocol;
they need separate serial endpoints or mutually exclusive transport modes.

## Layout

```text
boards/
  waveshare_esp32s3_rlcd_4_2/
    hardware.json              Board capability inventory and reserved pins
    bringup/                   Zephyr hardware diagnostic app (uncompiled)
    integration/               Unlinked SmallVM primitive adapter and .ubl blocks
    docs/                      Physical acceptance checklist
    README.md                  Board-specific setup and safety
docs/
  ARCHITECTURE.md              Cross-board API and runtime design
  ROADMAP.md                   Scope, milestones and acceptance criteria
tests/                         Offline source/manifest checks
tools/                         Validators and optional GitHub publishing helper
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

## Publish this repository on GitHub

The GitHub connector used to inspect the sources cannot create repositories.
After reviewing the files, from a machine with authenticated [GitHub CLI](https://cli.github.com/):

```sh
gh auth login
bash tools/publish-github.sh public  # or private
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
