# Native Zephyr MicroBlocks camera

This port runs genuine SmallVM v417 on native Zephyr, on the Waveshare
ESP32-P4-WIFI6 revision 1.3/pre-v3 board (32 MiB flash and PSRAM). The tested
camera is the IMX219 Camera V2.1 in the WX-RPI CAMERA adapter socket. DISP is
unused. Keep COM12 untouched. Do not use ESP32-P4 revision-v3 firmware.

Physical tests: three 1280x720 RGB565 stills, 160x90 resize/grayscale,
RGB888 HWC uint8 preprocessing, bounded export and handle lifecycle passed.
Scene quality is untuned: fixed exposure/gain, no calibrated AWB/AE/LSC.
The latest dark scene failed the strict content check; new camera captures
are on hold pending Fred's lighting confirmation. Historical frame/pipeline
passes do not override that current quality limit.
The OV5647 800x640 RAW8 driver is retained but not physically retested under
Zephyr with the current IMX219 attached. See [tasks](docs/TASKS.md).

## Build

Two targets are retained: USB-only and station-hosted with the same native VM
and blocks. AP was canceled. See [station setup](docs/NETWORK_STATION.md).
For the tested bounded neural backend, add `profiles/neural.conf` and the
pinned TFLM module with `P4_TFLM_SOURCE`/`ZEPHYR_EXTRA_MODULES`; see
[NN contract and measured tests](docs/NEURAL_NETWORKS.md). Direct ONNX Runtime,
CNN/KWS operators and P4 kernel acceleration remain unavailable.

Use the pinned Zephyr workspace, not an ESP-IDF application build:

```bash
source /home/fred/microblocks-zephyr-work/.venv/bin/activate
export ZEPHYR_SDK_INSTALL_DIR=/home/fred/microblocks-zephyr-work/tools/zephyr-sdk-1.0.1
cd /home/fred/microblocks-zephyr-work
west build -b esp32p4_wifi6/esp32p4/hpcore \
  -s /mnt/c/Users/fred_/Documents/Codex/2026-10-25/task-2/microblocks-zephyr/boards/waveshare_esp32p4_wifi6/zephyr \
  -d /home/fred/microblocks-zephyr-work/build-p4-native
```

Zephyr is `a915b2f12675b48b16d56653ea145dcd8f20cbbf`, Espressif HAL is
`b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`, SDK 1.0.1 / GCC 14.3.0.
Run `tools/fetch_p4_sources.py --help` for the verified existing SmallVM and
editor source manifests. The build consumes `build-artifacts/p4-sources/smallvm`.
Use a persistent build directory: WSL restart clears `/tmp` on this computer.

Before building, apply the small reviewed fixes to that exact Zephyr commit:

```bash
python3 /path/to/microblocks-zephyr/tools/apply_p4_zephyr_patches.py \
  --zephyr /home/fred/microblocks-zephyr-work/zephyr --execute
```

The build checks that these patches are applied. Pre-v3 P4 I2S uses XTAL,
because its PLL/APLL selection otherwise stalls the RX register update.
The SDHC patch preserves native interrupt-allocation errors. Unused AXI DMA
is disabled to leave CPU interrupt vectors for SDIO; camera DW-DMA and audio
AHB-DMA are separate. These are native Zephyr fixes, without an IDF RTOS shim.

## Bounded PCM blocks

Image-producing blocks now show their own inline thumbnail. Results expand
on first execution; use +/minus to show or hide them without executing the
block. A deliberate collapse survives reruns. With no image, the view is
collapsed. Snapshots are bounded copies, so releasing an image handle does
not invalidate its displayed thumbnail. Reloading the project clears them.

The record PCM block similarly displays duration and an explicit browser
Play/Pause button. Playback does not record again and never starts by itself.
Results stay local to the editor, outside `.ubp` files and autosave. Rerun,
disconnect and project replacement clear old audio and revoke playback URLs.
These views use the same USB/WebSocket byte protocol; actual board-hosted
Wi-Fi remains pending the companion protocol work described below.

The physical inline acceptance used generated image create/resize/grayscale
and two bounded 500 ms captures, without taking another camera picture.
See `evidence/2026-10-25/p4-media-browser.json` and `p4-media-native.json`.

The editor also loads **P4 Audio**. Select **Bounded PCM levels** and press
Start explicitly for a 500 ms recording, RMS/peak
report and release. No recording/listening begins merely by opening the page.
Stop All cancels pending recording and releases completed audio handles.
At startup the identified ES8311 ADC and speaker amplifier are disabled.

Actual codec ID, 16 kHz DMA timing, two-handle capacity, release/cancellation
and concurrent VM execution passed physical tests. The one-second run measured
15,999.1 frames/s from DMA completion timing. A separately approved Windows
speaker/P4 microphone test verified acoustic response (envelope correlation
0.7442 and RMS rise from 0.57 to 103.49). Recognition accuracy and wake-word
detection remain separate tests. No raw recordings are committed or uploaded.

```powershell
python tools/test_p4_audio_usb.py --execute --evidence evidence/2026-10-25/p4-audio-pcm.json
```

The default build remains USB-only. The separate `profiles/c6-probe.conf`
and `profiles/c6-sdio.overlay` build is a transport/version diagnostic, with no
Wi-Fi consumer or credential/AP RPC. It requires the pinned Nanopb module
(`west update nanopb`) and `grpcio-tools` for code generation. SDIO initializes;
the installed companion has not yet answered the current version protocol.
No companion firmware was changed. See [network proposal](docs/NETWORK_PLAN.md).

The separate [native hosted target](docs/HOSTED.md) is now built and flashed
with verified local editor assets and nonoverlapping app/model/settings regions.
C6 initialization and USB/Whistle regression pass. AP configuration request
284 currently times out, so board-hosted HTTP/GP/WebSocket functionality is
blocked. The approved unique key is privately saved on P4, excluded from
source/evidence; C6 firmware and Windows networking remain unchanged.

## Flash and physical checks

### Optional native Whistle profile

The small default USB profile has no model. The larger Whistle profile uses
the same native camera/audio/VM transport and reads its verified model from
flash; it reserves a bounded 12 MiB PSRAM workspace per job. It accepts copied
16 kHz mono PCM of 0.1 to four seconds, returns UTF-8 text asynchronously, and
supports Stop cancellation. Release image handles if the workspace cannot be
reserved. Model weights and generated fixtures remain outside Git.

Fetch the pinned Apache-2.0 source:

```powershell
python tools/fetch_p4_whistle_sources.py --output build-artifacts/whistle-sources
```

For fixture testing, supply a local 16 kHz mono PCM16 WAV, 0.1 to four
seconds, saying `The camera is ready.`. The controlled fixture used here was
generated by the installed offline Windows SAPI voice and is kept under
ignored `build-artifacts/whistle/camera-ready.wav`. No script execution policy
or output-volume setting is changed. A fixture is optional for normal use.

Use the verified four-layer `whistle_d4.cact` from the earlier local release;
the exact size/SHA256 and original model/license source are in
`dependencies/p4-whistle.json`. Supply its local path explicitly. From the
configured WSL west workspace, with `P4_REPO` pointing to this checkout:

```bash
west build -b esp32p4_wifi6/esp32p4/hpcore -s "$P4_REPO/boards/waveshare_esp32p4_wifi6/zephyr" -d build-p4-whistle -- \
  -DEXTRA_CONF_FILE=profiles/whistle.conf \
  -DEXTRA_DTC_OVERLAY_FILE=profiles/whistle.overlay \
  -DP4_WHISTLE_MODEL=/absolute/local/path/whistle_d4.cact \
  -DP4_WHISTLE_FIXTURE="$P4_REPO/build-artifacts/whistle/camera-ready.wav"
```

The optional fixture is embedded only for an explicitly invoked board test;
it does not run on boot. Every build verifies all source hashes, the linked
model hash/address and the application boundary at 0xfe0000. This profile
uses one direct simple-boot image at 0x2000 and has no OTA slot. Copy its
`zephyr.bin`, guard and flash it using the same COM5-only commands below.
Then run `tools/test_p4_whistle_usb.py --execute --evidence ...` for native
fixture, VM responsiveness, cancellation and reuse checks. Adding
`--acoustic-fixture build-artifacts/whistle/camera-ready.wav` plays a brief
phrase at the existing Windows output volume and records a bounded clip;
use it only with explicit acoustic-test authorization. No audio is exported.

The editor exposes **P4 Local Speech** and the **Local speech** example.
`local speech available?` distinguishes the model profile from the default
small firmware. See [native contract and acceptance](docs/WHISTLE_NATIVE.md)
for memory/storage/error details and measured status.

Measured scalar native baseline: about 22 seconds for the clean two-second
fixture, 32.2–33.4 seconds for a four-second microphone clip, 2.27–2.80 MB
peak requested workspace inside the separate **12 MiB reserved arena**, and
21,572 unused bytes in the guarded 64 KiB worker stack. The same private PCM
returned `The camera is ready.` on the host and twice on P4; releasing the
original audio handle did not change the copied-input result. The genuine
graphical example returned `The cameras is ready.` in 26.39 seconds. Another
microphone trial was misrecognized. This is an experimental local recognizer,
not a general accuracy or real-time claim. No wake-word listener is installed.

With explicit acoustic-test authorization, the reusable same-PCM diagnostic
exports only to an ignored private path for offline host comparison:

```powershell
python tools/test_p4_whistle_same_pcm.py --execute --fixture build-artifacts/whistle/camera-ready.wav --private boards/waveshare_esp32p4_wifi6/outputs/private --evidence evidence/2026-10-25/p4-whistle-same-pcm.json
python tools/test_p4_resources_usb.py --execute --evidence evidence/2026-10-25/p4-whistle-resources.json
```

The resource test checks image-handle preservation when the large inference
arena cannot fit, recovery and full image-budget reallocation; it does not
establish scene quality. After STT, the current camera still returned correct
frame dimensions and transformed/exported bytes, but the strict scene-content
gate failed on an almost-black capture (gray 10–16, four levels). A lit-scene
retest is pending physical adjustment. That failure is retained in evidence;
the contrast criterion was not lowered.

Copy `build-p4-native/zephyr/zephyr.bin` to `build-artifacts/p4-zephyr/zephyr.bin`.
Native simple boot uses one image at **0x2000**; it does not use the IDF app,
partition-table and bootloader offsets. Tighten the ROM header's revision
fields without changing its hidden flash sections:

```powershell
python tools/p4_image_guard.py build-artifacts/p4-zephyr/zephyr.bin build-artifacts/p4-zephyr/zephyr-checked.bin
# Only under current explicit firmware-replacement authorization:
python tools/flash_p4_zephyr.py --image build-artifacts/p4-zephyr/zephyr-checked.bin --execute --evidence evidence/2026-10-25/p4-zephyr-csi-flash.json
python tools/test_p4_usb.py --execute --evidence evidence/2026-10-25/p4-zephyr-camera.json --private boards/waveshare_esp32p4_wifi6/outputs/native
```

The helpers require COM5 CH343 VID/PID 1a86:55d3, never select another port,
and do not back up firmware. Images/raw local logs stay under ignored outputs.
Capture stops after each still and test cleanup releases images/stops tasks.
Sanitized evidence contains dimensions, checksums, numerical results and status.

## Graphical client

Package the genuine pinned GP editor and run the local COM5 bridge:

```powershell
python tools/package_p4_ide.py --ide-source build-artifacts/p4-sources/ide --output build-artifacts/p4-editor-native
python tools/serve_p4_ide.py --editor build-artifacts/p4-editor-native --http-port 8875
```

Open `http://127.0.0.1:8875/?bridge=1`, select **Projects & board → Camera
grayscale preview**, then **Connect → Connect Waveshare ESP32-P4 camera**.
After the board identity turns green, Start runs the actual block compiler
and native VM pipeline. The Camera image panel displays/transfers the result;
Download PNG exports within the browser. Stop releases native image handles.
Only one browser/serial controller can own COM5 at a time; close/disconnect
the graphical session before running Python board tests or flashing.

This bridge binds loopback only. It is a local development client, not
board-hosted Wi-Fi. The native C6 hosted profile has passed initialization and
asset checks, but AP startup fails and actual network/editor acceptance is
blocked. Approved AP credentials were privately saved. No Windows firewall,
association or network-security setting was changed.

## Ownership and limits

Four immutable generation-tagged image handles share an 8 MiB store. One
asynchronous capture may additionally own a bounded 1,843,264-byte aligned
DMA workspace including its guard. Store adoption occurs only on the VM
thread; GC owns integers and bounded copied ByteArrays, never native pixels.
Release images explicitly. Pending/busy/capacity errors return zero/false
with camera status. If DMA cannot be quiesced, its buffer is retained and
further capture is prohibited until reset. Nearest-neighbor resize and
weighted grayscale are software. Tensor layout is uint8 HWC RGB888, with
explicit dimensions and no hidden normalization/letterboxing.

The code store is currently RAM-only: programs survive a USB reconnect but
not power loss/reset. ArduinoCore-Zephyr is not linked or validated for P4.
Native bounded microphone PCM and experimental local Whistle are physically
validated. DSP acceleration, codecs and wake word remain staged in
[DSP](docs/DSP.md) and [speech](docs/SPEECH.md). The native TFLM INT8 fixture
also passed on P4. Bounded native neural blocks load the tested INT8 catalog
model or compatible static float32/INT8 dense TFLite artifacts; restricted
offline ONNX conversion is described in [neural networks](docs/NEURAL_NETWORKS.md).
No direct ONNX Runtime or generic YOLO runtime is installed.

Choose **Find I2C devices and read IDs** in Projects & board, or open
`integration/i2c-devices.ubp`. The I2C Devices library has separate **scan I2C
bus** (addresses only) and **identify devices on bus** (documented ID reads).
Bus 0 is SDA7/SCL8; other buses return an explicit unsupported error. Use
device name/address/identification/measurement reporters before reading.
The read reporter formats the value and unit; advanced numeric value/unit/scale
reporters support later processing. Device indices are one-based. References
expire on rescan. See [I2C acceptance and limits](docs/I2C_DISCOVERY.md).

Offline shared image tests: `python3 tools/test_p4_images.py` under WSL with
a host C compiler. They include ASan/UBSan, 10,000 reuse cycles, three formats,
capacity/bounds/stale handles and allocation failure. Root regression check:
`python tools/validate.py`; any pre-existing checkout/provenance failure is
reported separately, without rewriting unrelated board sources.
