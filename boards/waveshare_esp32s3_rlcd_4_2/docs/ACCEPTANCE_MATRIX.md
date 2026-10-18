# Hardware acceptance record - 2026-10-17

Evidence is under `evidence/2026-10-17/`. PASS applies only to the behavior listed.

| Feature | Verified behavior | Remaining acceptance |
|---|---|---|
| Zephyr / USB recovery | Pinned build and physical COM4 boot/reset; app-only writes verified by esptool hash | Physical unplug/replug |
| Display ST7305/ST7306 | Checkerboard and text driver transfers return success | Human observation/photo of appearance, edges and orientation |
| IP / pairing LCD screen | Earlier physical station/AP boot logs show CFB transfer 0; compiled-font layout fits visible bounds | Physical IP/pairing text readability and orientation; no framebuffer/photo capture |
| SHTC3 | Real temperature/humidity reads; graphical temperature block returned 26093 milliC | Independent calibrated comparison |
| RTC | Real UTC setter/readback, 15 invalid inputs rejected, leap-day rollover, ticking and powered COM4-reset retention pass | Battery/power-removal retention and long-term accuracy |
| BOOT / KEY | Released-state inputs read; KEY boot fallback is implemented | Physical press/release events |
| Battery ADC | Real raw ADC reads, 1291 in final wireless regression | Voltmeter comparison/calibration |
| microSD | Unused; no formatting or file mutation | Read-only card detection and filesystem support |
| Wi-Fi | Protected startup AP, DHCP, station settings/reboot, local HTTP/WS | Mid-session station-loss fallback is not implemented; long-duration stability |
| AP fallback triggers | No-saved-network AP physically joined; DHCP, editor assets, authenticated VM arithmetic pass in earlier image | KEY-at-boot and failed-saved-station triggers physically untested; final graphical acceptance used station mode |
| Real graphical IDE | 148/148 assets; four fresh 39-request loads; pairing, 12 to 13 edit, 500 ordered outputs, stop/variables/reconnect | Broader browser/device coverage |
| Saved program | CRCs preserved, count 500 autostart after COM4 reset; 1-variable/3-chunk readback then graphical 500 run | Full original project metadata is not stored |
| Memory | Ten heap samples during active graphical count/say workload | VM object arena GC-free-space telemetry; long-duration stress |
| BLE | Not implemented | GATT/connection tests |
| External I2C/GPIO/ADC/PWM/UART | Arduino API compiles; onboard I2C used by SHTC3 | External-pin and third-party library physical tests |
| ES8311 / ES7210 audio | Not implemented | Codec, PCM, channel and volume tests |
| Power / sleep | Not implemented | Charge/sleep current and wake tests |
| SmallVM bytecode | Real v417: arithmetic/edit, fragmented 1019-byte upload, timeout recovery, CRCs, 500 outputs, stop/reconnect/autostart | Wider program suite |
| Arduino API | Real pinned module compiles alongside Zephyr/SmallVM; Wire initialization/buffer/clock adapter | Representative third-party sensor/SPI/GPIO library tests |

No PASS is inferred from Devicetree node presence or source checks. The board's
full peripheral feature set remains experimental.
