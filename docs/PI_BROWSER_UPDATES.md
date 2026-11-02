# Pi browser SmallVM updates

The supplied phone captures show the generic editor's v417/v421 firmware warning
and desktop-USB installation guard. They concern the native runtime, not editor
assets. The Pi port is validated at v417, independently of the editor's upstream
v421 recommendation. The Pi-specific overlay reports that compatibility policy
and routes the manual update command to the native Pi panel. Other boards keep
their USB installation guard.

The panel uploads a native Linux ARM64 runtime archive and its independently
supplied SHA-256 through the same-origin `/ws/update` socket. It shows progress,
checks the archive/ELF/source/version and presents the exact release and digest
for confirmation. It works on HTTP without `crypto.subtle` or a session key.
`GET /api/pi/update` reports current runtime and update/rollback state.

Supported input is the four-file runtime format from `linux/arm64/package.py`:
`smallvm`, `manifest.json`, `LICENSE` and optional `NOTICE`. This updates the VM
executable while preserving the current editor, SFC and host integration code.
Whole standalone Pi installer bundles and USB board flash images are not accepted.

As of 2 November 2026 the public native Pi release is
[`rpi5-v417-20261028-alpha2`](https://github.com/speccy88/microblocks-zephyr/releases/tag/rpi5-v417-20261028-alpha2).
It is v417, not a native v421 upgrade. Its old executable predates the headless
cleanup correction needed by the current mobile editor; that known binary is
refused as an upgrade. A new validated native release must be built before
claiming a v421 or later native update is available.

The managed service can create `BrowserUpdater` with installation enabled only
when its `service.json` explicitly sets `allow_browser_native_install` to true.
The default is package review only. Enabling the workflow does not install a
runtime: each apply still requires the reviewed release, SHA-256 and explicit
confirmation. The assistant has not applied a new native version to Fred's Pi.

Apply uses the guarded native installer without its service flag, validates the
candidate before stopping the owned VM, snapshots the persisted program, and
atomically selects the candidate. The managed supervisor exits for its own
systemd restart. Readiness confirms the new selection. Failed startup restores
the previous selection and saved program before retrying. Old executable files
and the last recovery snapshot remain. No OS reboot, firmware flashing, router,
Caddy or firewall modification belongs to this update operation.

The service root must be private, owned by its runtime user, with managed code,
executable, editor and data under that root. Place the reviewed
`scripts/install-smallvm-linux-arm64.sh` alongside `lan_service.py` when enabling
native installation. No archive-supplied script is executed.

For an existing Python extension gateway, preserve its canonical private socket
path in `microduck_socket`. Set `required_runtime_capabilities` to the installed
integration's manifest capabilities before allowing native updates; a candidate
missing any required capability is refused. These settings preserve an existing
integration and do not create or expose a new gateway.

Tests exercise actual archive bytes and transaction files in private temporary
Linux directories, with native installation and restart callbacks simulated.
The browser test uses the real phone-size editor and mocked update transport.
These establish the workflow, not a physical native-version installation.

Bonjour/LAN discovery remains reserved for the native iPhone app. Safari keeps
the known-address connection; no LAN scanner was added.
