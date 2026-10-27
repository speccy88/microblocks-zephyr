# MicroDuck protocol implementation

Status: implemented protocol core with simulated acceptance only. No MicroDuck
hardware has been connected. No physical compatibility or secure provisioning is
claimed.

## Contract and acceptance criteria

Use the actual upstream NDJSON protocol with bounded byte reassembly, matching
request IDs, sequential acknowledged 20-byte GATT writes, subscribe-before-write,
timeouts and disconnect cleanup. Reject unknown methods and methods refused by
the upstream BLE permission table. Authenticate before protected calls; require
explicit confirmation for mutations. Never log or persist PINs or Wi-Fi keys.

Acceptance uses mock GATT/JSON-RPC devices: fragmentation including UTF-8,
coalescing, malformed/oversized replies, request matching, authentication,
timeouts, disconnects, permissions and refused secret transmission. A mock result
does not prove radio interoperability, pairing security, motor safety or browser
support on physical hardware.

## Pinned source

Reviewed Pollen Robotics MicroDuck commit
`96b89d8613f06722c1d64ce75ab0d7124fed9d8f`, API version 44:

- [GATT UUIDs](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duck-ble/src/gatt.rs)
- [Framing](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duck-ble/src/framing.rs)
- [BLE permission table](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/btd/src/route.rs)
- [Authentication](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/btd/src/session.rs)
- [Security default](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/btd/src/main.rs)
- [CLI sequencing](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duckctl/src/main.rs)

The service UUID is `6f5d2a10-3b47-4c8e-9a1f-2d7e8c4b6019`.
The single read/write/notify RPC characteristic is
`6f5d2a11-3b47-4c8e-9a1f-2d7e8c4b6019`. Read its API-version byte first,
subscribe, then authenticate. Requests are capped at 8 KiB and client reply
reassembly at 64 KiB. Frames end with newline; no binary length header exists.

## Confidentiality blocker

At the pinned commit, `btd --require-pairing` is **off by default**. Upstream's
`route.rs` explicitly records that the PIN and Wi-Fi passphrase can cross in
cleartext. The GATT read or successful application PIN authentication does not
prove encryption. Even the optional just-works bond lacks MITM authentication.

Web Bluetooth does not provide this client an encryption-attestation API. Its
transport therefore exposes immutable `confidential: false`. The client refuses
to send `system.authenticate` or `net.connect` through it. No checkbox overrides
this. Discovery, API-version read and `hello` can run; protected commands remain
blocked. Provision Wi-Fi using the robot's trusted local console until the
upstream configuration and transport can establish confidentiality. An injected
confidential transport exists for deterministic mocks and a future separately
reviewed secure bridge; callers must not label an ordinary BLE link confidential.

## Integration

Load `commands.js`, `rpc.js`, then `bluetooth.js` in that order. Each is also a
CommonJS module for Node tests. `MicroDuckBluetooth.connect()` must be called
from an explicit user gesture. It opens the browser's service-filtered chooser,
checks read/write/notify properties, reads the API version and subscribes before
creating the RPC client. It never opens a port or requests a device automatically.
An API mismatch is reported as metadata, not silently treated as compatibility.

`RpcClient.request(method, params, {confirmed: true})` only forwards the local
allowlist. `confirmed: true` is required for mutations and must come from a
concrete UI confirmation. There are no automatic retries. A timeout, abort,
malformed reply or partial write failure closes the session because remote
execution may already have happened. Reconnect creates a fresh unauthenticated
client. It does not replay commands.

An early response does not release stream ownership or resolve the request until
the final acknowledged write completes. This prevents a caller chaining its next
request from overlapping ATT operations. The timeout and abort remain active
while that acknowledgement is pending. Each transient write chunk is cleared
after acknowledgement or write failure; the original encoded request is also
cleared on completion or session closure.

The application must render robot-supplied strings as text. This module does
not use storage, URLs or console logging for credentials; JavaScript strings
cannot be reliably zeroed from memory and should remain transient form values.

## Command compatibility

All forwarded commands below are permitted by the pinned upstream BLE table.
All protected commands are currently blocked on real Web Bluetooth by the
confidentiality prerequisite to authentication. Fixtures exercise their wire
behavior only.

| Surface | Implemented subset | Client control |
|---|---|---|
| Discovery/version | service chooser, characteristic read, `hello` | user gesture; no PIN |
| Identity/network reads | `system.info`, `system.services`, `system.logs`, `net.status`, `net.scan` | authentication |
| Monitoring/discovery | `robot.health`, `robot.policies`, `robot.skills`, `robot.model`, `robot.vetbook`, `pad.status`, `pad.bindings` | authentication |
| Updates | `update.check`, `update.status`, `update.log`, `update.show`, `update.listInstalled`, `update.subscribe` | authentication |
| Configuration | `system.setName`, `net.connect`, `net.forget` | authentication + confirmation; confidential transport for secrets |
| Robot actions | `robot.sound`, `robot.init`, `robot.enable`, `robot.do` | authentication + confirmation; discover skill names first |
| Update changes | `update.apply`, `update.rollback`, `update.select` | authentication + confirmation; no force/local-directory options |
| Continuous control/camera | not forwarded | upstream BLE refuses; use separately reviewed WebRTC/local IPC |
| Reset/PIN access | not forwarded | upstream BLE refuses |
| Other upstream methods | not forwarded | not implemented; deny by default |

There is no BLE e-stop button: upstream refuses `robot.stop`, and an unreliable
radio must not be presented as an emergency stop. The robot daemon retains its
own control loop and safety rules. Policy installation/editing, gamepad pairing,
account login and raw sensor streaming are not implemented here.

## Hardware validation still required

The [standalone protected console](../linux/microduck/CONSOLE.md) wraps this
existing client with strict bounded JSON preparation, one-use confirmations,
current skill discovery, explicit unknown outcomes and ephemeral redacted text.
It excludes `update.subscribe` and all secret methods from the raw editor;
credentials have a separate confidential-only path. Its Web Bluetooth client
remains confidential:false, so real protected operations stay blocked. The
in-memory fixture and mock-DOM tests are separate from real robot acceptance.

Verify shipping firmware identity/API version, secure provisioning design,
desktop Chrome/Edge chooser and GATT behavior, notifications across MTUs,
authentication and reconnect, actual command refusals, health/battery fields,
discovered skills, supported sounds and robot safety behavior. Do not execute
movement until an operator is present and confirms the specific action.

## Reproducing simulated checks

Run `node --test tests/test_microduck_protocol.cjs` from the repository root.
The test uses explicit in-memory GATT and JSON-RPC fixtures; it never connects
to a robot, opens a serial device or requests Bluetooth permission. The initial
20 tests plus 3 acknowledgement-ordering regressions passed on 2026-10-27 using
Node on Windows. The repository-wide
`python tools/validate.py` must also be run with LF source bytes; Windows Git
`core.autocrlf=true` changes pinned source hashes and fails provenance checks.
