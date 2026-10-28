# Device file manager: shared UI and transport contract

This stage adds a shared frontend to the real editor's **Projects & board →
Device files** entry. The same production assets are packaged for Pages and
the station-hosted editor. The controller and RAM service are installed in the
local USB firmware, with real GP editing and independent COM5 byte readback
verified in [physical acceptance](STORAGE_PHYSICAL.md). Station RAM transfer and
the bounded [SD file manager](SD_FILE_MANAGER.md) now also have physical evidence.
A separate local-only
fixture adapter demonstrates and tests the UI using browser memory; its banner
must always say **Browser fixture — not the board**. It is opt-in, loopback-only
and excluded from Pages/hosted packages. The fixture opens no network connection.

## Acceptance contract

- List canonical paths and byte sizes, show capacity/file slots/per-file limit,
  open strict UTF-8 text or identify binary content, create/edit text, and
  download raw bytes through an explicit user click. Flash remains unavailable;
  SD has the separate bounded create/open/save-as-new contract linked above.
- Preserve native editor styling. A keyboard-accessible dialog uses text-only
  DOM insertion and a textarea, never HTML rendering. Dirty edits require an
  explicit discard before changing selection/closing. Save and overwrite use
  distinct create/conditional-replace semantics. No automatic save or upload.
- File text, credentials and transfer payloads never enter project serialization,
  localStorage, analytics, console logs or URLs. No credential partition is
  browsable. File names follow the existing RAM service's strict path grammar.
- Every operation is bounded: eight files, 8192 bytes per file, 1024-byte chunks,
  one foreground operation, per-request timeout and explicit cancel. Stale,
  duplicate/mismatched or malformed replies are rejected. No automatic retries
  of mutations; uncertain commits block further writes until reconnect.
- Downloads use an opaque `application/octet-stream` Blob and a sanitized
  basename. HTML/SVG/script contents are shown only as literal text or downloaded,
  never executed or embedded. Blob URLs are revoked; all state is cleared when
  the page closes or the transport changes.

## Abstract transport v1 (not a wire protocol)

`request({version:1,id,op,args}, {signal})` resolves an envelope
`{version:1,id,ok:true,data}` or `{version:1,id,ok:false,code}`. IDs are monotonic,
not reused during a client session. Data bytes are bounded `Uint8Array`s; a
USB/WebSocket adapter must encode/fragment them through the existing
controller and enforce the same limits, not open a second connection.

Operations: `capabilities`, `list`, `stat`, `read`, `begin`, `append`, `finish`,
`cancel`. A write begins with path, declared byte length and expected revision
(`null` means create only). Chunks are sequential. Finish commits atomically
and returns a new revision. Reads carry the selected revision for every chunk,
so concurrent replacement cannot mix file versions. An expired read or changed
file returns a conflict; the UI preserves the draft. A lost finish reply is
uncertain, not success. The native server binds staging to its controller
session, expires incomplete writes and cancels them on disconnect.

The native C RAM core now has per-file revision guards and a controller-owned
dispatcher, with a bounded binary codec and injected JavaScript frame adapter.
The actual JavaScript client is tested against that C implementation through a
synthetic stdio harness. See [the dispatcher contract](STORAGE_DISPATCH.md).
The [controller integration](STORAGE_CONTROLLER.md) now packages the adapter,
routes extension217 through the actual P4 controller and VM, and opens files
only after **Connect files**. Replacing a connection clears pending replies
and detaches an unsaved text draft. The draft stays visible, but cannot be saved
to the new session until the user explicitly discards it and reopens/creates a
file. No extra serial/socket connection is opened.
Generated-adapter/native-bridge tests use synthetic streams. The subsequent
physical acceptance uses the production GP editor, loopback WebSocket bridge
and COM5, without the browser fixture. It does not establish board-hosted Wi-Fi.

## Local-only verification plan

1. Node tests: request/reply bounds, response IDs, path/UTF-8 validation, byte
   caps, staged writes/cancel, revision conflicts, mixed reads, malformed data,
   timeout/late replies, uncertain outcome and safe download names.
2. Actual disconnected GP editor: unavailable state; opt-in fixture list,
   capacity, literal markup, edit/save/reopen, dirty-discard handling, binary
   download, empty/large/invalid text and keyboard/normal viewport behavior.
3. Verify production Pages/hosted assets exclude fixture code. Carry prior
   JSON, automation and storage checks forward; no flash, publication or
   deployment. Capture actual labeled screenshots for feedback.

## Reproduction and current limits

Run `node --test tests/device_files.test.js` and the repository Python validation.
Package normal USB/Pages/hosted assets without any fixture flag. For a separate
local preview only, use `tools/package_p4_ide.py --ide-source <pinned-assets>
--output build-artifacts/p4-files-fixture-editor --file-fixture`, then serve that
directory on `http://127.0.0.1`. The fixture is unavailable on other origins and
cannot be included in a hosted image. Reusing a fixture directory for production
packaging is rejected so stale fixture code cannot leak into an artifact.

The real GP editor has been checked while disconnected: listing and capacity,
literal script text, save/reopen, Unicode creation, dirty-edit protection,
unsafe-path rejection and binary-only display work with synthetic browser data.
The browser download verification was interrupted; completed download bytes are
not verified. Core tests verify the copied download bytes, MIME and safe name.
The later physical USB tests validate create/edit/reopen, capacity, revisions,
session cleanup, exact bytes and RAM clearing on reset. A filesystem mount,
Flash/SD support, large media archive and completed browser download remain
unverified or unavailable. See the [release boundaries](P4_RELEASE_2026_10_26.md).

## Wi-Fi acceptance and local session repair, 2026-10-27

The actual board-hosted editor on the P4 created a unique RAM file, replaced
its text, refreshed the list and reopened it. After the HTTP stress test, a
new file session reopened the same text with an exact string/UTF-8 length
match (52 bytes, including an em dash and accented e). The file was left on
the board. No browser-memory fixture was used. Browser download permission
repeatedly stalled outside the page; the transfer is **not verified** and was
not repeated. Do not confuse the copied download-buffer unit tests with that
missing browser result.

The existing native file lease expires after 30 seconds without a request.
The installed editor failed its first creation after ordinary editing exceeded
that interval; a fresh directory read proved that failed attempt created no
file. Local-only repair now makes a read-only capability request every 10
seconds while the dialog is open and visible, sharing the client's request-ID
and busy guards. Closing/hiding the dialog stops those checks; a check failure
pauses them. An explicit native expired-session reply leaves ready state;
a client-side timeout remains uncertain and is never retried automatically.
Detached drafts remain visible and cannot silently overwrite another session.

The actual UI source is tested with a minimal synthetic DOM/connection for
lease renewal, a busy foreground operation, expiry, draft preservation,
reconnection, explicit discard and timer cleanup. Controller/frame tests use
the native C bridge with synthetic I/O. The repair is packaged in local Pages
and hosted assets. The local station installation below now includes it; it has
not been published.

## Native SD and real graphical acceptance, 2026-10-27

The board-hosted editor's Device files dialog now lists the actual SD MBFILES
directory, creates a unique 60-byte UTF-8 test file, and reopens the same accented
text exactly. An independent COM5 lease then read the same bytes and removed
only that test creation through the native snapshot/content guard. The earlier
native 8 KiB test passed alongside a hash-verified Wi-Fi editor asset transfer;
the SD backend sources are unchanged across the subsequent UI updates.

Real browser testing found a ready-listener ordering bug that synthetic DOM
tests had missed. A next-task startup now waits for the portal panel, with a
regression covering a microtask checkpoint between ready listeners. The active
SD view also has its own persistence banner instead of the RAM volatility text.
Both repairs are installed in the local final pair. See the
[curated evidence](../evidence/2026-10-27/p4-sd-files-summary.json) for exact image
identities, tests and the retained incomplete host-harness receipt. Browser
download remains unverified. The later opt-in
[saved-boot profile](P4_SAVED_WIFI_BOOT.md) verifies automatic station connection
after warm resets, with the same editor assets and no further SD writes.

The subsequent [bounded Wi-Fi recovery profile](P4_WIFI_LOSS_RETRY.md) keeps
the same file-manager assets and SD backend. Loss recovery never replays file
writes or restores a lease automatically. Hardware SD checks in that follow-up
were read-only; initial TCP connection intermittence remains documented.
