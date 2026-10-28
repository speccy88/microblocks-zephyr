# Real Pi graphical readback and service execution

The approved public migration tip `2c060b7f4e9153dd7213d9b7c2a479810577eb51`
passed all three hosted workflows. The native workflow passed both x86_64 and
aarch64 jobs. Raw public API responses and verified remote refs are retained here.
These results apply to that published tip, not subsequent local changes.

The actual pinned JS editor was served by a loopback bridge on the real Raspberry
Pi 5 and reached through an owned SSH loopback forward. Initial graphical readback
exposed an upstream decompiler shape problem and missing code-manager bindings:
the recovered `return 20 + 22` stack did not execute when clicked. The screenshots
and console log retain that failed baseline; it is not a passing arithmetic test.

With the separate readback adapter, Project > Open from board recovered a green
`20 + 22` reporter. The first explicit click displayed **42**, close/reconnect
displayed **42** again, and a fresh page recovered and ran the reporter as **42**.
Readback preserved the original `program.ucode` SHA-256
`5eb1428507ee871aa765c43e81ceab9bb61f277cb7f0b7f396abbbd3b608a00d`.
An explicit run synchronized the recovered project as designed, producing
`793b3a2f02e4371cff270f3323e8d45b3df0b8483fd72bb4706ef9ddcc5ab07f`.
The final graceful cleanup preserved that new saved program. The v417/v421
firmware notice was acknowledged; no runtime upgrade was performed.

The transferred editor archive hash is in `editor-transfer.json`. Its full input
manifest binds the packaged assets and changed adapter/bootstrap/packager bytes;
upstream engine pin `5564b1e42d6790360450ebf11c9eb33a1c6877f2` was unchanged.
Nine focused checks use the actual pinned decompiler, project, block and code
manager classes, including lazy synchronization and cancellation cases.

A uniquely named transient user service then ran the private installed native
binary with `NoNewPrivileges=yes`, `PrivateTmp=yes`, `ProtectSystem=strict` and
only its private data path writable. Its discovered PID matched systemd's MainPID;
it answered an actual PTY ping. It stopped cleanly and preserved its program hash.
The transient unit was collected. No persistent unit was installed/enabled, no
linger or security setting changed, and no reboot was performed. The reported
post-stop default property values belong to the unloaded unit, not weakened
properties of a running service. Existing user-manager degraded state and enabled
linger were observed, not changed.

Owned graphical supervisor/VM/bridge children stopped with return code zero.
The Windows forwarding process was absent on the final process check; no broad
SSH cleanup was used. All three pre-existing Pi VMs (4819, 5601, 6874) remained
alive. No robot service, physical motion or MicroDuck hardware was exercised.

Remaining acceptance: arbitrary-project decompiler parity, broader graphical
save/reopen/autosave behavior, persistent installer service, login/boot/reboot
and real MicroDuck peripherals. The new local adapter and Pages proposal are
not published under the earlier exact-checkpoint approval.
