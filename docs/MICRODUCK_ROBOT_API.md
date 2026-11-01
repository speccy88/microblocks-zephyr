# Requested robot methods, telemetry and CLI mapping

Fred supplied the [protocol source](https://raw.githubusercontent.com/pollen-robotics/microduck/main/duck-ipc-proto/src/lib.rs)
and [control-loop design](https://github.com/pollen-robotics/microduck/blob/main/docs/design/robotd-design.md).
Read-only review resolved main to5def2f3e66501f0f365d4fb1183020b8ee875443,
API45. Existing preparation is pinned to API44/96b89d8. The intervening protocol
diff changes vet-book gallery sharing, not the sensor/control/state types below;
tof/src/lib.rs and padd/src/tap.rs are unchanged. No live permission or method
allowlist is expanded by this review. Shipping revision/ownership remain unknown.

The design is a draft and describes a daemon-owned50Hz control loop, one motor
bus, nonblocking/decimated telemetry and robot-side safety/arbitration. It is not
evidence of hardware behavior. Client bounds/confirmation, health and a recorded
request cannot establish applied motion or safe-to-move authorization. Keep
robotd authoritative; do not open its bus, bypass arbitration or parse CLI text
as a substitute for typed service data.

## Explicit method coverage

All real MicroDuck behavior remains unverified. Implemented native/Pi tests use
simulated daemons. Dedicated packet-preview and typed-state blocks now run against fixed fake
services in [the API45 lab](../linux/microduck/ROBOT_SIMULATION.md). Preview
receipts mean recorded_not_executed; admission and applied behavior stay unknown.
No row claims a production/live controller exists.

| Requested method | Exact interface/semantics | Existing blocks and remaining work |
|---|---|---|
| robot.move | Notification: vx/vy m/s, vyaw rad/s; trunk x-forward/y-left/z-up, positive yaw left | Separate bounded Motion Simulation lease block,10Hz recorder, client opt-in/confirmation. Live admission/applied velocity/gait unverified. |
| robot.head | Notification: neck_pitch,head_pitch,head_yaw,head_roll f64 radians | Dedicated confirmed packet preview implemented, using integer mrad. Joint targets, not a gaze point; live travel/holding and neutral-on-expiry behavior are not invented. |
| robot.look | Request: x,y,z metres in trunk frame plus neck_pitch radians; reply head targets and clamped | Dedicated confirmed point/neck packet preview implemented. IK belongs to daemon; no solved/achieved gaze is claimed. |
| robot.stop | Empty request: zero velocity | Dedicated confirmed request preview implemented. It does not cut torque or guarantee emergency stopping. |
| robot.enable | Request: on Boolean, toggle Boolean(defaultfalse); toggle ignores on and acts on daemon state | Advanced gated job and dedicated confirmed preview exist. Policy enable differs from joint torque; previews do not model the toggle result. |
| robot.init | Empty request: power joints/ramp home | Advanced gated job and dedicated confirmed preview exist. Physical movement/safety unverified. |
| robot.relax | Empty request: cut joint torque | Dedicated confirmed preview implemented; a real robot can collapse. No torque command is forwarded by the lab. |
| robot.do | Request: skill String advertised by robot | Dedicated confirmed skill wrapper exists, with conservative discovery. Review skills/built_in and actual advertised names rather than hardcode an enumeration. |
| robot.pose | Notification: z metres(-.025..+.010 trained span),roll/pitch radians(±.26 trained span),active Boolean(defaulttrue) | Dedicated confirmed preview implemented within the trained span. Source says daemon does not clamp training distribution; activefalse snaps nominal on a real controller. |
| robot.mouth | Notification: open f64,0..1; daemon clamps | Dedicated0..1000 permille packet preview implemented. No policy/servo implementation is supplied by the client. |
| robot.sound | Request or documented held-notification form: SoundTag; optional hold Boolean for wheee | Confirmed discrete wrapper and source-shaped wheee hold/release packet previews exist. A repeated held emitter and physical audio remain unverified. |
| robot.health | Empty request, HealthResult diagnostics | JSON and18 typed native readings implemented. This is not CLI health's entire composite report or universal robot readiness. |
| robot.subscribe | SubscribeParams hz optionalu32, absent means every tick; ack then robot.state notifications | Bounded one-frame capture and29 typed selectors implemented with fake robotd; four five-second snapshots. No infinite stream is put through one-reply jobs or left running. |
| robot.policies | Empty request, actual loaded slots, mode, fallback/error/discovery | Dedicated JSON wrapper exists; loaded state must be reread after change, not inferred from acceptance. |
| robot.loadPolicy | Nullable slot/path: bothsome=load; slotonly=clear that override; bothnone=clear all; pathwithoutslot refused | Advanced guarded job covers a conservative advertised-slot/path subset. Dedicated preview/load/clear-one/clear-all blocks use fictional advertised paths. No applied swap or arbitrary upload is granted. |
| robot.model | Empty request, static MJCF asset/joint names/head order/ToF beams/reference poses/skeleton tree | Advanced read and dedicated bounded model metadata block exist (asset, counts, joint/link names). Calibrated geometry/beam blocks remain missing; no beta mount is invented. |
| robot.setMode | Request mode String(walk/roller known); home transition and policy switch | Dedicated confirmed request preview implemented. Config is unchanged by a real switch; a preview is neither acceptance nor completed motion. |

Parameter types are from the immutable
[API45 protocol](https://github.com/pollen-robotics/microduck/blob/5def2f3e66501f0f365d4fb1183020b8ee875443/duck-ipc-proto/src/lib.rs),
including MoveParams,HeadParams,LookParams,EnableParams,DoParams,PoseParams,
MouthParams,SoundParams,SubscribeParams,LoadPolicyParams andSetModeParams.
Before live commissioning, verify the actual daemon revision, caller privileges
and robotd implementation alongside this draft design.

## Requested state telemetry

These are fields of RobotState pushed as robot.state, not individual RPC methods.
The separate Robot Telemetry Simulation library now provides typed readings
from one retained source-shaped state. These are simulated values, not measured
robot telemetry. Continuous/live commissioning remains missing.
Present zero/false must stay known; absent, null or omitted vectors stay explicit.
Fields with serde defaults need a documented old-release fallback, not fabricated
measurements. u64 counters/time remain exact decimal strings where needed.

| Requested field | Source type and units | Implemented simulated typed representation |
|---|---|---|
| move.requested / move.applied | [f64;3], vx/vy m/s and yaw rad/s | Per-component fixed mm/s or mrad/s readings from one retained state; requested and applied remain separate. |
| move.limited_by | Vec<String>, omitted defaults to empty | Count/indexed reasons; omitted count is known0 with origin sim_default, explicit empty count has origin simulation. Missing indexed reason is not_reported. Neither establishes general safety. |
| loop.hz | f64 achieved rate, legitimate0 until first window closes | Fixed mHz; no client-side timing estimate. |
| safety | fallen/limp required Boolean; gravity[3] default; gainOption<u16>; picked_up defaultBoolean | Separate typed fields; unknown gain before first write and older omitted diagnostics remain visible. No safe-to-move Boolean. |
| joints / targets | Vec<f64> radians in JOINT_NAMES/model joint order | Indexed measured/commanded mrad readings; missing/index mismatch is unknown, not zero. |
| velocities | Optional/empty Vec<f64> rad/s | Indexed mrad/s; omitted/empty means not reported. Never difference decimated joint frames. |
| currents_ma | Optional/empty Vec<f64> magnitude mA | Indexed fixed microamp readings; no sign or force direction inferred from velocity. |
| odom | Position[3] metres,yaw radians; old serde defaultzero | mm/mrad with explicit original-absence state. World is boot-relative/gravity-aligned, not absolute location or compass heading. |
| imu | Optional trunk gyro[3] rad/s,quat[4] scalar-firstwxyz | mrad/s and fixed quaternion components; no false zero orientation for absent IMU. |
| frames | Optional camera/tof PoseState(positionmetres,quatwxyz); head_imu optional | Named component readings; preserve camera versus ToF axis conventions and beta mount limitation. No reprojection/calibration claim. |
| skeleton | Optional/empty Vec<PoseState> in model skeleton order | Indexed pose components paired with advertised link/parent metadata; no fabricated tree or FK. |
| t_ns | u64 CLOCK_MONOTONIC nanoseconds, default0 from olderdaemon | Exact decimal string; distinguish unsupported/legacyzero from a fresh sample. Never coerce through VM signed31 or JavaScript float. |

## robotctl diagnostics

Reviewed immutable sources:
[main.rs](https://github.com/pollen-robotics/microduck/blob/5def2f3e66501f0f365d4fb1183020b8ee875443/robotctl/src/main.rs),
[monitor.rs](https://github.com/pollen-robotics/microduck/blob/5def2f3e66501f0f365d4fb1183020b8ee875443/robotctl/src/monitor.rs).
No robotctl command was run or installation assumed on a physical robot.

| CLI | Actual implementation | Blocks/diagnostics mapping |
|---|---|---|
| robotctl version | Own build info; hello on updaterd/robotd/configd; updater status/listInstalled and configd system.services; running versus installed/revision warnings | Existing hello/services/update reads are partial ingredients. A composite version block is missing. Preserve unreachable/build-unknown states; do not infer btd's running binary from installed release. |
| robotctl health | robot.health plus composite software report, camera/remote runtime metadata, account and local board report; optional --check checks sources | Existing18 typed health readings cover robot.health only. Composite diagnostic blocks remain partial. No shell parsing, board reconfiguration prompt or implicit network check is introduced. |
| robotctl monitor | robot.subscribe(hz), then state stream; TUI may separately attach pad,ToF,media and tolerate their absence; piped/--json mode requires robot stream and treats closure as error | Bounded state capture and typed telemetry are implemented with fake services. Sensor snapshots cover separate depth/pad ingredients, not the entire monitor. No unbounded subprocess or CLI output parser. |

The [four-service matrix](MICRODUCK_SERVICE_CAPABILITIES.md) remains the coverage
index. Source review is not execution or physical acceptance.
