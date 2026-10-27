# Protected browser console contract

The standalone console uses the existing reviewed API44 command table and real
RpcClient. It attaches only an existing client, or an explicitly in-memory
fixture. It never opens a network URL, SSH, Unix socket or bridge. Its only real
transport chooser is the existing Web Bluetooth implementation, opened by an
explicit button. That transport remains immutable confidential:false; actual
authentication/provisioning stays blocked. No actual robot is used in tests.

API source is Pollen commit96b89d8613f06722c1d64ce75ab0d7124fed9d8f:
`duck-ipc-proto/src/lib.rs`, `btd/src/route.rs` and `btd/src/session.rs`.
No newly invented method is allowed. Streaming update.subscribe uses a separate
[bounded read-only watch](UPDATES.md), outside the raw request editor. Arbitrary
methods, direct motors/teleop, reboot/reset, PIN management and transport/security
changes are outside this console. Update mutations are requests to the existing daemon;
no download, install or rollback is actually performed in simulation.

## Core interface (console-core.js)

Export `Controller`, `parseParams`, `METHODS`, `FIXTURE_PIN`='000000',
`FIXTURE_SSID`='SIMULATION-NET-OPEN', `EXAMPLES`, `describe` and `safeCode`.
`METHODS` is the frozen list of27 raw-console methods. The two credential
methods have separate structured paths; streaming has a dedicated watch. Methods:

- `attach(client,{apiVersion,simulation=false})`: exact RpcClient, API44 only,
  no I/O; replaces/closes the old session and invalidates all state. The core
  reads client.transport.confidential, never overrides it.
- `detach()`, `invalidate()`, `cancel()`, `snapshot()`.
- `authenticate(pin)`: requires confidentiality, no automatic retry. Simulation
  accepts only the public fixture PIN. Never stores/logs credentials. Result
  exposes only authentication Boolean and bounded attempts_remaining.
- `preview(method,paramsText='{}')`: parse a bounded strict JSON object; rejects
  duplicate keys, unsafe/unknown methods, streaming and secret methods/fields.
  Returns a frozen one-shot preview `{id,method,paramsPreview,mutation,motion,
  simulation}` with private copied normalized parameters. Protected calls require
  authentication. hello is pinned to API44. No request is sent while preparing.
- `previewProvisioning({ssid,psk})`: separate structured path, confidential and
  authenticated only. Preview redacts PSK. Simulation accepts only its fixed open
  SSID, no PSK; a real credential form is never shown for real Web Bluetooth.
- `execute(preview,{confirmed=false})`: accepts only the current exact preview,
  consumes it before I/O, and requires confirmed:true for every mutation. Returns
  `{method,result,simulation,outcome:'completed'}`. Robot.do needs previously
  discovered skill names and rechecks robot.policies immediately before sending;
  removed skills are refused, never guessed. No retry or replay.

Snapshot exposes only phase, busy, apiVersion, confidential, authenticated,
simulation, advertised skills, current redacted preview and at most32 audit
entries `{sequence,method,outcome,code,simulation}`. It never contains raw params,
PIN, PSK or result payloads. Authentication, preparation, editing, refresh,
session replacement and disconnect invalidate prior confirmation state. Stale
asynchronous completion cannot update a replacement session. Cancellation closes
the RPC client; accepted remote operations cannot be undone.

Well-formed remote errors are rejected; failure after sending is conservatively
unknown. Preflight refusal is not_sent. Unknown outcomes require inspection,
not automatic retry. Audit diagnostics expose fixed codes, never remote text.
Results are bounded ephemeral text rendered with textContent. Known sensitive
keys/active provisioning secret are redacted; arbitrary daemon log strings may
still contain sensitive data and must not be persisted/exported automatically.
Raw parameters are limited to4096 UTF-8 bytes, depth16,1024 values,128 members
per object and256 array entries. The RPC frame still has its existing8192-byte
bound. Preview text escapes directional format controls explicitly. Numeric
IDs, sequential acknowledged writes, reply matching and deadlines remain owned
by the existing RpcClient. No lower transport permission is overridden.

## UI (console-panel.js / console.html)

`mount(container,options={})` creates the core internally and returns
`{element,controller,attach(client,metadata),detach(),destroy()}`. Optional
`options.bluetooth` is a chooser provider for deterministic tests;
`options.lifecycleTarget` defaults to the browser window. Production connection
uses the existing Bluetooth module, API44 check, no automatic hello/auth/read.
`Use in-memory simulation` is explicit and labels every status/result as fictional.

The panel provides method dropdown, JSON parameter editor, Prepare/Review,
specific confirmation checkbox, Execute, Cancel and ephemeral result/audit areas.
Changing method/params consumes staged confirmation immediately. Secret methods
are absent from the raw console. Skills have discovered choices, no free-form
movement names. Rename/forget/sound/init/enable/update methods use the same
review-and-confirm path. No controls claim emergency-stop semantics.

Simulation authentication is a fixed-fixture button, not a PIN input. Its network
form chooses only the fictional open SSID and has no password input. A separately
attached confidential non-simulation client may show transient password fields;
clear them on submit/error/teardown and never copy them into preview/audit. With
the real BLE transport those forms do not exist and a confidentiality explanation
is visible. No user can turn off this gate with a checkbox or endpoint option.
The controller reads a client flag; it cannot attest encryption by itself. A
host supplying a future confidential client must separately establish that
guarantee. The standalone page has no bridge/URL input and CSP connect-src none.
It does not implement a confidential replacement for current Web Bluetooth.

## Fixture and acceptance

`console-fixture.js` exports `createFixture({timeoutMs=10000}={})` returning
`{client,apiVersion:44,simulation:true,snapshot(),advanceUpdate(),close()}`. It allocates the only
transport internally (no caller transport/URL), uses actual NDJSON framing/IDs
and acknowledged writes, and accepts only fixture credentials/network names.
All identity/health/services/logs/policies/update states and actions are explicitly
fictional. Enforce bounded requests/actions/history. No actual daemon, network,
BLE, download, update or movement is contacted/performed.
advanceUpdate accepts no progress payload: it advances only the fixed fictional
sequence during an active watch, capped at 128 samples. It cannot inject a
transport or arbitrary daemon data. The snapshot labels observation explicitly.

Tests must exercise actual core/RPC/panel logic with mocks: strict JSON, denied
methods/secrets, immutable false-confidential BLE, unauthenticated calls, API skew,
one-shot confirmations and edited/stale tokens, latest skill discovery, updates,
provisioning redaction/cleanup, timeout/cancel/disconnect/no-replay, DOM text-only
rendering and bounds. Use Node/mock DOM independently of unavailable Edge native
control. Graphical browser acceptance remains a distinct unverified gate.

## Try the isolated implementation

Build the portal from the pinned local GP asset cache, serve that generated
folder on loopback, and open `/microduck/console.html`. The MicroDuck discovery
card also links to it. The packaged page reuses `/portal.css`; it is intended
to run from the generated portal tree rather than directly from the source
directory. No action happens until an explicit connection choice and request.

Choose **Use in-memory simulation**, then **Authenticate fixed fictional
fixture**. Select a read method, Prepare/Review and Execute. For a mutation,
review its exact parameters and check its specific confirmation first. For a
skill, first execute `robot.policies`, then choose one advertised fixture skill.
The controller rechecks policies before dispatch and refuses removed names.
Renaming, forgetting the fake network, sounds, init/enable and update changes
all use the same one-use confirmation path. They only update fictional fixture
state. The network form offers the fixed open demo SSID and no password field.

For read-only progress, choose **Watch update progress** after authenticating.
It clears the staged mutation confirmation, sends only update.subscribe and
occupies this session until stopped or bounded. The first write acknowledgements
do not attest server acceptance. The console retains eight typed samples without
arbitrary daemon detail strings, for at most 60 seconds or 128 notifications.
**Advance fictional progress sample** exists only in the fixture and performs
no update. Idle and 100 percent are not success or health signals.
**Stop watching and disconnect** closes observation; accepted updater operations
continue independently. Reconnect and authenticate explicitly for another request.

Clear review/results locally when finished, or Disconnect. Timeout, cancel or
transport loss may leave an unknown outcome; the interface retains inspection
guidance across edits/replacement. There is no automatic retry. Neither Cancel
nor a local disconnect is an emergency stop or rollback.

```sh
node --test tests/test_microduck_console_core.cjs tests/test_microduck_console_fixture.cjs tests/test_microduck_console_panel.cjs
```

The48 new tests cover actual core/RPC/panel logic, mock DOM/GATT, all27 raw
methods plus the two structured paths, fixture bounds and faults. The selected
browser/portal/protocol suite passes139 tests. The repository Linux validator
passes181 tests with zero skips. [Console validation](tests/console-validation.json)
records scope, hashes and a reproducible fictional scenario; no actual robot,
software update, Bluetooth chooser, Edge control or network connection was used.
Real confidentiality, hardware behavior, graphical browser acceptance and
published Pages behavior remain unverified. The earlier Edge-control approval
expired. Fred later requested one fresh attempt, which the platform stopped
because it could not determine the current browser URL confidently enough to
enforce policy. No input or bypass followed that stop.
