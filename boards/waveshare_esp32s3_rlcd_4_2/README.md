# Waveshare ESP32-S3-RLCD-4.2 board port

**Experimental development port — 2026-10-17.**

Goal: a portable **Zephyr + Arduino API + MicroBlocks SmallVM** platform with board-specific graphical blocks and full access to the hardware on Waveshare's ESP32-S3-RLCD-4.2.

## What this package really contains

* `bringup/`: a **native Zephyr app** with real driver calls for ST730x display, SHTC3, PCF85063A RTC, BOOT/KEY input events and battery ADC. Commands appear in Zephyr's serial shell.
* `hardware.json`: structured pin, I2C address and feature map for **all known board peripherals**. Each feature declares its implementation/testing state.
* `arduino_smoke/`: compiled target using the real Arduino API module.
* `smallvm/`: linked SmallVM v417 with bounded execution and a recovery/test USB transport.
* `standalone/`: actual graphical IDE in compressed flash assets, Wi-Fi setup, HTTP/WebSocket server and program snapshots. Station Wi-Fi, protected fallback AP, HTTP assets and binary WebSocket are physically tested.
* `integration/rlcd_smallvm_primitives.c`: linked named primitives calling the same Zephyr board APIs.
* `integration/Waveshare_RLCD_4_2.ubl`: board blocks embedded in the standalone editor. The library loads in the real board-served editor; graphical live execution is awaiting acceptance.
* `tests/`: offline manifest/source integrity checks.

**Current evidence:** pinned Zephyr/SDK builds, physical boot, SHTC3 and battery
reads, released button inputs, LCD transfers and Wi-Fi association. RTC is
unset. Wireless VM arithmetic/editing, 500 ordered outputs, CRCs, stop/variables,
reconnect and reboot/autostart pass. Graphical live programming, display
appearance, physical button presses, SD, BLE and audio remain unvalidated. See the
[session record](../../docs/DEVELOPMENT_SESSION.md) and `hardware.json`.

## Board facts (source-backed)

* Exact mainline Zephyr board target: `esp32s3_rlcd_4_2/esp32s3/procpu`.
* Flash 16 MiB, PSRAM 8 MiB, ESP32-S3 dual-core Xtensa LX7.
* Visible RLCD 300×400; upstream Zephyr uses an ST7306-compatible driver with 312×400 memory geometry, while Waveshare calls the chip ST7305. Screen mapping/orientation require a physical test.
* Onboard I2C bus: GPIO13 SDA, GPIO14 SCL; SHTC3 0x70, RTC 0x51, ES8311 0x18, ES7210 0x40. Codec addresses are confirmed in Waveshare's Arduino code.
* ST730x SPI: GPIO11 SCLK, GPIO12 MOSI, GPIO40 CS, GPIO5 DC, GPIO41 RESET, GPIO6 TE.
* microSD: GPIO21 CMD, GPIO38 CLK, GPIO39 DAT0 (1-bit SDMMC upstream).
* Audio I2S: GPIO16 MCLK, GPIO9 BCLK, GPIO45 WS, GPIO10 MCU→DAC, GPIO8 ADC→MCU.
* Battery ADC: GPIO3, schematic 100k/200k divider -> multiply ADC pin voltage by 3; ESP32 ADC calibration needs independent validation.
* Buttons: BOOT GPIO0, KEY GPIO18. Power (PWR) is a power-control button rather than a normal application input.
* No touchscreen advertised or visible in supplied schematic, despite a misleading mention in upstream Zephyr overview. ESP32 capacitive touch pad capability is not the same as an LCD touch panel.

Do **not** drive board-reserved signals as generic GPIO, especially GPIO0 (strap), 3 (battery ADC), 18 (KEY), 13/14 (shared I2C), 40/41/5/6/11/12 (LCD), 19/20 (USB), 8/9/10/16/45 (audio), and SD pins 21/38/39.

## Step 1 — Prepare a Zephyr workspace (Linux or WSL)

```sh
sudo apt update
sudo apt install -y git cmake ninja-build gperf ccache dfu-util \
    device-tree-compiler wget python3-dev python3-venv python3-pip \
    xz-utils file make gcc g++
python3 -m venv ~/zephyr-venv
. ~/zephyr-venv/bin/activate
pip install --upgrade pip west
mkdir -p ~/zephyrproject && cd ~/zephyrproject
west init -m https://github.com/zephyrproject-rtos/zephyr.git --mr main
# Reproduce the actual upstream board definition examined for this starter:
git -C zephyr checkout a915b2f12675b48b16d56653ea145dcd8f20cbbf
west update
west blobs fetch hal_espressif
west packages pip --install
west sdk install
```

`west sdk install` may download a substantial toolchain. Zephyr/Espressif versions change; record tool versions and resolve any local SDK installation prerequisites rather than substituting an incompatible toolchain. The Espressif RF blobs are required for wireless support.

The ESP32 board target above is **PROCPU**. Zephyr's current APPCPU support has serial/logging limitations that make it a poor initial MicroBlocks target.

### Optional USB pass-through from Windows 11 to WSL

From elevated PowerShell, with the board connected:

```powershell
usbipd list
usbipd bind --busid <BUSID>
usbipd attach --wsl --busid <BUSID>
```

Then under WSL check `ls /dev/ttyACM* /dev/ttyUSB*`. Replace `<BUSID>` with the actual hardware bus ID from `usbipd list`. USB detaches from Windows while assigned to WSL; stop serial monitors first.

## Step 2 — Check the base target before any MicroBlocks work

```sh
cd ~/zephyrproject
. ~/zephyr-venv/bin/activate
west build -b esp32s3_rlcd_4_2/esp32s3/procpu zephyr/samples/hello_world -p always
```

If that compiles, **BACK UP THE CURRENT FLASH BEFORE FLASHING.** Reading flash may require manually entering ESP32-S3 download mode. Replace PORT with the actual device and keep the backup outside any public repository:

```sh
pip install esptool
python -m esptool --chip esp32s3 --port /dev/ttyACM0 read-flash 0 0x1000000 ~/rlcd-factory-flash-16MB.bin
sha256sum ~/rlcd-factory-flash-16MB.bin
```

Only when you are satisfied the backup is complete and readable:

```sh
west flash
```

This replaces installed firmware and can erase application settings depending on the chosen boot mode/partition layout. A flash dump is valuable, but test restore procedures separately. Waveshare also publishes factory firmware under GitHub Releases.

## Step 3 — Build the Waveshare hardware diagnostics

From the cloned `microblocks-zephyr` repository, then:

```sh
cd ~/zephyrproject
west build -b esp32s3_rlcd_4_2/esp32s3/procpu \
    /absolute/path/to/microblocks-zephyr/boards/waveshare_esp32s3_rlcd_4_2/bringup -p always
```

Inspect the Kconfig warnings/errors first. **This has not been compiled against Zephyr in this environment.** If successful, after backing up and selecting the correct board/port:

```sh
west flash
```

Open the Zephyr serial shell at the board's advertised serial port (typically 115200 baud). Try these commands **one at a time**, checking return errors:

```text
hw status
hw sensor
hw rtc
hw battery
hw buttons
hw display checker
hw display black
hw display white
```

A successful driver-ready check is **not** proof the physical part has been exercised. Photograph the display result and note physical button events and sensor measurements. `hw display` is opt-in and does not run on boot.

## Step 4 — Make it a genuine MicroBlocks runtime

See [`integration/PORTING.md`](integration/PORTING.md). Use the BeagleBoard Zephyr SmallVM port as the static-build reference, your tested `speccy88/uno-q-microblocks` port as the protocol and IDE reference, and this `rlcd_board.*` API as the board-driver boundary.

Work in increments:

1. Port and compile SmallVM + Zephyr + the Arduino API module with a USB serial transport; verify official MicroBlocks bytecode (arithmetic and 500-value output) before hardware blocks.
2. Link `integration/rlcd_smallvm_primitives.c`, add it to the VM's IO primitive table, and load the experimental `.ubl` library.
3. Add display text/pixel primitives, device enumeration and persistence; keep the existing UNO Q IDE behavior when porting.
4. Integrate SD/FAT, Wi-Fi and BLE, then ES8311/ES7210 audio using correct Zephyr I2S/codec drivers.
5. Make a board-capability handshake and auto-import only the blocks supported by the live firmware.

Arduino API note: `ArduinoCore-zephyr` **does not magically support every Zephyr target**. Espressif's `arduino-esp32` library ecosystem also assumes ESP-IDF and FreeRTOS APIs in places; full binary/source compatibility cannot be promised. Verify a working Arduino API port on ESP32-S3, then add individual library adapters. Do not attempt to link an `arduino-esp32` binary into a Zephyr image.

## Tests that can be run without a board

```sh
# from the repository root
python3 tools/validate.py
```

These check only the manifest, reserved pins and source contracts. They do **not** replace a Zephyr compilation or hardware test.

## Reference projects

* Zephyr board DTS: https://github.com/zephyrproject-rtos/zephyr/tree/main/boards/waveshare/esp32s3_rlcd_4_2
* Waveshare schematics and manuals: https://docs.waveshare.com/ESP32-S3-RLCD-4.2/Resources-And-Documents
* Waveshare examples: https://github.com/waveshareteam/ESP32-S3-RLCD-4.2
* Working UNO Q SmallVM: https://github.com/speccy88/uno-q-microblocks
* BeagleBoard MicroBlocks Zephyr: https://github.com/beagleboard/microblocks-zephyr
* ArduinoCore-Zephyr: https://github.com/arduino/ArduinoCore-zephyr
* SmallVM source: https://codeberg.org/MicroBlocks/smallvm

## Licensing

New diagnostic files and scripts in this package: MIT. `integration/rlcd_smallvm_primitives.c`: MPL-2.0 as an extension of the MicroBlocks SmallVM integration. Third-party upstream source is **referenced, not redistributed** in this repository. Follow the respective upstream licenses when combining projects.
