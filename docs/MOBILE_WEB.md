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
