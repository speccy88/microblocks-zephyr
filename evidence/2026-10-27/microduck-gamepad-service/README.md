# Normal gateway gamepad observation checkpoint

Base eff609fe01384aa72aeda80d394ece93b5fba42e, isolated integration branch.
[Gamepad adapter and usage](../../../linux/microduck/GAMEPAD_SERVICE.md) connect
actual SmallVM jobs to normal Gateway, an explicit private padd socket/UID and a
finite observed input window. The separate Gamepad library and read-only example
provide five input selectors, eight descriptor selectors and eleven metadata
fields. Existing primitive indices are preserved; gamepadReading is appended at18.

The source-reviewed pad.input request comes first without hello. Cached Attached
value/pressed fields are ignored as observations; descriptor discovery is still
available when a quiet pad sends no frames. A successful capture means a retained
handle, never known live controls. Empty frames preserve held events. Sequence
gaps, kernel/socket drops and detach invalidate state; later clean per-control
events restore observations. Unknown values never become zero/false.

Raw axis, declared-span position, Boolean buttons and exact event/report clocks
remain distinct. Position applies no centre/deadzone/calibration; code/name/range
metadata supplies no gamepad semantic mapping. Exact u64 sequence/kernel Unix us
and signed64 inter-report us preserve precision and negative intervals. Four
five-second retained/in-flight slots, bounded0.35s/16-notification/16KiB capture,
release/expiry/cancellation and strict native decoding preserve resource limits.
Scalar reads neither resubscribe nor renew. local_ipc denotes transport only;
all gamepad and robot inputs in this checkpoint are fictional.

## Verification

- [24 focused tests](../../../linux/microduck/tests/gamepad-service-focused.txt):
  PASS in17.596s, zero skips; eight protocol, ten Unix/client/CLI and six actual
  native VM/PTY/GC tests.
- [421 full local tests](../../../linux/microduck/tests/gamepad-service-final-linux.txt):
  PASS in162.154s, zero skips. The unchanged validator ran in a private Linux
  filesystem replica; [1985 hashes](../../../linux/microduck/tests/gamepad-service-linux-replica.json)
  bind the entire supplied repository/editor assets and verified sanitizer VM.
  [Runner](../../../linux/microduck/tests/gamepad-service-full-runner.py.txt) and
  [Git metadata receipt](../../../linux/microduck/tests/gamepad-service-replica-metadata.json)
  retain the exact path. No assertion, exclusion, compiler flag, build deadline or
  production lifetime was changed. Coherence clocks were fixed from the outset;
  separate lifetime/regression/cancellation tests remain.
- [Fresh real Pi builds/results](../../../linux/microduck/tests/pi5-gamepad-service-pi-gamepad-service-validation.json):
  RPI5/fred/AArch64,209 tests each ordinary and ASan/UBSan, zero skips,55 native
  adapter cases each. Both binaries were compiled anew from the verified source
  kit, passed self-test and identify ELF machine183. ASan build140.658s/test52.559s;
  ordinary build25.123s/test51.989s. All services provide fictional input. The
  separate denied Pi numeric acceptance suite was not invoked.
- [Actual VM scenario](../../../linux/microduck/tests/gamepad-service-scenario.json):
  normal Gateway to checked fictional padd; all eleven metadata, eight discovery
  and five input selectors, exact large counters, quiet metadata-only capture,
  dropped-control refusal, release and extraction errors. Three source captures,
  zero robot RPC. Capture-ok never supplies a known unobserved control.
- [Seven-profile editor package](../../../linux/microduck/tests/gamepad-service-packaging.json):
  exact Gamepad library/example/import; six other GP profile pairs and all seven
  connection flags preserved. Camera/console/BLE assets unchanged and release
  unavailable. No new Node or graphical run is claimed.

[Validation](../../../linux/microduck/tests/gamepad-service-validation.json) binds53
current repository inputs to the verified168-file Pi payload (169 archive files
including its manifest). [Log retention](../../../linux/microduck/tests/gamepad-service-log-retention.json)
records raw and retained hashes with CRLF-to-LF normalization only. All retained
results above passed on their first run in this phase; no earlier checkpoint's
failure/recovery is presented as a new result.

Native source SHA-256:
c8fbeea07c1098d08188a23f89702726b742cb51a9f713c3d19f9f9abe4ce54f.
Local sanitizer binary:
7a231fc8663bf8ba0758239955fbf887f7bb2c6a8ac602eb555514e5243bfc4a.
Pi sanitizer binary:
c492ce1fb305861091291c3ac8029b12159ba888152edbbf993e3dacaccb843f.
Pi ordinary binary:
85ecc3c2c81b382066b7f381fd0956e69ff8a2a20bcff97ecadb61b874e1a738.
[Pinned upstream audit](../../../linux/microduck/tests/gamepad-service-source.json)
records API45/5def2f3e protocol/tap/main source facts and hashes; production API44
is unchanged. [Evidence input hashes](../../../linux/microduck/tests/gamepad-service-evidence-hashes.json)
bind implementation, documentation and retained proof. Capability/usage documentation and the validation receipt in vm-contract were
completed after tests; executable source is unchanged. The hash preflight identified
these five documentation differences before staging; they are recorded explicitly.

## Remaining gates

Physical gamepad/radio, source revision/socket/UID/caller commissioning, calibration,
continuous freshness, graphical blocks and editor/Pages shipping deployment remain
unverified. The protocol observer is usable with explicit source configuration;
no shipping values, pairing, device permissions or automatic drive are invented.
Normal pad IMU and robot telemetry routes, native camera pixels/decoding and live
media/session authentication remain separate software gaps. Mediad audio remains
explicitly unsupported by the reviewed upstream interface. See the updated
[capability matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md) and
[remaining objectives](../../../docs/MICRODUCK_REMAINING_OBJECTIVES.md).

No physical movement, P4 checkout/board, shared main, credential/security/service/
network/startup change, reboot, denied retry or publication occurred. No approval
or current test operation remains pending. Existing historical UI sessions are
not revalidated by this checkpoint.
