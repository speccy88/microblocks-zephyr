# MicroDuck local JSON-RPC integration

Status: implemented gateway and Python client, tested with mock robot services
over real Linux Unix-domain sockets. No physical MicroDuck, production daemon deployment,
locomotion, sensor, battery or sound validation has occurred. This component is
linked into the Linux ARM64 SmallVM build, but disabled unless an operator
supplies `--microduck-socket`. Tests on the real Pi use simulated robot daemons;
they do not establish physical MicroDuck compatibility.

## Source contract

Reviewed Pollen Robotics commit `96b89d8613f06722c1d64ce75ab0d7124fed9d8f`,
API 44. The actual defaults are `/run/robotd.sock`, `/run/configd.sock` and
`/run/updaterd.sock`; these are configurable daemon defaults, not assumed peer
identities. Relevant pinned sources:

- [Methods, parameters, destinations and response types](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duck-ipc-proto/src/lib.rs)
- [robotd IPC](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/robotd/src/main.rs)
- [configd peer policy](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/configd/src/main.rs)
- [updaterd peer policy](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/updater/src/ipc.rs)

`robotd` owns the controller and its 50 Hz loop. This gateway sends supported
discrete requests; it never opens motor buses, writes joints, replaces the
controller or grants itself a daemon's UID/group membership. `configd` and
`updaterd` enforce their own caller policies, which remain authoritative.
`btd` is a separate BLE transport; `system.authenticate` is answered there and
has no Unix daemon destination. `mediad` owns media/WebRTC; it is not connected
by this gateway. No Wi-Fi credentials, application PINs, account tokens,
continuous motion or camera endpoints are accepted here.

A separate [receive-only browser camera core](CAMERA.md) prepares the documented
GStreamer/WebRTC transport independently of this gateway and BLE. Its tests use
internal fake signaling, RTC and media tracks only. It exposes no motion RPC or
live endpoint in the portal and does not establish physical video playback.
The [viewer follow-up](CAMERA_VIEWER.md) adds frame-callback observation,
reported-rotation layout and an explicitly fictional standalone lab. Its fake
callbacks and drawn test card do not execute a native video decoder.

The separate [motion simulation lab](MOTION_SIMULATION.md) adds bounded native
block wrappers and an opt-in private backend. Only an internal recording service
receives API44-shaped robot.move notifications; no real movement path is added.
The ordinary gateway and BLE still deny these motion calls. The new library is
clearly named Motion Simulation and its example issues only a status read.

The separate [tofd head IMU lab](HEAD_IMU_SIMULATION.md) adds a checked finite
head_imu.stream reader and nine typed snapshot selector families, with an
explicitly simulated block gateway. This uses the existing VM connection; live
shipping socket/UID commissioning and beta frame semantics remain open. No
automatic daemon fallback, transform or movement authority is introduced.

The [normal read-only head IMU adapter](HEAD_IMU_SERVICE.md) connects the same
finite reader to explicitly configured tofd through the standard gateway and a
separate Head_IMU library. local_ipc describes transport only; shipping config
and physical/beta/graphical acceptance remain open. A labelled fixture command
exercises this normal path with fictional input and no system/network changes.

The [normal coherent depth adapter](DEPTH_SERVICE.md) adds one8x8 capture, eight
typed rows/all64 zones, raw diagnostics and seven metadata fields through checked
tofd IPC. Both head/depth wrappers are admitted by the Python convenience client.
Depth has a separate library/example and labelled normal-gateway fixture; all
current acceptance input is fictional and shipping/physical/graphical gates remain.

The [normal gamepad adapter](GAMEPAD_SERVICE.md) adds finite padd observations,
quiet-pad descriptor discovery, typed axes/buttons/span and exact timing. Attached
values remain unobserved until events arrive. Dedicated Gamepad blocks/example
and a labelled fixture use normal Gateway; physical/radio/graphical acceptance
and shipping permissions/deployment remain open. No direct evdev or robot control.

## Filesystem-only commissioning inspection

The optional [preflight](PREFLIGHT.md) inspects host and explicitly supplied
config/socket/runtime metadata. It makes no daemon connection or request,
creates no listener, changes no permission/service and never claims robot-ready.
Expected API 44 and configured/file UIDs remain distinct from unobserved daemon
API and peer identity. Its INCOMPLETE result is not authorization to act.

## Executable service

Python 3.11+ standard library only. Run unprivileged as the same OS user as
SmallVM. Supply a private current-user-owned configuration file (0600) with
exactly `version: 1` and `upstreams`. Each configured upstream is a fixed service
name (`robot`, `config`, `updater`) mapped to `path` and a **verified numeric
server UID**. Obtain those identities from the actual robot's trusted local
inventory; no UID is guessed or inferred from a username here. Services may be
configured individually, so a down or absent daemon doesn't prevent startup.

For example, the shape of one entry is
`"robot": {"path": "/run/robotd.sock", "uid": <verified numeric UID>}`.
Replace the angle-bracket placeholder before using JSON; this is not a runnable
configuration. Do not change upstream permissions to make an unknown caller
work. An OS permission error or daemon refusal is a commissioning blocker.

```text
python linux/microduck/gateway.py --socket /private/runtime/microduck.sock --config /private/config.json
```

The socket parent must already exist, be current-user-owned and private (0700).
The service binds only this Unix socket, makes it 0600, accepts only the same
UID via `SO_PEERCRED`, refuses any existing file/socket and removes only its own
socket inode on shutdown. There is no TCP listener or shell execution. Upstream
paths must be canonical, non-symlink sockets, with the configured owner and no
permissions for other users; upstream 0660 group access is respected. Both the
socket inode and connected server UID are verified. Nothing reads a password
manager, provisions SSH or modifies systemd or group membership.

The default is read-only. A mutation requires **both** an operator startup
allowlist such as `--allow-mutation robot.sound` and `"confirmed": true` in
that specific request. These are explicit operation gates, not protection from
a malicious program running as the same OS user. Movement must be enabled only
when a present operator has approved the concrete action and setup. Nothing
in startup, discovery or reconnect performs an action automatically.

## Gateway wire schema

One UTF-8 JSON object plus newline per connection, maximum 8192 bytes including
newline. One request, one terminal response, then close. No batches, notifications,
duplicate JSON keys, non-finite numbers, unknown fields or arbitrary methods.

```json
{"jsonrpc":"2.0","id":1,"method":"robot.health","params":{}}
```

IDs are integers 1..2147483647. The optional gateway member `confirmed` is a
boolean. It is stripped before forwarding, so the upstream receives its exact
official JSON-RPC envelope and parameter shape. Replies preserve the upstream
`result`; a gateway-only `gateway` member reports the selected service and actual
hello API version. API skew is reported, not silently labelled API-44 validation.
The local `microduck.capabilities` method reports this gateway's allowlist,
enabled mutation subset, limits, pinned source and observed API versions; it is
explicitly not an invented robot API.

Replies are at most 65536 bytes including newline. Limits also cover JSON depth,
node count, four concurrent clients and bounded connect/read/write deadlines.
The gateway opens a fresh checked upstream connection, sends `hello` with API
44 and ID 0, verifies its reply, then sends the requested method with the original
ID. Response IDs must match. Streaming methods are excluded. It never retries.
Errors contain fixed diagnostic text and `error.data.outcome`:

- `not_sent`: the requested action was not forwarded.
- `rejected`: a terminal upstream JSON-RPC error refused the request.
- `unknown`: a disconnect, timeout or malformed reply occurred after forwarding;
  the action may have happened. Reconnect and inspect; do not automatically retry.

No raw request, result, credential or remote error payload is logged.

## Supported subset

| Service | Read methods | Optional mutations |
|---|---|---|
| robotd | `robot.health`, `robot.policies`, `robot.skills`, `robot.model`, `robot.vetbook`, `pad.bindings` | `robot.sound`, `robot.do`, `robot.init`, `robot.enable`, `robot.loadPolicy` |
| configd | `system.info`, `system.services`, bounded `system.logs`, `net.status`, `net.scan`, `pad.status` | none |
| updaterd | `hello`, `update.status`, `update.check`, `update.log`, `update.show`, `update.listInstalled` | none |

Every skill invocation first fetches `robot.policies` and requires the requested
name in its actual `skills` list. Policy selection requires an advertised slot
and an already advertised policy path, or `null` to restore that one slot's
default. Loading arbitrary files or clearing every override is not exposed.
This is a deliberately smaller surface than all robotd Unix permissions.

`client.py` provides `Client.call`, `health`, `battery`, `quack` and
`perform_skill`. Battery fields are the actual optional `robot.health.battery`
`volts` and `percent`; absence returns `None`, never invented zero values. Raw
health includes any supported motor, IMU, thermal and control-loop fields. It
does not fabricate a universal robot-ready or sensor-value method. Its command
line reads one bounded request from stdin, avoiding payloads in process arguments.

## Native SmallVM adapter and blocks

The native [C adapter](../arm64/platform/microduck.c) implements four nonblocking
Unix-socket jobs. SmallVM polls them between bounded VM slices. Pending input
and reply bytes stay outside the moving VM heap. No synchronous socket wait,
worker thread, shell or TCP client is used. Start the real gateway first, then:

```sh
smallvm --data-dir /absolute/private/programs --microduck-socket /absolute/private/gateway.sock
```

Both gateway parent and socket must be owned by the VM user, mode 0700 and 0600
respectively. The client checks canonical paths, inode identity and Linux peer
UID before writing the first request byte. Configuration copies a path only;
`gateway configured?` does not claim a reachable or ready robot.

The `microduck` primitive set is appended at index 22 for this Linux build.
Other board indices are unchanged. The MicroDuck editor profile includes
[MicroDuck.ubl](MicroDuck.ubl), matching compiler mapping and a read-only health
example. Pi's ordinary editor retains its core-only library.

| Primitive | Behavior |
|---|---|
| `configured` | Boolean; checks explicit CLI configuration without I/O. |
| `quote` | Strict JSON quote for a VM string, before any request construction. |
| `jobs` | List of retained IDs, for recovery after a stopped script. |
| `begin` | Validated method, JSON object and confirmation Boolean to a positive job ID. |
| `status` | `pending`, `ready`, `error` or `unknown` for an existing job. |
| `result` | Terminal JSON-RPC reply string; pending is an explicit VM error. |
| `release` | Close/free one job, including an unfinished job, without retry or rollback. |

Limits: four retained jobs, 8192-byte request including newline, 65536-byte reply,
ten-second deadline, signed31 IDs 1..1073741823 without reuse within the process,
strict UTF-8/JSON, depth 16, at most 8192 values and 256 members per object. All
requests are compact NDJSON. Wrong IDs, malformed messages, transport loss and
timeouts after any sent byte produce an `unknown` outcome. Error bodies are
sanitized. Poll failures never set another VM task's global error flag.

Convenience blocks wait cooperatively, return the full reply JSON, and release
the finished job. Health, optional battery health, skills, policies and gateway
capabilities are available. Battery absence is unknown; these blocks do not
invent a universal robot-ready sensor. Sound and skill
blocks default to unconfirmed and also require the gateway operator allowlist;
skill discovery remains authoritative. Native JSON quoting protects string
parameters. Other allowed methods remain in advanced `begin` calls.

Stop All cancels pending local waits, retaining terminal error/unknown jobs for
inspection with `jobs` and explicit release. A single stopped script may leave
a retained job too. Do not blindly issue another command after an unknown
outcome. Cancellation cannot undo an accepted robot action and is not an
emergency stop. Ordinary IDE disconnect preserves autonomous VM execution;
gateway connection loss terminates its job, and VM process shutdown frees all
jobs. Jobs/results do not survive VM process restart.

Standard VM errors are: arity 28, string 14, integer 13, Boolean 12,
invalid/blocked/unconfirmed/pending 32, absent/released job 18, disabled 27, and
exhausted slots 10. See the [machine-readable contract](vm-contract.json).

Library0.2 and the new native `healthSample`/`readingValue` names add
[typed readings from a single health snapshot](TYPED_READINGS.md). The primary
blocks return `[status, value, unit, origin]`, exposing known zero/false while
keeping missing, invalid, overflow and JSON-RPC errors distinct. Fixed-point
integers carry explicit `0.01%`, `mV`, `mC` and `mHz` units. Counter and Boolean
defaults follow the pinned serde contract; no physical threshold is guessed.
Simulation replies have an explicit true marker propagated to every reading.
Unmarked data never proves a physical measurement. Extract a value only after
checking the reading; extraction refuses any non-ok status.

Health verdict and IMU convergence/missing/frozen state expose documented
diagnostics, not authorization to move. Optional sensor streams/pose and a
universal ready flag are not invented. Conversion has no I/O, freshness or
authentication claim; it only interprets the supplied snapshot. The updated
health example prints raw JSON and labelled battery/IMU readings. It requires
the new VM and library together; the earlier unpublished source candidate does
not contain these primitive names. [Typed test evidence](tests/typed-validation.json)
distinguishes native bytecode acceptance from incomplete graphical execution.

## Reproducing tests and hardware gates

To try the blocks before the robot arrives, start the explicit read-only
simulation backend in a fresh private directory, then configure the VM with
the printed gateway path:

```sh
python3 linux/microduck/simulator.py --directory /tmp/microduck-sim-UNIQUE
smallvm --data-dir /absolute/private/programs --microduck-socket /tmp/microduck-sim-UNIQUE/gateway.sock
```

It runs the real gateway and a mock API-44 robot daemon over private Unix
sockets. Health replies clearly say SIMULATION, report `healthy: false`, and
label battery/skill data as fictional. It cannot reach a real robot, open motor
buses or listen on TCP. The optional `--allow-mock-actions` flag permits only
confirmed, discovered sound/skill simulations, with a bounded private action
log. It does not enable any real action. Shutdown removes owned sockets while
retaining metadata/logs for inspection.

```text
python tests/test_linux_microduck_gateway.py
python -m unittest discover -s tests -p test_linux_microduck_vm.py -v
python tools/test_linux_microduck_native.py --upstream /path/to/smallvm-git --evidence build-artifacts/microduck-native-tests/evidence.json
```

Tests run mock official JSON-RPC daemons over real Unix sockets, with the real
OS peer-credential checks. They never connect to `/run` robot sockets, use BLE,
SSH, install a service, open physical hardware or execute movements. All fixtures
and sockets are in disposable private directories.

The 2026-10-27 WSL run passed 21/21 tests in 5.656 seconds. It covers exact API-44
handshakes and routing, optional battery fields, mutation gates, actual skill/slot
discovery, wrong IDs, malformed and oversized messages, timeouts without retries,
unknown outcomes after forwarding, socket ownership/permissions, private config,
client limits, both executable CLI entrypoints and preservation of existing files. The denied-client branch is
additionally fault-injected; normal peer checks use real Linux credentials. The
unchanged Web Bluetooth suite separately passed 23/23 tests.

The native adapter also passed ten real-interpreter/PTY tests under ASan/UBSan
on LP64 Linux and on the actual AArch64 Pi. The gateway and sockets were real;
robot daemons and adverse replies were simulated. The tests exercise moving GC
while a job is pending, concurrent VM execution, confirmation/operator gates,
slot retention, Stop All recovery and the production ten-second deadline. A
separate native harness passed 380 checks; its 40-ms test timeout and synthetic
peer/write fault providers are explicitly separate from the production deadline.

Before MicroDuck acceptance: verify shipping firmware/API/daemon ownership;
validate actual socket permissions without weakening them; run read-only health,
identity, policy/skill discovery and battery checks; then separately obtain
action-time operator approval for sound and
movement. Physical gait safety, real sensors, robot service recovery and actual
motion remain untested. The existing 23 BLE mock tests are separate and unchanged.

## Read-only sensor simulation

The additive [Sensor Simulation](SENSOR_SIMULATION.md) library supplies separate
depth-zone, raw-axis and button JSON read blocks against fixed private fake
tofd/padd streams. All values are fictional. The
[four-service matrix](../../docs/MICRODUCK_SERVICE_CAPABILITIES.md) tracks the
remaining robotd/mediad/tofd/padd block families and physical acceptance gates.
