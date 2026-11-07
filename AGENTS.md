# AGENTS.md â€” development principles

Goal: portable MicroBlocks SmallVM + Arduino API on Zephyr, with hardware
capabilities reflected honestly in the IDE. The first port is Waveshare
ESP32-S3-RLCD-4.2; the independently maintained UNO Q port is a reference.

## Working method (spec-first when change is substantial)

- Work directly in `main` and keep completed work committed and pushed.
  Do not create or use additional development branches, including `gp`.
  Historical work remains in the `main` history. Preserve uncommitted work;
  deletion of branches or local data requires explicit user authorization.

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

6. Every new or changed custom block needs matching authored Help in
   `docs/block-help/`: explain behavior, inputs/units, results, prerequisites,
   examples and limits. Follow `docs/BLOCK_HELP.md`. Run
   `python3 tools/block_help.py`; missing entries fail packaging and validation.
   Keep selectors stable across palette changes and distinguish examples from
   measured hardware acceptance.

## Shared core and target adaptations

- Apply this architecture to every target: keep the VM core, generic fixes,
  domain libraries and editor behavior shared in canonical source modules.
  Put OS/board differences behind target adapters and explicit profiles;
  do not maintain independently evolving copies of generic code per board.
- Generated, versioned deployment packages may contain source/build copies,
  but changes belong in canonical sources and their shared build/packaging
  path. A deployed version is not a new source fork.
- Reveal/enable features from the target's declared and reported capabilities.
  Distinguish supported, configured/enabled, available and physically validated
  states. Use the same editor capability interface across targets, with a
  clear unavailable reason; retain saved project blocks when a target changes.
- Pi5 Blinka detection, dependencies, I2C wiring and pin mappings establish
  nothing about MicroDuck or another Linux board. Validate each target adapter,
  model, bus and pin map independently; never force a Pi/Radxa profile to make
  an unvalidated target appear supported.
- Keep execution family (bare metal, Zephyr, Linux), CPU architecture and
  feature capabilities distinct. Zephyr does not imply an Arduino core is
  linked; ARM64 tests do not establish ARM32 support; a native CI host is not
  physical board acceptance. UNO Q MCU and MPU are separate execution targets.
- Maintain the reviewed board-by-feature matrix in `capabilities/matrix.json`
  and regenerate `docs/CAPABILITY_MATRIX.md`. Keep hardware prerequisites,
  backend implementation, configuration and tests by actual hardware separate.
  Unknown/absent validation must not be converted to available support. A
  common block may select different target backends under one shared contract.
- MicroDuck UART2 is motor-reserved according to the operator test report.
  Use the appropriate robot/device interfaces; never force a Radxa Blinka map.
- See `docs/ARCHITECTURE.md`; record current implementation gaps honestly.

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
