# Read-only ToF and gamepad simulation blocks

This increment implements Fred's requested tofd/padd read blocks against fixed,
source-shaped simulated Unix services. There is no live endpoint argument,
robot movement, automatic driving, BLE forwarding or hardware acceptance.
The ordinary gateway does not gain stream methods. Local sensorSim wrappers
are project adapters, not Pollen RPC names. All results say simulation:true.

## Source and behavior before implementation

Pollen API44, commit96b89d8613f06722c1d64ce75ab0d7124fed9d8f:
duck-ipc-proto defines tof.stream/tof.frame and pad.input/pad.report; padd's tap
accepts pad.input as its first call without hello. tof/src/lib.rs Frame::zone
classifies status5/9 with positive distance as a range,255 as no target, every
other case as unusable. Rows/columns are8x8; distances are signed16 millimetres
and raw statuses unsigned8. Preserve missing/failed data instead of zero.

The separate Sensor Simulation library uses existing asynchronous native jobs:

| Local wrapper / block | Exact params | Result |
|---|---|---|
| microduck.sensorSim.tof / simulated depth zone JSON | row,col integer1..8 | First frame on a fresh tof.stream subscription; range mm, raw status/distance, no-target/unusable/absent/waiting/refused states |
| microduck.sensorSim.axis / simulated gamepad axis JSON | code integer0..65535 | First raw frame after attached, with declared min/max and a matching EV_ABS event; no normalization or inferred zero |
| microduck.sensorSim.button / simulated gamepad button JSON | code integer0..65535 | Matching EV_KEY event; zero released, nonzero held, including repeat2 |

Acceptance is not attachment or sensor presence. No frame means waiting, not a
zero reading. A pad detach clears the read; a frame without the selected event
returns no_event. Unadvertised codes return unsupported. after_drop or a positive
socket_dropped counter makes the value unknown. A fresh subscription deliberately
does not synthesize held-state updates from cached events. Numeric convenience
reporters, continuous state cache, pad IMU and live commissioning remain future
work. Do not use a first-frame sample as a dead-man switch or robot authorization.

Device code/ranges come from attached metadata. Signed32 raw axis values remain
in JSON; no forced signed31 conversion or guessed stick/trigger scaling. u64
sequence/timestamps/drop counts and signed64 since_us are returned as decimal
strings, avoiding VM numeric precision loss. ToF at_us is sender uptime; pad
at_us is kernel CLOCK_REALTIME and since_us may be negative. Local arrival does
not establish source freshness or physical sampling. No wall/monotonic clocks
are compared or reprojected into robot coordinates.

## Bounds and acceptance

Each request uses a verified same-UID private socket and a new subscription,
closes it on completion/cancellation, consumes at most16 notifications and waits
at most0.35s. Wire lines are capped at16KiB, pad device axes64/buttons256 and
events128. Malformed frames, duplicate members, wrong IDs/methods, bad dimensions,
types/ranges are rejected; no reconnect, cached history or replay.
Replies are capped at760bytes for native reporter transport. Fixtures use a
fresh0700 directory and0600 sockets, default normal fictional readings or an
explicit absent profile. There is no injected production service provider.

Tests must include source-shaped real Unix subscription exchanges, absence,
drop/detach/no-event/timeouts and malformed input; then actual sanitizer-built
VM bytecode/native read jobs and bounds rejection before I/O. Pair the changed
C source with a new verified binary; historical Pi evidence is not acceptance
of these new wrappers. Package the separate library only in MicroDuck, preserve
the other six profiles and all hardware flags, and run tools/validate.py.

```sh
python3 linux/microduck/sensor_simulator.py --directory /tmp/microduck-sensors-NEW
# Point a newly built VM at the printed private gateway.sock.
```

Graphical UBL execution, actual tofd/padd permissions/revision/timestamps and
physical sensor/gamepad input remain unverified. The four-service matrix tracks
camera/media, controller and hardware work separately.

The focused suite is tests/test_linux_microduck_sensors.py:21 tests, including
four actual native VM cases, all passing with zero skips. The source audit is
tests/sensor-source.json; native provenance, sample scenario and package evidence
are retained under tests/sensor-*. A raw JSON value remains distinct from a
native numeric convenience reporter. The latter is not implemented here.

Each depth-zone call starts a new subscription. Reading64 zones separately does
not guarantee a coherent single frame; compare sequence identifiers and do not
reconstruct a synchronized depth map from arbitrary samples. Source geometry
and head calibration remain outside this simulation. A timeout before an
acceptance reply returns timeout; after acceptance with no selected frame it
returns waiting. Neither establishes a fresh physical measurement.
