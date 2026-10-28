# Raspberry Pi 5 as a standalone SmallVM target

Raspberry Pi 5 is a target in its own right. Running the Linux ARM64 SmallVM,
ordinary MicroBlocks programs and an editor requires no MicroDuck, robotd,
mediad, tofd, padd, Bluetooth or configured robot gateway. The optional native
MicroDuck adapter is disabled unless an explicit private socket is supplied.
Pi 5 GPIO/I2C/SPI, camera and audio primitives are not implemented by this port.

The separate **MicroDuck Rockchip RK3566** entry is an experimental placeholder.
Its public profile supports offline editing/preparation, with installation and
hardware connections disabled. Pi tests and simulated robot services do not
establish Rockchip/MicroDuck hardware or OS compatibility.

## What is established

| Path | Evidence and boundary |
|---|---|
| Native VM | Actual Pi 5 Model B Rev 1.0, Debian AArch64 builds and real SmallVM bytecode/PTY execution. This is independent of simulated robot services. |
| Candidate installation | Actual unprivileged install/reinstall/upgrade/checksum-failure preservation/uninstall in a private prefix, using retained bytecode. No service was installed. |
| Saved VM programs | Atomic durable `program.ucode`, exclusive data-directory ownership, process restart/autostart, acknowledged-write durability and corrupt-file refusal were physically tested. This is not OS reboot acceptance. |
| GP editor reconnect | Actual graphical arithmetic, variables/loop, browser project restore and SSH-loopback reconnect were tested against the real Pi. |
| JavaScript editor | Pinned actual JS compiler/port upload and execution on Pi; typed functions also have explicit simulated-service evidence. The later representative project save/manual-file/reopen check ran on the host, without a VM. A complete normal JS/Pi lifecycle is still an acceptance gate. |
| User service / reboot | Unit generation uses a mocked systemctl. Actual user-service start/stop and full OS reboot remain untested. No boot-before-login setup is enabled. |
| Public install | No reviewed ARM64 release is published; the portal release manifest remains unavailable and install-command copy stays disabled. Publishing source branches is not a binary release. |

See [dated native evidence](../linux/arm64/tests/README.md),
[Pi installation notes](RASPBERRY_PI_5_INSTALLATION_TESTING.md) and the
[JS project round trip](JS_PROJECT_ROUNDTRIP.md). Their versions/binary hashes
and scopes remain separate; a new target label does not upgrade those claims.

## Normal local installation and launch path

Use a reviewed local candidate, its exact version and independent archive hash
with `scripts/install-smallvm-linux-arm64.sh --archive ...`. This is a local
candidate procedure until an actual immutable release is reviewed/published.
The installer checks architecture, source pin, archive layout, digest and the
real executable's self-test before replacing its own launcher. Defaults are
`~/.local` for installation and `${XDG_DATA_HOME:-~/.local/share}/microblocks`
for programs. Existing programs survive reinstall/upgrade/uninstall.

The current persistent foreground path uses two processes. Supply the actual
reviewed version/editor/project environment; the following is a path template,
not a published installation command:

```sh
# Terminal 1: the installed launcher supplies its configured persistent data-dir.
"$SMALLVM_PREFIX/bin/smallvm" --pty-info "$SMALLVM_DATA/pty.json"

# Terminal 2: point identity validation at the actual versioned ELF, not the shell launcher.
"$SMALLVM_VENV/bin/python" linux/arm64/bridge.py \
  --editor "$SMALLVM_EDITOR" --pty-info "$SMALLVM_DATA/pty.json" \
  --vm-executable "$SMALLVM_PREFIX/lib/microblocks/$SMALLVM_VERSION/smallvm" \
  --http-port 8876
```

`SMALLVM_DATA` must match the launcher's configured data directory. It must be
private (0700), owned by the running user and have only one active VM. Do not
reuse another session's data. The executable lock refuses competing owners.
The bridge is separate, binds only 127.0.0.1 and permits one controller. Existing
Caddy/Docker/Ollama or ports 80/443 need no change. A browser on the Pi can use
that loopback editor; a PC uses an already verified SSH tunnel to the same port.
HTTPS Pages still requires a trusted WSS path; no insecure fallback is supplied.

`linux/arm64/session.py` is currently a disposable development supervisor: it
requires a fresh data directory. Do not present restarting that helper against
an existing directory as a supported resume operation. A combined normal-use
launcher with explicit resume, fresh-child PTY identity checks and safe logs is
a concrete follow-up; the two-process path above remains the existing interface.

## Persistence and reconnect acceptance still needed

Keep three things distinct: VM `program.ucode` on the Pi, client `.ubp` backups,
and optional browser project storage. Reopening an editor and connecting can
synchronize its project to the VM, so load the intended project or use the
editor's explicit read-from-board path before replacing existing code. Do not
infer safe readback from a fresh editor merely connecting.

The next standalone Pi acceptance should install a reviewed candidate in a
fresh private prefix, launch without any MicroDuck socket, upload a harmless
bounded program, record acknowledged CRCs, close/reopen the browser link, and
restart only its own VM/bridge with the same data directory. Verify retained
code and actual execution after each step, plus exclusive ownership and stale
PTY refusal. Test normal JavaScript editor readback/reconnect separately from
the earlier GP evidence. Keep other active Pi sessions untouched.

Only afterward consider actual optional user-service and OS reboot acceptance.
Those phases require explicit actions and evidence; no service, lingering,
firewall, certificate, SSH, networking or reboot change was made for this
assessment. ARM64 compatibility on other boards remains unverified.

## Portal and migration state

The target catalog now distinguishes Pi 5 and the requested MicroDuck RK3566
placeholder, retaining stable IDs. The source/preview has seven board choices;
the screenshot of the older public main site contains five. Main/Pages must
remain unchanged until the P4 work is reconciled and deployment coordinated.
The GP portal target catalog and separately pinned JS editor are not yet a
completed seven-target JavaScript portal migration.
