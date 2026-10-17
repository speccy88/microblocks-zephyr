# Architecture

The target is one portable runtime; *board profiles* adapt it to real hardware.

```text
MicroBlocks GP IDE (browser/desktop)
        |  MicroBlocks wire protocol (USB CDC/UART; BLE/Wi-Fi later)
SmallVM bytecode runtime (Zephyr task)
        |  named primitives + capability query, errors, bounded queues
   portable board API
   /              \
Zephyr device APIs  ArduinoCore-Zephyr API + selectively validated libraries
   \              /
      board DTS, Kconfig, board drivers -> Waveshare hardware
```

## Deployment modes

- **Static** (initial): link SmallVM, board hardware layer and Arduino API into
  a single Zephyr image. Smaller platform surface and predictable boot.
- **LLEXT** (optional, future): where supported, load a native VM/library
  extension dynamically. Requires per-board loader/ABI validation.

## Design rules

- Zephyr owns bus devices, interrupts, drivers and resource arbitration.
- SmallVM consumes stable C wrapper functions, not raw board-specific driver
  internals. Keep bytecode execution bounded and preemptible; audio and networking
  should not block interpreter progress.
- Expose device capabilities at runtime. Devicetree node presence or `ready`
  is **not proof** of working peripherals; preserve physical test status separately.
- Generic I²C reads/writes require protected onboard addresses, bus locks, rate
  limits and explicit unsafe-mode opt-in for register writes. Never automatically
  identify a device using only an ACK at its I²C address.
- Reserve pins for boot, display, I²S audio, USB, SD, power and integrated buses.
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
