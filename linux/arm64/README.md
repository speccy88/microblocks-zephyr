# Linux ARM64 SmallVM: current status

The [complete Pi installer candidate](../../docs/PI_INSTALLER.md) now bundles the
VM, pinned JavaScript editor, bridge and a private offline Python dependency.
Actual fresh-prefix installation, identical reinstallation and automatic recovery
after either child fails pass on the Pi. The first graphical evaluation after
reading an older raw-protocol fixture now returns 42 without reconnect: Linux
protocol cleanup no longer calls the unsupported display primitive. Explicit
unsupported hardware blocks still fail normally. See [current evidence](../../evidence/2026-10-28/pi-complete-installer/README.md).
The complete VM-and-bridge service's reboot check is blocked after automatic
approval review rejected the requested reboot; it has not run. The earlier
VM-only reboot result below remains separate. No public installer URL is ready.

The 2026-10-28 JavaScript-editor follow-up passes graphical standalone Pi
arithmetic, project serialization/reopen, reconnect and real VM readback.
Separate fictional robotd fixtures exercise simple missing-servo/model-name
blocks alongside advanced reference geometry in one project, including readback
and execution after reconnect. Its [local readback adaptation](../../docs/JS_PI_READBACK_SPEC.md)
preserves VM slot identities and serializes rapid explicit evaluations.
This later result supersedes the older typed-example graphical limitation below
for that tested subset; it does not validate every block, physical MicroDuck,
live robot control, a browser Save dialog or full OS reboot.
The later [user-service acceptance](../../evidence/2026-10-28/pi-user-service/README.md)
passes actual install, bytecode upload/reconnect, explicit restart, crash
recovery and uninstall with the service hardening enabled. It preserves the
three pre-existing VMs and leaves no test service enabled. A later separately
authorized [reboot test](../../evidence/2026-10-28/pi-user-service/REBOOT.md) also
passes automatic VM startup, saved code42 and graphical readback/reconnect.
That reboot ends the old foreground VMs, retaining their three saved programs.

The later [typed health checkpoint](../microduck/TYPED_READINGS.md) adds two pure
snapshot-conversion primitives and library0.2. Ordinary and sanitizer Pi binaries
each pass all eighteen MicroDuck feature tests (simulated robot services), with
181 required Linux tests passing. See [typed evidence](../microduck/tests/typed-validation.json).
The new ordinary binary is `0b5c2b269fb4e12b7ef8422c2961e2b1e09094de287796a297a93620ea43136f`.
Graphical execution of the updated typed example remains unverified because the
native Edge-control approval timed out. Earlier graphical evidence below covers
the earlier prototype. No physical MicroDuck or published release is claimed.

The native headless SmallVM v417 now builds and executes on Fred's Raspberry Pi
5, Debian 13.4, AArch64, GCC 14.2. Both ASan/UBSan and ordinary ARMv8-A builds
pass real interpreter/PTY tests: arithmetic, variables, start/stop, live edits,
fragmented uploads, compaction, process restart/autostart, acknowledged-write
durability after process termination, and corrupt-file refusal. Actual install,
repeat install, checksum-failure preservation, upgrade and uninstall also pass
in a private test prefix. These are physical Pi results.

The real GP 2.5.8 graphical editor also uploads and executes arithmetic (12), a
50-iteration variable/output script, browser project save/restore, and an explicit
WebSocket disconnect/reconnect through the SSH tunnel. Screenshots and a scoped
browser report are retained in `tests/`. The IDE's first-ping handshake and its
BLE preference message are covered by regressions found during this real test.

No ARM64 release is published yet. Pi reboot acceptance passes with the lab's
pre-existing lingering enabled; the foreground bridge is restarted manually.
Windows reboot/SSH-agent persistence and clean-machine setup remain unverified.
No physical MicroDuck test has run.
See [SPEC.md](SPEC.md), [hardware.json](hardware.json) and the evidence in
[tests](tests/) for the acceptance boundary. CPU/RAM readings are short bounded
idle samples, not performance benchmarks.

The guarded installer accepts a separately built and tested candidate package:

```sh
bash scripts/install-smallvm-linux-arm64.sh --version RELEASE_TAG --sha256 ARCHIVE_SHA256
# Opt-in user systemd service (does not configure boot without login):
bash scripts/install-smallvm-linux-arm64.sh --version RELEASE_TAG --sha256 ARCHIVE_SHA256 --service
bash scripts/uninstall-smallvm-linux-arm64.sh
```

These are templates, not working published installation commands. Obtain the
actual immutable tag and independent SHA-256 from a reviewed release manifest.
The default install prefix is `~/.local`; programs live in
`${XDG_DATA_HOME:-~/.local/share}/microblocks`. Reinstall preserves that directory.
Uninstall removes the managed launcher/service and retains programs and old
version binaries for recovery. No root, SSH-key installation, firewall changes,
network listener, system service or change to unrelated software is performed.

`--archive /absolute/path` validates an already downloaded package.
`--verify-only` runs on Linux of either architecture and checks the digest, manifest, safe archive structure and AArch64
ELF identity without running its executable or installing anything. Such a
header check cannot prove that a binary works. Real installation additionally
requires the candidate executable to pass `--self-test` before replacing the
active launcher. That release CLI is part of this port's acceptance contract;
the existing upstream executable must not be assumed to implement it.

Builds target baseline ARMv8-A without Pi 5-only optimization. The current
ordinary Pi binary links only libc and requires glibc 2.34 or newer according to
its ELF version metadata; it ran on glibc 2.41. Older distribution compatibility
and other ARM64 boards have not been tested. A reproducible
package must include corresponding MPL source/provenance and license notices.
The official targets were inspected in the pinned `linux+pi/` directory. Its
generic script uses `-m32` and 32-bit SDL archives; the Raspberry Pi script uses
WiringPi. Neither establishes Linux ARM64 support. The older README's separate
`linux` and `raspberryPi` folder names are obsolete at this revision.

`package.py` creates a deterministic candidate archive/checksum from an existing
AArch64 executable and the exact upstream license read from Git. It never builds,
executes or publishes the binary. Gzip/tar timestamps, ownership and order are
fixed. Packaging tests use fake non-executable ELF headers and establish only
the packaging contract. Corresponding port source/build recipe and physical Pi
evidence remain required for a release.

Build from the exact upstream Git revision (Linux):

```sh
python3 linux/arm64/build.py --upstream /path/to/smallvm-git --output build-artifacts/linux-native --test
# Add --sanitize for ASan/UBSan, or --source-only to prepare on Windows.
build-artifacts/linux-native/smallvm --data-dir /absolute/private/programs
```

The VM creates no network listener. It publishes a private PTY discovery JSON
inside its owned mode-0700 data directory. One VM can own that directory at a
time. The graphical transport uses the separate [loopback bridge](bridge.py),
with exact Host/Origin checks and one controller. See the
[portal connection guide](../../docs/LINUX_PORTAL.md).

The build also registers an optional [MicroDuck Unix adapter](../microduck/README.md).
It is disabled unless `--microduck-socket /absolute/private/gateway.sock` is
explicitly supplied. Four nonblocking jobs, a fixed method allowlist, verified
same-user peer credentials, bounded strict JSON and confirmation/operator gates
keep it separate from the VM scheduler. It passed real Pi bytecode and graphical
health-block tests with simulated robot services. Those results do not validate
physical MicroDuck hardware. The pinned yyjson dependency and its MIT notice
are retained in source manifests and candidate packages.

The LP64 implementation stores 32-bit arena offsets in VM objects while native
addresses remain native pointers at explicit boundaries. It retains the v417
four-byte field/header/code format, uses typed native primitive callbacks and
adds bounded scheduling. The memory tests exercise moving GC with the heap
above 4 GiB, deep/wide graphs, temporary roots and invalid references. There is
no low-address mapping or weakening of ASLR. Original pinned sources are read
from Git and verified before strict, hash-guarded transformations.

Local test command (Linux, no board access):

```sh
python3 -m unittest discover -s tests -p 'test_linux_arm64*.py' -v
```

The lifecycle tests run real shell/file operations in a temporary workspace,
including install, reinstall, upgrade, failure preservation, uninstall and
user-service generation. They mock the reported architecture, the executable's
self-test, and systemctl. No fixture binary is executed, no real service starts,
and these tests do not establish native AArch64 runtime or reboot behavior.
