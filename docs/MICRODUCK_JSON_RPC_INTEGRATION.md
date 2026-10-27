# MicroDuck JSON-RPC Integration

The [gateway and native adapter guide](../linux/microduck/README.md) is the
executable contract, with pinned API-44 source links, parameter shapes, limits
and exact error behavior. No physical MicroDuck daemon has been contacted.

```text
MicroBlocks editor -> loopback WebSocket bridge -> native SmallVM
    -> nonblocking C jobs -> private same-user gateway socket
    -> checked robotd / configd / updaterd Unix sockets
```

`robotd` owns robot control and the 50 Hz loop; `configd` owns system/network
configuration; `updaterd` owns software state. `btd` handles BLE sessions/auth,
while `mediad` handles media/WebRTC. The optional gateway selects only documented
discrete/read APIs. It does not replace these services, use motor buses, expose
continuous movement/camera or accept PIN/Wi-Fi secrets.

The gateway defaults to read-only. Every enabled mutation requires both an
operator allowlist and confirmation in that request. Skills/policy slots must
be discovered from the actual upstream response. Same-user socket ownership,
canonical private paths and actual connected peer UID are verified; the daemon's
own permissions remain authoritative. Arrival inventory must establish numeric
UIDs rather than guessing them or relaxing socket permissions.

The MicroDuck editor appends primitive set 22 and includes `MicroDuck.ubl`.
Cooperative convenience blocks expose health/battery-health JSON, skills,
policies, capabilities, and confirmed sounds/skills. Advanced bounded jobs cover
the remaining allowlist. Battery absence remains unknown, not zero; health is
reported rather than inventing a universal ready/sensor API. Library0.2 adds
[typed readings](../linux/microduck/TYPED_READINGS.md) for eighteen documented
health fields. Every reading carries status, typed value, unit and origin;
missing data is never silently zero. The health verdict and IMU convergence
state are diagnostics, not universal movement readiness. Raw JSON retains the
remaining upstream fields. These conversions are tested with simulated readings
through real native Pi bytecode, not physical sensors.

Stop All cancels local waits; it cannot undo an accepted robot action. A timeout
or disconnect after sending can leave an `unknown` outcome. Inspect retained
jobs/results and current robot state before considering a new action. There is
no automatic retry or reconnect replay. An ordinary IDE disconnect preserves
autonomous scripts.

Real Pi acceptance executed bytecode, moving-GC and concurrency cases through
the C adapter and real Unix gateway against explicitly simulated robot daemons.
The graphical health block returned labelled fictional data and issued zero
sound/skill actions. [Evidence and reproduction](../linux/microduck/tests/README.md)
keep this distinct from physical battery, motion, sensor or service validation.
