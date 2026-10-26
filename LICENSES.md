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

- [MicroBlocks GP editor](https://codeberg.org/MicroBlocks/smallvm)
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

The P4 native camera port uses the pinned external Zephyr/Espressif HAL
(Apache-2.0), without linking FreeRTOS or ESP-IDF camera/ISP RTOS drivers.
`p4_csi.c` retains Espressif's Apache-2.0 notice for adapted CSI/ISP/DW-GDMA
register setup. `p4_sensors.c` retains Circuit Valley, tinyVision.ai and
Espressif Apache-2.0 notices; `ov5647_mode.h` preserves the Espressif mode-table
notice. The tested authored sensor initialization was explicitly requested
from private source commit `fc60acbb0c1eb080ee57b3aca5942e81539e6049`;
private frames, credentials and raw logs are excluded. The shared image engine
and backend use MIT; SmallVM primitive/transport/editor adaptations use MPL-2.0.
Speech model weights remain external and are not committed.

The native P4 ADC-only ES8311 register sequence adapts Espressif
`esp_codec_dev` 1.5.4 (Apache-2.0), source commit
`fcce23e3d5ecf7ba75ce9f4e3761489dc9e0299e` in `esp-adf`.
Its Espressif copyright notice is retained in `audio_backend.c`; native
Zephyr I2S transport/ownership is integrated locally. The portable PCM store
uses MIT, and SmallVM/editor/audio-library adaptations use MPL-2.0.

The optional native P4 Whistle profile fetches and verifies the independent
Apache-2.0 C99 engine from `andrisgauracs/whistle-esp32` commit
`9e9e996e55b0f945438da1082eac4a087ed3ca39`. Its complete upstream LICENSE
is retained with the external fetched source. Generated wrappers select the
portable RV32 C branch and redirect allocations without modifying those
verified upstream files. Native worker/SmallVM/editor adapters are MPL-2.0;
the build/fetch/validation helpers have their own MIT notices. The optional
Cactus Whistle model is Apache-2.0, with source revision, exact derived-model
size and SHA256 in `dependencies/p4-whistle.json`. Model weights, generated
speech fixtures and private microphone captures are excluded from Git and
Pages deployment; this change does not redistribute a model binary.

`boards/propeller2/native/` contains the required C/header subset of the
recovered MicroBlocks SmallVM v405 native FlexC port, derived from commit
`4dc5f4df2fe1eeb0ee3bb9c4bf694e2e34087e8c` plus recovered uncommitted changes.
It retains MPL-2.0 file notices and its full upstream LICENSE. Original file
hashes are in `boards/propeller2/recovery-provenance.json`. New P2 primitive
changes retain MPL-2.0. The recovery archive, Git database, executables and
unrelated recovered files are not vendored. P2 mode encodings are factual
constants verified against Parallax's official PNut table; PNut source is not
copied. FlexProp/loadp2 binaries stay external and retain their own licenses.

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

The XRP-only cooperative HTTP preparation retains Zephyr's Apache-2.0 notices
in both generated source files. Original pinned HTTP sources remain external
and unchanged. The preparation script and synthetic test harness have their
own SPDX headers; generated files and test binaries are not committed.

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

The optional native P4 TensorFlow Lite Micro probe uses the pinned external
Zephyr TFLM module under Apache-2.0. Its sine fixture and model remain external
build inputs with source/hash attribution in `dependencies/p4-tflm.json`.
The bounded NN backend now loads tested static dense TFLite artifacts; its
fixed-batch builtin derivative retains both original/derived hashes and Apache-2.0
attribution. No model binaries or ONNX Runtime binaries are vendored. Optional
host conversion uses pinned ONNX (Apache-2.0), FlatBuffers (Apache-2.0), NumPy
(BSD-3-Clause) and protobuf (BSD-3-Clause); their installed packages retain their
own notices. New converter/contract code is MIT, GP/library integration MPL-2.0.
Microduck/Arduino/Tasmota remain design references, not copied implementations.
P4 C6
driver patches retain the pinned Zephyr/Espressif Apache-2.0 attribution;
new application transport/server code carries its own MPL-2.0 headers.
