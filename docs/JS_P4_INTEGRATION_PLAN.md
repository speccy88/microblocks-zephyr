# P4 integration after the JavaScript project round trip

Follow-up: [service integration](JS_P4_SERVICES_SPEC.md),
[inline media](JS_P4_MEDIA.md), and [owner-source readback](JS_P4_OWNER_READBACK_SPEC.md)
now have local implementations and fixture tests. The owner’s sealed fe01c3fb
source has been reconciled in the migration branch; see
`dependencies/p4-native-owner.json` for provenance. Physical JS acceptance and
a new Zephyr build remain outstanding.

The remainder records the earlier assessment at
`279321173eff14a4c4fadbc58f33818184579cc4` and its acceptance plan. The protected
owner checkout, COM5/COM12, physical board and paused SFC work were not accessed.
No new hardware validation is claimed by this assessment.

The official JS engine remains pinned to `5564b1e42d6790360450ebf11c9eb33a1c6877f2`.
The GP preservation branch and SmallVM v417 pin remain separate. Keep adapting
through local overlays and guarded hook contracts, rather than editing cached
upstream files or replacing the runtime for an editor migration.

| Boundary | Preserved implementation and required next work |
|---|---|
| Library syntax | `P4_Camera.ubl` is ordinary `.ubl` syntax. Import and save/reopen its functions/specs with the actual JS parser. Test native names and every emitted argument; merely seeing a palette is insufficient. |
| Native namespace | `image_primitives.c` registers `p4` as `IOPrims` (set 3). The Linux profile also uses set 3 under `linux`, with a different platform's entries. Keep `p4` rejected by the Linux profile. Add a separately identified P4 profile only after board/VM capability verification; do not globally add an alias. |
| Wire transport | Existing image preview and inline snapshots share the VM byte stream. JS `MB_connection.processMessages()` currently has no P4 extension dispatch. Add a bounded adapter for the documented messages after negotiating capability/session; preserve ordinary VM parsing, ordering and reconnect behavior. |
| Reusable core | `web/p4-media-core.js` is independent of GP and already defines bounded metadata, RGB/grayscale/RGB565 conversion, WAV packaging, cache disposal and packet 208 encoding. Reuse its existing portable tests before adapting browser consumers. |
| GP-specific bridge | `web/p4-media.js` currently creates `MicroBlocksPortal.EditorAPI(GP, document)` and calls `p4.media.*`. `tools/patch_p4_media.py` injects those endpoints into GP, plus compiler, block-layout and step hooks. These routes do not exist in the JS editor; importing this script alone cannot provide inline results. |
| Compiler tracing | GP wraps visible producing expressions with `mediaSnapshot(handle, site, session)`, preserving return values and evaluation order. A JS counterpart must give each visible block an ephemeral site ID, handle nested transforms and library calls correctly, and leave disconnected compilation unchanged. No global latest-image substitution. |
| Actual block rendering | Port `web/p4-media.gp` result views to the actual JS block/Morphic layout. Preserve aspect ratio, expansion/collapse, dragging, clipping, deleted blocks/undo history and bounded disposal. A separate HTML gallery does not establish this requirement. |
| Project lifecycle | Keep pixels, PCM, URLs, site/session IDs, textures and cache state outside `.ubp`, copied scripts and autosave. Fresh load/reconnect starts with no cached result. The new matrix default regression demonstrates why custom fields must be tested through the complete serializer, not a block-only print/parse test. |
| Camera/audio acceptance | Real PPA/camera/audio behavior and remote transport require the owner's existing firmware/evidence plus new physical tests. Do not record, play audio automatically, move hardware or assume board-hosted HTTP/WSS is operational. |

Retain the existing resource contract: four immutable native snapshots within
512 KiB, image thumbnails at most 160x90, audio at most eight seconds of 16 kHz
mono PCM, 512-byte reads, and session/site/token checks. Browser cache limits
remain eight entries, two audio clips and 1 MiB of accounted media. Messages
208/209 are not new ports and do not justify opening another connection.

## Coordinated sequence and acceptance

1. Obtain the owner's exact P4 commit/dirty checkpoint and preserve it on GP,
   without resuming SFC. Rehearse integration in a separate worktree; keep main.
2. Add parser/compile/save/reopen fixtures for the P4 libraries using mocks and
   the real JS classes. Preserve Linux rejection of P4 primitives and unchanged
   source pins. Do not connect the board during this first slice.
3. Negotiate and test bounded frame dispatch with protocol-faithful fixtures:
   malformed sizes, old sessions, partial reads, interleaved VM replies,
   disconnection, timeouts, eviction and cancellation.
4. Adapt compiler and actual block views together. Test distinct nested output
   sites, original-handle release, repeated execution, collapse, deletion/undo,
   viewport/zoom and project replacement. Assert no media/session data enters
   saved project text or autosave; require actual graphical evidence.
5. Coordinate physical P4 USB and any board-hosted/WSS acceptance separately.
   Native processing evidence and GP renderer tests remain useful but cannot
   stand in for the new JS rendering and transport acceptance.

See `boards/waveshare_esp32p4_wifi6/docs/INLINE_RESULTS.md` for the existing
ownership, lifecycle and physical-evidence boundaries. The dated source-hash
receipt records exactly which preserved files this assessment inspected.
