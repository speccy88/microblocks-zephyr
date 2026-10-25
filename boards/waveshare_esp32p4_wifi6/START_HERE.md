# Native Zephyr MicroBlocks camera

This port runs genuine SmallVM v417 on native Zephyr, on the Waveshare
ESP32-P4-WIFI6 revision 1.3/pre-v3 board (32 MiB flash and PSRAM). The tested
camera is the IMX219 Camera V2.1 in the WX-RPI CAMERA adapter socket. DISP is
unused. Keep COM12 untouched. Do not use ESP32-P4 revision-v3 firmware.

Physical tests: three 1280x720 RGB565 stills, 160x90 resize/grayscale,
RGB888 HWC uint8 preprocessing, bounded export and handle lifecycle passed.
Scene quality is untuned: fixed exposure/gain, no calibrated AWB/AE/LSC.
The OV5647 800x640 RAW8 driver is retained but not physically retested under
Zephyr with the current IMX219 attached. See [tasks](docs/TASKS.md).

## Build

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

The editor also loads **P4 Audio**. Select **Bounded PCM levels (acoustics
unverified)** and press Start explicitly for a 500 ms recording, RMS/peak
report and release. No recording/listening begins merely by opening the page.
Stop All cancels pending recording and releases completed audio handles.
At startup the identified ES8311 ADC and speaker amplifier are disabled.

Actual codec ID, 16 kHz DMA timing, two-handle capacity, release/cancellation
and concurrent VM execution passed physical tests. The one-second run measured
15,999.1 frames/s from DMA completion timing. Quiet samples alone do not verify
microphone acoustic response, speech recognition or wake-word detection; these
remain separate controlled tests. No raw recordings are committed or uploaded.

```powershell
python tools/test_p4_audio_usb.py --execute --evidence evidence/2026-10-25/p4-audio-pcm.json
```

The default build remains USB-only. The separate `profiles/c6-probe.conf`
and `profiles/c6-sdio.overlay` build is a transport/version diagnostic, with no
Wi-Fi consumer or credential/AP RPC. It requires the pinned Nanopb module
(`west update nanopb`) and `grpcio-tools` for code generation. SDIO initializes;
the installed companion has not yet answered the current version protocol.
No companion firmware was changed. See [network proposal](docs/NETWORK_PLAN.md).

## Flash and physical checks

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
board-hosted Wi-Fi. C6 SDIO handshake, approved network setup and true
board-hosted assets/WebSockets remain separate acceptance gates. No Wi-Fi,
firewall or network security configuration has been applied.

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
DSP acceleration, codecs, microphone/Whistle and wake word are staged in
[DSP](docs/DSP.md) and [speech](docs/SPEECH.md); unsupported functions are not
presented as working blocks. No generic ONNX/YOLO runtime is installed.

Offline shared image tests: `python3 tools/test_p4_images.py` under WSL with
a host C compiler. They include ASan/UBSan, 10,000 reuse cycles, three formats,
capacity/bounds/stale handles and allocation failure. Root regression check:
`python tools/validate.py`; any pre-existing checkout/provenance failure is
reported separately, without rewriting unrelated board sources.
