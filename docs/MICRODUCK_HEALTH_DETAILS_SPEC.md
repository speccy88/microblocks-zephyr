# Additional read-only robot health details

Use pinned upstream HealthResult, MotorThermal and CpuThrottle declarations.
Add hottest-joint identity and the four CPU throttle u32 readings, plus the
upstream derived throttled predicate (level>0 or max_khz>0 and khz<max_khz).
Clock ceilings are kHz, not instantaneous frequency. No health reading grants
movement authority. Missing optional sections/keys remain not_reported; zero
is known only when present. Keep exact u32 values as decimal text with explicit
units through the native signed31 VM boundary. Reject bool, negative and u32
overflow. Bound names to128 UTF-8 bytes; preserve origin and immutable snapshot.

Expose named advanced Robot blocks and simple capture/read/release helpers for
reported board temperature and health verdict. Both layers share the same
gateway, typed records and release handling, and coexist in one project.
No control methods, real robot connection, CLI parsing or media API is added.

Acceptance: faithful Unix robotd fixture through actual gateway and new native
VM; every new selector, false/zero/absence/overflow/forgery; actual JS import,
compile and source reopen, with simple and advanced blocks together. Full
validator and clean isolated commit. Pi and physical robot acceptance remain
separate; do not claim those from local Linux execution.
