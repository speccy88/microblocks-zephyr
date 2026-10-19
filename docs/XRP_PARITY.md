# Production XRP feature parity and acceptance

Target: SparkFun XRP Controller ROB-26619, discrete RP2350B and RM2, not the
Pico W beta ROB-22727. The robot has not been identified or accessed. No motion,
flash, reset, credential entry or physical feature validation is authorized by
this source-stage checkpoint alone. Other connected RP2350 boards are excluded.

## Sources and architecture

The hardware authority is SparkFun's production schematic at
`86c4cd7fbc40c49308ec9d28007809906f18eec3`, especially
[`Hardware/core.kicad_sch`](https://github.com/sparkfun/SparkFun_XRP_Controller/blob/86c4cd7fbc40c49308ec9d28007809906f18eec3/Hardware/core.kicad_sch)
and [`Hardware/peripherals.kicad_sch`](https://github.com/sparkfun/SparkFun_XRP_Controller/blob/86c4cd7fbc40c49308ec9d28007809906f18eec3/Hardware/peripherals.kicad_sch).
Exact hashes and licenses are in `dependencies/xrp-production-reference.json`.
The core schematic confirms RP2350B, W25Q128JVPIM 16 MiB flash,
APS6404L-3SQR-ZR 8 MiB PSRAM and RM2. PSRAM is not assumed to be usable heap.

The overview's Phase/Enable motor headings do not match the production
schematic's IN1/IN2 nets and DRV8411A devices. Production is dual-input PWM:
coast both low, brake both high. XRPLib's production implementation corroborates
this and reverses logical left/motor3 orientation; beta wiring/code must not
be copied unchanged. The schematic names LSM6DSOX while the overview says
LSM6DSO. WHO_AM_I 0x6C identifies the compatible family, not the exact part.
Default IMU address is 0x6B on I2C1, with jumper selection 0x6A.

[XRPCode](https://github.com/Open-STEM/XRPCode/tree/108010b3d62086bc9f79fc92876c752add584c52)
is a hosted Python/Blockly editor using Web Serial/Web Bluetooth. It does not
establish that the robot serves that IDE. [WPILib XRP](https://docs.wpilib.org/en/stable/docs/xrp-robot/programming-xrp.html)
runs the user program on the PC and controls the robot remotely; it is not a
Zephyr/SmallVM program executing on the robot. Our intended live mode compiles
blocks in the real GP browser and runs SmallVM bytecode on the XRP itself.

The intended portal flow is USB from HTTPS Pages, or opening the same editor
served by the robot on its LAN origin for plain WebSocket. Same-page HTTPS to
plain `ws://` is unavailable; it requires a separately implemented secure
endpoint. Board-hosted HTTP/WebSocket does not require WSS to function on its
own origin. BLE and a PC UDP remote-control compatibility layer are separate
features, not prerequisites for the requested Wi-Fi mode.

## Feature and test matrix

| Function | Required behavior / acceptance | Current boundary |
|---|---|---|
| Correct production target | RP2350B/high GPIO, exact radio nets, USB identity and firmware/source hashes | Source definition; no physical identity |
| Live blocks / variables | Real GP compile, 5+7=12, edit=13, stop, variables, reconnect, 50 ordered outputs | Portal preview; XRP VM not installed |
| Four motor channels | Signed bounded duty, dual PWM and correct orientation; zero-safe boot/Stop/reset | Hardware primitives pending; no motor commands in baseline |
| Four quadrature encoders | Signed counts, reset and velocity; pulse-generator accuracy under Wi-Fi load | Driver and measured limits pending |
| Tank / arcade / drivetrain | Differential scaling, saturation, wheel calibration and cooperative bounded moves | API/control loops pending |
| Four servos | Explicit pulse/angle bounds and 50 Hz output; detached at boot/Stop by default | Driver/calibration pending; baseline does not drive signals |
| Ultrasonic distance | Trigger0/Echo1, bounded edge timeout, explicit out-of-range/error | Driver/waveform test pending |
| Line follower | ADC GPIO44/45, raw/calibrated ranges; no fabricated line classification | Driver/calibration pending |
| IMU | Identity, acceleration/gyro, units/ranges, bias calibration and orientation limits | Baseline read-only family ID probe; physical test pending |
| Button / RGB / STAT | Button36 active-low, RGB37; STAT belongs to radio GPIO0 | Button input only in baseline; no automatic RGB/STAT output |
| Voltage / current | VIN46 and currents40..43, documented divider/gain and calibration | Scaling and electrical calibration pending |
| Extension I/O / Qwiic | Safe unused GPIO12..19, I2C0 4/5, I2C1 38/39; enforce reserved pins | Pin ownership specified; broad Arduino API pending |
| Wi-Fi live programming | RM2 PIO shared DATA/IRQ; association, all assets, fragmented VM traffic and reconnect | Pinned Zephyr radio definition adapted; board integration pending |
| Local project storage | Per-board IndexedDB, named save/restore/export, preserve fresh workspace | Shared portal code; XRP browser acceptance pending |
| Save / boot / update | Separate application, program and Wi-Fi settings; retain current program through update | Partitions reserved; firmware storage integration pending |
| Stop and connection loss | Stop all task outputs; manual/teleop mode stops on loss of control; explicit autonomous policy | Policy must be implemented/tested before actuator release |
| Python / Blockly / REPL / robot files | XRPCode offers these distinct workflows | Not provided by MicroBlocks; full XRPCode equivalence is not claimed |
| Optional gamepad / dashboard | Explicit user enable, bounded commands, clear ownership/link loss | Separate future scope |
| Bluetooth | Verify RM2 gSPI/shared-IRQ HCI support on pinned Zephyr before promising BLE | Unsupported/unverified; not equivalent to enabling CONFIG_BT |

## Stages and release gates

1. Source-backed manifest and independent RP2350B board target. Compile a quiet,
   non-actuating baseline: motors coast, servo signals untouched, button input,
   one read-only IMU family-ID query. No Wi-Fi join, scan, reset or flash writes.
2. Compile USB SmallVM and actual Arduino API with safe GPIO ownership, exact
   source/image/partition evidence. The preview must reject hardware connection
   until a compatible XRP image exists; no substitute board is accepted.
3. Integrate RM2 Wi-Fi and board-hosted GP/WebSocket, one-controller ownership,
   common USB setup and dedicated persistent settings. Reserve PIO0 for radio;
   budget encoder/RGB PIO separately. Preserve Infineon firmware/CLM blob terms.
4. Implement and simulate motor/encoder/servo/sensor primitives and stop policy.
   Add GP blocks only as their implementations become available; test motor
   orientation, reversing transitions, invalid arguments and transport loss.
5. Before any physical installation: identify this XRP, back up firmware,
   filesystem/program/settings and verify recovery. Confirm wheels are safely
   raised or the robot is restrained before any motion test. Begin with motors
   disabled, then one low-duty channel/servo at a time under explicit readiness.
6. Test real USB and Wi-Fi bytecode, projects/persistence, all peripherals,
   bounded ultrasonic failures, encoder accuracy with concurrent Wi-Fi, supply
   behavior and normal safe Stop/reset/link-loss. Record measured results and
   limitations rather than promoting source or simulated tests to hardware PASS.

SparkFun hardware references are CC BY-SA 4.0, its software MIT. Zephyr board
composition keeps Apache-2.0 notices. XRPCode/XRPLib are GPLv3 references; their
source is not copied into the MIT/MPL implementation. WPILib firmware has no
general root license grant established here and is not copied. No schematic
artwork, firmware blob, secret or full robot flash dump is committed.
