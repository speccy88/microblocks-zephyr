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
| robotd | [Normal health/state adapter](../linux/microduck/ROBOT_SERVICE.md):21 health and29 state selectors; separate confirmed simulation control preparation | Commissioned live control/identity, continuous freshness and physical robot acceptance |
| tofd | [Coherent8x8 depth](../linux/microduck/DEPTH_SERVICE.md) and [nine head-IMU selectors](../linux/microduck/HEAD_IMU_SERVICE.md) through the normal read-only gateway; separate simulation libraries retained | Shipping config/identity, continuous freshness, physical/calibration, beta head-frame and graphical acceptance |
| padd | [Normal gamepad observations/discovery](../linux/microduck/GAMEPAD_SERVICE.md): raw axes, declared-span position, Boolean buttons, code/name/range metadata and exact event timing; [normal13-field IMU batches](../linux/microduck/PAD_IMU_SERVICE.md), separate simulation library retained | Shipping identity/permissions, physical/radio/graphical, continuous freshness/calibration and shipping IMU acceptance |
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
| robotd: health, battery, IMU, temperatures, loop and bus diagnostics | robot.health; robotd owns these reports and the controller | [Normal read-only adapter](../linux/microduck/ROBOT_SERVICE.md): coherent health snapshots with21 typed fields, exact counters and explicit schema defaults; existing raw/18-field path retained. Pi validation uses fictional robotd. No safe-to-move signal. | Physical readings, shipping units/absence semantics and commissioned live source identity. Composite CLI health/version diagnostics remain partial. |
| robotd: skills, sounds and policy slots | robot.policies, robot.skills, robot.do, robot.sound, robot.loadPolicy; authoritative discovery and caller policy | Dedicated discovery/sound/skill wrappers and advanced reviewed job calls. API45 lab adds confirmed load/clear-one/clear-all and sound/wheee packet previews using fictional advertised slots/paths. | Live slot/ONNX lifecycle, repeated held sound, supported discovery/install flows and physical acceptance. An arbitrary model path, policy upload or control-loop replacement is not granted. |
| robotd: continuous motion | robot.move notifications; vx/vy m/s, vyaw rad/s; current mediad uses reliable ordered control | [Motion Simulation](../linux/microduck/MOTION_SIMULATION.md): separate native library, bounded confirmed leases and internal recorder. No applied movement is modelled. | Commissioned live control, source identity/authorization, video visibility, configured robot arbitration/safety and physical gait/stopping. The deferred unreliable teleop protocol is not invented. |
| robotd: servos, head/body, power and safety | robot.head/pose/mouth are notifications; look/stop/init/enable/relax/rest/rebootMotors are distinct requests. Daemon owns the bus. | Dedicated head/look/pose/mouth/stop/enable/init/relax/setMode packet previews have backend opt-in, native/Python validation and confirmation. They only record; admission/applied remain unknown. Existing advanced init/enable gates remain. | Rest/restart/direct motor and live safety controls remain missing. Stop is not torque-off/e-stop; no motor bus is opened and no physical outcome is inferred. |
| robotd: continuous telemetry | robot.subscribe streams robot.state | [Normal robotd adapter](../linux/microduck/ROBOT_SERVICE.md) and separate simulation library supply finite one-frame subscription and29 typed selectors. Health/state share four five-second slots; missing values, exact counters and source-default limit counts are explicit. No repeated reader or mutation transport. | Live source identity, continuous freshness and physical telemetry are unverified. A completed one-frame capture leaves no reader running. |
| mediad: camera/video | GStreamer signaling, producer offers, receive-only browser video; local media.video metadata on control | Camera transport, video-element observer, reported rotation and labelled browser lab are implemented with fake signaling/RTC/frame callbacks. | Trusted live signaling and native decoding/browser playback are unverified. Native camera pixel/frame blocks and graphical acceptance remain missing; metadata is not a frame or calibration. |
| mediad: local raw camera frame | media.frame on the local MEDIA Unix socket: JSON header followed by its named binary bytes, deliberately outside Service/Lane and WebRTC control routing | Not implemented in native MicroBlocks. Existing JSON-only jobs cannot safely consume its binary tail. | Next camera-block software: a separately bounded frame/header reader, pixel/format/stride validation, ownership and lifetime, mock binary-tail tests, then shipping camera acceptance. Never add it to the generic NDJSON allowlist unchanged. |
| mediad: audio | Reviewed pipeline is video-only; frames-only media.stream explicitly carries no audio. main.rs describes microphone support as future work. robot.sound belongs to robotd. | [Media Simulation](../linux/microduck/MEDIA_SIMULATION.md) supplies explicit unsupported send/receive readings with no extractable value; no invented audio RPC or fake playback. Camera observer keeps audio inactive. | No usable mediad audio track/microphone API was found in the pinned source. Actual audio transport, capture/playback, permissions and shipping-hardware support remain missing or unverified. |
| mediad: remote RPC relay and diagnostics | SSE plus POST/send peer/sessionId/rpc envelopes; separate from ICE/video. media.video metadata, media.stream params{} status, and routed robot.health/policies. RemoteStatus is a local runtime-file shape, not an RPC. | Separate native SIMULATION library:17 typed media/relay/robot diagnostic selectors and nine confirmed discrete-command packet families. Fixed internal fake session, ID correlation, bounded attempts/deadline and explicit error/absence/unsupported results. Previews retain packets only; zero mutation forwarding. No source credential or endpoint input. | Real HTTP/SSE/session discovery/account authentication, peer identity and live commissioning remain missing. Continuous intents/held wheee/subscriptions, stream start/stop and secret operations are refused. Registered status/metadata never grants motion authority. Physical and graphical acceptance are unverified. |
| tofd: 8x8 depth | tof.stream acknowledgement then tof.frame; parallel row-major distance_mm i16 and raw status u8, sender uptime and monotonic clocks | [Normal depth adapter](../linux/microduck/DEPTH_SERVICE.md): explicit private path/UID, immutable whole8x8 frame, eight typed rows/all64 zones, raw diagnostics and seven exact metadata selectors. Four five-second slots, bounded reader and release/cancellation. Separate simulation library retained; local_ipc describes transport only. Real Pi VM tests use fictional tofd. | Shipping identity/permissions and source revision, continuous freshness, physical depth/calibration, deployment and graphical acceptance. Missing/ragged data never becomes a range; no_target is not clear-path authority. |
| tofd/robotd: head IMU | head_imu.stream/head_imu.frame; tofd owns BMI088 on zero3, robotd owns beta sensor | [Normal read-only gateway adapter](../linux/microduck/HEAD_IMU_SERVICE.md) and separate simulation library: checked explicit source config, first request without hello, one immutable frame and nine typed selector families. Gyro mrad/s, accel mm/s2, quaternion wxyz ppm, cached temperature mC, exact u64 sequence/uptime/monotonic clocks, sensor and declared Hz. Four five-second slots; missing data, legacy t_ns0 and degenerate quaternion explicit. local_ipc denotes transport only; no hardware claim, fallback or transform. Pi tests use fictional tofd. | Shipping source/path/UID commissioning, continuous freshness, calibration and graphical/physical acceptance. Beta deferred: robotd code rotates into head axes despite shared protocol sensor-axis docs. No guessed mount or automatic daemon switch. |
| padd: actual gamepad inputs | pad.input first request, accepted then pad.report attached/frame/detached and independent IMU messages | [Normal Gamepad adapter](../linux/microduck/GAMEPAD_SERVICE.md): private explicit padd path/UID; finite observed window and immutable snapshots; typed raw/Boolean/span/event sequence;1-based code/name/range discovery and11 metadata fields. Quiet descriptor-only capture does not claim live values. Held events survive empty frames; loss/detach invalidate state. Real Pi VM tests use fictional input. | Shipping revision/identity/caller permissions, physical input/radio, calibrated semantics, continuous freshness, graphical and deployment acceptance. Attached value/pressed are not current observations; no automatic drive or direct evdev access. |
| padd: gamepad IMU | Independent imu_attached/imu/imu_detached on pad.input; ordered sample batches, own drop counter, driver resolution and raw axes | [Normal padd IMU adapter](../linux/microduck/PAD_IMU_SERVICE.md) and separate simulation library: explicit checked source, one immutable1..32-sample batch; four five-second slots,13 typed selectors, mg/mdps from reported scale, exact u64 sample/kernel time and explicit loss/unknown-scale states. No orientation, automatic drive or additional subscriptions for component reads. | Real caller/peer identity, shipping resolution/time behavior, continuous freshness, physical IMU/radio and graphical UBL remain unverified. No head/trunk pose or calibration is inferred. |

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
