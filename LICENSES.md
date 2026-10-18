# Licensing and upstream projects

Most new source files and documentation in this repository use the **MIT License** (`LICENSE`).
The experimental SmallVM adapter at
`boards/waveshare_esp32s3_rlcd_4_2/integration/rlcd_smallvm_primitives.c`
uses **MPL-2.0**, as indicated by its SPDX header.
The SmallVM transport, preparation patches, GP package integration and runtime
harness also use MPL-2.0. Generated dependency sources and binaries are excluded
from Git; exact revisions and file hashes are recorded under `dependencies/`.

The combined firmware links Zephyr and ArduinoCore-Zephyr (Apache-2.0),
ArduinoCore-API 1.5.2 (LGPL-2.1), and MicroBlocks SmallVM/GP (MPL-2.0).
ESP32 Wi-Fi libraries retain the notices and license attached to the pinned
`hal_espressif` module. Preserve these licenses in any redistributed build and
provide the corresponding source and build/relink materials as each requires.
The editor asset preparation retains upstream content and changes its existing
UNO Q integration endpoints and embedded hardware library for this board.

`boards/waveshare_esp32s3_rlcd_4_2/bringup/src/rlcd_audio.c` uses Apache-2.0
and retains Espressif Systems' 2023 attribution for the adapted ES8311 register
initialization. The pinned source and hardware references are in `docs/AUDIO.md`.
See `licenses/Apache-2.0.txt` for the license text. Other new audio integration
files retain their individual MIT or MPL-2.0 headers. The generated ESP32 I2S
driver copy retains Zephyr/Espressif's Apache-2.0 header; its exact source hash
and minimal guard are recorded in `tools/prepare_i2s.py`.

Source from the following projects is **not vendored** in this starter and must
preserve its own licensing and attribution when integrated:

- [MicroBlocks SmallVM and GP editor](https://codeberg.org/MicroBlocks/smallvm)
- [Zephyr RTOS](https://github.com/zephyrproject-rtos/zephyr)
- [ArduinoCore-Zephyr](https://github.com/arduino/ArduinoCore-zephyr)
- [BeagleBoard MicroBlocks-Zephyr](https://github.com/beagleboard/microblocks-zephyr)
- [Waveshare ESP32-S3-RLCD-4.2 examples](https://github.com/waveshareteam/ESP32-S3-RLCD-4.2)
- [UNO Q MicroBlocks implementation](https://github.com/speccy88/uno-q-microblocks)
- [Raspberry Pi debugprobe](https://github.com/raspberrypi/debugprobe) (MIT),
  [Pico SDK](https://github.com/raspberrypi/pico-sdk) (BSD-3-Clause and component notices),
  and their FreeRTOS/TinyUSB/CMSIS dependencies. The Pico 2 W preparation script
  copies pinned sources outside Git and retains their original licenses.
- [Adafruit Fruit Jam PCB](https://github.com/adafruit/Adafruit-Fruit-Jam-PCB)
  (CC BY-SA 3.0). Schematic files are read-only external references; this repo
  records source attribution and factual pin assignments, not copied PCB designs.

Review each upstream project's actual license and notices before copying files.
Having a device driver API available does not transfer upstream code ownership.
