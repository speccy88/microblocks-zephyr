# Tofd head IMU typed snapshot checkpoint

Base76f5b65f8ad32b61c9e1ab3d9cf14863b739dc11, isolated integration branch.
No main/P4, service, networking, credential, security or reboot change;
nothing published. The [capability matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md)
keeps the self-hosted SmallVM/editor or Pages goal and port80/WSS/shipping gates.

[Nine typed selector families](../../../linux/microduck/HEAD_IMU_SIMULATION.md)
read one immutable tofd head_imu.frame: gyro, acceleration, quaternion wxyz,
reported cached temperature, exact u64 sequence/uptime/monotonic clocks, sensor
and declared rate. Scalar reads create no subscriptions. Four retained/in-flight
slots expire after five seconds; missing/zero/degenerate/legacy-clock distinctions,
range checks, release, cancellation and clock regression are explicit.

The existing VM/private gateway supports this finite capture without a new
connection architecture. A reusable reader checks the explicit socket/peer UID,
sends head_imu.stream first without hello, correlates its acknowledgement and
closes after one frame. Blocks use only a fixed private fake tofd. Production
routing and shipping identity/permissions remain uncommissioned.

## Verified results

- [20 focused tests](../../../linux/microduck/tests/head-imu-focused.txt): PASS
  in10.954s, six native interpreter/PTY/GC cases, zero skips.
- [353 full local tests](../../../linux/microduck/tests/head-imu-final-linux.txt):
  PASS in231.706s, zero skips, including all20 prior gamepad IMU regressions.
  The unchanged validator used the verified x86_64 sanitizer binary and existing
  source override to a byte-identical pinned tree held alive on WSL's filesystem.
  No flags, assertions, exclusions or deadlines were weakened.
- [Real Pi results](../../../linux/microduck/tests/pi5-head-imu-pi-head-imu-validation.json):
  RPI5/fred/AArch64;144 selected tests on each ordinary and ASan/UBSan build,
  zero skips,37 native adapter cases per build. Source/binary manifests, self-tests,
  runner, kit manifest and logs are retained. The Pi numeric suite was not invoked.
- [Scenario](../../../linux/microduck/tests/head-imu-scenario.json): actual VM
  reads all nine fields, exact clocks and signed vector components, then refuses
  unavailable extraction and expired handles. Five fake tofd subscriptions,
  no robot RPC and no component-read subscription. The scenario clock is fixed;
  real expiry/regression is covered by the Unix tests.
- [Seven-profile package](../../../linux/microduck/tests/head-imu-packaging.json):
  exact new library/example bytes and import; six other GP pairs and all seven
  connection flags unchanged. Camera/console/BLE assets unchanged, release false.
  No new Node or graphical run is claimed.

All sensor/robot input is simulated; native execution occurred on the real Pi.
No physical head IMU, robot, motion, camera, bus or live daemon was accessed.
The [initial focused run](../../../linux/microduck/tests/head-imu-initial-focused.txt)
had two test-harness errors: a nonexistent Simulator.calls attribute. An actual
result-call recorder replaced that attribute; the same no-RPC assertions pass.
No VM/backend correction was needed. Raw/retained hashes and LF-only normalization
are in [retention](../../../linux/microduck/tests/head-imu-log-retention.json).

## Source and limits

[Pinned source audit](../../../linux/microduck/tests/head-imu-source.json) records
API45/5def2f3e facts and file hashes. Production API44 remains unchanged.
Tofd's BMI088 reports tilted sensor axes. Beta robotd rotates vectors/quaternion
into head axes despite the shared protocol's sensor-axis description. Beta routing,
mount and frame mapping are deferred; no automatic fallback or invented transform.
Acceleration includes gravity, quaternion yaw is arbitrary, reported temperature
can be cached/startup0 and rate is declared. None proves freshness or readiness.

[Validation receipt](../../../linux/microduck/tests/head-imu-validation.json)
binds38 current repository files to the verified153-file Pi payload (154 archive
files including manifest). The [input hash index](../../../linux/microduck/tests/head-imu-evidence-hashes.json)
binds this checkpoint. Native C SHA-256:
cb2251a877833fe3b4a18b31dbd579420a0797dfcf4259485bece897c6e6f449.

Remaining: shipping/live identity and permissions, beta semantics, continuous
freshness/calibration, physical and graphical acceptance; native camera pixels,
live media/relay/session transport, an actual mediad audio interface, secure
shipping editor/Pages deployment and coordinated integration/publication.
No approval is pending and no denied action was retried.
