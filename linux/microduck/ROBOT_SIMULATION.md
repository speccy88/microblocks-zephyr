# Robot API45 preparation: control previews and typed state snapshots

Spec-first continuation aftere74f496. Source mapping is
[MICRODUCK_ROBOT_API.md](../../docs/MICRODUCK_ROBOT_API.md), API45 at5def2f3e.
Use the actual IPC types and robotd control-loop design. Preserve the production
gateway/BLE/camera allowlists and all confidentiality gates. No physical robot,
motor device, daemon install or live endpoint is supplied by this lab.

## Control preparation

Provide dedicated SIMULATION blocks for the requested move,head,look,stop,
enable,init,relax,do,pose,mouth,sound,health,subscribe,policies,loadPolicy,model,
setMode families. Existing health/policy and bounded motion blocks remain.
New mutation blocks default confirmationfalse and need an explicit backend
--allow-control-previews opt-in plus per-request native/Python validation.
The backend only records a source-shaped request/notification in a bounded128
entry audit. It never calls a robot service for a mutation. A local receipt
says recorded_not_executed, admission:null and applied:null; it must not invent
IK, policy admission, torque state, a successful mode/network swap or physics.

Continuous move/head/pose/mouth (and held wheee) previews are single source-shaped
notifications withoutid. They are packet preparation, not a live/repeated sender.
The separate existing Motion Simulation lease is the timed twist recorder.
No neutral head/body/mouth target or physical stop is synthesized at preview
completion. stop means zero velocity on the actual API, not torque-off/e-stop;
relax can collapse a real robot. Existing protection and future commissioning
gates remain essential before any real control transport.

Blocks use integer mm,mrad,mm/s,mrad/s and mouth permille, converting once to
source metres/radians/seconds. Pose bounds follow the documented trained span:
z_mm -25..10, roll/pitch_mrad ±260. Move caps match the existing preview300/300/
1500. Other preview serialization bounds (head±3142mrad,look±1000mm and neck±3142)
are project input limits, not source travel limits or a safe physical envelope.
Only known walk/roller modes, fixed fictional advertised skills/slots and advertised
fictional absolute policy paths may be recorded; nullable reset semantics are
explicit. No arbitrary model file is fetched/opened and no credentials are used.

Read-only health/policies/model come from fixed private fake robotd responses.
Model metadata is explicitly uncalibrated; no beams, camera calibration, beta
IMU mount or kinematics are invented. The CLI is not a runtime dependency.

## Typed robot.state

Subscribe on the fixed private mock socket using the source hello/request and
robot.subscribe(hz) envelopes. Bound rate1..50Hz, deadline0.5s and one complete
state frame; close on completion/error/cancellation. Verify UID/socket identity,
ack/notification types and resource bounds. Use at most four immutable five-
second snapshots. No continuous reader or replay remains after capture.

Implement typed per-field/component/index readings for move.requested/applied,
limited_by count/reasons,loop.hz,safety,joints,targets,velocities,currents_ma,
odom,imu,frames,skeleton andt_ns. Preserve required/optional/source-default
semantics explicitly. Present zero/false is known; omitted/null/empty optional
telemetry is not_reported, never a substitute zero. Requested and applied data
stay distinct; safety telemetry is diagnostic, not universal motion authority.
The source explicitly defaults an omitted move.limited_by list to empty. Its
count is therefore known zero with origin sim_default; an explicitly received
empty list has origin simulation. An indexed absent reason is not_reported.
This schema default is not a physical safety observation.

Integer units: mm/s,mrad/s,mHz,mrad,microamp,mm; quaternion/gravity components
use fixed1e6 scale. Raw/scaled values must fit signed31 or return out_of_range.
u64 counters/t_ns remain exact decimal strings; legacy t_ns0 is not a fresh
clock. Odometry is boot-relative; currents are magnitude only; velocities are
reported directly, never differentiated from decimated joints. Frames/skeleton
follow advertised model ordering and source axis conventions; no FK is performed.

Use small scalar receipts within760bytes and GC-safe four-field reading records.
Do not route a full unbounded state or binary media frame through the raw job
reporter. Keep existing primitive names/indices and append any required helper.
Package a separate labelled library/example in MicroDuck only.

Acceptance: exact source envelopes/types, all control guards/defaults, zero
mutation upstream calls, audit caps/no replay, finite typed values and units,
missing versus zero/false, optional geometry/IMU, precision, lifetime/cancel and
actual VM/GC tests with mocks. Run full local validation, selected JavaScript
tests and seven-profile package checks. Rebuild/current-revision Pi acceptance
uses only simulated services and never the denied numeric suite or Edge action.
Physical MicroDuck, graphical UBL and live commissioning remain unverified.
