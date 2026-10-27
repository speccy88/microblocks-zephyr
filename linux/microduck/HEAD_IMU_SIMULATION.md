# Tofd head IMU: bounded native typed snapshots

Spec-first continuation after76f5b65. Review Pollen API45 at
5def2f3e66501f0f365d4fb1183020b8ee875443: duck-ipc-proto, tof/src/main.rs,
tof/src/imu.rs and robotd/src/head_imu.rs. Keep production API44 and all existing
control, BLE, network and service settings unchanged.

The existing native VM/private Unix gateway path already supports finite read
jobs. Implement the actual tofd IPC reader: send head_imu.stream params{} as the
first request, correlate its response, then read exactly one head_imu.frame.
No hello is sent: this tofd socket serves tof.stream/head_imu.stream, unlike the
robot gateway handshake. Check socket owner/SO_PEERCRED before writing. A reusable
reader takes an explicit absolute socket path and expected UID; it makes no
identity, permission or hardware inference from a UID match. Shipping deployment
still needs authoritative path/UID/permission inventory. The simulator's block
wrappers accept no endpoint and use only their own fixed private fake tofd.sock.

On zero3, tofd owns the BMI088 head IMU. A beta uses robotd/LSM6DSV16X; tofd can
return accepted:true without a sensor and name the proper owner in unavailable.
Do not automatically dial another daemon or change permissions/config. There is
also a pinned-source frame ambiguity: the shared HeadImuFrame docs describe
sensor axes, while robotd/src/head_imu.rs to_head explicitly rotates beta vectors
and quaternion into head axes. This increment supports tofd only. Beta mapping,
shipping revision and its model mount require separate validation; do not guess.

Nine typed selectors from one immutable snapshot: gyro(mrad/s), accel(mm/s2),
quat components(ppm, wxyz), reported temperature(mC), exact seq(count64), sender
uptime at_us(us_sender), t_ns(ns), reported sensor(text) and declared rate(Hz).
Gyro/accel are the tofd chip's tilted axes, not robot/head/camera axes. Specific
force includes gravity. Quaternion is sensor-to-its-own-world with arbitrary yaw;
no normalization, FK, calibration, orientation-ready or motion authority is added.
Temperature is cached by the source and may initially report0; a reported value
does not prove a fresh successful temperature read. Rate is declared, not measured.

Preserve explicit zero values and missing fields separately. HeadImuFrame has
serde defaults, but an omitted measurement is not evidence of physical zero:
return not_reported rather than inventing one. Empty/counter-only frames produce
no handle. Present all-zero quaternion is unusable; missing quaternion is
not_reported. t_ns0 is a legacy/unavailable clock; seq0 and at_us0 remain exact
reported values. Reject malformed/nonfinite/f32-overflow fields before retention.
Use signed31 fixed-point numbers, nearest rounding with ties away from zero;
out_of_range has no value. Preserve u64 values as exact decimal strings.

Four retained/in-flight snapshots, five-second expiry, explicit release and
clock-regression invalidation. Scalar reads do no I/O or lifetime extension.
Bound Unix lines to16KiB and capture to0.35s; close on completion, cancellation,
timeout or error. acceptedfalse is refused; no sensor is absent; accepted sensor
without a frame is waiting; pre-ack silence is timeout. A single frame cannot
prove sequence continuity, freshness, source identity or a safe robot state.

Add local headImuSim capture/read/release wrappers, a separate library and a
read-only example. Reuse the GC-safe IMU decoder with separate head field/kind
validation and append a headImuSample primitive without renumbering old names.
No commands, bus access, live endpoint, credentials, automatic drive, reconnect
or fallback. Audio stays unsupported. Acceptance requires source-shaped Unix
tests, exact units/absence/precision, resources/UID/cancellation, actual VM/GC,
unchanged other profiles, full validator and selected real Pi tests with fake
data. Physical head IMU, beta, graphical UBL and shipping deployment remain open.

## Using the simulation blocks

On Linux, start a lab using a new private directory:

```sh
python3 linux/microduck/head_imu_simulator.py --directory /tmp/head-imu-lab-NEW
```

Run the current VM with `--microduck-socket` set to the printed gateway.sock.
Import MicroDuck and Head_IMU_Simulation, then open head-imu-simulation.ubp.
The packaged MicroDuck editor includes the library and read-only example.
Capture once, check the returned status, read any component from that snapshot
and release it. Reading records are [status,value,unit,origin]; use the existing
readingValue block only for statusok. Vector components are1-based, quaternion
order is w,x,y,z. Scalar reads neither subscribe again nor renew the five-second
lifetime. A successfully captured frame is historical data, not current safety.

| Selector | Unit / interpretation |
|---|---|
| gyro | mrad/s, three tofd sensor-axis components |
| accel | mm/s2, three tofd sensor-axis components, including gravity |
| quat | ppm, four wxyz components; source orientation with arbitrary yaw |
| temperature | mC, reported cached temperature; source startup0 can be reported |
| seq | Exact u64 decimal sample counter |
| at_us | Exact u64 decimal sender uptime microseconds, not Unix time |
| t_ns | Exact u64 decimal CLOCK_MONOTONIC ns;0 is unavailable |
| sensor | Reported sensor identifier; no physical identity attestation |
| rate | Declared Hz; not a measured sample rate |

Use `--fixture` with absent, wrong_owner, refused, waiting, pre_ack_timeout,
partial, empty, zero_quat, legacy_clock or malformed to inspect failure semantics.
The [source audit](tests/head-imu-source.json) records pinned files and the beta
frame discrepancy. No fixture establishes actual sensor support.

The [tested checkpoint](../../evidence/2026-10-27/microduck-head-imu/README.md)
records353 full local tests and144 selected tests on each real Pi build, all
with simulated sensor input. Physical, beta and graphical acceptance remain open.
