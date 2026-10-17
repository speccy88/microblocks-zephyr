# SmallVM + Arduino API: actual integration work still to do

## Why the hardware bring-up is separate

The already-working UNO Q solution uses an ArduinoCore-Zephyr **LLEXT** loader, a bridge to the Linux CPU, a pinned SmallVM v417 interpreter and a patched graphical editor. The BeagleBoard `microblocks-zephyr` project instead statically builds the VM together with an earlier Zephyr Arduino API module. Neither firmware image can be flashed unchanged onto Waveshare's ESP32-S3 board.

**We should start with a static SmallVM build** using Zephyr's `esp32s3_rlcd_4_2/esp32s3/procpu` board, rather than requiring a new LLEXT loader on day one. `CONFIG_ARDUINO_API=y` requires adding a compatible module to the `west` manifest. It is not automatically provided by Zephyr's generic board target.

The original BeagleBoard CMake compiles `modules/microblocks/vm/*` and links it with `modules/lib/Arduino-Zephyr-API`; test that arrangement against ESP32-S3. Do not blindly import its flash-persistence overlay, which is for BeagleConnect Freedom and could erase reserved ESP32 partitions.

## MicroBlocks port acceptance criteria

1. SmallVM firmware boots, `hardwareInit()`, `primsInit()`, `restoreScripts()` and `vmLoop()` run without watchdog starvation.
2. USB serial transport (binary framing, not text shell) connects to a matching GP MicroBlocks editor. `5+7` returns 12 and 500 records arrive in order, without CRC failure. **The shell and SmallVM must not share the same binary transport simultaneously.**
3. `rlcd_smallvm_primitives.c` is compiled with the SmallVM source and links without duplicate `addIOPrims()` definitions. A valid program reads SHTC3 and display checkerboard, after error cases are handled.
4. The `.ubl` library is imported and its reporter/command semantics verified against the exact pinned GP IDE build. It is a proposed library until then.
5. Same compiled MicroBlocks high-level program can run on UNO Q and Waveshare when all used common capabilities are present.
6. Core Arduino compatibility is independently demonstrated with `pinMode`, `digitalWrite`, `Wire`, `SPI`, and at least one peripheral library on ESP32-S3. If ArduinoCore-Zephyr lacks a supported target, create the required variant/loader extension; do not claim `arduino-esp32` is a drop-in replacement.

## Architectural boundaries

```text
MicroBlocks GP editor (PC/web)
  -> binary transport (USB serial first; BLE/Wi-Fi later)
  -> SmallVM bytecode runtime (separate Zephyr task)
  -> IO named primitives + generic board capability API
  -> Zephyr display/RTC/sensor/ADC/SD/I2S/net drivers
         + selective Arduino API/library adapters
  -> Waveshare hardware
```

Real-time audio I2S processing should use its own bounded thread/queues and cannot be allowed to block the bytecode loop or starve Wi-Fi/BLE. Reserve separate transport from shell logging, and add persistent storage with power-fail tests before enabling automatically loaded programs.

## Missing native drivers/wrappers

* Display: implement graphical pixmaps/text and the required logical 300x400 area versus upstream 312x400 panel memory. Do not assume LVGL coordinates match Zephyr framebuffer layout.
* Audio: upstream board DTS provides I2S pin group, but not a complete initialized codec chain. Waveshare's vendor ES8311 (I2C 0x18) / ES7210 (0x40) code is tied to Espressif codec APIs. Port or wrap equivalent drivers, including gain, sample format, I2S clocking and any speaker-amp enable GPIO confirmed by schematic.
* SD: test 1-bit SDMMC and FAT filesystem, verify removable-card error handling; do not write files in the initial read-only smoke test.
* Wi-Fi/BLE: test RF blobs, stack sizes and coexistence while VM and display refresh are active.
* Power: validate ADC calibration, battery voltage, charger behavior, charging indication and sleep/wake behavior; do not infer state-of-charge from one voltage measurement without appropriate caveats.
* GPIO: maintain a reserved-pin whitelist and reject attempts to drive boot, battery, display, codec and SD signals.
