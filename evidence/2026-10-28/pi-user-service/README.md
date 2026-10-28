# Actual Raspberry Pi 5 user-service acceptance

A later separately authorized [full reboot test](REBOOT.md) passes VM startup,
saved code and graphical readback/reconnect. The no-reboot results below describe
the earlier non-disruptive service run; both histories are retained.

The corrected installer starts a real unprivileged SmallVM on RPI5/aarch64.
`NoNewPrivileges=yes`, `PrivateTmp=yes` and `ProtectSystem=strict` remain enabled.
The ordinary VM SHA256 is
`34416161437bb3195f6063838f1dadc777a6d35828914cda30a4b5a5a4546d8b`;
the local candidate package SHA256 is
`56bf440b3f3c15ce4c5dbf86889ea602cd50caf9f601f455016b7bd89a6e72b1`.
No robot service is connected.

The [final receipt](final-receipt.json) records real bytecode12, acknowledged
upload CRC, a WebSocket reconnect, explicit systemd restart and `Restart=on-failure`
recovery after SIGKILL of only the test unit's verified main process. Saved
`program.ucode` SHA256 remains
`f4e946a2914b20538a18d4f4d10fda4bba35845b6c424c1f538e127f5756965c`.
The bridge uses temporary loopback ports and is stopped after each phase.

Uninstall removes the test unit, enable symlink and launcher while retaining
the private program/versioned binary. All three pre-existing VMs preserve their
PID/executable/start identities. The pre-existing failed OpenClaw unit and
`Linger=yes` state are unchanged. No user-manager reset, lingering, firewall,
Caddy, credential or network-security setting is changed. No OS reboot is run.

## Failures retained separately

The first real attempt found quoted `WorkingDirectory` being treated literally
by systemd and rejected before VM startup. The original uninstaller removed the
enable link but stopped at the unloaded unit error. Independent inspection
confirmed `MainPID=0`, inactive, bad-setting. The corrected uninstaller removed
only the marker-owned unit/launcher after confirming inactive state and zero
PID. It preserves files if stop outcome or manager access is uncertain.

The second attempt passed startup/upload/reconnect, then the probe read `/proc`
before a replacement process completed exec. Its cleanup succeeded. The final
probe waits for the executable identity; it does not alter process permissions.
This is a probe correction, not weakened service hardening. [Raw attempt receipts
and exact test scripts](raw-service-evidence.zip) retain the distinct outcomes.
The scripts are opt-in lab fixtures, not a production startup mechanism.

Installer regressions include real `systemd-analyze verify` with spaces in the
paths, inactive rejected-unit cleanup, and retention on active/unknown/manager
failure. The complete local validator result is in the adjacent
[memory/service checkpoint](../p4-sram-service/README.md).

Full OS reboot, boot-without-login acceptance, Windows agent behavior after
Windows reboot, clean-machine installation and a published ARM64 release remain
unverified. No shipping MicroDuck or physical robot behavior follows.
