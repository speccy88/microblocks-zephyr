# Linux ARM64 portal installation handoff

The source portal modules offer Raspberry Pi 5 and MicroDuck profile information,
SSH target validation and a reviewable installation command. Raspberry Pi native
SmallVM/PTY protocol tests now pass. The real graphical editor also passed
arithmetic, a bounded 50-output loop, browser save/restore and reconnect to the
Pi through SSH. Full OS reboot acceptance and physical MicroDuck validation
remain pending.

**No ARM64 release is published yet.** `web/portal/linux-release.json` has
`available: false`; the panel refuses to generate or copy an installation command.
This is intentional. A successful native build does not create a release asset.

## Published-release gate

After a real release and its installation tests are reviewed, the maintainer may
update the manifest with:

```json
{
  "schemaVersion": 1,
  "repository": "speccy88/microblocks-zephyr",
  "available": true,
  "version": "EXACT_RELEASE_TAG",
  "artifactSHA256": "ACTUAL_64_HEX_ARCHIVE_DIGEST",
  "installerCommit": "ACTUAL_40_HEX_GIT_COMMIT",
  "installerSHA256": "ACTUAL_64_HEX_INSTALLER_DIGEST"
}
```

This example is a schema, not a working manifest. The generator rejects missing
hashes, moving version aliases, shell syntax and unsupported values. Download
URLs are derived from the fixed project repository; arbitrary URLs are not
accepted. The expected archive name is
`smallvm-linux-arm64-<version>.tar.gz`. The installer comes from its exact Git
commit, never a moving branch.

## User workflow

1. Select the Linux board and review its physical/mock validation status.
2. Enter its actual SSH username and IPv4 address or DNS hostname. The page does
   not discover or probe an SSH server. IPv6 and custom SSH ports are not yet
   supported by this form.
3. Independently verify the board's SSH host fingerprint and establish its
   matching known-host entry using normal SSH tooling. Generated commands use
   `StrictHostKeyChecking=yes`; they never bypass a host-key warning.
4. Choose PowerShell or a macOS/Linux terminal. Review the decoded script and
   optionally request a user systemd service. That service does not enable boot
   before login or change system-wide services.
5. Click Copy, then paste the command into the chosen terminal. SSH handles
   interactive authentication there. The browser never receives a password.

Both terminal commands use the same quote-free remote payload wrapper to avoid
PowerShell native-argument quoting differences. Its Base64 data is an ASCII
encoding of the displayed script, not a secret. The decoded script creates a
private temporary directory, downloads the commit-pinned installer over HTTPS,
checks its independent SHA-256, and executes it only after that check succeeds.
The installer then verifies the release archive against the separately pinned
artifact digest. No password, Wi-Fi secret, token or SSH key is placed in either
the copied command or browser storage. Switching profiles clears the target
fields; the module does not persist them.

## Graphical connections

The panel has
an editing entry point and an optional `wss://host/ws/vm` endpoint field for a
separately configured bridge with a trusted certificate. It rejects `ws://`,
credentials in URLs, query parameters and fragments. Selecting an endpoint
passes configuration to the editor; it performs no connection or availability
probe. The user must explicitly connect in the editor. Certificate trust is
still enforced by the browser. There is no insecure fallback from HTTPS Pages.

The Pi development path serves the actual pinned GP editor and a separate VM
bridge on `127.0.0.1:8876`. This port does not conflict with Caddy on 80/443. Build
the dedicated editor with:

```sh
python3 tools/package_linux_editor.py --ide-source build-artifacts/ide-source --output build-artifacts/linux-editor
python3 -m venv /absolute/project/venv
/absolute/project/venv/bin/python -m pip install -r linux/arm64/bridge-requirements.txt
# Start the VM separately with a private data directory, then:
/absolute/project/venv/bin/python linux/arm64/bridge.py --editor /absolute/editor --pty-info /absolute/private/data/pty.json --vm-executable /absolute/smallvm --http-port 8876
```

Pass `--pty-info /absolute/private/data/pty.json` to the VM to match that example.
The optional `linux/arm64/session.py` starts both as foreground child processes
using a fresh data directory; it is a development supervisor, not a service.
Keep SSH host verification enabled and forward the same loopback port:

```sh
ssh -N -o StrictHostKeyChecking=yes -o ExitOnForwardFailure=yes -L 127.0.0.1:8876:127.0.0.1:8876 USER@VERIFIED_HOST
```

Open `http://127.0.0.1:8876/` on the client PC and explicitly Connect. The dedicated
local profile accepts only its own loopback origin and `/ws/vm`; the published
HTTPS profile still requires WSS. No LAN listener, certificate exception or
browser security change is needed. The bridge permits one controller, validates
the VM's process/executable/PTY identity, and refuses stale metadata or unsafe
asset paths. It serves an exact local asset tree without query parameters.

The MicroDuck discovery panel is separate from VM connection. Its tests use
mock GATT. It sends no RPC command, PIN or Wi-Fi password; the currently exposed
browser BLE connection cannot attest encryption. Authentication/provisioning
and actual robot control remain gated on secure transport and hardware tests.
The [Unix gateway and native VM adapter](../linux/microduck/README.md) now have
real Pi execution tests against simulated robot services. The MicroDuck editor
profile includes the matching block library and a read-only health example.
Physical robot validation is still pending; a CLI-configured gateway path is
required and does not by itself attest robot readiness.

## Module integration

Load `linux-core.js` before `linux-panel.js`. The latter exports:

```js
const panel = MicroBlocksLinuxPanel.mount(container, {
  profile: 'raspberry-pi5', // or 'microduck'
  releaseManifest,
  onOpenEditor: ({profile}) => openTheExistingEditor(profile),
  onEndpoint: ({profile, endpoint}) => selectEditorEndpoint(profile, endpoint)
});
panel.setProfile('microduck');
panel.setReleaseManifest(updatedManifest);
// panel.destroy() removes the mounted panel.
```

These callbacks integrate with the existing portal; the module does not replace
the editor or implement SSH in a web page. Without an endpoint callback it emits
a bubbling `microblocks-linux-endpoint` event carrying the same configuration.
The panel uses existing `connection-card`, `hosted`, `board-picker` and `tag`
classes, plus `linux-install-*` hooks for the shared stylesheet. Shared portal
index/profile/asset packaging integration belongs to the common portal code.

Run the focused source tests without connecting to hardware:

```sh
node --test tests/linux-install-command.test.cjs
```

Tests use synthetic reviewed-release metadata. They do not download or install a
release and do not establish SSH, WSS or physical robot compatibility.
