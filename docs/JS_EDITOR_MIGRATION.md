# JavaScript editor staging and upstream updates

The migration now has a local `gp` preservation branch and a separate
`codex/js-editor-migration-20261027` worktree. Both started at
`3905dc1808f65dad65d5a37b05990f74cc4fca83`, including the existing Pi/MicroDuck
work and all commits in this clone's main. Main remains
`af742e8d34b194603182a303e07c130859f0cf8c`; remote main was
`9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226` at inspection. These are local
preservation/staging refs, not published branches or a completed main migration.

## Independent source pins

| Component | Exact pin | Strategy |
|---|---|---|
| Official JS editor | `5564b1e42d6790360450ebf11c9eb33a1c6877f2` | Codeberg `dev` snapshot; `dependencies/editor-js.json` |
| Existing GP 2.5.8 assets | `70690291ac44a5c3a50dce572ee0c29ba99dc57f` | Existing manifest unchanged; retained on `gp` and staging |
| Existing SmallVM v417 | `2071df569623ba9cdcd6f8106b61796e047df38b` | Existing source pin, port and binary unchanged |

The official source is [MicroBlocks/smallvm](https://codeberg.org/MicroBlocks/smallvm).
At this JS pin the source is under `chromeApp/webapp/engine/`; the former
`snapBlocks/` location no longer exists. Do not use the moving hosted preview
as a reproducible build input. The source manifest records 550 blobs, paths,
sizes and hashes. The generated package includes a manifest of every output.

Upstream engine files remain byte-identical. A separate `linux-compat.js`
extends the port and creates a private primitive-set map (`linux`=3,
`microduck`=22). Unknown named sets fail visibly. A changed upstream layout
or HTML integration anchor stops the build/integration instead of guessing.
The generated entry page permits HTTP only for the existing `127.0.0.1`
loopback bridge; remote HTTP retains upstream's HTTPS redirect. No browser,
firewall, SSH or server security setting changes are involved.

The local port accepts the bridge's single `ready` control marker, then only
binary frames. It waits for readiness, caps each frame at 4096 bytes, received
data at 128 KiB and queued socket output at 32 KiB. It performs no discovery
or automatic connection. Use **Connect local VM** on the experimental page.
**Close local link** closes the link without the stock editor's explicit
disconnect action that starts all scripts. Normal editor code still controls
program uploads/start/stop after the user connects.

## Build and inspect without updating anything

Use a source cache containing the exact pinned Git objects. Neither packaging
nor candidate generation contacts the network or executes upstream scripts.

```sh
python3 tools/package_js_editor.py --source /path/to/smallvm-git \
  --output /new/path/to/js-editor
JS_EDITOR_UPSTREAM=/path/to/smallvm-git NODE_BINARY=node \
  python3 -m unittest discover -s tests -p test_js_editor_migration.py -v
node tests/js-editor-compat.test.cjs /new/path/to/js-editor
```

Output must be a new directory; packaging refuses to overwrite existing work.
The existing foreground `linux/arm64/session.py` accepts this package through
`--editor`, using a separately verified SmallVM and a private data directory.
Use a free high loopback port and the existing authorized local-forward flow
when the browser runs on another host. `tests/js_editor_pi_probe.py` shows a
bounded disposable session and stops only its own processes. It is a test,
not a service installer or the eventual MicroDuck deployment product.

Only fixed asset aliases (Libraries, Examples, images, translations, versions)
are resolved from the Git tree. Filesystem symlinks are never followed.
Firmware images, upstream service worker and the GP WASM entry are excluded.
The original `purejs.html` is retained for source provenance; use the generated
`index.html`/`microblocks.html` entry with this loopback package.

## Repeatable upstream sync

1. Fetch a chosen official revision into the separate source cache using normal
   verified Git transport. Record its exact 40-character commit. Do not merge
   the upstream monorepo into this project's runtime tree or update moving
   pins during an ordinary build.
2. Create a review candidate on a dedicated sync branch:

   ```sh
   python3 tools/sync_js_editor.py --source /path/to/smallvm-git \
     --commit EXACT_COMMIT --candidate /new/path/editor-js.candidate.json
   ```

3. Diff candidate versus `dependencies/editor-js.json`. Review source/license
   changes, compiler opcode/primitive layout, connection and parser contracts,
   new imports, storage behavior and the generated HTML anchors. The candidate
   tool never replaces the pin, moves a branch or pushes.
4. Adopt the reviewed candidate explicitly on the sync branch. Package and run
   the full validator, the actual upstream compiler/connection contract tests,
   private real-VM tests, then graphical project/library/save/restore acceptance.
   Recheck custom slots, P4 transport and SFC separately when they are ported.
5. Coordinate integration before merging the tested sync branch. Runtime and
   GP manifests stay independent; a JS editor update does not authorize a VM
   upgrade. Keep local code outside upstream files so future syncs are normally
   a manifest diff plus an explicit compatibility-layer review.

This is a pinned-source overlay workflow. An upstream fork can later host
contributions, but this slice creates no remote fork, remote branches or
publication. Preserve upstream notices and corresponding modified source;
see packaged `THIRD_PARTY_NOTICES.md` and [LICENSES.md](../LICENSES.md).

## Work that must survive integration

The [inventory](../evidence/2026-10-27/js-editor-migration/branch-inventory.json)
records this clone's refs, remote refs and independent sealed owner checkpoints.
Pi staging is 31 commits ahead of the inspected remote main and contains local
main. The original Pi preparation and rehearsal refs/worktrees remain intact.

The separate P4/SFC task's sealed UI/export archive has SHA-256
`eafcd114b3373ae429db8c28404bb8cf99b3cb999c0f499678a1f4224f0459b1`;
its earlier semantics archive has SHA-256
`61fea86c7ad5ea7938bb4337defc60c83d1f2ee8eff6cb7d30a44bff92a14d4b`.
These are independent recovery artifacts, not merged Git commits. Fred paused
SFC work; this migration does not resume, modify or import it. The active P4
checkout and its board/serial ports were not accessed. Owner coordination is
still needed to inventory its latest uncommitted state and integrate any newer
checkpoint. Thus `gp` preserves the complete known clone history, but does not
yet claim to consolidate every independent P4/SFC change.

Before main changes: preserve the owner-approved P4/SFC checkpoint on `gp`,
rehearse its merge in a separate worktree, resolve overlaps without dropping
tests/evidence, and run the resulting GP acceptance. Then integrate the JS
staging branch through an ordinary reviewed merge. Do not reset or force-push
main, rename active owner branches, or delete the GP packaging as a shortcut.

## Remaining acceptance gates

This first profile is Linux/MicroDuck only. Custom UNO Q matrix editing, P4
media preview/message extensions, portal serialization/restore APIs, SFC editor
integration, browser save/autosave/privacy behavior and graphical usability
remain pending. Stock format compatibility alone proves none of those custom
features. Physical MicroDuck service behavior, secure robot access and shipping
self-hosted/WSS deployment remain unverified; no physical motion is enabled
by this headless test. See the earlier
[3.0 assessment](MICROBLOCKS_3_MIGRATION_ASSESSMENT.md) for those boundaries.

The [typed-library slice](JS_TYPED_LIBRARIES.md) now adds a generated file-browser
index and a coherent six-module MicroDuck import. The actual editor import path
and 140 functions have headless/Pi evidence, including typed wrappers over
fictional depth and gamepad streams. Graphical import, save/restore and custom
slot rendering remain separate gates.
