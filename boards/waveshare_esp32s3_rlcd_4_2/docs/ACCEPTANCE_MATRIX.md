# Hardware acceptance record - updated 2026-10-18

Evidence is under `evidence/2026-10-17/` and `evidence/2026-10-18/`.
PASS applies only to the behavior listed.

| Feature | Verified behavior | Remaining acceptance |
|---|---|---|
| Zephyr / USB recovery | Pinned build and physical COM4 boot/reset; app-only writes verified by esptool hash | Physical unplug/replug |
| Display ST7305/ST7306 | Checkerboard and text driver transfers return success | Human observation/photo of appearance, edges and orientation |
| IP LCD screen | Earlier physical station/AP boot logs show CFB transfer 0; compiled-font layout fits visible bounds | Physical text readability and orientation; no framebuffer/photo capture |
| SHTC3 | Real temperature/humidity reads; graphical temperature block returned 26093 milliC | Independent calibrated comparison |
| RTC | Real UTC setter/readback, 15 invalid inputs rejected, leap-day rollover, ticking and powered COM4-reset retention pass | Battery/power-removal retention and long-term accuracy |
| BOOT / KEY | Released-state inputs read; KEY boot fallback is implemented | Physical press/release events |
| Battery ADC | Real raw ADC reads, 1291 in final wireless regression | Voltmeter comparison/calibration |
| microSD | Unused; no formatting or file mutation | Read-only card detection and filesystem support |
| Wi-Fi | Protected startup AP, DHCP, station settings/reboot, local HTTP/WS | Mid-session station-loss fallback is not implemented; long-duration stability |
| AP fallback triggers | No-saved-network AP physically joined; DHCP, editor assets, authenticated VM arithmetic pass in earlier image | KEY-at-boot and failed-saved-station triggers physically untested; final graphical acceptance used station mode |
| Real graphical IDE | Historical 148/148 assets and graphical editing/readback; current basic check is 50 outputs, direct local connection | Broader browser/device coverage; see current session evidence |
| Saved program | Original three CRCs preserved across app-only updates and powered reset; 1-variable/3-chunk readback and current graphical 50 run | Full original project metadata is not stored |
| Memory | Ten heap samples during active graphical count/say workload | VM object arena GC-free-space telemetry; long-duration stress |
| BLE | Not implemented | GATT/connection tests |
| Generic I2C | Native register get/set and named read/write/exists implemented; ES8311 ID reads via ByteArray/List return 131/17; known-address presence and atomic write/read pass | Arbitrary data writes and absent-device behavior simulated; external devices/libraries untested; no bus scan |
| External GPIO/ADC/SPI/PWM | Safe pin map compiled; actual VM/backend simulations pass for bounds, error propagation, SPI cache refresh, PWM duty/Stop and deferred init | External ADC accuracy, SPI loopback and PWM waveform/duty; no physical output test |
| ES8311 / ES7210 audio | Speaker tone/busy/stop implemented; silent timing/DMA/stop tests pass in preceding checkpoint; current boot remains muted | Audible speaker confirmation pending; microphone not implemented |
| Power / sleep | Not implemented | Charge/sleep current and wake tests |
| SmallVM bytecode | Real v417: arithmetic/edit, fragmented 1019-byte upload, timeout recovery, CRCs, current 50 outputs, stop/reconnect/autostart; 43 generic I/O simulation checks | Wider program suite |
| Arduino API | Real pinned module compiles alongside Zephyr/SmallVM; Wire initialization/buffer/clock adapter | Representative third-party sensor/SPI/GPIO library tests |

No PASS is inferred from Devicetree node presence or source checks. The board's
full peripheral feature set remains experimental.
