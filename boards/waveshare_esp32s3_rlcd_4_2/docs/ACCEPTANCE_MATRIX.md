# Hardware validation checklist — fill with actual device test evidence

| Feature | First physical test | Phase-1 software status | Evidence to collect |
|---|---|---|---|
| USB / console | Build Zephyr hello_world, read log, open serial shell | Compile not verified | COM/tty port, boot log |
| Display ST7305/ST7306 | `hw display checker`, confirm all edges and orientation | Driver call implemented, uncompiled | Screen photo, visible crop, errors |
| SHTC3 | `hw sensor`; compare to room conditions | Driver call implemented, uncompiled | Values + timestamp |
| RTC | `hw rtc`, power-cycle with RTC battery | Driver call implemented, uncompiled | Time retention, read return |
| BOOT / KEY | Hold/release one at a time; `hw buttons` | Input callback implemented, uncompiled | Both state transitions |
| Battery ADC | `hw battery`, compare voltmeter | ADC call implemented, uncompiled | Raw counts, measured voltage, calibrated gain |
| microSD | Read CID, mount FAT, list existing files | Not yet implemented | Card size / read-only test |
| Wi-Fi | Scan SSIDs, join AP, IP, TLS | Not yet implemented | Connectivity + throughput |
| BLE | Advertise GATT capability service, connect | Not yet implemented | Discoverable advertisement + pairing |
| I2C external | Detect a known added sensor on GPIO13/14 | I2C ready check only | Sensor ID, voltage levels |
| Generic GPIO/ADC/PWM/UART | Verify isolated external pins with meter | Not yet implemented | Pin table with drive/current limits |
| ES8311 speaker | PCM tone / controlled volume | Not yet implemented | Scope/audio test, codec registers |
| ES7210 dual microphones | Stereo PCM test, measured signal | Not yet implemented | Sample data, channels, gains |
| Power/charging | USB, protected battery, charging indicator, sleep | Not yet implemented | Charge/sleep current, wake paths |
| SmallVM bytecode | 5+7, 500 ordered values, reconnect | Adapter source only | Compiler/VM protocol evidence |
| Arduino API | GPIO, I2C, SPI, third-party sensor library | Not yet integrated | Compiled code + hardware observations |

No rows may be marked PASS solely from Devicetree node presence or automated source checks.
