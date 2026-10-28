# Standalone Pi foreground lifecycle

Actual RPI5 / Debian AArch64 acceptance uses the retained ordinary VM SHA-256
`22387aeabb91c99041b13c07a453233496eb80f771881e5143394b1618f24d84`.
The guarded candidate installer ran in a fresh private project prefix, followed
by the installed launcher's real self-test and nine session policy/lifecycle
tests. No system/user service, default user install, security/network setting,
robot service or OS reboot was used.

The actual pinned JS compiler and connection classes uploaded `20 + 22`,
received CRC `[41,52,161,243]` and returned 42. A second fresh connection verified
the CRC and returned 42 without upload. The owned VM/bridge then stopped and
resumed using the same data. Two further connections verified the CRC and 42
without upload. Stored code SHA-256 remained
`5eb1428507ee871aa765c43e81ceab9bb61f277cb7f0b7f396abbbd3b608a00d`.
Earlier logs were preserved and discovery paths differed between launches.
All owned children stopped; the three pre-existing VMs remained alive.

These are headless compiler/transport tests with minimal block-view fixtures.
They do not test graphical project synchronization, decompilation, autosave,
native browser reconnect or physical peripherals. The packaged editor engine
is the unchanged verified `5564b1e42d6790360450ebf11c9eb33a1c6877f2` source;
optional MicroDuck libraries are not automatically imported and no gateway is
configured. Shared main, Pages, GP, protected P4 and paused SFC remain untouched.

`pi/` contains byte-preserved receipts fetched from the owned Pi directory, plus
their evidence hashes. `input-hashes.json` binds all 581 transferred input files.
No VM executable, candidate archive, stored program or credential is committed.
The private Pi candidate/program files remain available for review.
