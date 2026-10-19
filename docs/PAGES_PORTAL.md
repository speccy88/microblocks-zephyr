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
