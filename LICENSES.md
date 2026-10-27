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
The portable I2C discovery registry/adapters are independently authored MIT
code. Their discovery/measurement organization is inspired by SparkFun's
MIT-licensed Universal Auto-Detect at commit
39b20cc3a9a1b1163f14fdfb8812c754926734c8. No bundled sensor library, Arduino
initialization or mux implementation is copied; factual TMP117 register
semantics come from the TI datasheet. Existing camera/codec source notices
remain intact. See the board's I2C_DISCOVERY.md for source links and limits.
P4 C6
driver patches retain the pinned Zephyr/Espressif Apache-2.0 attribution;
new application transport/server code carries its own MPL-2.0 headers.

P4 image transforms call the pinned external native Zephyr PPA API/driver
under Apache-2.0 (Zephyr a915b2f12675b48b16d56653ea145dcd8f20cbbf).
No IDF RTOS driver or new third-party binary is vendored. The independently
authored bounded worker/generated-pixel hardware test are MIT; GP library,
preview integration and packaging retain MPL-2.0.

The optional Okay Nabu wake-word model is pinned in
`dependencies/p4-wake-word.json`. ESPHome's model collection explicitly licenses
the weights and manifests under Apache-2.0; its complete attribution notice is
retained in `licenses/ESPHome-Wake-Word-NOTICE.txt` alongside Apache-2.0.txt.
Weights and synthetic/private audio remain external build inputs. The trained
frontend uses the pinned external TensorFlow Lite Micro Apache-2.0 sources
and KissFFT (Mark Borgerding, BSD-3-Clause; `licenses/KissFFT-BSD.txt`). A generated
copy of filterbank_util.c adds its missing NULL-allocation check; the original
notice is retained and the external checkout is unchanged. Native worker,
allocation and test helpers are independently authored MIT; SmallVM/GP adapters
retain MPL-2.0. No ESPHome GPL implementation or FreeRTOS integration is copied.

The portable JSON service vendors unmodified yyjson 0.13.0, commit
`6447536015f3d600f3d65323b10976103b337ca7`, under MIT. The complete license is
`third_party/yyjson/LICENSE`; source hashes are pinned in `dependencies/json.json`.
The bounded service/tests use MIT; its separate SmallVM/GP adapter uses MPL-2.0.
Existing tinyJSON and other SmallVM sources are not replaced or relicensed.

The clock/timer and logical step/transition cores and host tests are newly
authored MIT code in `common/automation`. The Zephyr SmallVM adapter and GP
libraries retain MPL-2.0. No GRAFCET runtime, timezone database, RTC driver or
NTP implementation is copied or bundled by this increment.

The bounded RAM-storage service, path/UTF-8 validation and host tests are newly
authored MIT code in `common/storage`. The SmallVM/GP adapter and library use
MPL-2.0. This increment vendors no Flash/SD filesystem or database implementation.

The shared device-file frontend, bounded transport contract, local browser-memory
fixture and tests are newly authored MIT code. Production packages exclude the
fixture. Existing editor packaging retains MPL-2.0; no Tasmota UI code is copied.

The isolated Flash record service and Zephyr VFS adapter/tests under
`common/storage/flash` and `tests/flash_native` are newly authored MIT code.
The simulator links the external Zephyr Apache-2.0 filesystem layer and its
pinned LittleFS module `e9a8638fc228e43a3156ed3ac602229af3e3c1d5` (BSD-3-Clause).
No LittleFS implementation is vendored or linked into the P4 application by
this local increment; the external module retains its original LICENSE.md.

The receive-only camera JavaScript modules, internal fake-media fixture and
tests are newly authored MIT code. Their wire contract is reviewed against
pinned Pollen mediad and GStreamer0.15.3 signaling source, with source URLs and
hashes in `linux/microduck/tests/camera-source.json`. No GStreamer/Pollen media
implementation, codec, source text or captured footage is redistributed here.
The additive video-element observer, simulation viewer UI/test card and fake
media callback fixture are also newly authored MIT code. Browser interface
specifications are referenced in `linux/microduck/CAMERA_VIEWER.md`; no browser
decoder implementation or third-party video file is copied.

The motion-simulation backend, internal notification recorder and Python tests
are newly authored MIT code. The native simulation-wrapper validator additions,
UBL library/example and GP packaging changes retain MPL-2.0. Only protocol facts
from pinned Pollen sources are used; no robot controller, gait, safety engine,
motor driver or physics implementation is copied or redistributed.

The read-only sensor-simulation backend, fixed fictional ToF/pad fixtures and
Python tests are newly authored MIT code. Native validator, UBL/example and GP
packaging additions retain MPL-2.0. Pinned protocol facts and zone interpretation
are referenced; no Pollen/ST driver, firmware or device capture is redistributed.

The bounded snapshot store and observed gamepad state model/tests are also
newly authored MIT code. Native typed sensor decoders, library/version1.1 and
example changes retain MPL-2.0. No Pollen controller or continuous driver is copied.

The API45 control-packet preview recorder, bounded robot.state simulator/typed
reader and tests are newly authored MIT code. Native validators/typed decoder,
separate Robot Simulation/Telemetry libraries and example retain MPL-2.0.
Only interface facts are used; no Pollen controller, policy/ONNX weights, IK,
kinematics, safety implementation or actual robot capture is redistributed.

The mediad/relay simulation backend and its Python tests are newly authored MIT
code. Native media reading/guard additions, UBL/example and GP packaging retain
MPL-2.0. Only source protocol facts are used; no Pollen relay, audio codec or media
implementation, account credential or captured media is redistributed.

The gamepad IMU simulator, bounded batch store and Python tests are newly authored
MIT code. The native IMU validators/decoder, UBL/example and GP integration retain
MPL-2.0. Only pinned Pollen protocol facts are used; no driver, filter, third-party
IMU implementation or physical sensor capture is redistributed.

The bounded tofd head-IMU reader, fictional stream simulator and Python tests
are newly authored MIT code. Shared native typed decoder, separate head-IMU
UBL/example and editor packaging retain MPL-2.0. Pollen/BMI088 protocol facts
are referenced; no driver, filter, sensor fusion, coordinate transformation or
physical capture is copied or redistributed.

The explicit read-only head-IMU service adapter/config loader and its Python
tests are newly authored MIT code. Native origin/decoder additions and the
separate Head_IMU library/example/editor integration retain MPL-2.0. No Pollen
daemon or driver implementation is copied; only protocol facts are used.

The coherent read-only depth adapter, private fictional-source fixture and Python
tests are newly authored MIT code. Native depth decoder/row reuse and the Depth
library/example/editor integration retain MPL-2.0. Pollen protocol/zone facts are
referenced; no sensor driver, controller or physical capture is redistributed.

The normal read-only gamepad adapter/discovery model integration, fictional-service
fixture and Python tests are newly authored MIT code. Native decoder/gate additions,
Gamepad library/example and editor integration retain MPL-2.0. Pinned Pollen/evdev
interface facts are referenced; no input driver, robot controller or capture is copied.

Normal robotd observer: linux/microduck/robot_health.py, robot_service.py and
robot_gateway_fixture.py retain MIT notices; Robot.ubl and robot-read.ubp follow
the repository MPL-2.0 library policy. Pollen protocol is reviewed at its pinned
source; no Rust source is copied into these adapters.
