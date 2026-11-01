# Normal read-only padd IMU adapter

Spec-first continuation after7844b80. Pollen API45/5def2f3e protocol and padd tap
have independent imu_attached/imu/imu_detached reports on pad.input. Reuse the
existing reviewed thirteen typed batch selectors, units, loss/order/unknown-scale
and resource rules. Preserve simulation paths and primitive indices/API44 pin.

An explicit private version1/daemon:padd/path/numeric uid config chooses the
source; no guessed socket, direct input node, pairing or permissions change.
Check canonical socket parent, owner/mode/inode and SO_PEERCRED before writing.
Send pad.input{} first without hello. Observe at most16 reports within0.35s,
16KiB lines. Require IMU attachment, capture exactly one complete1..32-sample batch,
close on success/error/cancel. Ordinary controls/attachments are independent and
never supply IMU samples. Positive socket_dropped or nonconsecutive samples yields
dropped without a handle. Malformed/oversized batches fail rather than truncate.

Four total retained/in-flight IMU slots, five-second TTL, release and clock-
regression invalidation. No background reader, retry or renewal from reads.
Normal microduck.padImu.capture/read/release wrappers retain immutable batches.
Zero raw data is known; missing scale/full-scale only disables derived readings.
Integer ties round away from zero; scaled/raw signed31 overflow has no value.
Exact u64 sequence/kernel Unix us remain strings; wall-clock regressions are
preserved, never confused with ToF/head monotonic clocks. No fusion/orientation,
robot frame, calibration, velocity, freshness or movement authority is inferred.

Append padImuReading primitive with source:padd/origin:local_ipc and false physical
verification/movement markers, no simulation member. local_ipc is transport only;
fixture metadata explicitly labels fictional input. Old source/kind gates remain.
Provide Pad_IMU library/example and normal gateway/client/CLI option. Validate
all fields/sample order/limits, availability/errors, exact scales/counters,
UID/private config, lifecycle/TTL/cancel, actual VM/GC, editor profile isolation,
full validator and fresh ordinary/sanitizer Pi builds using fake services only.
Physical IMU/gamepad/radio, shipping identity/permissions, continuous freshness,
calibration and graphical/editor deployment acceptance remain open. No commands,
credentials, device, network/security/service/startup changes, main or push,
denied numeric-suite/UI retry or physical movement.

## Use with fictional input

On Linux Python3.11+, start a new private fixture:

```sh
python3 linux/microduck/pad_imu_gateway_fixture.py --directory /tmp/pad-imu-read-NEW
```

The simulation:true metadata prints the normal gateway socket. Point SmallVM's
--microduck-socket there, import MicroDuck and Pad_IMU, then open pad-imu.ubp in
the MicroDuck editor package. Capture one batch, test microduckReadingKnown, read
1-based sample/components, then release. Scalar reads do not subscribe or renew.
Records are [status,value,unit,origin]; only ok is extractable. local_ipc describes
transport, never physical identity. seq/at_us are exact strings; at_us is kernel
Unix microseconds and can step backwards. Zero scale/max disables derived/limit
readings while raw zero remains known. mg includes gravity; mdps uses degree/s.
No orientation, frame transform, calibration or radio freshness is inferred.
Ctrl-C closes owned sockets; metadata remains. Use a new directory next time.
Named fixtures unscaled/dropped/no_imu/waiting/detached/refused/bad_order/oversized
exercise explicit unavailable/error paths, never hardware readiness.

After shipping inventory, use a private same-user regular config with exactly
version1, daemon:padd, inventoried absolute socket path and expected numeric uid.

```sh
python3 linux/microduck/gateway.py --config /absolute/private/gateway.json --pad-imu-config /absolute/private/pad-imu.json --socket /absolute/private/gateway.sock
```

The normal version1/upstreams config can be empty with this reader configured.
Other read-only adapters can coexist; IMU has four separate slots. Raw pad.input,
node/path inputs, pairing and arbitrary forwarding remain outside client wrappers.
No source permissions, groups or services are changed. Standalone installer and
shipping/editor/Pages transport acceptance remain separate. See the
[pinned source audit](tests/pad-imu-service-source.json).

## Verified checkpoint

465 full local tests and18 focused tests passed with zero skips. Fresh ordinary
and ASan/UBSan RPI5 builds each passed251 selected tests,66 native cases each.
All input is fictional; seven editor profiles checked. Graphical import/
compilation, physical/radio and shipping acceptance remain unverified.
See [evidence and remaining gates](../../evidence/2026-10-27/microduck-pad-imu-service/README.md).
