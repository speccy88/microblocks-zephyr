# Architecture

The repository-wide requirement is one shared core with target adapters.
Generic improvements belong in canonical shared modules and must propagate to
the relevant target builds. A board profile selects capabilities and validated
hardware mappings; it does not create an independent copy of the runtime.

```text
Shared editor/domain blocks + common capability/operation contracts
        |  target transport adapter (USB/UART/WebSocket/native shell)
SmallVM core + generic primitives/libraries + bounded operations
        |  execution-family and target adapters
     bare metal              Zephyr                      Linux
  native board API     Zephyr/Arduino if linked     shared Python/Unix API
        \                    |                          /
       target profile + reported capabilities + physical acceptance
```

Execution family, CPU architecture and capabilities are independent axes.
Bare-metal Propeller2 currently retains native FlexC VM405; this is not a Zephyr
port or proof of common v417 behavior. RP2350 ARM targets, ESP32-S3 Xtensa and
ESP32-P4 RV32 have their own Zephyr/Arduino-linkage statuses. UNO Q's MCU and
Linux MPU must remain separate targets. The repository's Linux LP64 code has
real Pi5 ARM64 and native x86-64 CI evidence; ARM32 remains an unvalidated
planned target. These distinctions are recorded in the matrix, not inferred
from a product name or processor width.


Generated immutable packages may include copies needed to deploy a version.
They are build outputs from canonical source and provenance, not places to
maintain a board-specific fork. Existing target implementations do not establish
that every layer has already been consolidated; move generic behavior into
shared paths as it is changed, with compatibility tests for affected targets.

## Capability-driven features

Keep support, configuration/enablement, current availability and physical
validation distinct. The same editor interface must consume target capabilities
to reveal or enable features and explain unavailability. A board name, library
installation, device-tree node or shared SoC is insufficient evidence. Changing
targets must preserve saved blocks and expose incompatibilities clearly.

For Linux Python, `linux/extensions` and the editor overlay/library are shared;
`linux/extensions/profiles/` supplies target settings. The Pi5 installer and
Blinka setup are Pi5 adapters with explicit model detection. MicroDuck retains
its separate profile, disabled climate example and unvalidated pin-map gate.
Pi5 software acceptance does not validate MicroDuck's board detection, buses,
pins, dependencies or sensors; never substitute a forced Pi/Radxa identity.

Current gap: `web/js-editor/python-blocks.js` still exposes all domain specs in
the palette. The service enforces enablement and rejects disabled extensions,
but the palette is not yet filtered by runtime capabilities. Finish this through
one common capability contract/adapter, not a copied Pi-only editor. Preserve
offline/saved project definitions and distinguish unknown from available.

## Reviewed board-by-feature matrix

The [generated matrix](CAPABILITY_MATRIX.md) and its machine-readable
[`capabilities/matrix.json`](../capabilities/matrix.json) cover neural inference,
speech/Whistle, sensors, I2C OLEDs, MQTT, SQLite, camera capture and image
processing. They separate implementation, test scope, target/CPU, backend,
prerequisites, configuration and limits. Camera records preserve unknown
formats/resolutions and distinguish capture from receive-only observation.

Per-target hardware manifests stay canonical. The index records reviewed
manifest hashes and evidence references; a changed manifest requires re-auditing
its summary, preventing silent divergence. It is a documentary evidence index,
not an online permission grant or proof that all named features exist. A future
common editor capability adapter must intersect it with actual runtime reports
and configuration while preserving saved blocks.

MicroDuck's UART2 is used by the motors according to the reported operator
test. The [recorded constraint](../evidence/2026-11-02/microduck-uart2-constraint.md)
prohibits forcing a Radxa Blinka pin map; use appropriate robot interfaces.
The report does not validate any SmallVM/Blinka sensor or camera on the robot.

## Deployment modes

- **Static** (initial): link SmallVM, board hardware layer and Arduino API into
  a single Zephyr image. Smaller platform surface and predictable boot.
- **LLEXT** (optional, future): where supported, load a native VM/library
  extension dynamically. Requires per-board loader/ABI validation.

## Design rules

- On Zephyr targets, Zephyr owns bus devices, interrupts, drivers and resource
  arbitration. Linux targets use their OS/device adapters and explicit permissions.
- SmallVM consumes stable C wrapper functions, not raw board-specific driver
  internals. Keep bytecode execution bounded and preemptible; audio and networking
  should not block interpreter progress.
- Expose device capabilities at runtime. Devicetree node presence or `ready`
  is **not proof** of working peripherals; preserve physical test status separately.
- Generic I2C reads/writes require protected onboard addresses, bus locks, rate
  limits and explicit unsafe-mode opt-in for register writes. Never automatically
  identify a device using only an ACK at its I2C address.
- Reserve pins for boot, display, I2S audio, USB, SD, power and integrated buses.
  Generic GPIO blocks must use an explicit board allowlist validated against the
  schematic and physical board revision.
- Avoid installing Arduino-ESP32 code assuming ESP-IDF/FreeRTOS into a Zephyr
  firmware; adapt source and validate compatibility instead.
- Keep MicroBlocks wire traffic isolated from Zephyr shell and system logs.
- No flashing, erasing, or changing bootloaders without explicit approval and
  a tested backup/recovery plan for the actual device.

## Reproducibility

Pin Zephyr revision and hardware dependencies before declaring a validated
build. The first Waveshare manifest records a Zephyr commit as reference;
its sample README shows how to check it out. The Arduino API module and
SmallVM revisions will be pinned when their integration is built.
