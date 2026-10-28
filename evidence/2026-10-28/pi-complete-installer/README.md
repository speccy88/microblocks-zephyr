# Complete Raspberry Pi installer checkpoint

Historical checkpoint: the later [approved reboot acceptance](../pi-complete-reboot/README.md)
resolves the reboot and uninstall gates below, and records a separately discovered
empty-editor reconnect defect and its fix. This alpha1 archive itself is unchanged.

This is an unpublished candidate for the independent Raspberry Pi 5 target.
The actual Pi runs the native AArch64 VM; no physical MicroDuck, GPIO, camera or
audio is exercised. No main, GP, live site, paused SFC or P4 hardware changes.

## Verified behavior

- Fresh private prefix, program directory and private Python environment installed
  the complete bundle on the existing Pi OS in 4.255 seconds. This was not a fresh
  SD image. Its pre-existing systemd lingering was retained unchanged.
- Identical reinstallation preserved the saved bytes, CRC and supervisor PID.
- Controlled termination of the verified owned bridge child, then the VM child,
  caused systemd to restart the combined session automatically. Both old children
  ended and the saved program and CRC survived each recovery.
- The actual JavaScript editor connected over a loopback SSH tunnel, read the
  earlier raw program, opened the arithmetic fixture and returned 42 on its first
  canvas evaluation without reconnect. The saved program was sealed with CRC
  `4087428137` and a private fsynced backup.
- All 571 installed editor files matched the authenticated bundle before adding
  visible private acceptance controls and the arithmetic fixture. The upstream
  editor engine remained unchanged. That test overlay is absent from the package;
  reinstallation was tested before the overlay changed the immutable directory.
- An earlier candidate passed actual uninstall and retained its saved program.
  The final candidate remains installed for the pending reboot check; final
  uninstall acceptance is therefore not claimed yet.
- Repackaging the same pinned inputs produced byte-identical archive and bootstrap
  hashes. Shell syntax checks passed. Full validation is recorded separately.

The screenshot's shared acceptance panel labels robot data as simulation. In
this arithmetic test no robot service was connected: 42 came from the real Pi VM.

## First-run regression

The old runtime reproduced `primitiveNotImplemented` (payload `1b00040000`)
after `deleteAllCodeMsg`, although the new arithmetic bytes were correct. The
protocol handler called `primMBDisplayOff(0, NULL)` outside a task; the headless
hardware stub set the global task error. Linux preparation now removes only the
three internal display cleanup calls from the exact pinned runtime source.
Explicit hardware primitives still report unsupported errors.

The saved negative-control log fails the erase/first-run regression on the old
binary. The new ordinary Pi and sanitizer host binaries pass erase, Boardie soft
reset and explicit-unsupported-hardware regression tests. This corrects the VM
cause without changing the pinned JavaScript compiler or suppressing task errors.

## Candidate identity

Version: `rpi5-v417-20261028-alpha1` (unpublished).

- Archive: `smallvm-pi5-rpi5-v417-20261028-alpha1.tar.gz`, 3,906,001 bytes.
- Archive SHA256: `edabb7b3da9d22d129b6e56c39369f89538de26b4ec3da3636c8f8375d122607`.
- Bootstrap SHA256: `6114e1400098131f5e967f42d025f6c892b96c60fedd8031b99d465ff1aa25fe`.
- AArch64 executable SHA256: `feea4dc52f7a4e083c6144bfa569518bd801cc62341dca04500464b3c4ac7b21`.
- Sanitizer host executable SHA256: `bd767a64d09a2d6ffb9d4e6ec87adcf7dd81680d04ab97c0b033a5f4960fcfde`.
- Corresponding source archive SHA256: `0037f8985e2ff359876594923107cacdf40e6117600d3927c12776eb43a696b7`.
- VM pin: `2071df569623ba9cdcd6f8106b61796e047df38b`; JS editor pin:
  `5564b1e42d6790360450ebf11c9eb33a1c6877f2`.

The bundle includes corresponding MPL source/build recipe, licenses, the pinned
Pi editor and hash-checked official websockets 15.0.1 universal wheel. Dependency
installation is offline in a private venv. See [installer instructions](../../../docs/PI_INSTALLER.md)
for prerequisites, startup consent, connection and retained-data uninstall.
The archive and bootstrap remain local ignored build artifacts, not Git payloads.
No public copy-paste installation command is ready until acceptance, coordinated
publication and download/hash verification are complete.

## Exact blocked operation and preserved state

Automatic approval review rejected
`ssh -o BatchMode=yes -o StrictHostKeyChecking=yes rpi5 sudo -n /usr/sbin/reboot`
before process creation. Reason: a reboot could disrupt services/foreground VMs,
and review required explicit trusted human confirmation for that particular
reboot. It did not execute and was not retried or routed through another command.
The parent subsequently instructed this task to wait for Fred's response.

The before-only reboot receipt is not acceptance. Boot ID remains
`589fbd5f-cfbc-41ca-8ed9-ceb925b094fb`. The owned user unit
`microblocks-smallvm.service` remains active, using private test root
`/home/fred/microblocks-fresh-install-afcxpmc5`, supervisor PID 2408, VM 2411,
bridge 2412 at the last read-only inspection. It binds only 127.0.0.1:8876.
Saved program SHA256 is
`e1670b43577fb8aa7335fdd4fbef213d482c79874db785842275e6aca3325600`.
No existing system-service configuration or lingering setting changed.

Remaining gates: approved combined-service reboot with no manual VM/bridge
restart; browser reconnect/readback afterward; final owned uninstall; clean OS
prerequisite/boot-consent path; release publication/download; physical MicroDuck.
Earlier VM-only reboot evidence does not satisfy the combined-service gate.
