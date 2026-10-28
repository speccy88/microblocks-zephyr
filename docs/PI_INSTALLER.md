# Raspberry Pi5 installation candidate

The installer bundle is being validated locally. No public release or ready-to-run
Internet command is claimed until the exact archive/bootstrap hashes are published
and downloaded back for verification. Do not replace pinned versions with `latest`.
MicroDuck remains a separate placeholder target; this installer does not commission
robot services or provide Pi GPIO/camera/audio support.

The approved full reboot now passes automatic combined VM/bridge startup and
byte-identical program persistence. Graphical acceptance found and fixed an
empty-editor connection that otherwise cleared the saved program. The corrected
adapter automatically reads a saved project when connecting an empty local
editor; an editor containing code or libraries retains normal synchronization
behavior. See [reboot evidence](../evidence/2026-10-28/pi-complete-reboot/README.md).
The older alpha1 archive predates this adapter fix and must be rebuilt and
revalidated before publication. A fresh SD image remains untested.

Prerequisites are a64-bit Raspberry Pi5 Linux OS, glibc2.34+, an unprivileged user,
Python3.10+ with `python3-venv`, bash/coreutils, curl and a working systemd user
manager. On Debian/Raspberry Pi OS, install missing prerequisites through the normal
package manager, e.g. `sudo apt install python3-venv curl`. No sudo password belongs
in chat or a configuration file. A fresh private prefix/venv is tested on the lab
Pi; that is not a freshly imaged SD-card claim.

The authenticated bundle contains the actual AArch64 SmallVM, corresponding prepared
source/build recipe and MPL license, pinned JavaScript editor, current bridge and
supervisor sources, and the official hash-checked websockets15.0.1 universal wheel
with its BSD license. Dependency installation uses a private venv with `--no-index`
and `--no-deps`; it does not modify system Python or fetch moving dependencies.

The default prefix is `~/.local`; programs are retained in
`${XDG_DATA_HOME:-~/.local/share}/microblocks`. The loopback editor/bridge listens at
`http://127.0.0.1:8876/`. The installer prints the exact SSH local-forward command,
editor URL, program directory and uninstall command. Keep host-key verification;
no keys, firewall rules, certificates, Caddy or port80 settings are installed.
An HTTPS Pages editor connecting directly through WSS is a separate transport gate.

One user unit supervises VM and bridge together. It resumes the same private data
directory, uses fresh verified PTY discovery, and restarts both when a child fails.
Unit success requires matching ready supervisor state, not merely an active PID.
NoNewPrivileges, PrivateTmp, ProtectSystem=strict and control-group termination stay
enabled. The default browser profile is standalone Raspberry Pi5.

Boot before login requires systemd lingering. If it is already enabled, the
installer leaves it unchanged. Otherwise the user must explicitly consent in the
terminal immediately before `sudo loginctl enable-linger USER`. There is no blanket
yes/approval-bypass flag. Noninteractive runs refuse that change. `--login-startup`
instead installs a service that starts after the user logs in; it does not promise
unattended startup. Tests never disable the lab's existing lingering to simulate a
fresh machine.

For an extracted, independently hash-verified candidate only:

```sh
python3 -B linux/arm64/install_bundle.py
# Optional private paths/port:
python3 -B linux/arm64/install_bundle.py --prefix /absolute/private/prefix \
  --data /absolute/private/programs --port 8876
```

Use the printed `microblocks-uninstall` command to remove the owned service and
launcher. Programs, private Python environment, immutable editor/runtime versions
and binaries remain for recovery. Uninstall does not change lingering or remove
unrelated files/services. Identical reinstallation preserves programs; changing an
active service configuration requires stopping that owned unit explicitly first.

Build the candidate from verified local inputs with `tools/package_pi_installer.py`.
It never downloads, runs software, moves refs or publishes. Its generated public
command is a publication proposal until the archive and bootstrap exist at the
specified immutable release URL. The embedded manifest checks bundle consistency;
the separately pinned outer/bootstrap SHA256 authenticates the downloaded payload.
