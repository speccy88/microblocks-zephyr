# Standalone graphical MicroBlocks

This target combines pinned Zephyr, the Arduino API, SmallVM v417 and the real
MicroBlocks 2.5.8 GP editor. The board serves compressed editor assets from
flash; compilation runs in the computer's browser and bytecode travels over an
authenticated binary WebSocket. USB is reserved for installation and recovery.

## Build

Use the pinned workspace described in the parent board README and verified
snapshots from `dependencies/`. The Arduino module is
`zephyrproject-rtos/arduino-core-zephyr` at
`af5b8610f9be6d7b962e2ba6dd8e6859697c44ff`, with checksum-verified
ArduinoCore-API 1.5.2 blobs. Prepare that checkout with
`python3 tools/prepare_arduino.py /path/to/arduino-api --fetch-api`.
Substitute absolute paths to those local sources:

```sh
export ZEPHYR_BASE=/path/to/workspace/zephyr
export ZEPHYR_SDK_INSTALL_DIR=/path/to/zephyr-sdk-1.0.1
export CMAKE_BUILD_PARALLEL_LEVEL=4
west build -b esp32s3_rlcd_4_2/esp32s3/procpu -d build/standalone \
  /path/to/microblocks-zephyr/boards/waveshare_esp32s3_rlcd_4_2/standalone -- \
  -DEXTRA_CONF_FILE= \
  -DZEPHYR_EXTRA_MODULES=/path/to/prepared/arduino-api \
  -DSMALLVM_SOURCE_DIR=/path/to/verified-smallvm-v417 \
  -DIDE_SOURCE_DIR=/path/to/verified-ide-2.5.8
```

CMake validates the pinned source hashes, applies the adapters, packages local
assets and creates device-specific access values in the build's `private/`
directory. Preserve that directory across rebuilds. It and the resulting
firmware contain access credentials and are excluded from Git.

The final tested command and compiler output are recorded in
`evidence/2026-10-17/production-keepalive-build.txt`. Installing firmware requires
explicit authorization for the selected board. App-only writes to offset zero
preserve this target's program and Wi-Fi partitions; a full erase does not.

## Use

1. With saved station settings, open the board's displayed IP in a browser on
   the same LAN. Without settings it starts a protected fallback AP; the KEY
   boot path can request that fallback while preserving station settings.
2. Use **Connect → Connect Waveshare**, entering the board's pairing code.
   **Board** contains the hardware library, examples and Wi-Fi setup link.
3. Drag and run blocks in the actual editor. Start runs start-hat scripts.
   Individual script stop retains variables; global Stop uses upstream
   `softReset` and clears them.
4. Program changes are snapshotted after a two-second debounce. Start-hat
   scripts automatically run from the saved bytecode after reset.
5. To retrieve a saved program into a fresh editor, choose **Project → Open
   from board before Connect**. Ordinary Connect synchronizes the current
   editor project to the board. Readback reconstructs logic and variable names;
   save a normal project file to retain original layout/comments and metadata.

Keep this local HTTP service on a trusted LAN. One authenticated controller is
allowed at a time. `/api/status` reports VM/storage state; `/api/memory` reports
the measured common-libc and kernel allocator pools with uptime.

## Verified checkpoint

The final image passes four fresh real-editor loads, 148 asset content/header
checks, graphical 12-to-13 editing, temperature reporting, 500 ordered outputs,
stop/variable inspection, reconnect, saved code/autostart and graphical readback.
Ten heap samples were taken during an active graphical counter workload.
Exact values, firmware hash and remaining limits are in
`evidence/2026-10-17/{graphical-acceptance,storage-capacity,runtime-memory}.json`
and `docs/DEVELOPMENT_SESSION.md`.

Display appearance, physical button presses, RTC setting/retention, calibrated
voltage, microSD, BLE, audio, sleep and broad Arduino library compatibility
remain unverified or unimplemented. Mid-session station-loss fallback is not
implemented. No microSD is needed for the editor assets.
