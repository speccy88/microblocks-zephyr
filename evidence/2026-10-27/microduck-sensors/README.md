# ToF and gamepad blocks: local simulated acceptance

Base8904aa3f3bf03373af49fa869355c419d3ff86eb, isolated integration branch.
Shared main, P4 checkout/board, Edge control, SSH, credentials and security/startup
settings are unchanged. No release or deployment occurs.

The [contract and reproduction](../../../linux/microduck/SENSOR_SIMULATION.md)
define a separate Sensor Simulation library with depth-zone, raw-axis and button
JSON reporters. A real native job opens a private gateway; its adapter subscribes
to fixed fictional tofd/padd on verified Unix sockets. Requests use actual pinned
tof.stream/pad.input envelopes, not made-up Pollen methods. No live endpoint or
automatic driving exists. Results always mark simulation and physical movement
disabled, retain explicit unknown/absence/drop states and preserve timestamp
precision as decimal strings. The ordinary gateway rejects the local wrappers.

- [21 focused sensor tests](../../../linux/microduck/tests/sensor-focused.txt):
  PASS, zero skips, four actual VM/PTY/native cases. Geometry, source-derived
  zone status, raw ranges, repeat buttons, loss/absence, exact selectors, bounded
  Unix subscriptions, cancellation and CLI cleanup are exercised.
- [249 full repository Linux tests](../../../linux/microduck/tests/sensor-linux.txt):
  PASS in142.033 seconds, zero skips. Full unchanged tools/validate.py discovery
  uses documented SMALLVM_MICRODUCK_BINARY and SMALLVM_NUMERIC_BINARY, both naming
  the fresh provenance-verified ASan/UBSan VM. No exclusions or deadline increases.
- [243 selected JavaScript tests](../../../linux/microduck/tests/sensor-node.txt):
  PASS, zero skips, using the14 exact workflow paths. An initial command selected
  only201 tests because four mistyped filenames were silently ignored by Node;
  that local partial capture is preserved separately and is not full acceptance.
- [Native scenario](../../../linux/microduck/tests/sensor-scenario.json): real
  current VM bytecode reads1063mm fictional depth, raw axis1583 and a held repeat
  button; no-target and absent values stay null. Five actual fake-service stream
  subscriptions, zero ordinary upstream calls. Invalid bounds and robot.move
  fail before I/O. [VM log](../../../linux/microduck/tests/sensor-scenario-vm.txt).
- [Native provenance](../../../linux/microduck/tests/sensor-native-provenance.json):
  new pinned SmallVM417 build+self-test in67.810 seconds, ASan/UBSan, x86_64 ELF,
  all12 current port-source hashes checked. Binary SHA256
  df75b7771e3a1748d48bc14a1b0ffe67c038da0f1ab25fcec140c2a199adaf7a.
- [Actual seven-profile package](../../../linux/microduck/tests/sensor-packaging.json):
  separate sensor library and read-only example embedded in MicroDuck GP data;
  all six other GP pairs and all seven hardware flags preserved. Existing
  camera/console/commissioning/security assets unchanged; licenses copied;
  release.available remains false. No graphical execution is inferred.
- [Source audit](../../../linux/microduck/tests/sensor-source.json),
  [validation receipt](../../../linux/microduck/tests/sensor-validation.json) and
  [evidence index](../../../linux/microduck/tests/sensor-evidence-hashes.json)
  bind source, build and captures. Log normalization only replaces CRLF with LF
  until stable, recording raw and retained hashes and number of passes.

The first full run executed249 tests and failed the new package assertion:
an earlier ownership test had rebuilt the shared default output as MicroDuck.
The corrected test builds its own fresh raspberry-pi5 core output and retains
the absence assertion. This changes test isolation, not production behavior.
The [failure trace](../../../linux/microduck/tests/sensor-linux-initial-failure.txt)
and [raw hash/size](../../../linux/microduck/tests/sensor-linux-initial-failure.json)
are retained. Its12.7MB dictionary dump remains in local ignored build-artifacts,
with a truncated trace in Git. Three read-only PowerShell tail operations became
slow on that single enormous line; only those owned reader sessions were
cancelled before preserving the original file. No hardware operation was stopped.

Current native revision on Pi/ARM64, graphical UBL compilation/execution and real
MicroDuck sensor/input streams remain untested. Each depth-zone block reads a
new frame; a coherent full-grid object, held-state cache, numeric convenience,
pad/head IMU, live control and native camera/audio/relay blocks remain gaps in
the [four-service matrix](../../../docs/MICRODUCK_SERVICE_CAPABILITIES.md).
Earlier Pi tests apply to their historical binaries. Final ARM64/library pairing
and publication await coordination. No denied action was retried or approval
left pending; physical hardware remains unavailable and the prior Edge stop is
still isolated.
