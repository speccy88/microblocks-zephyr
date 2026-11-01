# Typed MicroDuck libraries in the staged JS editor

Keep the editor/VM pins and pristine upstream engine unchanged. Extend only
the local package and compatibility layer. Remain on the isolated migration
branch; shared main, P4 and paused SFC work are outside this slice.

Acceptance:

- Expose the existing six normal gateway libraries (base MicroDuck, Head IMU,
  Depth, Gamepad, Robot and Pad IMU) in the JS file browser. Preserve exact
  library bytes, dependencies, availability records and safety descriptions.
- Import them through the actual pinned `MB_Project`/`MB_Parser` code with
  actual block classes; compile their functions with the actual compiler.
  A headless DOM/canvas fixture is not graphical acceptance.
- Verify dependency loading and representative typed blocks, not just native
  primitive names. Unknown or missing dependencies must fail visibly.
- Execute representative imported functions on the existing real Pi VM with
  CRC acknowledgements. Use no gateway for explicit unavailable results and,
  where feasible, the existing faithful simulated read-only service path.
  Do not issue physical robot commands or mistake simulated readings for
  physical sensor evidence. Retain statuses, values, units and origins.
- Run focused tests and the required repository validator, retain failures,
  provenance and exact limitations, then commit a clean checkpoint.

Simulation-only libraries and robot motion are not automatically imported or
executed. Browser graphical acceptance and physical MicroDuck acceptance
remain independent gates.
