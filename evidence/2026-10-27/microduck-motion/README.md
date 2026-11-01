# Bounded MicroDuck motion simulation: local acceptance

Base 97a5a26058fde0316c4cce49ca43da831450f382 on the isolated integration branch.
No shared main, P4 checkout, publication, credential, reboot or security change.

The [contract](../../../linux/microduck/MOTION_SIMULATION.md) supplies a separate
native library and a private simulation backend. Integer client limits,
explicit simulation opt-in and per-request confirmation gate finite leases.
An internal recorder receives source-shaped robot.move notifications. It never
opens robotd, motor buses, WebRTC or real motion. Applied movement remains unknown.

- [23 focused tests](../../../linux/microduck/tests/motion-focused.txt): PASS,
  zero skips. Four cases execute real bytecode through the current native VM,
  PTY and private Unix gateway. Bounds and confirmation fail before I/O;
  an ordinary gateway rejects the local simulation wrappers.
- [227 full Linux repository tests](../../../linux/microduck/tests/motion-linux.txt):
  PASS in 125.938 seconds, zero skips. Full unchanged tools/validate.py discovery
  uses the documented SMALLVM_MICRODUCK_BINARY and SMALLVM_NUMERIC_BINARY inputs,
  both naming the newly built provenance-verified ASan/UBSan x86_64 VM.
  No suite, assertion or deadline was removed or increased.
- [243 selected Node tests](../../../linux/microduck/tests/motion-node.txt): PASS,
  zero skips. Existing camera, console, BLE and update-watch tests remain.
- [Native scenario](../../../linux/microduck/tests/motion-scenario.json): actual
  current VM requests status, rejects unsafe requests before I/O, records a
  confirmed simulated lease and cancels it with one final zero notification.
  The two recorded frames remain internal; there are zero upstream calls.
- [Native provenance](../../../linux/microduck/tests/motion-native-provenance.json):
  fresh pinned SmallVM417 build and self-test in 57.632 seconds, native x86_64,
  ASan/UBSan and 12 exact current port-source hashes. Binary SHA256
  aa997f9f0743af428e2a7bdb2049355e95beee25018699e6814894dc97352bca.
  A first temporary build passed but its /tmp folder disappeared; the retained
  build was copied to project build-artifacts before WSL exited and then verified.
- [Seven-profile package receipt](../../../linux/microduck/tests/motion-packaging.json):
  the actual MicroDuck GP data contains the separate library and status-only
  example. Only that profile changes; all six other GP pairs and all seven
  hardware-connection flags match the viewer package. Release remains unavailable.
- [Pinned source audit](../../../linux/microduck/tests/motion-source.json),
  [validation receipt](../../../linux/microduck/tests/motion-validation.json) and
  [evidence hashes](../../../linux/microduck/tests/motion-evidence-hashes.json)
  bind source and captures. Captured PowerShell logs are retained with only
  CRLF-to-LF normalization, with both original and retained hashes recorded.

The first real VM probe exposed a reporter-message size limit. Replies now use
a compact last-frame summary bounded at 760 bytes, keeping full bounded history
inside the simulator. No global native string/report limit was loosened.

Graphical UBL compilation/execution, this new C revision on Pi/ARM64, live SCTP
transport, controller arbitration/physics and physical movement remain untested.
Earlier Pi evidence applies to its exact historical binary, not this revision.
No Edge-control or previously denied operation was retried. Physical hardware
is unavailable. Final binary/library pairing and publication await coordination.

Fred's expanded objective is documented in the
[four-service matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md): robotd,
mediad, tofd and padd, with dedicated blocks and remaining gaps identified.
