# Normal padd IMU checkpoint

Base7844b801edb6616b96063ce31023e6d7bcb4c085, isolated integration branch.
[Adapter and usage](../../../linux/microduck/PAD_IMU_SERVICE.md) connect actual
SmallVM jobs to normal Gateway and an explicit private padd socket/UID. Pad_IMU
library/example provides all13 existing typed batch selectors. The reviewed
parser/store now accepts a checked source/envelope hook; simulation defaults and
libraries remain. Native padImuReading is appended at20 without renumbering.

pad.input{} is first, without hello. Require independent IMU attachment before
one complete1..32-sample batch. Ordinary controls do not supply IMU data. Batch
socket loss or sequence gaps yield dropped; malformed/oversized data is refused.
Four retained/in-flight slots, five-second TTL, release/regression invalidation;
350ms/16-report/16KiB capture closes on completion/error/cancel. No continuous
reader, retry or renewal from component reads. UID/owner/mode/parent/inode checks
and SO_PEERCRED verify transport consistency, never physical identity.

Raw zero stays known; unknown driver resolution/full scale disables only derived
or limit readings. Integer conversion uses reported raw/g and raw/degree/s with
ties away from zero and explicit signed31 overflow. Sequence/kernel Unix us are
exact strings; wall-clock steps are preserved. No orientation/fusion, robot frame,
calibration, radio freshness or movement authority is inferred. local_ipc is
transport only; every sensor/robot input in this checkpoint is fictional.

## Final verification

- [18 focused tests](../../../linux/microduck/tests/pad-imu-service-focused.txt):
  PASS in16.555s, zero skips; three protocol, ten Unix/client/CLI/lifecycle and
  five actual native VM/PTY/GC cases. All selectors/components across the retained
  three-sample fixture reuse one subscription. Source/kind/unit/type/bounds gates
  and unavailable extraction remain strict.
- [465 full local tests](../../../linux/microduck/tests/pad-imu-service-final-linux.txt):
  PASS in206.872s, zero skips. Unchanged validator in a private Linux filesystem
  replica; [2081 file hashes](../../../linux/microduck/tests/pad-imu-service-linux-replica.json),
  [runner](../../../linux/microduck/tests/pad-imu-service-full-runner.py.txt) and
  [Git receipt](../../../linux/microduck/tests/pad-imu-service-replica-metadata.json)
  bind source/editor assets and verified sanitizer VM/source pin. No assertion,
  exclusion, compiler flag or build deadline changed.
- [Fresh Pi builds/results](../../../linux/microduck/tests/pi5-pad-imu-service-pi-pad-imu-service-validation.json):
  RPI5/fred/AArch64,251 tests each ordinary and ASan/UBSan, zero skips,66 native
  cases each. Both compiled anew from verified sources and passed self-test,
  ELF machine183. Sanitizer build142.102s/test75.978s; ordinary25.669s/test75.349s.
  All services fictional; the separate denied Pi numeric suite was not invoked.
- [Actual bytecode scenario](../../../linux/microduck/tests/pad-imu-service-scenario.json):
  all13 selector families/all available samples/components, exact large counters,
  negative scaling, raw zero, unknown scale, release, dropped/waiting/absent and
  oversized error paths. Six finite source captures; zero mutation RPC. Raw VM
  log retained after verified exit0/no ASan/UBSan diagnostics.
- [Seven-profile package](../../../linux/microduck/tests/pad-imu-service-packaging.json):
  exact normal Pad_IMU library/example/import; six other GP profile pairs and all
  seven connection flags preserved. Earlier libraries and camera/console/BLE
  security assets unchanged; release unavailable. No new Node, graphical
  compilation or deployment is claimed.

## Initial failure and recovery

The [initial focused run](../../../linux/microduck/tests/pad-imu-service-focused-initial.txt)
ran18 tests with one failure. A real fictional-source capture reached its350ms
deadline during a store-capacity test, leaving fewer than four successful slots;
the next capture correctly returned ok rather than busy. The pure store-lifetime
fixture now mocks its source-frame hook, isolating capacity/expiry/regression from
transport scheduling. Actual transport, pending-capacity/cancellation and native
integration tests remain. Assertions and production350ms/5s limits were not
weakened; production/native code did not change during recovery. The initial
failure is retained separately from final passing focused/full/Pi results.

[Validation](../../../linux/microduck/tests/pad-imu-service-validation.json) binds64
current repo inputs to the verified179-file Pi payload (180 archive files with
manifest). [Log retention](../../../linux/microduck/tests/pad-imu-service-log-retention.json)
records raw/retained hashes and CRLF-to-LF normalization only. Final contract and
guide receipts were completed after tests; executable source unchanged.
[Input hashes](../../../linux/microduck/tests/pad-imu-service-evidence-hashes.json)
bind implementation/docs/proof. [Pinned source audit](../../../linux/microduck/tests/pad-imu-service-source.json)
covers protocol and padd tap/main at API45/5def2f3e. Production API44 unchanged.

Native C SHA-256:
f768e16145379805481583c25e81ca250dbd66e60b2dfce97188846e92e6a6ac.
Local sanitizer binary:
695fc61a5d4ed119704eb84e4828b738816667d53bb9b4b83d06e350222c02a1.
Pi sanitizer binary:
48cb5730f0b058201eae3eb2d547b6af28245f2c2902fc2b7691350e6389a196.
Pi ordinary binary:
22387aeabb91c99041b13c07a453233496eb80f771881e5143394b1618f24d84.

## Remaining gates and read-only3.0 assessment

Physical IMU/gamepad/radio, shipping revision/socket/UID/permissions, calibration,
continuous freshness, graphical blocks and self-hosted/Pages deployment remain
unverified. Selected health gaps, native camera pixels/decoding, live media/session
identity and unsupported mediad audio remain separate objectives in the
[matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md) and
[ledger](../../../docs/MICRODUCK_REMAINING_OBJECTIVES.md).

[MicroBlocks3.0 assessment](../../../docs/MICROBLOCKS_3_MIGRATION_ASSESSMENT.md)
reviews official announcement/preview source as text. Standard libraries/projects
are promised compatible, but custom compiler registration, transport, UNO Q matrix
slot and P4 inline-renderer hooks need JS adaptations. This branch's pinned UNO Q
slot is fixed13x8; a later arbitrary-size variant is not verified here. No preview
execution, dependency/runtime upgrade, P4 code edit or new compatibility acceptance.

No physical movement, active P4 checkout/board/COM access, shared-main change,
credentials, security/network/service/startup changes, reboot, denied retry or
publication. No approval or current test operation pending. Historical UI sessions
not revalidated; Caddy/port80 settings untouched.
