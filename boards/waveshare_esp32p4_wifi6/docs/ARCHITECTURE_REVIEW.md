# Native Zephyr architecture

2026-10-25. Fred selected native Zephyr to preserve the cross-platform
MicroBlocks ecosystem and future ArduinoCore-Zephyr integration. This is the
implemented target. The tested ESP-IDF proof remains on a separate local-only
reference branch and is not the delivered runtime.

## Physical native milestone

SmallVM v417 runs on Zephyr with native UART, PSRAM, I2C, regulator, video,
cache and thread interfaces. The new P4 receiver uses the bundled Espressif
CSI/ISP/DW-GDMA HAL directly, with no FreeRTOS camera drivers or task shim.
COM5 tests passed arithmetic/edit, 50 outputs, fragmented uploads, reconnect,
and three real IMX219 captures with resize/grayscale/RGB888/export/release.
The genuine graphical GP compiler also ran the camera script and displayed
its 160x90 grayscale result. Arduino API parity and board-hosted Wi-Fi remain
separate gates; a loopback development server does not establish either.

The motivation was to reuse the exact tested CSI/ISP path in camera source
fc60acbb0c1eb080ee57b3aca5942e81539e6049. That implementation depends on
esp_video V4L2, esp_cam_sensor, esp_ipa, IDF I2C, and FreeRTOS scheduling.
That original reference was not evidence that Zephyr cannot support P4.

## Existing repository baseline

The repository's primary design is SmallVM in a Zephyr task, with Zephyr device
APIs and ArduinoCore-Zephyr integration. The installed/repository reference
Zephyr revision is a915b2f12675b48b16d56653ea145dcd8f20cbbf (2026-10-16).
The existing S3/Fruit Jam/XRP transport, scheduler, GC integration, and browser
compiler work are reusable for a native P4 port. P2 is already a separately
identified native SDK exception, but that does not authorize changing the P4
goal from Zephyr without discussing the tradeoff.

## Verified Zephyr capabilities and gap

- Exact esp32p4_wifi6/esp32p4/hpcore target exists, including revision-1.3
  settings, 360 MHz CPU, UART0 GPIO37/38, I2C0 GPIO7/8, 32 MiB flash and a
  32 MiB PSRAM node. Native P4 boot/VM is therefore a viable starting point.
- IMX219 sensor driver and the generic video buffer/endpoint API exist.
- ESP-Hosted-MCU SDIO transport and Wi-Fi drivers exist. They are separate
  from the older esp_hosted SPI driver. The current MCU driver's expected C6
  firmware major version defaults to 3; it must match the actual companion.
- The exact board documentation says MIPI CSI/DSI, audio and C6 wireless are
  not enabled in its initial board port. Hardware presence is not validation.
- At the pinned revision and the current upstream video CMake list inspected,
  Espressif video support selects video_esp32_dvp.c; its Kconfig identifies
  ESP32-S3 DVP. No P4 MIPI CSI receiver/ISP video implementation is listed.
  The NXP CSI drivers in that list serve different hardware. This identifies
  missing integration, not an impossibility or a claim about all external work.
- No OV5647 sensor driver is listed there. Retaining that camera requires a
  Zephyr sensor adaptation as well as the P4 receiver path.

## Native Zephyr work required

1. Build the existing exact-board target with revision/PSRAM settings, then
   link the repository's Zephyr SmallVM platform and verify COM5 transport.
2. Implement/adapt a P4 MIPI CSI receiver and ISP path behind Zephyr's video
   API, including clocks/LDO, DMA descriptors, interrupts, cache coherency,
   timeouts and buffer lifecycle. Port low-level HAL code where compatible;
   a FreeRTOS task shim alone does not supply those integrations.
3. Bind the existing IMX219 driver to that pipeline and validate mode/crop;
   adapt OV5647 while preserving its license and tested settings.
4. Replace the current IDF worker, allocator, UART/time and NVS adapters with
   Zephyr equivalents. Reuse the portable image store and native block API.
5. Enable the C6 SDIO node/pins, verify the installed firmware handshake, then
   validate Wi-Fi and the repository's native HTTP/WebSocket service on P4.
   Neither a successful build nor a Wi-Fi control RPC proves bidirectional data.

The image store, conversion algorithms, .ubl API, real GP editor packaging,
preview protocol, sanitizer tests and physical image-pipeline acceptance
criteria survive that change. The current IDF capture driver is a proven
reference and an interim working path, not a drop-in Zephyr driver.

## Primary references checked

- https://docs.zephyrproject.org/latest/boards/waveshare/esp32p4_wifi6/doc/index.html
- https://raw.githubusercontent.com/zephyrproject-rtos/zephyr/main/drivers/video/CMakeLists.txt
- https://raw.githubusercontent.com/zephyrproject-rtos/zephyr/main/drivers/video/Kconfig.esp32_dvp
- https://docs.zephyrproject.org/latest/build/dts/api/bindings/video/sony,imx219.html
- https://docs.zephyrproject.org/latest/build/dts/api/bindings/wifi/espressif,esp-hosted-mcu-sd.html
- Pinned local drivers/misc/esp_hosted_mcu/Kconfig and exact board DTS files.

The subsequent native implementation was built and flashed under Fred's
explicit P4 firmware authorization. No companion firmware, network/security
configuration or audio recording was changed in this milestone.
