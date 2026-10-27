# Normal gateway tofd head IMU checkpoint

Base ae86fcd2e7925c027c618e15237278217a5d0130, isolated integration branch.
The foundational missing connection was simulation-only typed routes: ordinary
Gateway could not connect these blocks to an explicitly configured tofd source.

[The new read-only adapter](../../../linux/microduck/HEAD_IMU_SERVICE.md) connects
actual native SmallVM jobs to normal Gateway, the checked finite Unix reader and
one source-shaped head_imu.frame. A private explicit path/expected-UID config
enables three local adapter methods. No auto-discovery, daemon fallback, arbitrary
forwarding, permission/service/network change or physical movement is added.

Head_IMU.ubl supplies nine typed selector families and a read-only example in the
MicroDuck editor package. The separate simulation library remains. New primitive
headImuReading is appended at index15; earlier indices and simulation decoder
requirements are preserved. Its origin local_ipc means transport only, never
physical sensor identity or hardware validation. Fake tofd input also produces
local_ipc; fixture metadata and every test receipt explicitly label it simulated.

## Verification

- [19 focused tests](../../../linux/microduck/tests/head-service-focused.txt):
  PASS in7.174s, zero skips. Config schema/permissions, UID rejection before write,
  normal gateway and fixture CLI, disabled routes, cancellation, expiry, typed
  marker separation, bounds and actual VM moving GC.
- [373 full local tests](../../../linux/microduck/tests/head-service-final-linux.txt):
  PASS in246.917s, zero skips. Includes legacy gateway and all sensor/IMU/telemetry
  regressions. Unchanged validator, verified x86_64 sanitizer VM and byte-identical
  pinned source override held alive locally; no weakened flags/assertions/deadlines.
- [Real Pi results](../../../linux/microduck/tests/pi5-head-service-pi-head-service-validation.json):
  RPI5/fred/AArch64,163 selected tests per ordinary and ASan/UBSan build, zero skips,
  43 native adapter cases per build. All service input is fictional. No separate
  Pi numeric acceptance suite or actual robot daemon/command was invoked.
- [End-to-end scenario](../../../linux/microduck/tests/head-service-scenario.json):
  SmallVM bytecode/PTY -> normal Gateway -> explicit checked reader -> fictional
  tofd. Nine typed fields, exact monotonic timestamp, signed/scaled vectors,
  immutable capture/release, unavailable extraction refusal and no owner fallback.
  Three fake subscriptions, zero robot RPC. Fixed scenario clock is declared;
  actual cancellation/expiry behavior is tested separately.
- [Editor packaging](../../../linux/microduck/tests/head-service-packaging.json):
  exact library/example bytes and import; six other GP profile pairs and all seven
  connection flags unchanged. Existing camera/console/BLE assets unchanged,
  release unavailable. No new graphical/Node execution or publication claimed.

The [first build](../../../linux/microduck/tests/head-service-initial-build.txt)
failed because a decoder edit referenced head in telemetrySamplePrimitive. Its
placement was corrected, then a new pinned native build/self-test passed. Eight
initial Unix tests also passed before adding the user-facing fixture case. The
initial and final logs are separate; [retention hashes](../../../linux/microduck/tests/head-service-log-retention.json)
record CRLF-to-LF normalization only. No failure is represented as a pass.

The [validation receipt](../../../linux/microduck/tests/head-service-validation.json)
binds42 byte-identical current files plus one AST-identical test file to the
verified158-file Pi payload (159 archive files including manifest). The test file
had one terminal blank line removed after validation; the [normalization receipt](../../../linux/microduck/tests/head-service-eof-normalization.json)
records both hashes and proves unchanged statements/assertions. Original tested
bytes remain in the verified kit. Native C SHA-256:
3d5bd174c38eb472882b4d78ca243ecc3b88b357ef94eb050a71cab113d70fe9.
[Input hashes](../../../linux/microduck/tests/head-service-evidence-hashes.json)
bind implementation, docs and retained evidence. [Pinned upstream audit](../../../linux/microduck/tests/head-imu-source.json)
remains API45/5def2f3e; the production API44 pin is unchanged.

## Usability and remaining gates

The documented head_imu_gateway_fixture.py command starts fictional tofd plus
normal Gateway and prints the private VM socket, library and example. It creates
only fresh project files/sockets and leaves no running service after shutdown.
The standard gateway also accepts --head-imu-config for an inventoried source.

Shipping socket/UID/permissions, source revision and physical/calibration checks
remain open; this checkpoint did not access a real MicroDuck. Beta robotd frame
semantics conflict with shared sensor-axis docs, so routing/transform is deferred.
Continuous freshness, graphical UBL and actual editor/Pages deployment remain
unverified. Standalone adapter deployment packaging and Python convenience-client
allowlist parity remain software gaps. Depth/padd/telemetry need equivalent normal
adapter paths. Native camera pixels/live media/relay/audio gaps remain in the
[matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md).

No P4 checkout/board, shared main, credentials, existing services, networking or
security setting changed. Nothing pushed/published; no denied operation retried.
No pending approval or in-flight operation remains for this checkpoint.
