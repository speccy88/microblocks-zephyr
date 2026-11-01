# Normal gateway coherent tofd depth checkpoint

Base ef080f147acac2f81452e732c3293f9aba2eb155, isolated integration branch.
[Depth adapter and usage](../../../linux/microduck/DEPTH_SERVICE.md) connect real
SmallVM jobs to normal Gateway, explicit checked tofd IPC and one immutable8x8
frame. Dedicated editor blocks expose all64 zones, eight coherent rows, separate
raw diagnostics and seven metadata fields. Four five-second slots per adapter;
bounded capture, release/expiry/cancellation, no background reader or movement.

Tofd receives tof.stream first without hello, then returns its acknowledgement
and tof.frame. Status5/9 plus positive mm is a range;255 means no_target; other
or nonpositive results are unusable. Missing/ragged data never becomes zero or a
range. Exact u64 clocks distinguish sender uptime from monotonic ns and preserve
legacy/missing clocks. Raw diagnostic status/distance can be known when a range
is not. local_ipc describes transport only; all input in this checkpoint is fake.

Normal Python client validation now admits the reviewed head/depth adapter
wrappers, preserving source/simulation/arbitrary/mutation restrictions. Existing
head and simulation primitive indices/gates remain; depthReading/depthRow are
appended at16/17. A labelled depth_gateway_fixture.py command supplies fictional
tofd through normal Gateway for the packaged Depth library and read-only example.

## Final verification

- [22 focused tests](../../../linux/microduck/tests/depth-service-focused.txt):
  PASS in16.063s, zero skips. Seven protocol, nine Unix/client/CLI and six actual
  native interpreter/PTY/GC cases.
- [396 full local tests](../../../linux/microduck/tests/depth-service-final-linux.txt):
  PASS in156.725s, zero skips. Full unchanged validator in a private Linux
  filesystem execution copy; [1922 file hashes](../../../linux/microduck/tests/depth-service-linux-replica.json)
  prove byte identity with the supplied source/editor assets and verified VM.
  Same pinned source tree and binary; no assertion, exclusion, compiler flag or
  build deadline changed. Production TTL/deadline remain5s/0.35s.
- [Final real Pi results](../../../linux/microduck/tests/pi5-depth-service-pi-depth-service-validation.json):
  RPI5/fred/AArch64,185 selected tests per ordinary and ASan/UBSan binary, zero
  skips,49 native adapter cases each. All sensor/robot services are fictional.
  No separate Pi numeric suite was invoked. Source, binary, self-test, runner,
  kit and execution evidence is retained.
- The [initial Pi builds](../../../linux/microduck/tests/pi5-depth-service-initial-pi-depth-service-validation.json)
  compiled on the real Pi and each passed185 tests. After a test-only clock fix,
  final suites reused those exact binaries with complete prepared-source,
  build-script, flags, ELF and SHA-256 equivalence checks. Compiled code did not
  change. Reuse is explicit in final manifests; no redundant compilation claimed.
- [Scenario](../../../linux/microduck/tests/depth-service-scenario.json): actual
  SmallVM -> normal Gateway -> checked reader -> fictional tofd, eight rows,
  seven metadata fields, one source subscription and zero robot RPC. No-target
  extraction refuses; raw status255 and negative raw distance remain diagnostics.
  Release invalidates later reads. Scenario/coherence clocks are fixed; separate
  lifetime/regression/cancellation tests retain their assertions.
- [Seven-profile package](../../../linux/microduck/tests/depth-service-packaging.json):
  exact new library/example/import; six other GP profile pairs and all seven
  connection flags unchanged. Existing camera/console/BLE assets unchanged,
  release unavailable. No graphical or new Node run is claimed.

## Initial failures and recovery

The [initial full run](../../../linux/microduck/tests/depth-service-initial-linux.txt)
ran396 tests with one failure and one error. The64-query coherence fixture read
row7/col5 after the real five-second expiry, correctly receiving expired_or_unknown.
A fixed clock now isolates coherence; the separate expiry/regression checks and
production lifetime are unchanged. The existing core compilation also exceeded
its120s limit on the Windows-backed filesystem.

The unchanged validator then ran from a byte-identical Linux filesystem copy.
First replica setup failed before tests because WSL could not resolve the Windows
worktree's C:/ gitdir. A verified local Git bundle supplied normal Linux metadata;
no source Git/security configuration was changed. [Setup diagnosis](../../../linux/microduck/tests/depth-service-replica-setup-diagnosis.json),
failed setup logs, initial/final receipts and the retained full runner distinguish
these phases. [Log hashes](../../../linux/microduck/tests/depth-service-log-retention.json)
record raw bytes and CRLF-to-LF normalization only. No initial failure is a PASS.

[Validation](../../../linux/microduck/tests/depth-service-validation.json) binds48
current repo inputs to the final verified163-file Pi payload (164 archive files
including manifest). [Input hashes](../../../linux/microduck/tests/depth-service-evidence-hashes.json)
bind the current implementation/docs/evidence. Native C SHA-256:
a539941c35c53bd690844a60908c0f02b1fe4489b69f3d5384d1a8548bb23e1c.
[Pinned upstream audit](../../../linux/microduck/tests/depth-service-source.json)
records API45/5def2f3e protocol, source clocks and Frame::zone facts. Production
API44 remains unchanged.

## Remaining gates

Shipping source revision/socket/UID/permissions, physical depth/calibration,
continuous freshness, graphical blocks and actual editor/Pages deployment remain
unverified. No map/mount transform or clear-path authority is inferred. Standalone
adapter deployment packaging, normal padd/robot telemetry adapters and media gaps
remain in the [capability matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md).
Beta head-IMU frame ambiguity is separate from this ToF path.

No P4 checkout/board, shared main, credentials, services, networking/security
settings or reboot changed. No denied operation retried or publication performed.
No approval or current test operation remains pending.
