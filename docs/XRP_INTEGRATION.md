# XRP firmware integration contract

This development image targets production SparkFun XRP RP2350B only. It uses
the pinned SmallVM v417, ArduinoCore-Zephyr API and Zephyr revisions already
recorded by this repository. It is a separate application; existing Fruit Jam
and Waveshare firmware and source preparation remain unchanged.

The first integrated build must provide quiet binary USB, raw production GPIO
numbering, I2C1 on GPIO38/39 for the stock XRP library, ADC GPIO40..46, encoder
inputs, and bounded VM scheduling. Motor inputs start and remain low/coast;
servo outputs cannot be selected by user code. Reserved radio, PSRAM and I2C
pins must fail closed through both VM adapters and the isolated Arduino API.
No actuator-unlock command is provided by this image.

Wi-Fi setup uses only USB message 205, MBNW v2. A bounded asynchronous worker
owns joining and the dedicated two-slot journal. Probe/status responses contain
capabilities and errors, never credentials. Remember=false does not write the
journal; remember=true commits only after successful association and DHCP.
Holding USER at boot skips saved-network joining without erasing settings or
the VM program. A failed join must leave USB available. No HTTP credential API
is added. Native HTTP/WebSocket programming is same-origin, one controller;
USB takes priority. HTTPS Pages cannot connect to plain ws://.

Acceptance before hardware installation: compile the exact board with real
SmallVM, Arduino and RM2 driver; validate ELF/UF2 load addresses against program
and settings partitions; run protocol/store fault tests and pin/transport
contracts; retain build logs and exact source identity. Simulated results do not
prove USB, sensor accuracy, flash durability or radio behavior on a robot.

Physical work remains a separate gate: identify the attached XRP, preserve its
current firmware/files/settings, verify recovery, then request installation.
Motion additionally requires explicit readiness with wheels safely raised or
the robot restrained. No reset, halt, flash or motion follows from detection.
The read-only identification on 2026-10-19 found COM10 (1b4f:0046,
6F937DF0E8E8A5A8), probe B2047FF29EB03C7E and RP2350 DPv3 0x4c013477.

Bluetooth, PSRAM, Python/Blockly/REPL parity and robot motion remain outside this
non-actuating development milestone. Encoder performance under Wi-Fi requires
measurement; GPIO interrupts are not claimed equivalent to a validated PIO
implementation.

Physical ADC acceptance found that missing default pinctrl states left ADC/PWM
devices uninitialized. Match the reviewed Fruit Jam pattern: explicit empty
default states initialize clock/reset/IRQ without selecting any GPIO. Arduino
and VM ADC entry points must reject an unready device. Run actual analogRead
on a dedicated worker; the VM waits at most 50 ms, rejects another conversion
while the old one is pending, and discards an abandoned late completion. A lost
ADC IRQ must not prevent USB ping/recovery. Validate both normal inputs and
temporary IRQ suppression/restoration before accepting this correction.

The native server includes the unchanged production XRP library. GPIO encoder
interrupts and bounded echo capture implement its existing primitive contracts;
motor and servo primitives remain deliberately unavailable. GPIO12..19 PWM uses
channels12,13,14,15,0,1,2,3: GPIO16..31 alias the first eight RP2350 PWM slices.
The isolated Arduino core rejects output on all input-only sensor pins as well
as rejecting access to reserved/actuator pins.

`tools/network_setup_client.py` provides an identity-checked USB setup client
for the compatible image. It probes before asking for a key and has no password
CLI option. It is not run against the currently installed firmware.
Use the port and USB serial observed after an authorized installation; COM10
and its current VID/PID must not be presumed to identify the new image.
The plaintext journal is written only with explicit `--remember`; transient
connections leave any older saved network intact. USER recovery never erases it.

The deployment country confirmed by the user is Canada. The integrated app
sets `CONFIG_WHD_WIFI_COUNTRY="WHD_COUNTRY_CANADA"`; the earlier build used
the upstream Australia default and was not used for association. Keep the
pinned Zephyr CYW43439/MURATA-1YN firmware, CLM and NVRAM resource selection.
Record the actual resolved country in build evidence before installation and
radio acceptance. Successful association does not establish RF calibration.
Credentials are supplied only through the user's local Connect action.
