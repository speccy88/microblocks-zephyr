# Coexisting MicroDuck abstraction layers

Keep the existing six-module normal read-only import unchanged. Add one optional
coherent Starter Lab import containing those same sources plus separate Simple
Sensors and Simple Practice categories and their preserved advanced simulation
dependencies. Exact source receipts and deterministic packaging are required.
The MicroDuck target stays an experimental offline placeholder.

Simple Sensors hides capture/read/release bookkeeping while preserving the same
typed reading records, units, origin and unavailable semantics as advanced
blocks. It never maps a missing value to zero or interprets health as movement
authority. Gamepad button indices use discovery, not assumed controller names.

Simple Practice explicitly labels every action SIMULATION. It delegates to the
existing bounded advanced mock interfaces; confirmation defaults false and
backend opt-in remains mandatory. No live movement, new gateway allowlist,
insecure secrets, distance/angle promise or automatic retry is introduced.

Acceptance: actual pinned JS file import/compile of all coexisting modules;
save/reopen and unique function IDs; actual local native VM bytecode against
the faithful mock services, testing both abstraction layers, errors, bounds and
confirmation. This does not establish physical or Pi validation of new helpers.
