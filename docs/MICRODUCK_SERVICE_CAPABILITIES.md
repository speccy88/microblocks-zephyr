# Four-service MicroBlocks objective and capability matrix

Fred's objective is block-level access to robotd, mediad, tofd and padd: read
depth/gamepad/camera data and control the robot through its supported interfaces.
This is broader than a generic JSON console. The table distinguishes dedicated
native blocks, advanced calls, simulated preparation and missing software.
No row is physical MicroDuck acceptance; the robot has not arrived.

Source baseline: Pollen API44 at
[96b89d8613f06722c1d64ce75ab0d7124fed9d8f](https://github.com/pollen-robotics/microduck/tree/96b89d8613f06722c1d64ce75ab0d7124fed9d8f).
Actual daemon ownership, permissions and shipping revision still need inventory.

| Service / capability | Actual documented interface | Current blocks / implementation | Missing blocks or transport / next acceptance |
|---|---|---|---|
| robotd: health, battery, IMU, temperatures, loop and bus diagnostics | robot.health; robotd owns these reports and the controller | Native health JSON and 18 typed readings; real Pi baseline tests use simulated daemons. No universal ready or safe-to-move signal. | Physical readings, shipping units/absence semantics and current-revision Pi acceptance. Dedicated policy/state telemetry beyond health remains partial. |
| robotd: skills, sounds and policy slots | robot.policies, robot.skills, robot.do, robot.sound, robot.loadPolicy; authoritative discovery and caller policy | Dedicated discovery/sound/skill wrappers and advanced reviewed job calls. Mutations require native confirmation plus operator allowlist; policy slots/paths must be advertised. | Dedicated slot/ONNX lifecycle blocks and supported discovery/install flows are incomplete. An arbitrary model path, policy upload or control-loop replacement is not granted. |
| robotd: continuous motion | robot.move notifications; vx/vy m/s, vyaw rad/s; current mediad uses reliable ordered control | [Motion Simulation](../linux/microduck/MOTION_SIMULATION.md): separate native library, bounded confirmed leases and internal recorder. No applied movement is modelled. | Commissioned live control, source identity/authorization, video visibility, configured robot arbitration/safety and physical gait/stopping. The deferred unreliable teleop protocol is not invented. |
| robotd: servos, power and safety | Daemon owns the bus; init/enable differ from direct joints, relax and physical e-stop | Advanced init/enable remain behind existing mutation gates. Typed health/IMU reports are diagnostics only. Motion simulation never enables policy or joints. | Dedicated servo/joint and physical safety controls remain unavailable. Review each actual method/permission before adding it; do not open motor buses or imply an emergency stop. |
| robotd: continuous telemetry | robot.subscribe streams robot.state | Existing native jobs are bounded one-reply operations; health is a snapshot, not a state stream. | A dedicated bounded native state subscription with freshness, missing data, cancellation and source identity. Do not route an infinite stream through a one-reply job unchanged. |
| mediad: camera/video | GStreamer signaling, producer offers, receive-only browser video; local media.video metadata on control | Camera transport, video-element observer, reported rotation and labelled browser lab are implemented with fake signaling/RTC/frame callbacks. | Trusted live signaling and native decoding/browser playback are unverified. Native camera pixel/frame blocks and graphical acceptance remain missing; metadata is not a frame or calibration. |
| mediad: audio and relay | Media tracks/pipeline and documented remote signaling/control relay; not a generic BLE method | No native audio/media relay block surface is supplied. Camera observer deliberately disables audio and rejects general control forwarding. | Review and implement the actual audio/frame/relay interfaces separately; no made-up camera.read or audio RPC. Privacy, authentication, playback/capture and network commissioning remain gates. |
| tofd: 8x8 depth | tof.stream on the sensor daemon, accepted/sensor/unavailable description, then tof.frame notifications; row-major distance_mm i16 and raw status u8 | No dedicated native ToF read blocks yet. Ordinary gateway does not accept this stream. | Next: bounded read/one-frame adapter and typed row/cell access with explicit absence/status. Use the source tof Frame.zone interpretation; do not treat missing or failed zones as zero distance. Test with source-shaped simulated services before hardware. |
| padd: actual gamepad inputs | pad.input on padd, then pad.report attached/frame/detached and optional IMU reports | pad.status/bindings exist in the current reviewed surface, but these are not the raw gamepad input stream. | Next: bounded raw input reader, device/axis ranges and button/axis blocks. accepted is not attached; timestamps/drop counters and stale inputs matter. Do not normalize guessed ranges or automatically turn cached input into robot commands. |

The Pollen protocol definitions are in
[duck-ipc-proto](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duck-ipc-proto/src/lib.rs).
The transport split is explicit in
[mediad routing](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/mediad/src/route.rs)
and [BLE routing](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/btd/src/route.rs).
The raw pad stream comes from
[padd's tap](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/padd/src/tap.rs),
and the ToF implementation/zone semantics from
[tof](https://github.com/pollen-robotics/microduck/tree/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/tof/src).

Implementation order: finish the bounded motion checkpoint, then add read-only
ToF/gamepad adapters and blocks, followed by native camera/frame and remaining
robot/media capability families where the actual interfaces support them.
Keep real control disabled until separately commissioned; keep the BLE secret
gate and existing camera receive-only scope. Graphical testing remains blocked
by the earlier Edge URL-policy stop and is not retried here. Do not publish or
merge shared main while P4 work is active. This matrix must evolve with evidence,
not replace the [remaining-objectives ledger](MICRODUCK_REMAINING_OBJECTIVES.md).
