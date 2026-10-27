# MicroDuck Christmas Hardware Validation Checklist

Record date, robot model/serial (exclude secrets), shipping image/API commit,
browser/OS, port commit, binary/source hashes and exact logs for each result.
Use PASS / FAIL / BLOCKED / NOT RUN. A mock response or Pi execution does not
fill in a physical robot result. All boxes below remain unchecked for hardware.

- [ ] Inventory AArch64/glibc, storage, existing services and recovery procedure.
- [ ] Compare shipping API and BLE UUID/permissions with pinned API 44.
- [ ] Record trusted daemon paths, file ownership and numeric peer UIDs.
      The optional filesystem-only preflight can check metadata but does not
      connect, verify SO_PEERCRED, observe API versions or satisfy this whole box.
- [ ] Confirm robotd/configd/updaterd caller permissions without relaxing them.
- [ ] Verify Web Bluetooth chooser, read/notify/write properties and API byte.
- [ ] Establish actual BLE confidentiality/authentication guarantees; keep PIN
      and Wi-Fi operations blocked if guarantees cannot be established.
- [ ] Configure Wi-Fi through a trusted path, verify IP and SSH host identity.
- [ ] Install reviewed binary/source release with independent hashes; self-test.
- [ ] Run real arithmetic, variables, lists, start/stop, upload and live edits.
- [ ] Verify graphics-editor connect, project restore, disconnect and reconnect.
- [ ] Verify no unintended listeners and no conflict with robot services.
- [ ] Validate read-only gateway hello/API, identity, health, optional battery,
      sensors, services, logs, skill/policy discovery and updater read methods.
- [ ] Compare units/absence semantics to real readings; keep unknown distinct
      from zero and retain actual health/error fields.
- [ ] Validate typed record units/scaling/origin against raw shipping health
      replies. Check documented defaults and optional data; unmarked is not an
      attested physical source. Confirm IMU convergence/frozen diagnostics never
      substitute for motor readiness or movement authorization.
- [ ] With an operator present, validate one permitted sound and one discovered
      skill according to the robot's safety procedure; no continuous locomotion.
- [ ] Exercise transport loss/timeout during a simulated or safely bounded
      operation; inspect outcome and confirm no replay on reconnect.
- [ ] Verify Stop All semantics and the robot's independent emergency-stop
      procedure. Local cancellation must not be represented as an emergency stop.
- [ ] Install/reinstall/upgrade/uninstall in a private prefix; preserve programs.
- [ ] Validate opt-in user-service startup and its actual runtime isolation.
- [ ] When authorized, reboot and validate autostart, durable programs,
      gateway/editor availability and secure access.
- [ ] Test published installer/copy command and deployed Pages using supported
      browser transport. WSS certificates remain trusted; no mixed-content bypass.
- [ ] Check Pi-independent board-selection/packaging regressions before release.
- [ ] Update the status matrix with evidence; retain failures and limitations.

Physical sound/skill/policy semantics, BLE security, shipping daemon identities,
service startup, reboot and deployed network behavior remain arrival gates.
Software-update mutations, continuous locomotion, camera and direct motors are
outside initial acceptance. Do not use a passed mock as authorization for them.
