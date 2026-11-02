# Pi browser SmallVM updates

The supplied phone captures show the generic editor's v417/v421 firmware warning
and desktop-USB installation guard. They concern the native runtime, not editor
assets. The Pi port is validated at v417, independently of the editor's upstream
v421 recommendation. The Pi-specific overlay reports that compatibility policy
and routes the manual update command to the native Pi panel. Other boards keep
their USB installation guard.

The panel first offers **Rechercher sur GitHub**, without requiring a file or
SHA-256 entry. The Pi checks this project's releases over verified HTTPS, finds
the latest verified compatible native package and presents it for explicit
selection. Installation remains a separate exact-version/digest confirmation.
The manual file/SHA-256 alternative remains in a collapsed section. Both paths
use the same-origin `/ws/update` socket, progress and existing guarded native
apply/recovery. HTTP browser origins need no `crypto.subtle` or session key.
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
confirmation. Fred's later explicitly approved joint deployment uses the tested native
release `pi417-python-20261102`, still VM v417, with browser installation enabled
in that managed instance. See the physical acceptance below.

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

## Joint Python integration and physical acceptance

The Python handoff at `548fea9` provides native v417 with `python-extensions`.
The managed supervisor runs recovery **before** reading configuration or
starting Python, so a failed candidate uses the restored profile and binary.
A Linux regression test checks both selections after rollback.

After explicit user approval, the reviewed source correction was transferred
once and the joint release was activated in the existing permanent service.
The original service unit and Caddy configuration were preserved. A single
service drop-in selects code under `releases/pi417-python-548fea9`; private
Python state is separate from the existing VM program directory. The original
release and backup remain available at `backups/joint-548fea9`.

Real browser acceptance used `http://192.168.1.105/`, its actual WebSocket,
compiler, ARM64 VM and Python SQLite. The phone-size updater reviewed the exact
archive SHA-256, confirmed and reinstalled `pi417-python-20261102`, then reported
completion after managed restart. This is a tested v417 reinstall, not a v421
upgrade. Existing host capability requirements remain enforced.

The ordinary SQLite example ran from the normal Start button. An actual input
was edited to 22600 and its value returned from SQL; row count increased from
one to two while an independent heartbeat progressed. The two database rows
were also verified directly. SQL editing acceptance used a 1440x1000 viewport;
updater/connection acceptance used 390x844. These are Chromium tests against the
physical Pi, **not a physical iPhone/Safari certification**.

A synthetic native-selection checksum mismatch exercised automatic recovery
without executing an invalid binary. The service restored its configuration,
Python profile and program in 2.743 seconds. After all graphical tests, the
latest preserved user program was restored exactly and the service restarted;
its checksum matches the pre-deployment snapshot. SQLite demonstration rows
remain in the newly created private database. No OS reboot or v421 installation
was performed.

See `evidence/2026-11-02/pi-lan/joint-deployment-preparation.json` for actual
hashes, browser results, rollback results, final runtime state and the earlier
approval denials resolved by the subsequent explicit user instruction.

## Compatible GitHub releases

The fixed source is `speccy88/microblocks-zephyr`, this Linux port project.
Official upstream MicroBlocks board firmware and the editor's v421 suggestion
are separate products; no upstream firmware image is selected for this process.
Stable releases are searched by default; previews require a visible opt-in.

The Pi checks at most 90 catalog entries and five recent native candidates,
within a bounded deadline. Only HTTPS GitHub/API/asset hosts are allowed;
browser commands cannot supply a URL. No token, environment proxy, credentials,
TLS bypass or extra listening port is introduced. Network/rate-limit failures
are reported, and a truncated search never silently chooses an older release.

Publisher contract: a fixed release tag matching the archive's `version`, with
asset `smallvm-linux-arm64-<tag>.tar.gz` in the existing four-file native format.
The asset needs GitHub's SHA-256 digest or an exact `SHA256SUMS` entry. Its
manifest must include `provenance.port_commit`, the pinned VM/source and all
installed host capabilities (including `python-extensions`). Existing native
packaging accepts the full provenance record; publishing must retain the real
source and acceptance evidence rather than inventing it.

The installed commissioning binary has a recorded native port revision.
Subsequent GitHub installs retain their port revision in configuration. A
candidate must descend from the installed revision according to the project's
commit graph. An identical binary reports up to date. Older/divergent revisions,
unprovenanced packages, unknown baselines or another binary from the same
revision are refused. The installed binary is checked again before applying a
previous selection. Integrity is checked against the trusted project's GitHub
release; this is not a claim of a separate cryptographic release signature.

On 2 November 2026, the actual catalog contains only the older whole Pi alpha2
bundle and an editor preview. Neither is a compatible native-runtime asset.
The deployed phone-size UI reports this absence and preserves the current Pi;
no release was published and no VM installed for this feature. Positive future
release selection was tested with real package bytes and explicitly synthetic
GitHub responses. Actual HTTPS catalog checks were exercised from the physical
Pi through the real browser UI, with stable and preview channels.

The app-only deployment preserves the v417 binary, Python configuration, user
program, original unit/drop-in and Caddy. The previous updater/config and program
snapshot remain under the new app release's private `backup` directory. Python
SQLite was rechecked using read-only `SELECT 42`. See
`evidence/2026-11-02/pi-lan/github-release-discovery.json` for exact hashes,
paths, actual catalog responses and test boundaries.
