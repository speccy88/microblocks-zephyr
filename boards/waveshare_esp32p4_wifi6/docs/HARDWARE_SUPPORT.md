# ESP32-P4-WIFI6 support audit, version 4

Audited 2026-10-26, updated 2026-10-27, against the linked Waveshare schematic (all three pages),
the pinned Zephyr source and this port's physical evidence. This is the
ESP32-P4-WIFI6 with 32 MiB PSRAM and 32 MiB NOR, not a 16 MiB DEV-KIT variant.
The attached P4 reports silicon revision 1.3/pre-v3. The PCB revision and
assembly markings have not been independently photographed/read: the supplied
images were product-listing screenshots, so they cannot establish PCB revision
or component population on Fred's particular assembly. Schematic population
below is distinguished from an actual electrical test.

Canonical runtime capabilities remain in [hardware.json](../hardware.json).
States describe this MicroBlocks port: **tested** = physical end-to-end
evidence for the stated operation; **implemented-unverified** = source/build
exists without that physical gate; **missing** = no usable port/block;
**incompatible** = the specified path cannot provide the requested contract.
Upstream driver availability alone never earns tested status.

## Populated circuitry and attached devices

| Part/path | Wiring and shared resources | Native backend / blocks | State and acceptance evidence |
|---|---|---|---|
| P4 HP core, PSRAM | ESP32-P4NRW32; 32 MiB stacked RAM; cache/DMA coherency required | Zephyr HP target; bounded native pools, SmallVM | **tested** UART execution and full frame allocations; `p4-zephyr-vm.json` |
| NOR U7 | Schematic GD25Q256 family; dedicated flash pins, 32 MiB | Simple-boot app/model, assets, NVS partition guards | **tested** image/hash flash, mapped Whistle model and saved station credential readback. Persistent MicroBlocks program/OTA are **missing**; no flash encryption claim |
| CH343P U4, Type-C H2 | UART0 TX37/RX38; RTS/DTR auto-reset into EN/GPIO35 | Native UART binary SmallVM, USB Web Serial editor | **tested** actual edit/compile/run/reconnect; not USB OTG |
| Reset / boot keys | RESET pulls EN low; BOOT GPIO35, also auto-download strap | Flash/recovery path used; no user button reporter yet | Recovery **tested**; MicroBlocks button input **missing**. Do not repurpose strap/reset pins |
| Power LED / supplies | LED1 tied to supply, not a programmable RGB LED; MP1585/MP1605 regulators; on-chip LDOs | Fixed supply setup; CSI LDO3 2.5 V | Running supplies/CSI **tested**. User LED/power-control blocks **missing**; no output driven for a nonexistent LED |
| I2C0 | SDA7/SCL8 shared by codec, CSI/DSI control and header; port uses 100 kHz | Zephyr I2C, bounded discovery/readings registry | **tested** address, identity, camera register readings and GP example; `p4-i2c-native.json`, `p4-i2c-clarity-native.json` |
| IMX219, external Camera V2.1 | Attached through WX-RPI-22-15 to J1 CAMERA; ID0219 at0x10; dedicated two-lane CSI | Native video sensor + CSI/DW-DMA/ISP, take picture | Capture/transform/export **tested**, `p4-zephyr-camera.json`. Latest dark-scene content gate **failed** pending lighting; AE/AWB/color tuning **missing** |
| OV5647, alternate attachment | ID5647 at0x36; mutually exclusive current camera attachment | Retained native sensor path and licensed reference | **implemented-unverified** in current native image; earlier IDF capture is not native Zephyr evidence |
| ES8311 U9 + MIC1 | Codec at0x18; I2C7/8; MCLK13/BCLK12/LRCK10, codec output→P4 RX11; P4 TX9→codec input | Native Zephyr I2S AHB DMA, bounded 16 kHz mono PCM blocks | Input/controlled acoustic response/GUI playback **tested**; `p4-audio-pcm.json`, `p4-audio-browser.json`, `p4-whistle-microphone.json`. Browser playback does not prove board speaker output |
| NS4150B U11, SPK H6 | ES8311 analog output to PA; enable GPIO53; separate speaker load required | PA held off; no TX I2S/codec playback path | **missing** output blocks/driver setup; attached speaker and safe load not verified |
| C6-MINI-1 U14 | SDIO P4 D0..3=14..17, CLK18, CMD19, reset54; C6 boot strap has GPIO6 path; UART header H4 is C6 IO9/GND/RX/TX | Native ESP-Hosted driver, station-only profile | Synthetic response540, real association/DHCP and wireless VM **tested** after host fixes; factory C6 unchanged, installed version unknown. Gated diagnostic reboot behavior only; no production reconnect pass. [Current results](NETWORK_LIVE_VALIDATION.md) |
| C6 Bluetooth / 802.15.4 | C6 radio silicon, no separate P4 radio | No selected Hosted transport/backend or blocks | **missing**; Wi-Fi presence does not establish BLE/Thread support |
| Unknown I2C responder | 0x64 on bus0 | Address-only record; no guessed probe/decoder | ACK **tested**, identity/measurements **missing** |

## Connectors and expansion

| Interface | Exact schematic routing / conflict | Port coverage / remaining gate |
|---|---|---|
| J1 CSI, 22 pins | Dedicated CSI0/1 data + clock; I2C7/8; connector control IO0/IO1 drawn via 0-ohm links to GPIO4/5 | Current IMX219 capture **tested**; connector presence does not validate arbitrary sensors |
| J2 DSI DISPLAY, 22 pins | Dedicated DSI lanes + clock; I2C7/8; shares the camera/codec control bus | Display attachment absent; MicroBlocks display/touch path **missing**. Do not infer a touch controller from the connector |
| MicroSD TF1 | CLK43/CMD44/D0=39/D1=40/D2=41/D3=42; active-low power GPIO45 | Native asynchronous read-only FAT32 mount/capacity/root count, cancellation/reuse and simultaneous Wi-Fi asset transfer **tested** on0a704563. Raw capacity31,299,993,600 bytes; six entries, no private filenames/content logged. SD file editing/backend and graphical library acceptance remain **missing**. No format or write. [Evidence](../../../evidence/2026-10-27/p4-sd-readonly-summary.json) |
| USB OTG P1, 4 pins | VCC5V/D-/D+/GND, dedicated SoC USB signals; distinct from Type-C CH343 | HS host/device application, HID, mass storage **missing**; no attached peripheral verified |
| USB FS/JTAG test pads | GPIO34/36 test pads; also header positions 17/16 per schematic | **missing** application/debug exposure; do not conflate with P1 HS or CH343 serial |
| 40-pin Pico-style header U10 | Physical header labels are GPIO numbers, not sequential P4 GPIO0..29. Includes power/ground/EN, SDA7/SCL8, GPIO2..5,20..33,46..52, USB34/36 | Generic GPIO/ADC/PWM/SPI/UART blocks currently **missing** (`platform.c` rejects them). Pin conflict validation must precede enabling raw outputs |
| Extra SPI/UART/I2S | SoC GPIO matrix can route suitable unused header pins; pins9..19 already serve audio/C6 | No selected expansion pinout or connected load: **missing**, not arbitrarily mapped |
| ADC / PWM / counters / RMT / TWAI | SoC facilities; only compatible bonded/exposed pins may be used; CAN requires external transceiver | Native drivers vary by instance. MicroBlocks binding and physical load/loopback tests **missing** |
| Ethernet | SoC MAC only; this schematic has no populated PHY/RJ45 | Onboard Ethernet claim **incompatible**; external hardware/port would be a separate task |

Reserved groups: flash/PSRAM pins; UART37/38; boot35/EN; audio9..13/53;
C6 SDIO14..19/reset54 and boot-control6; SD39..45; shared I2C7/8;
CSI control4/5 when used; USB34/36 when selected; clock/strapping functions
on0/1. A header connection does not make a pin conflict-free. No generic
pin-output support is claimed or enabled by this audit.

## Compute, media and system facilities

| Facility | MicroBlocks backend and evidence | State / next gate |
|---|---|---|
| CPU image resize/grayscale/RGB888 | Immutable four-handle store, 8 MiB budget; actual generated/camera pipelines and offline sanitizers | **tested**; nearest resize retains its exact algorithm |
| ISP | Native demosaic/RAW8/10→RGB565 for capture | Demosaic **tested**; statistics, denoise, AE/AWB and other controls **missing** |
| PPA / 2D DMA | Pinned native `soc/espressif/common/esp_ppa.c` exposes scale/rotate/mirror, fill and blend | Scale/rotate/mirror **tested**, generated-pixel/lifecycle checks and real GP inline views; `p4-ppa-native.json`. Blend/fill **missing**; no CPU speedup or injected DMA fault claim |
| JPEG | P4 hardware encode + decode | Native bounded codec blocks **missing**, not established by IDF documentation |
| H.264 | Hardware encoder; software decoding is separate | Both block paths **missing**; hardware decoding claim **incompatible** |
| Audio RMS/peak and Whistle STT | Native PCM pool, independent C99 scalar engine, mapped depth4 model, bounded worker/cancel | **tested** known WAV and microphone PCM plus GP; variable recognition quality and ~22s scalar fixture latency |
| NN | Native TFLM reference kernels, bounded static dense float32/int8 models; catalog/custom import | **tested** physical golden/rejections/lifecycle and GP. Direct ONNX Runtime/RV64 Linux artifacts **incompatible** with RV32 Zephyr. Restricted offline conversion is separate |
| Wake word | Native trusted Okay Nabu TFLM reference backend, trained frontend, bounded PCM ring and GP event hat | **tested** fixture score parity, event handlers and microphone lifecycle; acoustic recognition **unverified** (Windows output muted); default listener off. See WAKE_WORD.md |
| P4 PIE/QACC NN/DSP kernels | Espressif target kernels need selective native build/context/memory validation | **missing** acceleration; no benchmark borrowed from IDF/S3 |
| ESP-NOW | P4 needs C6 RPC support and an authorized second radio peer | **missing**; current Hosted support unverified; official issue19 open. Direct ESP32 radio sample is not this topology |
| HP second core / LP core / sleep | Zephyr has SoC facilities; application does not distribute VM/inference to LP | Application support **missing/unverified**; LP is not an NN accelerator |
| RNG / crypto / security | Zephyr/SoC facilities distinct from user-facing blocks | Blocks/physical acceptance **missing**. No eFuse, secure-boot or flash-security modification authorized or performed |
| Timers / watchdog / cache / DMA | Used as native infrastructure by current camera/audio/VM | Current paths **tested**; does not establish every controller/mode or standalone block |
| Clock / scheduling blocks | Zephyr monotonic uptime, bounded eight-timer core and manual UTC/fixed-offset clock | **implemented-unverified on board**; host fake-clock sanitizer tests, both native builds and disconnected GP layout pass. RTC/NTP providers, automatic timezone rules and retained calendar clock **missing** |
| Logical steps / transitions | Separate portable core, 16 steps / 24 transitions, explicit deterministic scans | **implemented-unverified on board**; host fork/join/conflict/timer/reset tests pass. No automatic physical outputs; no IEC 60848 or safety certification claim |
| User file storage | Separate bounded RAM service, eight files up to 8192 bytes; staged replacement and cancellation | USB acceptance and additional 918 real Wi-Fi WebSocket file requests **tested**; cleanup/revisions/reconnect/resource pressure pass. [USB acceptance](../../../docs/STORAGE_PHYSICAL.md), [network follow-up](NETWORK_LIVE_VALIDATION.md). Complete hosted graphical file manager/download, Flash/SD/media archive and database remain **missing/unverified** |
| Board-hosted editor | Flash asset/whole-layout validation; strict same-origin HTTP/WS and single programming controller | Actual served-asset hashes and VM programming **tested**. Concurrent HTTP closes intermittently; complete graphical load still **blocked/unverified**. Local numeric diagnostic built but not installed; USB remains usable |
| ArduinoCore-Zephyr | Future board variant/compatibility work | **missing**, no arbitrary Arduino library/board portability promise |

Evidence filenames above are under `evidence/2026-10-25/`, with physical RAM
acceptance in `evidence/2026-10-26/`; full constraints and
reproduction are in START_HERE, NETWORK_STATION, DSP, NEURAL_NETWORKS and
I2C_DISCOVERY. This audit does not claim all hardware is already supported.
Priority after tested PPA SRM and KWS fixture/event/lifecycle: acoustic KWS when playback is available; safe
GPIO/button/storage support after explicit resource mapping. Display,
speaker, SD and radio-peer acceptance need the corresponding actual attachment.

## Sources and revision basis

- [Waveshare exact-board resources](https://docs.waveshare.com/ESP32-P4-WIFI6/Resources-And-Documents),
  [schematic/assembly drawings](https://files.waveshare.com/wiki/ESP32-P4-WIFI6/ESP32-P4-WIFI6-datasheet.pdf),
  visually inspected all pages; schematic references are not proof of fitted
  components on an unphotographed PCB revision.
- [Zephyr board documentation](https://docs.zephyrproject.org/latest/boards/waveshare/esp32p4_wifi6/doc/index.html).
  Application pins/configuration were checked against our pinned board DTS,
  not inferred from a generic feature list.
- Source baseline Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`,
  Espressif HAL `b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`.
  Reviewed local driver patches are versioned under `zephyr/patches/`.
- [ESP-Hosted ESP-NOW support issue](https://github.com/espressif/esp-hosted-mcu/issues/19).
