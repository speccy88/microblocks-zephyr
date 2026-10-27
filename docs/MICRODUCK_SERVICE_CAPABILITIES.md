# Four-service MicroBlocks objective and capability matrix

Fred's objective is block-level access to robotd, mediad, tofd and padd: read
depth/gamepad/camera data and control the robot through its supported interfaces.
This is broader than a generic JSON console. The table distinguishes dedicated
native blocks, advanced calls, simulated preparation and missing software.
No row is physical MicroDuck acceptance; the robot has not arrived.

Deployment goal: SmallVM runs on the MicroDuck itself, with a self-hosted editor
or the GitHub Pages editor connecting to its VM bridge. Native Pi/SSH-loopback
execution is evidence for the Linux architecture, not shipping MicroDuck
commissioning. Local typed service adapters belong beside the VM and use checked
Unix identities/permissions. No cloud command runner is required or invented.
Do not assume port80 is free: inspect the shipping image and existing services
before proposing a bind/proxy change; the lab Pi's Caddy remains untouched.
Pages-to-robot transport still needs a trusted WSS endpoint/certificate and actual
browser local-network acceptance. Do not bypass mixed-content, certificate or
permission warnings, or change networking/security settings without required
approval. Self-hosted HTTP and Pages are separate deployment acceptance paths;
neither turns metadata, simulated input or an open socket into robot authority.

| Service | Usable typed preparation | Remaining software / acceptance |
|---|---|---|
| robotd |18 health fields and29 coherent state selectors; confirmed simulation control preparation | Commissioned live control/identity, continuous freshness and physical robot acceptance |
| tofd | Coherent8x8 depth capture, eight row readers and typed zone/status values | Dedicated head-IMU stream, live commissioning and physical/calibration acceptance |
| padd | Typed raw/Boolean/span control state plus [13 coherent IMU batch selectors](../linux/microduck/PAD_IMU_SIMULATION.md): raw/scaled acceleration/gyro, exact sample/time and reported limits | Continuous freshness, semantic control calibration, physical IMU/radio and graphical execution |
| mediad |17 metadata/status selectors and bounded relay preparation; audio explicitly unsupported by reviewed API | Native camera pixels/decoding, live relay/session authentication and a supplied audio interface |

Source baseline: Pollen API44 at
[96b89d8613f06722c1d64ce75ab0d7124fed9d8f](https://github.com/pollen-robotics/microduck/tree/96b89d8613f06722c1d64ce75ab0d7124fed9d8f).
Actual daemon ownership, permissions and shipping revision still need inventory.
The user-supplied current protocol was also reviewed at API45/5def2f3e;
[method, telemetry and CLI mapping](MICRODUCK_ROBOT_API.md) records every requested
robot family, actual types and outstanding blocks. The API45 diff is vet-book
gallery sharing; the reviewed sensor/control/state shapes remain unchanged.

| Service / capability | Actual documented interface | Current blocks / implementation | Missing blocks or transport / next acceptance |
|---|---|---|---|
| robotd: health, battery, IMU, temperatures, loop and bus diagnostics | robot.health; robotd owns these reports and the controller | Native health JSON and18 typed readings, plus bounded robot.state selectors. Real Pi tests use simulated daemons. No universal ready or safe-to-move signal. | Physical readings, shipping units/absence semantics and commissioned live source identity. Composite CLI health/version diagnostics remain partial. |
| robotd: skills, sounds and policy slots | robot.policies, robot.skills, robot.do, robot.sound, robot.loadPolicy; authoritative discovery and caller policy | Dedicated discovery/sound/skill wrappers and advanced reviewed job calls. API45 lab adds confirmed load/clear-one/clear-all and sound/wheee packet previews using fictional advertised slots/paths. | Live slot/ONNX lifecycle, repeated held sound, supported discovery/install flows and physical acceptance. An arbitrary model path, policy upload or control-loop replacement is not granted. |
| robotd: continuous motion | robot.move notifications; vx/vy m/s, vyaw rad/s; current mediad uses reliable ordered control | [Motion Simulation](../linux/microduck/MOTION_SIMULATION.md): separate native library, bounded confirmed leases and internal recorder. No applied movement is modelled. | Commissioned live control, source identity/authorization, video visibility, configured robot arbitration/safety and physical gait/stopping. The deferred unreliable teleop protocol is not invented. |
| robotd: servos, head/body, power and safety | robot.head/pose/mouth are notifications; look/stop/init/enable/relax/rest/rebootMotors are distinct requests. Daemon owns the bus. | Dedicated head/look/pose/mouth/stop/enable/init/relax/setMode packet previews have backend opt-in, native/Python validation and confirmation. They only record; admission/applied remain unknown. Existing advanced init/enable gates remain. | Rest/restart/direct motor and live safety controls remain missing. Stop is not torque-off/e-stop; no motor bus is opened and no physical outcome is inferred. |
| robotd: continuous telemetry | robot.subscribe streams robot.state | [Robot Telemetry Simulation](../linux/microduck/ROBOT_SIMULATION.md) supplies bounded one-frame subscription,29 typed selectors and four five-second retained snapshots. Missing data, exact timestamps and source-default limit counts are explicit. | Live source identity, continuous freshness and physical telemetry are unverified. A completed one-frame capture leaves no reader running. |
| mediad: camera/video | GStreamer signaling, producer offers, receive-only browser video; local media.video metadata on control | Camera transport, video-element observer, reported rotation and labelled browser lab are implemented with fake signaling/RTC/frame callbacks. | Trusted live signaling and native decoding/browser playback are unverified. Native camera pixel/frame blocks and graphical acceptance remain missing; metadata is not a frame or calibration. |
| mediad: local raw camera frame | media.frame on the local MEDIA Unix socket: JSON header followed by its named binary bytes, deliberately outside Service/Lane and WebRTC control routing | Not implemented in native MicroBlocks. Existing JSON-only jobs cannot safely consume its binary tail. | Next camera-block software: a separately bounded frame/header reader, pixel/format/stride validation, ownership and lifetime, mock binary-tail tests, then shipping camera acceptance. Never add it to the generic NDJSON allowlist unchanged. |
| mediad: audio | Reviewed pipeline is video-only; frames-only media.stream explicitly carries no audio. main.rs describes microphone support as future work. robot.sound belongs to robotd. | [Media Simulation](../linux/microduck/MEDIA_SIMULATION.md) supplies explicit unsupported send/receive readings with no extractable value; no invented audio RPC or fake playback. Camera observer keeps audio inactive. | No usable mediad audio track/microphone API was found in the pinned source. Actual audio transport, capture/playback, permissions and shipping-hardware support remain missing or unverified. |
| mediad: remote RPC relay and diagnostics | SSE plus POST/send peer/sessionId/rpc envelopes; separate from ICE/video. media.video metadata, media.stream params{} status, and routed robot.health/policies. RemoteStatus is a local runtime-file shape, not an RPC. | Separate native SIMULATION library:17 typed media/relay/robot diagnostic selectors and nine confirmed discrete-command packet families. Fixed internal fake session, ID correlation, bounded attempts/deadline and explicit error/absence/unsupported results. Previews retain packets only; zero mutation forwarding. No source credential or endpoint input. | Real HTTP/SSE/session discovery/account authentication, peer identity and live commissioning remain missing. Continuous intents/held wheee/subscriptions, stream start/stop and secret operations are refused. Registered status/metadata never grants motion authority. Physical and graphical acceptance are unverified. |
| tofd: 8x8 depth | tof.stream on the sensor daemon, accepted/sensor/unavailable description, then tof.frame notifications; row-major distance_mm i16 and raw status u8 | [Sensor Simulation1.1](../linux/microduck/SENSOR_SNAPSHOTS.md): immutable whole-frame capture, all eight coherent rows, typed zone/status records and numeric extraction. Four shared five-second snapshots; explicit release/expiry. Ordinary and sanitizer native VMs tested on real Pi with fake tofd. | Missing live commissioning, physical depth/calibration and continuous freshness. Historical rows can be retained after release but are not current obstacle-avoidance authorization. Graphical UBL execution remains unverified. |
| tofd/robotd: head IMU | head_imu.stream/head_imu.frame; daemon ownership depends on zero3/beta hardware | Existing health IMU diagnostics do not read this stream. | Dedicated bounded head-IMU stream blocks missing. Inventory hardware/owner, preserve units/timebase and unavailable semantics. |
| padd: actual gamepad inputs | pad.input on padd, then pad.report attached/frame/detached and optional IMU reports | Separate simulated JSON blocks plus bounded observed-state snapshots. Held events persist across empty frames; typed raw/Boolean/declared-span permille helpers preserve unknown/loss states and signed31 limits. | Missing live commissioning, continuous freshness/reader, semantic stick/trigger calibration and physical acceptance. Attachment values are not refreshed by upstream padd and are not treated as fresh state. Never automatically drive from retained/simulated input. |
| padd: gamepad IMU | Independent imu_attached/imu/imu_detached on pad.input; ordered sample batches, own drop counter, driver resolution and raw axes | [Pad IMU Simulation](../linux/microduck/PAD_IMU_SIMULATION.md): one immutable1..32-sample batch; four five-second slots,13 typed selectors, mg/mdps from reported scale, exact u64 sample/kernel time and explicit loss/unknown-scale states. No orientation, automatic drive or additional subscriptions for component reads. | Real caller/peer identity, shipping resolution/time behavior, continuous freshness, physical IMU/radio and graphical UBL remain unverified. No head/trunk pose or calibration is inferred. |

The Pollen protocol definitions are in
[duck-ipc-proto](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duck-ipc-proto/src/lib.rs).
The transport split is explicit in
[mediad routing](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/mediad/src/route.rs)
and [BLE routing](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/btd/src/route.rs).
The raw pad stream comes from
[padd's tap](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/padd/src/tap.rs),
and the ToF implementation/zone semantics from
[tof](https://github.com/pollen-robotics/microduck/tree/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/tof/src).

Motion and read-only simulated ToF/gamepad blocks are implemented. Continue with
native camera/frame and remaining robot/media capability families where the
actual interfaces support them; the table keeps unsupported families visible.
Keep real control disabled until separately commissioned; keep the BLE secret
gate and existing camera receive-only scope. Graphical testing remains blocked
by the earlier Edge URL-policy stop and is not retried here. Do not publish or
merge shared main while P4 work is active. This matrix must evolve with evidence,
not replace the [remaining-objectives ledger](MICRODUCK_REMAINING_OBJECTIVES.md).
