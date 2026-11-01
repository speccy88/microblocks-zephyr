# Typed health readings contract

This adds pure, read-only conversion of one already received `robot.health`
JSON-RPC reply. No new network method, daemon permission, action, polling loop
or readiness guarantee is introduced. Source is API44 at Pollen commit
`96b89d8613f06722c1d64ce75ab0d7124fed9d8f`, `duck-ipc-proto/src/lib.rs`:
HealthResult, Battery, MotorThermal, LoopHealth, BusHealth and ImuHealth.
Primary source: [API44 health types](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duck-ipc-proto/src/lib.rs#L3634-L3900).

Append two primitive names to set22 without changing older names or indices:
`healthSample(replyJSON, field)` returns `[status, value, unit, origin]`;
`readingValue(reading)` returns its typed value only when status is `ok`, otherwise
VM error32. Non-list arguments produce error11; invalid record shapes error32.
Unknown field names, wrong argument types, invalid UTF-8 or malformed/duplicate/
oversized JSON produce existing explicit VM errors. Conversion opens no socket.

Statuses: `ok`, `unknown` (absent/null optional section/measurement), `invalid`
(wrong schema/type or required healthy field absent), `out_of_range` (cannot fit
signed31 after scaling), `error` (well-formed JSON-RPC error). Non-ok values are
empty strings; only explicit value extraction raises an error. Zero and false
are valid known values. `origin` is `simulation` only for an explicit true
`result.simulation` or `result.simulated` marker, otherwise `unmarked`; absence
never proves hardware measurement. Simulator health must add a true marker.
An absent/null optional section is unknown; inside a present section, a missing
required member is invalid. Only root `cpu_temp_c` and loop `achieved_hz` are
optional scalar members. Explicit null in a defaulted Boolean/counter is invalid.

Supported fields:

| Field | Typed value/unit |
|---|---|
| `healthy`, `degraded` | Boolean / `boolean` |
| `health.state` | `healthy`, `degraded`, `unhealthy` / `state` |
| `battery.percent`, `battery.volts` | integer / `0.01%`, `mV` |
| `cpu_temp_c`, `motors.max_c`, `motors.mean_c` | integer / `mC` (millidegrees C) |
| `control_loop.target_hz`, `control_loop.achieved_hz` | integer / `mHz` |
| `control_loop.last_tick_age_ms` | nonnegative integer / `ms` |
| `bus.consecutive_errors`, `bus.startup_failures` | nonnegative integer / `count` |
| `imu.ready`, `imu.missing` | Boolean / `boolean` |
| `imu.stale_blocks`, `imu.consecutive_stale_blocks` | nonnegative integer / `count` |
| `imu.state` | `missing`, `frozen`, `converged`, `not_converged` / `state` |

Fixed scaling rounds nearest with ties away from zero, never clamps or silently
wraps. Input must be a finite JSON number; counters must be unsigned integers.
Report only representability bounds; do not invent battery/thermal thresholds.

Upstream explicitly defaults absent `degraded` to false and bus counters to
zero. An absent IMU section is unknown; within an existing IMU object, absent
fields default to false/zero per its `serde(default)`. Missing IMU wins over
frozen; a stale run of at least25 uses upstream's FROZEN_RUN; otherwise expose
the reported convergence flag. This diagnostic is not motor readiness or motion
authorization. A true `imu.ready` alone may accompany frozen data upstream.

UBL adds typed battery/temperature/loop/health/IMU reporters and record helpers,
all using the same supplied snapshot. Missing/error readings remain observable
before explicit extraction. Tests must cover actual VM dispatch/bytecode,
unknown vs zero/false, malformed shapes, JSON-RPC errors, scaling and signed31
bounds, documented defaults, IMU 24/25 boundary and simulation marker retention.
Native allocation tests must exercise GC while constructing a reading record.
No physical MicroDuck compatibility may be claimed from these fixtures.

## Using the blocks

The MicroDuck library is version0.2 and requires a VM containing the two new
primitive names. Older prototype binaries without them cannot run these blocks.
Use `health JSON` once, then pass that same reply to any typed reporter. The
reporters parse the supplied snapshot without any I/O; reusing a snapshot does
not make it fresh, and its origin marker is reported metadata, not attestation.

The visible battery/temperature/loop/health/IMU blocks return reading lists.
For example, fictional `73.25%` becomes
`[ok, 7325, 0.01%, simulation]`, and missing battery becomes
`[unknown, "", 0.01%, simulation]`. Check `reading ... has a known value` before
`known reading value`; the latter refuses non-ok data instead of silently
coercing it. `reading status`, `reading unit` and `reading origin` remain useful
when no scalar value is available. The read-only health example prints both
raw JSON and labelled typed battery/IMU readings.

`reported health verdict reading` reflects the upstream release-health verdict.
`IMU convergence state reading` reports orientation convergence/missing/frozen
diagnostics. A program may explicitly wait for its chosen documented condition,
but neither reading is a universal robot-ready flag or permission to move. No
automatic action, wait loop, retry or threshold for physical safety is added.
True `imu.ready` may coexist with stale/frozen data, which is why the diagnostic
state exposes that distinction. Optional raw sensor streams and inferred pose
are outside the health interface and are not fabricated here.
