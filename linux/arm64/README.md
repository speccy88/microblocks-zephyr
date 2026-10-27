# Linux ARM64 SmallVM: current status

The native ARM64 VM is **not implemented or compiled yet**. No ARM64 release is
published by this change. Raspberry Pi execution, IDE uploads, persistence,
networking and MicroDuck hardware are not tested. See [SPEC.md](SPEC.md) for
the acceptance contract and the pinned VM's 32-bit object-layout obstacle.

The guarded installer is implemented for a future validated release:

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

Builds must target baseline ARMv8-A without Pi 5-only optimization. A reproducible
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

Local test command (Linux, no board access):

```sh
python3 -m unittest discover -s tests -p 'test_linux_arm64*.py' -v
```

The lifecycle tests run real shell/file operations in a temporary workspace,
including install, reinstall, upgrade, failure preservation, uninstall and
user-service generation. They mock the reported architecture, the executable's
self-test, and systemctl. No fixture binary is executed, no real service starts,
and these tests do not establish native AArch64 runtime or reboot behavior.
