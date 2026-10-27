# Raspberry Pi 5 - Installation and Testing

SmallVM executes real MicroBlocks programs on Fred's Pi 5 Model B Rev 1.0,
Debian 13.4 AArch64, GCC 14.2 and glibc 2.41. The exact ordinary binary hash is
`0365d817036b74819f27ea405f8036f2d892f503891a03d561eb9e1c12f51ef2`.
Both ordinary and sanitizer builds passed interpreter/PTY tests; the graphical
editor produced 12 from 5+7, ran a 50-iteration program, restored a browser project
and reconnected. See [evidence](../linux/arm64/tests/README.md) and the newer
[MicroDuck adapter evidence](../linux/microduck/tests/README.md).

No release is published. The following is a **local candidate** procedure,
using a reviewed archive and the independent SHA256SUMS file, not a copy/paste
public installation command:

```sh
bash scripts/install-smallvm-linux-arm64.sh --version VERSION --sha256 ARCHIVE_SHA256 --archive /absolute/candidate.tar.gz
~/.local/bin/smallvm --self-test
bash scripts/uninstall-smallvm-linux-arm64.sh
```

Replace all placeholders using the reviewed candidate. Default installation is
unprivileged in `~/.local`, with programs in
`${XDG_DATA_HOME:-~/.local/share}/microblocks`. Reinstall/upgrade preserve programs;
uninstall retains programs and old version binaries. The installer refuses
checksum, source pin, archive structure, architecture or self-test failures.
`--verify-only` validates a candidate on either Linux architecture without
executing it. It is weaker evidence than native runtime acceptance.

An opt-in `--service` installs a user systemd unit. Its shell/unit-generation
tests passed with a mocked systemctl; actual user-service operation and full OS
reboot are still untested. It does not enable user lingering or create a system
service. Do not infer reboot persistence from process restart testing.

For graphical development, build the self-hosted loopback editor and run the
foreground VM/bridge supervisor as described in [Linux portal](LINUX_PORTAL.md).
Use a verified SSH tunnel from the PC. The bridge binds loopback and accepts one
controller with exact Origin/Host checks. HTTPS Pages requires trusted WSS for a
remote device; it has no insecure LAN fallback. Existing Pi Caddy/Docker/Ollama
services are preserved. The tested sessions use separate private directories and
high loopback ports; no system service or port 80/443 is replaced.

Acceptance still needed: actual user-service startup, OS reboot, public download
installation, website copy-command and deployed Pages behavior. Neither Pi tests
nor an AArch64 ELF header establish compatibility with the future MicroDuck.
