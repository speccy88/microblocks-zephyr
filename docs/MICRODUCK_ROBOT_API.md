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
simulated daemons. New missing families below are queued after the coherent
sensor checkpoint; no row claims a production/live controller exists.

| Requested method | Exact interface/semantics | Existing blocks and remaining work |
|---|---|---|
| robot.move | Notification: vx/vy m/s, vyaw rad/s; trunk x-forward/y-left/z-up, positive yaw left | Separate bounded Motion Simulation lease block,10Hz recorder, client opt-in/confirmation. Live admission/applied velocity/gait unverified. |
| robot.head | Notification: neck_pitch,head_pitch,head_yaw,head_roll f64 radians | Dedicated block missing. Joint targets, not a gaze point; do not invent motor IDs or neutral-on-expiry behavior. |
| robot.look | Request: x,y,z metres in trunk frame plus neck_pitch radians; reply head targets and clamped | Dedicated block missing. IK belongs to daemon; simulated tests must not claim solved/achieved gaze. |
| robot.stop | Empty request: zero velocity | Dedicated block missing. It does not cut torque or guarantee emergency stopping. |
| robot.enable | Request: on Boolean, toggle Boolean(defaultfalse); toggle ignores on and acts on daemon state | Advanced native job exists behind allowlist+confirmation; dedicated block needed. Policy enable differs from joint torque. |
| robot.init | Empty request: power joints/ramp home | Advanced gated job exists; dedicated block needed. Physical movement/safety unverified. |
| robot.relax | Empty request: cut joint torque | Dedicated block missing; a real robot can collapse. Keep explicit confirmation. |
| robot.do | Request: skill String advertised by robot | Dedicated confirmed skill wrapper exists, with conservative discovery. Review skills/built_in and actual advertised names rather than hardcode an enumeration. |
| robot.pose | Notification: z metres(-.025..+.010 trained span),roll/pitch radians(±.26 trained span),active Boolean(defaulttrue) | Dedicated block missing. Source says daemon does not clamp training distribution; activefalse snaps nominal. |
| robot.mouth | Notification: open f64,0..1; daemon clamps | Dedicated block missing. No policy/servo implementation is supplied by a client. |
| robot.sound | Request or documented held-notification form: SoundTag; optional hold Boolean for wheee | Confirmed six-tag discrete wrapper exists. Wheee held lifecycle remains missing; no physical audio acceptance. |
| robot.health | Empty request, HealthResult diagnostics | JSON and18 typed native readings implemented. This is not CLI health's entire composite report or universal robot readiness. |
| robot.subscribe | SubscribeParams hz optionalu32, absent means every tick; ack then robot.state notifications | Bounded native state adapter/typed blocks missing. Do not run an infinite stream through one-reply jobs unchanged. |
| robot.policies | Empty request, actual loaded slots, mode, fallback/error/discovery | Dedicated JSON wrapper exists; loaded state must be reread after change, not inferred from acceptance. |
| robot.loadPolicy | Nullable slot/path: bothsome=load; slotonly=clear that override; bothnone=clear all; pathwithoutslot refused | Advanced guarded job covers a conservative advertised-slot/path subset. Dedicated lifecycle/reset blocks missing. Accepted does not mean swapped network is applied; no arbitrary upload granted. |
| robot.model | Empty request, static MJCF asset/joint names/head order/ToF beams/reference poses/skeleton tree | Advanced native read allowed; dedicated bounded model/geometry blocks missing. Never invent calibration or a beta IMU mount. |
| robot.setMode | Request mode String(walk/roller known); home transition and policy switch | Dedicated block missing. Config unchanged by switch; acceptance is not completed motion. |

Parameter types are from the immutable
[API45 protocol](https://github.com/pollen-robotics/microduck/blob/5def2f3e66501f0f365d4fb1183020b8ee875443/duck-ipc-proto/src/lib.rs),
including MoveParams,HeadParams,LookParams,EnableParams,DoParams,PoseParams,
MouthParams,SoundParams,SubscribeParams,LoadPolicyParams andSetModeParams.
Before live commissioning, verify the actual daemon revision, caller privileges
and robotd implementation alongside this draft design.

## Requested state telemetry

These are fields of RobotState pushed as robot.state, not individual RPC methods.
The table describes typed-block work still missing after sensor snapshots.
Present zero/false must stay known; absent, null or omitted vectors stay explicit.
Fields with serde defaults need a documented old-release fallback, not fabricated
measurements. u64 counters/time remain exact decimal strings where needed.

| Requested field | Source type and units | Typed representation to implement |
|---|---|---|
| move.requested / move.applied | [f64;3], vx/vy m/s and yaw rad/s | Per-component fixed mm/s or mrad/s readings from one retained state; requested and applied remain separate. |
| move.limited_by | Vec<String>, omitted empty | Count/indexed reasons; empty means no reported limit, never general safety. Distinguish original absence in diagnostics. |
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
| robotctl monitor | robot.subscribe(hz), then state stream; TUI may separately attach pad,ToF,media and tolerate their absence; piped/--json mode requires robot stream and treats closure as error | Bounded state/typed telemetry adapter is next. Sensor snapshots cover separate depth/pad ingredients, not the entire monitor. No unbounded subprocess or CLI output parser. |

The [four-service matrix](MICRODUCK_SERVICE_CAPABILITIES.md) remains the coverage
index. Source review is not execution or physical acceptance.
