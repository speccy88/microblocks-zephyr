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
- [Pinned ArduinoCore-Zephyr module](https://github.com/zephyrproject-rtos/arduino-core-zephyr)
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

The production XRP target references SparkFun's schematic at `86c4cd7f`
(hardware CC BY-SA 4.0; software MIT) for factual wiring/part data; no schematic
artwork is copied. The RP2350B/RM2 DeviceTree composition retains Apache-2.0
upstream notices. The portal selects Russell Owen's unchanged production XRP
library already present in the pinned MPL-2.0 MicroBlocks GP package. XRPCode
and XRPLib GPLv3 sources are behavioral references only and are not copied.
No Infineon firmware/CLM blob is committed. The XRP wireless build verifies
two external CYW43439 blobs from pinned `hal_infineon` metadata; their hashes
are in `dependencies/xrp-radio-blobs.json`. The complete applicable EULA is
preserved in `licenses/Infineon-WHD-Blob.txt`. These terms remain distinct from
this repository's source licenses; local build binaries are not published by
the Pages workflow. Host-driver source retains the external HAL's notices.

Fruit Jam's `smallvm/src/nina_protocol.c` and `nina_socket_protocol.c` adapt the MIT-licensed command/reply
framing from Adafruit CircuitPython ESP32SPI, copyright (c) 2019 ladyada for
Adafruit Industries. The pinned reference and SHA256s are recorded in
`dependencies/fruit-jam-airlift-reference.json`; its full MIT notice is retained
in `licenses/Adafruit-ESP32SPI-MIT.txt`. The server/provisioning implementation
communicates with the factory ESP32-C6 firmware in place. The separate
user-requested official WiFiNINA restoration has its own provenance and private
backups; no firmware blob is vendored here. The official NINA 3.3.0 command-handler
source is an external LGPL-2.1 reference for factual wire formats, not copied
into this native application.
