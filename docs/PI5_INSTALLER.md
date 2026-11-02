# Raspberry Pi 5 complete source installer

This installs this project's native VM417, its mobile JavaScript editor,
SQLite/Python blocks and Adafruit Blinka10.1.0 in an isolated environment.
It builds from pinned sources; it does not claim an official upstream ARM64
binary release. The upstream editor's VM421 suggestion is not installed.

Prerequisites: Raspberry Pi 5 Model B with a current **64-bit** Pi OS/Debian,
Python3.11+, curl, git, GCC/build-essential, python3-venv, python3-dev and HTTPS
access to GitHub, Codeberg and PyPI. Use an ordinary account. If a prerequisite
is absent, the installer prints the exact apt command and stops; the explicit
`--install-prerequisites` option can install only these build prerequisites.
For system service setup, first run `sudo -v`; the runtime itself is non-root.

## Published entry point

The readable bootstrap is published only after its immutable source payload
passes the real Pi build. Its GitHub URL and payload SHA will be recorded here
at that checkpoint. No executable download command is offered before then.

## Options and behavior

Default installation prepares `~/.local/share/microblocks-pi5` for foreground
use at `http://127.0.0.1:8877/`. Run the printed `bin/microblocks-pi5` launcher
to start it. `--prepare-only` explicitly requests this preparation.

Pass `--lan --service` to install a boot service and serve the editor on one
detected private interface address at port8877. Multiple private addresses
require `--bind ADDRESS`. `--port PORT` chooses an unprivileged port and
`--clients CIDR` narrows permitted clients (/24 or narrower, inside a private
IPv4 network). Only this exact HTTP Host/Origin is accepted for programming.
The LAN option uses **unauthenticated, unencrypted HTTP/WebSocket**; devices
in that scope can program the Pi and see or alter traffic. It does not alter
the firewall, router, TLS trust, I2C configuration or group memberships.

Port80 and occupied ports are refused before installation changes. Existing
Caddy, OpenClaw and other services are not overwritten. Configuring an existing
port80 proxy is a separate administrator action, not part of this installer.
Keep a stable DHCP reservation if a persistent IP URL is required.

`--prefix /absolute/private/path` selects an independent installation. An
unrecognized existing directory or modified/unrelated service is refused.
The earlier private `microblocks-lan` deployment uses a different layout and
is deliberately not adopted automatically by this installer.

Runtime Python packages are pinned by version and official PyPI SHA256 hashes
in `linux/arm64/pi5-python-lock.json`. pip configuration is disabled only for
the child process, avoiding accidental PiWheels substitution. Failed installs
retain the previous selected environment. Blinka imports and automatic Pi5
detection are checked without creating I2C, GPIO, PWM or sensor objects.
SQLite is enabled; climate, HTTP and MQTT plugins are disabled by default.
Installing Blinka does not establish a physical sensor test.

Repeat the same command to verify and reuse the installed source/environment.
A newer published bootstrap may select a descendant source revision; older or
diverging revisions are refused. Build/dependencies are staged before stopping
only the owned service. Old code, config and data backups are retained, and a
failed service readiness check restores the prior selection and program data.
Custom state paths require manual migration and are preserved on refusal.

Browser native update discovery remains available. Applying a native package
requires explicit `--enable-native-updates` and a verified compatible project
release; this does not create a release or treat upstream421 as compatible.

Use the same bootstrap with `--uninstall` to disable/remove only its owned
service and launcher. Programs, SQLite databases, backup/code versions and
Python environments remain in the installation prefix. No recursive user
data deletion is performed. `--dry-run` validates the intended endpoint and
prints the plan without installing or opening a listener.

## Acceptance boundary

Linux fixture tests cover fresh/repeat/source update, failed build/start and
rollback, preservation of program/SQLite/profile, unrelated service and
occupied-port refusal, downgrade checks and uninstall. Blinka10.1.0 imports
and `RASPBERRY_PI_5` detection pass on Fred's actual Pi without changing its
current SmallVM service. Real source/bootstrap results will be recorded with
the published payload. A fresh OS, physical iPhone, sensor and reboot remain
separate physical acceptance tests.
