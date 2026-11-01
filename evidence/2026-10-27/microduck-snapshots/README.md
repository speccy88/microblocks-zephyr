# Coherent sensor snapshots: native Linux and real Pi acceptance

Base361ceb9e940a8dcde643934d1b26e3d850d1b232, isolated branch. Shared main and
P4 checkout/board remain untouched. No release, Pages deployment, service,
credential or security-setting change. Physical robot movement stays disabled.

The [specification](../../../linux/microduck/SENSOR_SNAPSHOTS.md) adds a four-slot,
five-second immutable snapshot store. Depth captures read one complete8x8 frame;
all eight row reads share its handle/sequence and issue no new subscriptions.
Gamepad windows retain observed EV_ABS/EV_KEY state across empty frames, invalidate
on loss/gaps/regression/detach and leave metadata-only controls unobserved.
Source review found that padd retains its original Attached metadata; it cannot
be treated as refreshed held-state for a new subscriber. Typed records preserve
unknown/error/no-target states, Boolean false and numeric zero. Raw signed31
limits and declared-span0..1000 position are explicit, without calibration or
dead-man/robot-readiness claims. Version1.1 preserves existing JSON reporters.

- [39 focused local tests](../../../linux/microduck/tests/snapshot-final-focused.txt):
  PASS, zero skips;9 native VM cases across snapshot and legacy sensor suites.
- [267 full Linux tests](../../../linux/microduck/tests/snapshot-final-linux.txt):
  PASS in151.909s, zero skips. Full unchanged tools/validate.py discovery uses the
  documented verified external ASan/UBSan VM inputs; no exclusions/deadline edits.
- [243 selected Node tests](../../../linux/microduck/tests/snapshot-node.txt): PASS,
  zero skips. The full14-file workflow selection is retained.
- [Real Pi result](../../../linux/microduck/tests/pi5-snapshot-pi-snapshot-validation.json):
  RPI5/fred/AArch64,62 tests on each ordinary and ASan/UBSan build, zero skips,
  including13 native VM cases per build. Actual bytecode/PTY, moving GC and Unix
  sockets execute on the Pi; every MicroDuck daemon/data value remains fictional.
  The dedicated numeric acceptance suite and robotctl CLI were never invoked.
- [Pi sanitizer tests](../../../linux/microduck/tests/pi5-snapshot-native-tests.txt)
  and [ordinary tests](../../../linux/microduck/tests/pi5-snapshot-native-plain-tests.txt)
  record the full cases. Both fresh pinned builds/self-tests pass, native ELF183.
  Their manifests, source hashes, logs and uploaded kit manifest are retained.
- [Local native provenance](../../../linux/microduck/tests/snapshot-final-native-provenance.json):
  fresh ASan/UBSan x86_64 build+self-test,12 current port-source hashes. Current
  microduck.c SHA256fab1d0507e1e6305830bd4716e679f2af6b7bba05a30b0c3d26ff9253908a6cb
  matches this build and both final Pi manifests.
- [Native scenario](../../../linux/microduck/tests/snapshot-scenario.json): all8
  depth rows coherent, typed raw1583/position524/held buttontrue, release becomes
  expired_or_unknown and error envelopes remain error readings. Two fake-service
  subscriptions, zero ordinary upstream calls; no applied motion is inferred.
- [Seven-profile package](../../../linux/microduck/tests/snapshot-packaging.json):
  MicroDuck contains the1.1 library and read-only example; six other GP pairs and
  all seven hardware flags remain unchanged. Camera/console/security assets are
  unchanged and release.available isfalse.

An earlier revision already passed267 local tests and62 per Pi build. Final
hardening then added strict validation for hand-crafted mismatched ToF status/
distance and out-of-range/missing axis ranges. The final revision was freshly
rebuilt and all affected validation rerun; earlier native provenance and the
initial Pi summary remain distinct historical evidence, not final-source proof.

The user's current upstream source resolves to API45/5def2f3e; its changes concern
vet-book gallery sharing. Sensor/control/state shapes reviewed here are unchanged
from the API44 pin. The [source review](../../../linux/microduck/tests/snapshot-upstream-review.json)
and [robot methods/telemetry/CLI mapping](../../../docs/MICRODUCK_ROBOT_API.md)
record Fred's additional objectives and exact missing families. No API version,
live permission or production allowlist is silently widened.

Graphical UBL compilation/execution remains unverified because the earlier Edge
URL-policy stop remains isolated. Native execution/embedding does not prove the
graphical blocks. Real sensors/gamepad, shipping daemon permissions, continuous
freshness, calibration and robot control remain unverified. No denied action was
retried or approval left pending. Pi tests used new private home directories and
temporary fixture folders; existing services/user work remain intact.

[Validation](../../../linux/microduck/tests/snapshot-validation.json) and
[evidence hashes](../../../linux/microduck/tests/snapshot-evidence-hashes.json)
bind sources/captures. Local PowerShell logs only normalize CRLF to LF until
stable, recording original and retained hashes. No sanitizer assertion was removed.
