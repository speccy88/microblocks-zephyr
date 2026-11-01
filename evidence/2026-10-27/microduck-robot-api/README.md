# API45 robot block preparation: final native and Pi checkpoint

Base e74f496520271e25b40a45a00130c3ed672e7572, isolated integration branch.
Shared main, the P4 checkout/board, existing Pi services and security settings
remain unchanged. No publication, physical robot command or secret transmission.

The [specification](../../../linux/microduck/ROBOT_SIMULATION.md) adds dedicated
SIMULATION libraries for the requested robot methods and telemetry. Thirteen
mutation families produce bounded source-shaped packet previews, with backend
opt-in and per-request confirmation. They never forward a mutation; receipts say
recorded_not_executed with admission/applied unknown. Health/policies and bounded
model metadata read fixed fake services. No controller, IK or physics is supplied.

One robot.subscribe capture reads a complete state into one of four five-second
immutable snapshots. Twenty-nine typed selectors cover requested/applied move,
limits, loop, safety, joints, targets, velocities, currents, odometry, IMU, frames,
skeleton, policy and exact timestamps/counters. Records preserve zero/false,
missing values, signed31 bounds and exact u64 decimal strings. Omitted limited_by
uses the upstream empty-list default: known count0 with origin sim_default.
Explicitly received empty lists have origin simulation; absent indexed reasons
remain not_reported. No default or safety diagnostic establishes motion authority.

## Final revision evidence

- [24 focused robot tests](../../../linux/microduck/tests/robot-default-focused.txt):
  PASS in9.876s, zero skips; six cases execute actual native VM bytecode/PTY.
- [292 required local Linux tests](../../../linux/microduck/tests/robot-final-linux.txt):
  PASS in176.281s, zero skips. Unchanged tools/validate.py discovery uses documented,
  hash-verified external sanitizer VM inputs; no exclusions or deadline changes.
- [Real Pi result](../../../linux/microduck/tests/pi5-robot-final-pi-robot-validation.json):
  RPI5/fred/AArch64,86 tests on each ordinary and ASan/UBSan VM, zero skips,
  including19 native VM cases per variant. Actual bytecode, moving GC, PTY and
  private Unix sockets run on the Pi; all robotd/tofd/padd services/data are fake.
  No robotctl, Pi numeric acceptance suite, service installation or reboot.
- [Sanitizer Pi log](../../../linux/microduck/tests/pi5-robot-final-native-tests.txt)
  and [ordinary Pi log](../../../linux/microduck/tests/pi5-robot-final-native-plain-tests.txt)
  retain all cases. Source/binary manifests, self-tests, kit manifest and runner
  are alongside them. The final uploaded kit contains142 files including its
  manifest;141 payload files are hash-listed. Twenty-six current repository files
  are also bound directly to that kit in the validation receipt.
- [Local native proof](../../../linux/microduck/tests/robot-final-native-provenance.json):
  fresh pinned x86_64 ASan/UBSan build and self-test;12 current port-source hashes.
  microduck.c SHA256 is
  76d36ee8e90ccb3c9bb341c4c71806d0ab09f972aa237b089bb3e3d4893fa50d,
  matching both final Pi source manifests.
- [Final scenario](../../../linux/microduck/tests/robot-final-scenario.json):
  unconfirmed preview refused before I/O; confirmed head/move packets retained
  only in an internal audit, zero mutations forwarded. Twelve typed examples
  distinguish requested125 from applied0 and preserve the exact timestamp.
  A second fake capture verifies omitted limit count as [ok,0,count,sim_default].
  Two additional fake depth/pad streams and uncalibrated model metadata complete
  the VM scenario. Applied physical motion remains unknown.
- [243 Node tests](../../../linux/microduck/tests/robot-node.txt): PASS, zero skips.
  This run precedes the last native/Python default correction; no browser source
  changes afterward. It is mock module acceptance, not graphical/physical proof.
- [Final seven-profile package](../../../linux/microduck/tests/robot-final-packaging.json):
  exact two new library bytes and the read-only example/library concatenation
  embedded in MicroDuck. Six other GP pairs and all seven connection flags are
  unchanged. Existing camera/console/security assets are unchanged, current
  notices are copied and release.available remains false.

Final binary SHA256 values:

| Build | SHA256 |
|---|---|
| Local x86_64 ASan/UBSan | f166ab8618d7e0a9f92f4fff7457d1eb9875753ee0e438a38eb7b173d0db156c |
| Pi AArch64 ASan/UBSan | 11cd9376d159896d1f9014c80f8733fc1113542941aca84821098a89f7897b1f |
| Pi AArch64 ordinary | 9c9a1ebbebba49b66ec4dc10e29e97f4bc35ff9049fc572c260fddd99d982909 |

## Earlier captures and interruption recovery

The initial revision passed292 local tests and86 tests per Pi variant before
the omitted limited_by correction. Its C hash10a869eb and binary15341f15 are
retained separately in robot-native-* and pi5-robot-initial-* evidence. They do
not prove the final revision. The final revision was rebuilt and the affected
focused/full/Pi/scenario/package checks rerun.

After the desktop interruption, existing scenario session32332 was recovered
with exit0/PASS. Final build/stage scripts and receipts had not been created;
an own-UID process probe found no final project operation. The unsupported CIM
inventory read was not retried. Work resumed only after reconciling those facts.
The final scenario has separate filenames and the new binary hash. No uncertain
hardware write, denied operation or security approval was repeated.

## Reproduction and limits

On Linux with the pinned SmallVM checkout2071df569623ba9cdcd6f8106b61796e047df38b:

```sh
python3 linux/arm64/build.py --upstream /path/to/smallvm --output /tmp/robot-vm --sanitize --test
SMALLVM_MICRODUCK_BINARY=/tmp/robot-vm/smallvm PYTHONPATH=tests python3 -m unittest \
  test_linux_microduck_snapshots test_linux_microduck_sensors \
  test_linux_microduck_motion test_linux_microduck_robot -v
```

Use a fresh output directory and omit --sanitize for the ordinary build.
The local full run additionally sets the documented SMALLVM_NUMERIC_BINARY to
the same verified sanitizer binary and runs python3 tools/validate.py. That full
command is local evidence only; the Pi run uses the four named fake-service
suites above. The Node command is the explicit fourteen-file workflow selection.
Packaging uses tools/package_pages.py with the pinned local ide-source directory.

The [source audit](../../../linux/microduck/tests/snapshot-upstream-review.json)
pins the user's protocol, robotd design and robotctl implementations to
API45/5def2f3e. Its delta concerns vet-book sharing, not these control/state
types. Production API44 and immutable BLE confidential:false remain unchanged.
The [API mapping](../../../docs/MICRODUCK_ROBOT_API.md),
[four-service matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md) and
[remaining objectives](../../../docs/MICRODUCK_REMAINING_OBJECTIVES.md) identify
live transport, continuous freshness, native camera/audio/relay, calibrated
geometry and partial composite CLI diagnostics still missing or unverified.

Physical MicroDuck and graphical UBL compilation/execution remain unverified.
The earlier Edge URL-policy stop remains isolated. Hosted CI, service startup,
reboot and coordinated release/Pages publication are not claimed. No approval
is pending for this completed checkpoint.

[Validation](../../../linux/microduck/tests/robot-validation.json),
[log retention](../../../linux/microduck/tests/robot-log-retention.json) and
[integrity index](../../../linux/microduck/tests/robot-evidence-hashes.json)
bind the sources and captures. Logs normalize CRLF to LF until stable, retaining
both raw and stored hashes; no diagnostic or assertion was removed.
