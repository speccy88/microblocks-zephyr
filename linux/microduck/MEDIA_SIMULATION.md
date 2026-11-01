# Mediad audio and remote relay preparation

Spec-first continuation of c0d4b03. Review Pollen commit
5def2f3e66501f0f365d4fb1183020b8ee875443, especially mediad/src/session.rs,
route.rs, relay.rs, stream.rs, main.rs, duck-ipc-proto and the remote-access design.
Keep production API44, the camera observer and BLE confidentiality unchanged.

Audio capture/playback is not supplied by this reviewed mediad interface. Its
frame stream explicitly carries no audio; the pipeline is video-only, and main.rs
describes a microphone as future work. Robot sound requests are robotd features,
not a mediad microphone/stream API. Supply explicit unsupported audio readings;
do not invent audio.start, PCM samples, mute/volume controls or successful playback.

The documented remote RPC lane carries {type:peer,sessionId,rpc:{jsonrpc:2.0,...}}
over SSE plus POST/send. It shares session routing with WebRTC but does not need
ICE/video. It is not a teleop lane:1200 requests/minute is shared with liveness.
This lab implements only fixed internal fake envelopes, never HTTP, OAuth, tokens,
signaling discovery, a real session or credentials. A fixed fictional session and
request ID must match every response. No automatic reconnect or replay.

Expose one-shot native readings for video geometry, media.stream status-only
queries, robot.health/policies diagnostics and the published RemoteStatus shape.
RemoteStatus is a local runtime-file contract, not a new remote RPC method; the
lab uses an internal fixture and never reads /run/mediad or a credential file.
Registered state is not a live session, current heartbeat or permission to move.
Preserve all five source states, unknown account, signed64 Unix seconds as exact
decimal strings, and u64 stream counters. Never expose service/account/peer URLs,
raw retry reasons or a camera destination. Width/height/rotation are metadata,
not decoded pixels, audio, calibration or camera readiness.

Supply confirmed discrete-command relay packet previews using the existing
source-validated robot preview arguments. Require a separate backend opt-in and
per-request native/Python confirmation. Reject continuous move/head/pose/mouth,
held wheee, subscriptions, credential/account changes and media.stream mutations.
Previews only wrap and retain a packet; admission/applied remain null and no
mutation is sent to a mock or real service. Audit is process-local and bounded.

Consumer limits are project bounds, not claims about the rendezvous:32 attempts
per rolling60s,128 attempts/audit entries per process, four concurrent gateway
clients,0.5s read deadline and bounded JSON/760-byte receipts. Read errors,
timeouts, rate limits, missing status and unsupported audio have no extractable
value. Zero/false from valid data remains known. Typed records use the existing
GC-safe representation and append a primitive without renumbering old entries.

Acceptance: source-shaped envelopes, session/ID/error/size checks, all five relay
states, exact timestamps/counters, unknown versus zero, confirmation/opt-in and
teleop rejection before I/O, bounded rates/no replay, actual VM/GC tests with
fake services, full required validation and unchanged other editor profiles.
Physical audio, real relay authentication/network, live motion, graphical UBL,
native media decoding and shipping-image ownership remain unverified.

## Use the isolated lab

Start from a fresh private directory on Linux:

```sh
python3 linux/microduck/media_simulator.py --directory /tmp/microduck-media-lab
```

Use its reported gateway.sock with the native VM's existing MicroDuck gateway
option, import MicroDuck and Media_Simulation, and open media-simulation.ubp.
The packaged MicroDuck editor imports the library automatically. The example is
read-only. Unsupported audio is an explicit status with an empty value; extract
only a reading whose status is ok. No URL, device, microphone or token is accepted.

Only for internal packet-preparation exercises, add --allow-relay-previews and
set a discrete preview block's confirmation true. Construction and startup send
nothing. Preview results are JSON receipts with recorded_not_executed, never a
successful robot action. No simulation flag or confirmation enables real motion.
The ordinary gateway, robot-simulation backend and receive-only camera observer
do not implement this media prefix. Separate relay opt-in leaves their existing
robot/motion preview flags disabled.

Named CLI faults timeout,wrong_session,wrong_id,error,absent,malformed exercise
read failures. They never turn unsupported audio into a supported interface.
Closing the process closes its private sockets; no service is installed. A
metadata-write startup failure also cleans up partially opened sockets/tasks.
Run tests with the current verified sanitizer VM in SMALLVM_MICRODUCK_BINARY:

```sh
PYTHONPATH=tests python3 -m unittest test_linux_microduck_media -v
```

The [source audit](tests/media-source.json),
[acceptance receipt](../../evidence/2026-10-27/microduck-media/README.md) and
[four-service matrix](../../docs/MICRODUCK_SERVICE_CAPABILITIES.md) keep simulated
implementation, missing live software and physical acceptance separate.
