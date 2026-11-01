# Touch editor on the website and board servers

## Contract — 2026-11-01

Start from deployed main `622c0c09fd0ad942f34048806629c0dd7a62c045`.
Preserve its frozen GP baseline, isolated Linux previews, reviewed JS preview,
and deployment workflow. Reuse the touch UI from iPhone implementation
`e10a5ee90bd2f5b04b6bc9245d806764c3df2483` and official JS editor pin
`5564b1e42d6790360450ebf11c9eb33a1c6877f2`; do not merge unrelated staging/SFC work.

Behavior:

- Detect a touch/mobile device and offer the optimized editor. Provide an
  explicit desktop/touch choice and remember an explicit choice when storage
  is available. Desktop visitors retain their normal editor. Mode changes
  protect unsaved work and do not overwrite existing GP project storage.
- Publish a self-contained `mobile/` subtree. Keep every existing GP/editor
  asset and JS preview unchanged; only the main landing document receives the
  mobile offer. Do not load the large GP iframe before a mobile visitor chooses
  desktop mode. Keep all runtime editor assets local, with no CDN dependency.
- Retain the 44-pixel targets, collapsible controls, anchored 50–250% pinch,
  panning, block dragging and insertion of the tested touch UI.
- Board-hosted touch mode can explicitly open the same-origin `/ws/vm` on
  supported RLCD, Fruit Jam and XRP firmware. Use the real browser WebSocket
  API, its real Origin, readiness marker, bounded queues and existing compiler.
  Do not impersonate an iOS native bridge or automatically connect to a board.
- GitHub Pages touch mode is available for editing. Its HTTPS origin cannot
  directly use the current plain-HTTP board endpoint or its exact board Origin.
  Offer the board's local website instead. Safari on iPhone has no Web Serial
  or Web Bluetooth path here. Propeller 2 stays desktop USB; P4 wireless stays
  unavailable. BLE, origin/security changes and remote WSS provisioning are
  outside this change.
- Board packaging adds verified compressed mobile assets only when a reviewed
  mobile source cache is supplied. Preserve legacy packaging when it is absent.
  Report flash/resource size changes and preserve bounded HTTP streaming. New
  installed board assets require rebuilding/updating firmware; this task does
  not authorize flashing or erasing a board.

Acceptance:

1. Verify source pins, local/offline assets, allowed landing-page differences,
   existing desktop asset hashes, routes including encoded library filenames,
   and board asset manifests. Never silently omit missing mobile assets.
2. Exercise mobile detection, explicit overrides, repeated mode/menu changes,
   project protection, six phone sizes/orientations, real gestures and browser
   connection limitations. Distinguish browser emulation and physical testing.
3. Check real same-origin browser WebSocket programming against the actual
   SmallVM over a loopback fixture, including version/ping, compiled result,
   CRC, stop/reconnect, interrupted links and a rejected foreign origin.
4. Run the repository validator and exact-head CI. For firmware changes, retain
   actual build evidence or state **not compiled**. Do not claim physical PASS.
5. Deploy Pages only through the existing supported workflow after confirming
   the live/default source has not advanced. Do not merge unrelated work,
   change repository/environment security, acquire credentials or overwrite a
   newer live version. Report any such blocker precisely. Verify the live
   entry points and retain screenshots if deployment succeeds.

## Mobile usability follow-up - 2026-11-01

Start from published `a651529d24c3f7ae10c6f9f5acd884c1dda57641`.
The supplied screenshots show French selected while mobile chrome stays English,
and clipped palette blocks with truncated category names. Keep the pinned engine,
desktop editor, transport and security policy unchanged. Bind mobile text and
accessible labels to the existing locale lifecycle; use official translations
where available and supplementary French, German and Spanish phone strings,
with an English fallback for missing translations. Preserve project text and
language preference across reloads.

Provide a visible 44-pixel palette resize grip, keyboard resizing, a temporary
wide palette, and readable category/library names. Retain workspace space and
collapse the palette after a successful block drop. Clamp widths after rotation.
During pinch, change the scene scale continuously using cached block drawings;
relayout text once on lift. Do not reset an unchanged canvas or present a cleared
bitmap between scale and pan. Navigation must not sync code to the VM.

Acceptance: actual browser language switching/reload, long names and blocks,
resize gestures, six phone sizes/orientations, continuous pinch frames, anchor
accuracy, limits, cancellation, one-finger continuation, and block drag/insertion
at several scales. Run the validator, existing browser/transport tests and
exact-head CI before publishing through the existing main-only Pages workflow.
Verify public asset hashes and behaviors after publication. Browser emulation
does not establish physical iPhone frame rate or Safari device behavior.

## Build and use

The shared source is `web/js-editor/iphone-*`; `web/mobile/` adds the explicit
browser transport, local loading and layout choice. The immutable official
engine remains byte-for-byte unchanged. Prepare the reviewed cache once:

```sh
python tools/prepare_mobile_editor.py --archive build-artifacts/reviewed.zip --output build-artifacts/mobile-source --fetch
```

For board firmware, either place that verified cache at
`IDE_SOURCE_DIR/mobile-editor`, or add
`-DMOBILE_EDITOR_SOURCE_DIR=/absolute/path/to/mobile-source` to the existing
board's documented `west build` command. The three packager CLIs also accept
`--mobile-source`. They never fetch assets themselves. An explicitly missing or
corrupt cache fails packaging. With no cache the existing desktop payloads and
root entry remain intact. `/mobile/` and `/mobile/index.html` open touch mode;
`/?layout=mobile` and `/?layout=desktop` explicitly choose a layout. On a board,
`/microblocks.html` retains the desktop editor and offers a touch-mode link.
Private browsing may prevent remembering a choice, so the explicit URLs work
without local storage. Editors keep their own project stores; export/import a
project to carry work between them. Cancelling a switch keeps the current work.

For Pages, the existing `pages.yml` builds its same frozen GP and reviewed JS
previews, then runs `tools/add_mobile_web.py`. The compositor refuses to alter
any previous asset except the root landing document. `/mobile/index.html` works
directly; the root offers it on mobile. `?layout=desktop` preserves the usual
desktop portal, with a visible touch-mode switch. Unsupported P2, P4 and Linux
targets retain explicit guidance instead of opening an unrelated board link.

Board packages add 571 files and about 2.75 MB compressed, for about 6.26 MB
total. Generated descriptors rise to roughly 720. These are asset verification
results, **not compiled firmware** or a final RAM/flash linker result. The
existing 2 KiB streaming limits and WebSocket Origin rules are unchanged.
The Fruit Jam root route change and optional CMake arguments are explicitly
recorded in `evidence/mobile-web-firmware-uncompiled.json`; historical compiled
evidence is preserved rather than relabelled as current validation.

## Publication gate

On 2026-11-01, read-only inspection of the existing `github-pages` environment
showed **Selected branches and tags: main, one branch allowed**. Feature-branch
deployment is therefore blocked by that existing policy. No deployment was
attempted, no environment/security setting changed, and no merge was performed.
After approval to merge this isolated mobile change, the normal main-push Pages
workflow can publish it. Recheck the live/default source before doing so; do not
replace a newer release. Board firmware still needs a separate build and
explicit authorization before any installation.

## Native browser protocol fixture

`prepare_mobile_vm_test.py` uses the approved Linux source pin without modifying
that checkout. The normal editor sends v417 `deleteAllCodeMsg`, whose runtime
cleanup calls `primMBDisplayOff(0, NULL)` outside a task. The pinned headless
display stub treated that housekeeping call as a hardware failure and left the
global error for the next real script. The fixture permits only that absent
display cleanup. Explicit display calls still fail; the native self-test checks
both paths. The overlay is hash-guarded and recorded in its source/build
manifests. Arithmetic, compilation, CRCs, task execution and WebSocket traffic
remain real. This does not update a Linux release or claim board hardware works.
