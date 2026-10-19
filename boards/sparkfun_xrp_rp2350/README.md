# SparkFun production XRP RP2350

Production ROB-26619 uses a discrete RP2350B and RM2, not the Pico W beta.
The [reference inventory](../../dependencies/xrp-production-reference.json),
[feature acceptance plan](../../docs/XRP_PARITY.md) and
[canonical capability manifest](hardware.json) record the exact scope.

The integrated SmallVM v417 / real Arduino API / Zephyr image is now installed
on the identified XRP, with the user's flash authorization and motor supply off.
SWD identified RP2350 rev2, QFN80 and Winbond W25Q128JV 16 MiB. The original
complete image and subsequent snapshots remain private, outside Git. Current
USB is COM11, 2fe3:0004, serial E464244647564B37. The earlier MicroPython USB
COM10 / 1b4f:0046 identity is historical and must not identify the new image.

The [Canada build](../../evidence/xrp-smallvm-build-verification-07-http-detail-2026-10-19.json)
uses source `b8232c3aa6abe4e02f459a15ff15a5ed71c2a245`, Zephyr
`a915b2f12675b48b16d56653ea145dcd8f20cbbf`, **4,010,680 flash bytes** and
**365,240 linker RAM bytes**. ELF/UF2 load bounds, actual 48-GPIO/9-ADC compiler
macros and linked APIs pass inspection. PSRAM remains unmapped.
[Programming, boot and update retention](../../evidence/xrp-http-detail-boot-2026-10-19.json)
pass; the existing program/settings tail was byte-for-byte preserved.

## Physical acceptance

- [USB VM](../../evidence/xrp-usb-baseline-2026-10-19.json): arithmetic/edit,
  exactly 50 outputs, fragmented upload, stop/variables and reconnect pass.
  [Reset retention](../../evidence/xrp-usb-after-reset-2026-10-19.json) passes.
- [Inputs](../../evidence/xrp-inputs-02-2026-10-19.json): IMU family ID 0x6c,
  ADC GPIO40..46, released USER level, four encoder start/count/stop APIs and
  passive bounded echo capture pass. No encoder motion or ultrasonic trigger
  was driven. Sensor scaling, calibration, accuracy and button transitions
  remain unverified.
- [ADC lost-interrupt recovery](../../evidence/xrp-adc-irq-fault-2026-10-19.json):
  bounded error, USB responsiveness, busy rejection, restored IRQ and discarded
  late completion pass. [The earlier failure](../../evidence/xrp-adc-diagnostic-2026-10-19.json)
  is retained with its pinctrl initialization cause.
- [Motor GPIO registers](../../evidence/xrp-motor-coast-registers-2026-10-19.json)
  read back as eight low SIO outputs. This is a register check, not an electrical
  waveform measurement. Motor and servo writes are blocked at both VM and
  Arduino entry points. No unlock command exists and no motion is accepted.

RM2 reports ready with `WHD_COUNTRY_CANADA`, the country confirmed by the user.
The [wireless acceptance](../../evidence/xrp-wireless-08-http-detail-2026-10-19.json)
passes all 147 assets (3,511,116 compressed bytes, exact body hashes and
COOP/COEP headers) over two concurrent HTTP connections during live VM traffic.
Arithmetic/edit, 50 ordered outputs, fragmented upload, partial-frame recovery,
stop/variables, IMU/raw ADC, origin/controller rejection, reconnect and USB
preemption pass. The 2,180,340-byte data file took 57.421 seconds in that run.
Graphical GP compilation and local-project browser acceptance remain unverified.
The [HTTP fairness check](../../evidence/xrp-http-fairness-02-2026-10-19.json)
served eight status requests in 0.093..0.344 seconds during a large download,
validated sequential keepalive hashes, and recovered after two partial-download
closes. This does not claim initial HTTP request pipelining support.
The [repeated-connection check](../../evidence/xrp-http-repeated-2026-10-19.json)
passes 30 fresh HTTP connections, three matching root HTML reads and three
WebSocket version/ping reconnects after the bulk-transfer tests.

The local Windows-vault Connect action supplies credentials only to the exact
USB-identified XRP. Remember is an explicit checkbox, off by default. No key
passes through chat, browser, VM scripts or Git. The journal is plaintext flash,
not encryption. Radio calibration and flash power-loss durability are unverified.

The native editor uses `http://<board-ip>/` and same-origin `ws://<board-ip>/ws/vm`.
USB preempts its single wireless controller. The HTTPS Pages XRP profile remains
an editing preview with hardware connection disabled; use the board-hosted editor
for compatible firmware. Exact wireless/graphical results are tracked in the
manifest and evidence; linkage alone never establishes acceptance.

## Rebuild

Keep the independent quiet `bringup/` baseline and other boards unchanged.
Use the pinned workspace/SDK and isolated XRP Arduino module:

```sh
python3 tools/prepare_xrp_arduino.py --source "$arduino_source" --output "$arduino_xrp"
python3 tools/prepare_xrp_radio.py --hal "$hal_infineon" --fetch
west build -b sparkfun_xrp/rp2350b/m33_0 -d build/xrp-smallvm \
  "$repo/boards/sparkfun_xrp_rp2350/smallvm" -- \
  -DZEPHYR_EXTRA_MODULES="$arduino_xrp" -DXRP_ARDUINO_DIR="$arduino_xrp" \
  -DSMALLVM_SOURCE_DIR="$smallvm_snapshot" -DIDE_SOURCE_DIR="$ide_source"
```

This builds only. Every later installation must preserve the current image,
program and settings and remain within explicit user authorization. Motion needs
a separate safe-placement/readiness decision. Keep the motor supply off during
this non-actuating milestone. Fruit Jam and Waveshare are excluded from these
flash/reset/test helpers. Fruit Jam's current program CRC remains `651a01da`.

Default Wire/I2C1 is GPIO38/39; Wire1/I2C0 is GPIO4/5. PIO0 belongs to RM2.
Production DRV8411A IN1/IN2 pairs are 34/35,32/33,20/21,10/11; never apply beta
phase/enable code. RGB, PSRAM and BLE remain unavailable. Full XRPCode parity,
motor orientation, servo bounds, distance/line/IMU calibration and encoder
accuracy under Wi-Fi load remain future acceptance gates.
