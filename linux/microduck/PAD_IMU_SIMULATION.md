# Typed gamepad IMU batch snapshots

Spec-first continuation after719d2b3. Pollen API45 at
5def2f3e66501f0f365d4fb1183020b8ee875443 defines independent imu_attached,
imu and imu_detached pad.report variants on pad.input. A batch contains ordered
PadImuSample entries and its own socket_dropped counter. This counter does not
describe stick/button loss. Device resolutions are raw units per g and per
degree/second; zero means unknown. No pad orientation, robot frame, calibration
or head IMU is inferred. Audio stays explicitly unsupported in the media lab.

Implement a separate read-only private simulator, native library and example:
capturePad/read/release local imuSim wrappers, not new Pollen RPC names. Capture
one whole source-shaped batch,1..32 samples, on the fixed private fake pad.input
socket. Keep at most four retained/in-flight IMU snapshots for five seconds.
Legacy depth/gamepad snapshots retain their separate bounded store. Explicit
release/expiry and clock-regression invalidation remove handles. Reads never
subscribe again and never refresh lifetime. Random32-hex handles are process-
local resources, not authentication or source identity.

Require an IMU attachment before its batch; ignore ordinary pad lifecycle/input
reports without treating them as IMU samples. IMU lifecycle is independent of
ordinary pad attachment. A dropped batch or nonconsecutive sample sequence
returns dropped with no handle. Reject malformed/oversized batches rather than
truncate them. Preserve sample ordering and every sample in the bounded batch.
at_us is the kernel's wall clock: keep its exact u64 value, including a clock
step backwards; it is not the head/ToF monotonic timebase. seq is exact u64.

Typed selectors: accel_raw,gyro_raw; accel_mg,gyro_mdps using only positive
advertised resolutions; seq,at_us; sample_count; accel_per_g,gyro_per_dps and
accel_max,gyro_max; accel_at_limit,gyro_at_limit against positive declared max.
Components1..3 and sample1..32 must be in the retained batch. Scale using integer
arithmetic, round nearest with ties away from zero, and refuse signed31 overflow.
Zero resolution/full-scale yields not_reported for derived readings; raw zero
remains known. Full-scale comparison is a reported-range diagnostic, not a
calibration or proof a physical sensor clipped. mg is milli-g; mdps is milli-
degree/second. No assumed gravitational constant or inferred velocity/orientation.

Unobserved IMU by a bounded deadline is not_reported, observed attachment with
no batch is waiting, imu_detached is detached, refused subscription is refused,
pre-ack deadline is timeout and event cap is event_limit. All non-ok readings
have no extractable value. Unknown data never becomes a zero or ready signal.
Bound private Unix messages to16KiB,16 notifications,0.35s and four clients.
Close the subscription on completion/cancellation/failure. No continuous reader,
real input device, endpoint/credential input, command, replay or automatic drive.

Append a GC-safe imuSample primitive without renumbering set22; package the
library/read-only example only in MicroDuck. Acceptance: schema/bounds, exact
scale/time semantics, loss/lifecycle/expiry/resource checks, actual VM/GC and
fake Unix subscription tests, unchanged other profiles and full validation.
Use the real Pi for selected fake-service suites; do not invoke the denied
numeric suite or Edge action. Physical/gamepad/radio and graphical UBL remain
unverified; real commissioning needs shipping identity/ownership and permissions.

## Use and units

Start the lab with a fresh private directory:

```sh
python3 linux/microduck/pad_imu_simulator.py --directory /tmp/pad-imu-lab-NEW
```

Point the current native VM at the printed gateway.sock using its existing
MicroDuck gateway option. Import MicroDuck and Pad_IMU_Simulation, then open
pad-imu-simulation.ubp. The packaged MicroDuck editor includes both library and
example. Capture once, check capture status, read the desired samples and release.
Only statusok has an extractable value. Sample numbers are1-based within that
retained batch; component1..3 follows the reported sensor axes, not robot axes.

| Reading | Unit / interpretation |
|---|---|
| accel_raw / gyro_raw | Raw driver integers; no implicit physical normalization |
| accel_mg / gyro_mdps | Milli-g / milli-degree per second from positive reported resolution; acceleration includes gravity |
| seq / at_us | Exact u64 decimal strings; sample sequence / kernel Unix microseconds |
| sample_count | Number of samples retained from this one batch |
| accel_per_g / gyro_per_dps | Reported raw units per g / degree per second; zero is explicitly unknown scale |
| accel_max / gyro_max | Reported raw full-scale values; zero means no usable limit |
| accel_at_limit / gyro_at_limit | Boolean comparison to a positive reported full scale; no calibration/physical clipping proof |

Named fixtures unscaled,dropped,no_imu,waiting,detached,refused,bad_order,oversized
exercise unavailable/error paths. Their results never establish hardware support.
The [acceptance receipt](../../evidence/2026-10-27/microduck-pad-imu/README.md)
records actual VM/Pi tests with fake data and all initial failures separately.
