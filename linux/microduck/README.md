# MicroDuck local JSON-RPC integration

Status: implemented gateway and Python client, tested with mock robot services
over real Linux Unix-domain sockets. No physical MicroDuck, daemon deployment,
locomotion, sensor, battery or sound validation has occurred. This component is
not installed or linked into the native SmallVM executable automatically.

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

## SmallVM integration boundary

No `.ubl` file is shipped yet: the current native port has no registered
`microduck` primitive namespace, so such blocks would call nonexistent primitives.
The machine-readable [VM adapter contract](vm-contract.json) describes the exact
remaining C/GP integration. The native VM must implement a bounded nonblocking
Unix socket job state machine, polled between VM slices, with copies of request
and reply bytes outside GC-managed objects while pending. A synchronous socket
read must never block the VM scheduler.

The root port must register the named primitive set and corresponding compiler
mapping without changing existing primitive indices, wire its poll hook, and
cancel local pending waits on stop/disconnect. Cancellation cannot undo an
already accepted robot action. Only after those functions are linked and tested
should the `.ubl` library expose begin/status/result/release blocks or higher-level
quack/skill/battery blocks. The Unix service and Python client are executable
now; direct SmallVM robot primitives remain **not implemented**.

## Reproducing tests and hardware gates

```text
python tests/test_linux_microduck_gateway.py
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

Before MicroDuck acceptance: verify shipping firmware/API/daemon ownership;
validate actual socket permissions without weakening them; run read-only health,
identity, policy/skill discovery and battery checks; integrate and test the VM
adapter; then separately obtain action-time operator approval for sound and
movement. Physical gait safety, real sensors, robot service recovery and actual
motion remain untested. The existing 23 BLE mock tests are separate and unchanged.
