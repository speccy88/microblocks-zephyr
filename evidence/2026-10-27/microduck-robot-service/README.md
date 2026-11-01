# Normal robotd health and state checkpoint

Base f56748ce99159c98b14927f8eb1eb324ec6c74ee, isolated integration branch.
[Adapter and usage](../../../linux/microduck/ROBOT_SERVICE.md) connect actual
SmallVM jobs to normal Gateway and explicitly checked robotd IPC. Robot.ubl and
robot-read.ubp supply21 selected health fields and29 state selectors. Health/state
share four five-second retained/in-flight slots; separate captures are not one
tick. Existing raw health, simulation paths and primitive indices remain;
robotReading is appended at19.

Hello API45/version diagnostic precedes robot.health or robot.subscribe(hz1..50).
Require correlated replies and acceptedbool before one robot.state notification.
Close after completion/error/cancellation;0.5s deadline and16KiB lines, no retry,
continuous reader, model fetch, device or mutation transport. Socket owner/mode,
parent/inode and SO_PEERCRED checks establish transport consistency, never daemon
or hardware attestation. local_ipc denotes transport only.

Health preserves exact counters/age strings, fixed measurement units, optional
absence, explicit zero/false and schema defaults marked ipc_default. IMU diagnostic
precedence uses source FROZEN_RUN25. State requested/applied movement, exact
count/ns clocks, optional arrays/frames and default limit counts remain distinct.
No health/pose/convergence/default becomes freshness or movement authority.
All service input here is fictional; Pi execution does not validate a robot.

## Verification

- [24 focused tests](../../../linux/microduck/tests/robot-service-focused.txt):
  PASS in17.919s, zero skips; eight protocol, ten Unix/client/CLI/lifecycle and
  six actual native VM/PTY/GC cases. Native decoding checks source, kind, units,
  indices, scalar types, exact decimal bounds and default claims. Existing
  simulation/tofd/padd decoders refuse the new source.
- [446 full local tests](../../../linux/microduck/tests/robot-service-final-linux.txt):
  PASS in175.444s, zero skips. Unchanged validator in a private Linux filesystem
  replica. [2033 file hashes](../../../linux/microduck/tests/robot-service-linux-replica.json),
  [runner](../../../linux/microduck/tests/robot-service-full-runner.py.txt) and
  [Git receipt](../../../linux/microduck/tests/robot-service-replica-metadata.json)
  bind source/editor assets and the verified sanitizer VM/source pin. No assertion,
  exclusion, compiler flag or build deadline changed. Fixed coherence clocks do
  not change expiry/regression/cancellation assertions or production TTL.
- [Fresh Pi builds/results](../../../linux/microduck/tests/pi5-robot-service-pi-robot-service-validation.json):
  RPI5/fred/AArch64,233 tests each ordinary and ASan/UBSan, zero skips, including
  61 native adapter cases each. Both compiled anew from verified sources, passed
  self-test and identify ELF machine183. Sanitizer build142.174s/test64.750s;
  ordinary build25.678s/test64.037s. All services fictional; the separate denied
  Pi numeric suite was not invoked.
- [Actual bytecode scenario](../../../linux/microduck/tests/robot-service-scenario.json):
  all21 health and29 state selector families, including vector components;
  exact large counters, requested125mm/s versus applied0, absent head frame,
  separate handles, wrong-kind/release, defaults, missing battery, empty velocity
  and legacy t_ns0. Five finite captures (two health, three subscriptions), zero
  mutation RPC. Unavailable extraction refuses. Harness verified VM exit0 and no
  ASan/UBSan diagnostics. Raw scenario VM log was removed during temporary
  cleanup; structured results and teardown receipt remain. Pi logs are retained.
- [Seven-profile package](../../../linux/microduck/tests/robot-service-packaging.json):
  exact Robot library/example/import; six other GP profile pairs and all seven
  connection flags preserved. Earlier libraries remain exact; camera/console/BLE
  security assets unchanged; release unavailable. No new Node, graphical
  compilation or deployment is claimed.

## Initial failures and recovery

The [initial focused run](../../../linux/microduck/tests/robot-service-focused-initial.txt)
ran24 tests with two failures and one error. Fixture profile was passed into a
Boolean opt-in argument; a keyword fixes startup. Windows text conversion
corrupted a UTF8 test literal, exceeding its intended128-byte boundary; Unicode
escapes now preserve it. The GC test filled nearly the heap after earlier VM
jobs; its pure-parser test now starts with a fresh heap. Actual compaction/value
assertions and source bounds remain. Native/production adapter code did not change
during recovery. Initial failure is retained separately from final passing runs.

Desktop transport disconnected after evidence collection and before final docs
could start. Reconnection inspection verified completed receipts, unchanged HEAD
and absence of the final guide/commit/bundle before resuming. Tests/source captures
were not repeated during connection recovery.

[Validation](../../../linux/microduck/tests/robot-service-validation.json) binds59
current repo inputs to the verified174-file Pi payload (175 archive files with
manifest). [Log retention](../../../linux/microduck/tests/robot-service-log-retention.json)
records raw/retained SHA-256 and CRLF-to-LF normalization only. Coverage docs and
final contract receipts were completed after tests; executable source unchanged.
[Input hashes](../../../linux/microduck/tests/robot-service-evidence-hashes.json)
bind implementation/docs/proof. [Pinned audit](../../../linux/microduck/tests/robot-service-source.json)
covers protocol, robotd, robotctl and control-loop design at API45/5def2f3e;
production API44 is unchanged.

Native C SHA-256:
00c59e3f1bd3bd4820b956a5587813edc1a3f94668acf4daf8c02beedeb13849.
Local sanitizer binary:
f870f0e1d25a4ae952242da114a255445a73bf6847cab1ade8069ce0ee3e6390.
Pi sanitizer binary:
5166705c3d274aa1df0591a0881ac9dd52f8c5a09e860234e4b17580bb4a360a.
Pi ordinary binary:
95a2630096f3fd68bf016333aba811800e6b4ec1a2a308575c457963bff2fc16.

## Remaining gates

Physical readings, shipping revision/socket/UID/caller commissioning, continuous
freshness, calibration, graphical blocks and editor/Pages deployment remain
unverified. Selected health coverage omits CPU throttle, hottest joint and missing
servo IDs. Composite robotctl version/health reads other services/files and is not
implemented by this adapter. Normal pad IMU routing, native camera pixels/decoding,
live media/session identity and unsupported mediad audio remain separate gaps in
the [capability matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md) and
[remaining ledger](../../../docs/MICRODUCK_REMAINING_OBJECTIVES.md).

No physical movement, P4 checkout/board, shared main, credential/security/service/
network/startup change, reboot, denied retry or publication occurred. No approval
or current test operation pending. Historical UI sessions were not revalidated.
Shipping port80 is not presumed free; Caddy remains untouched.
