# Typed gamepad IMU batch checkpoint

Base719d2b3f06b02bc9641aeab1b11084038ca9db8e, isolated integration branch.
No shared-main/P4, service, credential, security or reboot change; nothing
published. The [four-service matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md)
now includes a concise coverage summary and the self-hosted SmallVM/editor versus
Pages deployment goal. Port80 is not presumed free; shipping IPC identities,
trusted WSS/certificates and browser network acceptance remain separate gates.

The [library/specification](../../../linux/microduck/PAD_IMU_SIMULATION.md) adds
13 typed selectors from one coherent gamepad IMU batch: raw/scaled acceleration
and gyro, exact sequence/kernel time, sample count, driver scales/full scales and
reported-limit diagnostics. Preserve every sample in the bounded1..32 batch;
component reads create no subscriptions. Four retained/in-flight slots expire
after five seconds; explicit release, cancellation and clock regression are
tested. Unknown scale, drop, detach, missing samples and overflow have no value.
No orientation, calibration, robot frame, current freshness or automatic drive.
All data/services are fixed simulations; no physical IMU or robot is accessed.

## Final acceptance

- [20 focused tests](../../../linux/microduck/tests/pad-imu-focused.txt): PASS
  in10.483s, zero skips; six actual native VM/PTY/GC cases.
- [332 required Linux tests](../../../linux/microduck/tests/pad-imu-final-linux.txt):
  PASS in203.696s, zero skips. The unchanged validator uses verified sanitizer VM
  inputs plus the existing SMALLVM_UPSTREAM override to an identical pinned
  source tree on WSL's local filesystem, held alive for the complete run.
  No compiler flag,120s deadline, test exclusion or assertion was weakened.
- [Real Pi result](../../../linux/microduck/tests/pi5-pad-imu-pi-pad-imu-validation.json):
  RPI5/fred/AArch64,124 selected tests on each ordinary and ASan/UBSan VM, zero
  skips,31 actual native VM cases each. All pad/robot/media services are fake.
  The separate Pi numeric suite and robotctl CLI were not invoked.
- [Pi sanitizer](../../../linux/microduck/tests/pi5-pad-imu-native-tests.txt) and
  [ordinary](../../../linux/microduck/tests/pi5-pad-imu-native-plain-tests.txt)
  logs, source/binary manifests, self-tests, runner and kit manifest retain the
  full cases. The verified150-file kit includes149 hash-listed payload files;
  34 repository files match the tested kit byte for byte.
- [Local native proof](../../../linux/microduck/tests/pad-imu-native-provenance.json):
  fresh pinned sanitizer build/self-test,12 current port-source hashes.
  C SHA25613d9055d92d9cef65e455d851a30b3181aac3d48e6fb94994e01d5334f718b85
  matches this binary and both Pi source manifests.
- [VM scenario](../../../linux/microduck/tests/pad-imu-scenario.json): all13 fields,
  known raw0/limitfalse, scaled1000/-500 mdps, exact high sequence strings and
  sample3 selection from one batch. Release becomes expired_or_unknown;
  unknown scale cannot be extracted; a dropped capture has no handle.
  Three explicit fake pad subscriptions in total; zero robot upstream calls.
- [Seven-profile package](../../../linux/microduck/tests/pad-imu-packaging.json):
  exact library/read-only example concatenation in MicroDuck only; six other GP
  pairs and all seven hardware flags preserved. Camera/console/BLE/security bytes
  unchanged, current notices copied and release.available false. No new Node run;
  web sources are unchanged from719d2b3, and earlier243-test proof remains separate.

| Final binary | SHA256 |
|---|---|
| Local x86_64 ASan/UBSan | 407ffaee8288728c5e6de5aa570fc726bc520c844fe040cd81fceea490a0ff48 |
| Pi AArch64 ASan/UBSan | 38f5102116ac2a771f56d5766ad0cd67abee78b062ca90d17136b654ed245a4d |
| Pi AArch64 ordinary | 1518f8119858792e8658e07b4fb65e87d0ba116a164334f51c85c018baf0e619 |

## Failures and recovery retained

The [initial focused run](../../../linux/microduck/tests/pad-imu-initial-focused-failure.txt)
had3 failures/5 errors because the fake service nested ordinary pad notification
envelopes. Correcting that fixture made the same assertions pass. The initial
full332-test run had a shared-output packaging fixture failure and an existing
120s core build timeout. The packaging assertion now uses an independent Pi
output directory; its condition is unchanged. Key-list rendering prevents an
assertion from dumping the whole embedded GP package.

The [initial full excerpt](../../../linux/microduck/tests/pad-imu-initial-linux-excerpt.txt)
keeps test/error diagnostics; its12.7MB raw capture remains outside Git. The
[retention receipt](../../../linux/microduck/tests/pad-imu-initial-excerpt-retention.json)
records raw/omitted-line hashes; only the giant packaged-source payload is shortened.
Other captures only normalize CRLF to LF, recording raw and stored hashes.

One temporary source cache vanished between WSL calls before tests began;
another tool-session run ended without a final receipt. Both are retained and
never counted as passes. Process inspection found no validator before restart.
The final temporary hidden process completed with returncode0 and all332 tests.
Its byte-identical pinned source cache stayed alive throughout the run; the
recorded tree is5699b1a910c64cf5e6ade8c89e510627383013ad at SmallVM
2071df569623ba9cdcd6f8106b61796e047df38b. The earlier read-only oversized-log
inspection was cancelled; no hardware operation or uncertain write was repeated.

Reproduce focused tests on Linux after building that pinned interpreter:

```sh
python3 linux/arm64/build.py --upstream /path/to/smallvm --output /tmp/imu-vm --sanitize --test
SMALLVM_MICRODUCK_BINARY=/tmp/imu-vm/smallvm PYTHONPATH=tests python3 -m unittest test_linux_microduck_pad_imu -v
```

The Pi selection additionally names snapshots,sensors,motion,robot and media
test modules. The full local validator also sets SMALLVM_NUMERIC_BINARY to the
verified binary and uses a Linux-local pinned source path; do not substitute a
Pi full/numeric run. The [source audit](../../../linux/microduck/tests/pad-imu-source.json)
pins Pollen API45/5def2f3e; production API44 and BLE confidentiality remain unchanged.

Dedicated head-IMU streams, native camera pixels/decoding, live relay/authentication,
physical/radio/calibration and graphical UBL acceptance remain missing or unverified.
Mediad audio is explicitly unsupported by the reviewed interface. The earlier Edge
stop was not retried. No current validation process or approval remains pending.

[Validation](../../../linux/microduck/tests/pad-imu-validation.json),
[log retention](../../../linux/microduck/tests/pad-imu-log-retention.json) and
[integrity index](../../../linux/microduck/tests/pad-imu-evidence-hashes.json)
bind this checkpoint and its recovery evidence.
