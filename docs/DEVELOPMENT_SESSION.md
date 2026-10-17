# Waveshare development session — 2026-10-17

## Scope and acceptance criteria

Start from `e07e6f9e6752f7722a8fa3f790c14f59c515de63` on
`development/waveshare-rlcd`. First compile the pinned upstream hello-world
application, then the board diagnostic application, then integrate SmallVM in
a separate application with exclusive binary serial transport.

The user explicitly authorized full flash erase and replacement on the
Waveshare connected as COM4, without a firmware backup. No backup is to be
made. This session-specific instruction overrides the starter's generic
backup recommendation. It does not authorize eFuse or security changes,
writing another board, or changing repository visibility.

Diagnostic acceptance requires compiler logs and live serial observations for
the exact binary hash. Device readiness alone is not physical validation.
Display appearance and button presses require human observation when no
independent measurement is available. Initial tests exclude SD writes, radios,
audio output and unrestricted GPIO. SmallVM acceptance requires real binary
protocol connection, arithmetic and ordered output, not merely a linked image.

## Target identity before modification

- Windows USB Serial/JTAG interface: COM4, VID 303A, PID 1001, interface 00.
- ROM reports ESP32-S3, revision v0.2; crystal 40 MHz; embedded 8 MB PSRAM.
- Read-only flash identification reports 16 MB flash, 3.3 V quad interface.
- Read-only security report: secure boot disabled; flash encryption disabled.
- Existing application explicitly identifies Waveshare ESP32-S3-RLCD-4.2,
  ST7305 300×400 and SHTC3 at 0x70. Its observations are identity evidence,
  not validation of this project's drivers.
- Opening Windows serial caused a USB serial reset despite DTR/RTS being
  deasserted. No firmware backup was taken. Application/network/token lines
  were excluded from retained evidence.
- COM5 was absent during inventory and is outside this session's write scope.

## Source references

- [Waveshare board documentation](https://docs.waveshare.com/ESP32-S3-RLCD-4.2)
- [Waveshare schematic and datasheets](https://docs.waveshare.com/ESP32-S3-RLCD-4.2/Resources-And-Documents)
- [Vendor examples](https://github.com/waveshareteam/ESP32-S3-RLCD-4.2)
- [Pinned Zephyr source](https://github.com/zephyrproject-rtos/zephyr/tree/a915b2f12675b48b16d56653ea145dcd8f20cbbf)
- [Zephyr board documentation](https://docs.zephyrproject.org/latest/boards/waveshare/esp32s3_rlcd_4_2/doc/index.html)
- [SmallVM upstream](https://codeberg.org/MicroBlocks/smallvm)
- [BeagleBoard reference integration](https://github.com/beagleboard/microblocks-zephyr)
- [ArduinoCore-Zephyr](https://github.com/arduino/ArduinoCore-zephyr)

## Build environment

Use an isolated Linux workspace on the WSL ext4 filesystem, not `/tmp`
(which is RAM-backed on this host). Limit Ninja to two jobs. The WSL VM has
approximately 6 GB RAM and 2 GB swap; the Windows host has approximately 16 GB
RAM. Serial access stays on Windows so no USB reassignment is required.
Dependencies and test results are recorded as they are verified below.

## Results

Pinned Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`
(4.5.0-rc2) and SDK 1.0.1 / GCC 14.3.0 compiled upstream hello-world and
the corrected diagnostic image. Python 3.12.15, west 1.5.0, CMake 4.4.4 and
Ninja 1.13.2 were used. The diagnostic linker reports 216,756 bytes FLASH,
61,484 bytes IRAM and 98,592 bytes DRAM, plus the board's PSRAM reservation.
All nine offline tests pass on Linux.

Build logs and module revisions are saved under `evidence/2026-10-17/`.
Deployment and physical tests are the next stage; no new firmware has been
deployed at this checkpoint.

The attempted COM4 `esptool --chip esp32s3 --port COM4 --after no-reset
erase-flash` command was denied before execution by automatic approval review.
The stated reason was that full erase without backup had not been explicitly
authorized, despite the session confirmation forwarded to this task. No erase
or flash occurred. Do not work around that denial by another writing command;
the parent must resolve it with new, relevant trusted confirmation evidence.

The next physical checks, once deployment is permitted, are `hw status`,
repeated SHTC3 readings, RTC progression/invalid-clock handling, battery raw ADC,
button states/events and display write return codes. Display appearance and
physical button operation remain unverified until observed.

Official SmallVM stable source was inspected at
`e614320450bc3c14cd95b4be4e7b74819ad8d13c` (VM v411, MPL-2.0).
Its existing Zephyr persistence backend assumes directly addressable flash
offsets; it must not be used unchanged for the ESP32-S3 memory map. A first
runtime should use an explicit RAM code store or a bounded, correctly mapped
partition backend. The existing ArduinoCore-Zephyr loader model also requires
an actual ESP32-S3 variant/integration; Zephyr board support alone does not
establish Arduino API compatibility.
