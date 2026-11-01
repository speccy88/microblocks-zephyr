# Coherent tofd depth through the normal read-only gateway

Spec-first continuation after ef080f1. Connect native depth blocks to the normal
gateway using an explicit private tofd path/expected-UID config, as with head IMU.
No source discovery, beta/head fallback, arbitrary RPC, device bus, command,
movement, service/network/security change or hardware-readiness claim.

Reviewed Pollen API45/5def2f3e: TofStreamResult/TofFrame in duck-ipc-proto,
tof/src/main.rs subscription/clock code, and tof/src/lib.rs Frame::zone. Send
tof.stream params{} first, no hello; correlate its acknowledgement and read one
tof.frame. Check socket owner, parent permissions, inode and SO_PEERCRED before
writing. Retain one validated immutable8x8 frame, never separate zone samples.
Source geometry/arrays are required; reject ragged or malformed data rather than
using the upstream convenience function's missing-zone fallback. Present values
must be i16 distance_mm, u8 status and u64 clocks/counters. Omitted clocks stay
unknown, t_ns0 means legacy/unavailable; explicit seq0/at_us0 remain known.

Four retained/in-flight frames per adapter, five-second expiry,0.35s deadline,
16KiB lines, explicit release and cancellation cleanup; no continuous reader,
reconnect or lifetime renewal on reads. Rows/zone/metadata queries reuse the same
frame. Raw status5/9 with positive distance yields a known mm range;255 is
no_target; everything else or nonpositive distance is unusable. No target is not
zero distance or permission to move. Raw distance/status are separate diagnostic
readings, including negative/zero raw distance; their known status is not a range.

Local depth.capture/row/zone/metadata/release wrappers use prefix microduck.depth.
Metadata: seq exact count64, at_us exact sender-uptime us, t_ns exact monotonic ns,
rows/cols count, reported sensor text and declared rate Hz. Never infer a missing
measurement, rate, mount/orientation, freshness, calibration or clear path.

Normal envelopes have source tofd, origin local_ipc and immutable false hardware-
verification/movement flags, with no simulation member. local_ipc describes only
transport; fixture input is always explicitly simulated elsewhere. Append native
depthReading/depthRow primitives, preserving existing simulation gates/indices.
Provide a dedicated Depth library/read-only example in MicroDuck editor packages,
and a labelled private fixture using the normal gateway and fake source protocol.

Acceptance: source-backed geometry/status/time semantics; strict config/selectors,
normal gateway capabilities/disabled routes, UID-before-write, coherent all64
zones/all8 rows with one subscription, lifetime/cancellation/bounds/errors,
actual native decoder/GC, editor packaging, full local validation and selected
real Pi ordinary/sanitizer tests with fictional input. Physical, graphical,
shipping identity/configuration and deployment acceptance remain unverified.

## Try the blocks with fictional input

On Linux with Python3.11+ and this source directory, start a fresh private lab:

```sh
python3 linux/microduck/depth_gateway_fixture.py --directory /tmp/depth-gateway-NEW
```

The printed metadata explicitly labels simulation:true and gives the normal
gateway socket. Start the current VM using its usual private program directory
and --microduck-socket set to that path. Import MicroDuck and Depth, then open
depth.ubp in the MicroDuck editor package. Capture once, check reading-known,
read any of the eight rows or individual zones/metadata, and release the capture.
Rows contain eight [status,value,unit,origin] records; only statusok is extractable.
Row/column indices are1-based and row-major, without an orientation transform.

The example prints a row, one distance, a diagnostic raw status and exact clocks.
Distance readings in mm preserve no_target versus unusable. Raw diagnostic values
can be known even when the corresponding distance is unavailable. Sensor ID/rate
are declared, not attestation or measured frequency. The metadata timestamps are
decimal strings to preserve u64 precision; at_us is sender uptime, not Unix time.
Missing t_ns or0 is not_reported. A retained frame is historical data, not current
robot safety. In this lab all input is fictional even though origin is local_ipc.

Ctrl-C closes owned sockets/subscriptions and preserves private fixture metadata.
Use a new directory for the next run. No device bus, robot, TCP listener, system
service or security/network configuration is touched. The source fixture uses
the reviewed acknowledgement/notification shapes, not a physical sensor driver.

## Explicit source configuration

After shipping inventory establishes the actual path, expected server UID and
caller permissions, use the same private version1/daemon:tofd/path/uid format as
[the head IMU adapter](HEAD_IMU_SERVICE.md). No shipping values are guessed here.
The normal gateway's existing upstreams config may be empty when a read-only
adapter is configured:

```sh
python3 linux/microduck/gateway.py --config /absolute/private/gateway.json --depth-config /absolute/private/depth.json --socket /absolute/private/gateway.sock
```

Both adapters can be configured independently, with four slots each. There is no
automatic daemon switch or permission change. The Python Client.call helper also
admits only the reviewed local head/depth wrappers, with the same strict params;
it does not forward raw tof.stream, simulation methods or arbitrary commands.
A standalone adapter/service installer is still missing. Physical, graphical,
calibration and live shipping deployment remain unverified. See the
[pinned depth source audit](tests/depth-service-source.json) for exact files/hashes.

The [tested checkpoint](../../evidence/2026-10-27/microduck-depth-service/README.md)
records396 full local tests and185 selected tests per real Pi binary, with
fictional input and initial/final recovery evidence kept separate.
