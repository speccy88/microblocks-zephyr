# AGENTS.md — development principles

Goal: portable MicroBlocks SmallVM + Arduino API on Zephyr, with hardware
capabilities reflected honestly in the IDE. The first port is Waveshare
ESP32-S3-RLCD-4.2; the independently maintained UNO Q port is a reference.

## Working method (spec-first when change is substantial)

1. Read `README.md`, the target board's `README.md`, `hardware.json`, and
   `docs/ROADMAP.md`. Preserve original working behavior.
2. Write down feature behavior, non-goals, dependencies and testable acceptance
   criteria before implementing drivers or protocol changes.
3. Keep stages small: hardware diagnostic -> VM transport -> primitives ->
   peripherals -> Arduino compatibility. Favor simple, reproducible changes.
4. Run `python3 tools/validate.py` after changes. For any Zephyr changes,
   provide exact build command/logs and target commit; if no toolchain is
   available, state **not compiled**, not PASS.
5. Never claim a device works based only on Devicetree, static tests or source.
   Physical PASS needs real measurement and logs/notes under the acceptance
   matrix; don't infer absent tests.

## Safety and boundaries

- **Never flash or erase a board without explicit user authorization.**
  Preserve the current image, bootloader, partition table and recovery path.
- Do not assume ArduinoCore-Zephyr works on ESP32-S3 without implementing
  and validating the variant / compatible modules.
- Respect reserved pins, electrical limits, shared buses and GPIO strapping.
- Keep firmware backup binaries, credentials, Wi-Fi keys and full flash dumps
  out of Git and diagnostic artifacts.
- Third-party code keeps its respective license/notice. See `LICENSES.md`.
- Use one canonical hardware-capability manifest per port with tested/untested
  statuses. Cross-platform features must degrade clearly if unsupported.
