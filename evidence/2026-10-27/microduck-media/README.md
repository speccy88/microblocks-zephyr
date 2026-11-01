# Mediad audio and relay block preparation

Base c0d4b0392bc053d7bfd5405ba88181fa2c59aed6, isolated integration branch.
Shared main and P4 checkout/board are untouched. No publication, service,
credential, security-setting or reboot change. Every robot/media service and
data value in this checkpoint is simulated; physical movement stays disabled.

The [specification and use](../../../linux/microduck/MEDIA_SIMULATION.md) supply a
separate native SIMULATION library with17 typed selectors and nine confirmed
discrete relay packet families. Source-shaped peer/sessionId/rpc messages carry
only fixed read-only media.video, media.stream params{}, robot.health and
robot.policies queries in an internal fake. Preview envelopes are retained only;
they are not sent even to a mock robot service. Admission/applied remain unknown.
Continuous intents, held wheee, subscriptions, media.stream start/stop and
credentials are refused before I/O. Separate opt-in and confirmation default off.

The [pinned source audit](../../../linux/microduck/tests/media-source.json) found
no supplied mediad audio track/microphone API: the pipeline is video-only, the
frame-stream fallback explicitly carries no audio, and main.rs treats microphone
support as future work. Audio receive/send blocks therefore return unsupported
with no extractable value. No audio RPC, waveform, mute/volume or playback result
is invented. robot.sound remains a separate robotd function.

RemoteStatus uses an internal fixture of the documented local runtime-file shape;
it is not a new remote RPC and /run/mediad is never read. Five registration states,
unknown account, exact signed64 Unix-second timestamps, u64 counters, Boolean
false and zero remain distinct. No account/peer/service destination or raw retry
reason is exposed. Registered status is not freshness or motion authorization.

## Final validation

- [18 focused tests](../../../linux/microduck/tests/media-final-focused.txt): PASS
  in9.361s, zero skips. Six execute actual native VM bytecode, PTY and moving GC.
- [311 required Linux tests](../../../linux/microduck/tests/media-final-linux.txt):
  PASS in185.907s, zero skips. Unchanged tools/validate.py discovery uses the
  current hash-verified external sanitizer VM inputs. No exclusions/deadline edits.
- [Real Pi result](../../../linux/microduck/tests/pi5-media-final-pi-media-validation.json):
  RPI5/fred/AArch64,104 selected tests per ordinary and ASan/UBSan VM, zero skips;
  25 actual native VM cases per variant. All media/relay/robot responses are fake.
  Neither robotctl nor the separate Pi numeric acceptance suite is invoked.
- [Pi sanitizer](../../../linux/microduck/tests/pi5-media-final-native-tests.txt)
  and [ordinary logs](../../../linux/microduck/tests/pi5-media-final-native-plain-tests.txt)
  retain all104 cases each. Their source/binary manifests, self-tests, runner and
  verified kit manifest are alongside them. The final kit has146 files including
  its manifest,145 hash-listed payloads;30 repository inputs match it byte for byte.
- [Native build proof](../../../linux/microduck/tests/media-final-native-provenance.json)
  binds12 current port sources to the actual x86_64 sanitizer build/self-test.
  C SHA2563a7933a400b8f5ac8579ee7685afa65c9685c66efea3b863a9dad1a89555723f
  matches both final Pi manifests.
- [Actual VM scenario](../../../linux/microduck/tests/media-final-scenario.json):
  all17 typed fields, explicit unsupported audio, known false/zero and exact
  counters, one confirmed internal init preview, and a precisely classified
  wrong-session error with extraction refused. Unconfirmed init and continuous
  move fail before I/O. Twelve fake read-only RPC exchanges, zero upstream calls.
- [Seven-profile package](../../../linux/microduck/tests/media-packaging.json):
  exact Media Simulation library and read-only example/library concatenation in
  MicroDuck only; six other GP pairs and all seven connection flags preserved.
  Camera/console/BLE/security bytes unchanged, current notices copied, release
  unavailable. No new Node run: prior243 tests at c0d4b03 remain historical proof;
  git diff confirms no web source changed. Modified GP bytes are checked separately.

| Final binary | SHA256 |
|---|---|
| Local x86_64 ASan/UBSan | 102880a461e2286a47e79542112593fa626ec25a3bdcfc60f6dcb0937a4c16d8 |
| Pi AArch64 ASan/UBSan | e632b22a73f7184b0e24432e745fc5f30b4b195b0c99572555bb8405e403772f |
| Pi AArch64 ordinary | 9d8fcb1122a3e09f020af0f560bb41f5dd3039683d3778d60e3a0fbf1407066b |

## Failure retained and corrected

The initial full311 tests and104 per Pi variant passed, but native failure tests
only required non-ok. The scenario caught that wrong-session errors were labelled
invalid and lost their unit, instead of preserving error/px. A bounded diagnostic
reproduction with the retained initial binary captured
[the exact failure](../../../linux/microduck/tests/media-scenario-initial-failure.txt).
No value was extractable in either case. The decoder now preserves error, native
assertions require exact status/value/unit/origin, and startup metadata-write
failure cleanup is also tested and fixed. Fresh final builds, focused/full/Pi
tests and the scenario pass. Initial evidence remains labelled initial and does
not establish final-source acceptance; no assertion was weakened or removed.

Consumer limits are project safeguards:32 relay attempts per rolling60 seconds,
128 per process, four gateway clients,0.5s read deadline and760-byte receipts.
No automatic reconnect/replay. The source rendezvous itself shares1200 requests
per minute with liveness; it is not a teleop or pixel transport. Fake peer/rpc
envelopes do not prove an HTTP/SSE parser, OAuth, real session or network behavior.

Real relay transport/discovery/account authentication, identity/permissions,
physical audio/robot behavior, native camera pixels/decoding and graphical UBL
remain missing or unverified. Production API44 and immutable BLE
confidential:false stay unchanged. The earlier Edge URL-policy stop was not
retried. No approval is pending and no current validation process remains.

[Validation](../../../linux/microduck/tests/media-validation.json),
[log retention](../../../linux/microduck/tests/media-log-retention.json) and
[integrity index](../../../linux/microduck/tests/media-evidence-hashes.json)
bind current sources and initial/final captures. Log cleanup is CRLF-to-LF only,
with raw/stored hashes retained. The
[four-service matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md) and
[remaining objectives](../../../docs/MICRODUCK_REMAINING_OBJECTIVES.md) retain
the unsupported and uncommissioned capabilities explicitly.
