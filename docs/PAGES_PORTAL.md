# Browser portal implementation and acceptance contract

The user requested one working `main` branch, a public repository and a GitHub
Pages portal offering the real MicroBlocks IDE over USB alongside board-hosted
LAN IDEs. All verified board work is now a fast-forward ancestor of `main`.

## Publication gate

The reachable-history audit found local user paths, owned device identifiers
and private network addresses in historical acceptance evidence. The owner
explicitly accepted publishing these audited technical details on 2026-10-19.
Preserve the existing repository and history; no anonymization, history
rewrite, force push, rename or replacement repository is authorized. Complete
private Git bundles remain outside Git. No actual password, private key or
token was detected by the audit; scanning is not a guarantee of absence.

The browser file-import acceptance test is blocked by repeated permission
prompts in the automation browser, including after the user selected Always
allow. Do not reproduce that permission loop or bypass it. Named save,
restore and a real downloaded UBP export have separate evidence. This tool
limitation does not establish whether importing works in a normal browser.

The production XRP RP2350 profile is an editing preview. It selects the actual
pinned production XRP library, keeps a separate browser project namespace and
rejects hardware connection before asking for a device or opening a socket.
The separate integrated XRP image now cross-builds SmallVM/Arduino/RM2 and the
native editor with actuators locked. It has not been installed or physically
validated, so the preview still rejects hardware connection. The original
quiet diagnostic remains available. See [XRP parity and acceptance](XRP_PARITY.md).

## Browser and hosting behavior

- Package the hash-pinned real GP 2.5.8 editor, compiler and both board libraries;
  preserve upstream licenses, corresponding GP source and provenance.
- Serve a static HTTPS Pages site built from `main`. Runtime code, fonts and
  other assets are local to the site. No analytics, third-party runtime CDN,
  credential endpoint, telemetry or server project storage.
- Select Fruit Jam or Waveshare before opening that board's editor. A USB port
  is opened only after an explicit user Connect action. One reader/writer owns
  the VM stream, with bounded queues and deterministic disconnect cleanup.
- The HTTPS site uses USB Web Serial, not an insecure WebSocket into the LAN.
  Opening a self-hosted board IDE is a separate direct navigation to the board.
- State plainly that supported desktop Chrome/Edge with Web Serial and a data
  cable are required for USB; an unsupported browser can still edit projects.

## Browser project storage

Use IndexedDB for the user's per-board workspace and explicitly named project
copies. Serialize actual GP project source, including libraries and scripts;
never infer projects from a screenshot or VM bytecode. Autosave changes only
after GP is ready. Restoring or importing requires an explicit user action and
does not automatically open a port. Include explicit UBP import/export and
show storage failures without claiming a save succeeded. Browser data can be
evicted, removed with site data, unavailable in private mode, and is neither
cross-device sync nor a substitute for exported backups. Never store Wi-Fi
passwords in IndexedDB, localStorage, URLs, logs or project files.

## Common USB Wi-Fi setup and persistence

The two board paths need one bounded, versioned USB-local control envelope,
separate from VM code. Probe the board identity and advertised capabilities
before allowing credential submission. Unknown/old firmware must show an
honest upgrade requirement. Reject Wi-Fi control from a WebSocket controller.
SSID/key values exist only in the user's form, a transient USB packet and the
board setup worker; clear transport/form buffers after completion or failure.
Do not automatically read an OS credential store.

Remembering credentials on a board is an explicit checkbox/action, not browser
storage. Preserve the VM program partition and existing settings. Use a
separate configuration partition with atomic records; do not claim encryption
without an actual provisioned key design. A recovery button selects setup
without erasing programs. Firmware replacement needs a target-verified backup
and source/artifact audit. Actual secret entry and any required action-time
device-access approval remain a bundled human handoff after the portal and
firmware are concrete and reviewable. No secret replay while the user is away.

The [portable protocol/storage component](COMMON_WIFI_SETUP.md) now has C source
and synthetic two-slot journal fixtures. It is not linked into either installed
image. Board workers, flash partition mappings, Waveshare USB ownership and
physical credential persistence remain pending; the portal must not advertise
those capabilities based on the portable tests alone.

## Acceptance

1. Verify all fetched upstream assets and notices; build Pages from a clean
   source tree and audit exactly the artifact that will be published.
2. Exercise real project serialization, browser save/list/restore/export/import,
   reload and storage-failure behavior with the actual GP editor.
3. Run protocol/queue tests, then verify the real published HTTPS editor and
   actual Web Serial paths on each positively identified board. A bridge or a
   fake serial fixture does not count as browser-to-board Web Serial proof.
4. Before physical changes, preserve each board's image, program and settings;
   validate USB arithmetic/reconnect and both self-hosted IDE regressions after
   updates. No LEDs/audio/button observations until the user says ready.
5. Confirm Pages deployment and URL, repository visibility, remote `main`
   commit/tree, safe ref consolidation, clean publication audit and remaining
   physical or credential handoffs. Never describe pending work as PASS.

## Native Propeller 2 profile

The P2 profile uses the same real GP 2.5.8 editor and browser project store,
with an independent `propeller2` namespace. Its compiler aliases `p2` to the
existing IO primitive set, and loads `P2_Hardware.ubl` through the original GP
library API. The stackable Smart Pin commands also expose checked boolean
variants for advanced scripts. Firmware reports the exact Eval/Edge/EC32MB
variant; other board identities disconnect this profile.

P2 connects through FTDI Web Serial at 115200 baud with DTR/RTS deasserted.
It has no Wi-Fi provisioning, WebSocket mode or board-hosted editor controls.
This is a native FlexC SmallVM port, without Zephyr or ArduinoCore-Zephyr.
See [P2 installation, pins and physical acceptance](../boards/propeller2/README.md).

Terminal COM12 protocol results establish real VM execution and storage.
Separate [browser acceptance](../evidence/2026-10-19/propeller2/browser-acceptance.json)
now verifies actual Edge Web Serial: arithmetic, live edit, named save,
autosave, restoration after a full reload and execution after reconnect.
The user chose COM12 in the native chooser. The test used the local preview;
it used no simulated provider, serial bridge or full-CDP access.

The shared editor API wrapper counts six seconds of visible-tab time and
cancels its own queued call on timeout. GP processes queued calls from its
animation loop; a hidden tab can suspend that loop. Leaving timed-out calls
in the pinned GP queue caused stale saves to accumulate and could leave a
project-load request waiting to execute after its caller reported failure.
Successful callbacks keep GP's original callback-then-remove ordering.

Offline checks cover visibility changes, bounded retries, cancellation of a
timed-out load and GP response ordering. To exercise the actual packaged GP
serialization source without opening a browser or serial port:

```text
python tools/test_gp_project_api.py --gp /path/to/gp-win.exe --editor build-artifacts/pages/editor/propeller2 --output build-artifacts/gp-project-api
```

The test substitutes the browser editor lookup and response sink, uses a
native GP interpreter, and requires an actual serialized response plus an
equal save/load roundtrip. It is a source-level compatibility check, not
browser storage or Web Serial proof. The later browser evidence establishes
the tested P2 workflows. Native timer functions retain their Window receiver;
the regression test covers the browser's receiver requirement as well as the
queue and visibility behavior. File import/export and external peripherals
still require separate P2 acceptance.
