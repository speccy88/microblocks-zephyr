# Phone workspace and touch contract

Follow-up to the initial iPhone slice, 2026-11-01. Use the pinned real editor
and local overlays; preserve its blocks, colors, project format and wireless
adapter. The supplied mobile Scratch image is a layout reference only.

## Behavior

- One 48-pixel toolbar uses small icons on targets at least 44 pixels square.
  Menu opens the original Project, Settings and Language controls. Blocks
  toggles the category/palette area in either orientation. View tools holds
  undo/redo and discrete zoom. Each toggle exposes its expanded/pressed state.
- Hide controls maximizes the workspace. A persistent 44-pixel Show controls
  button restores it. Stop stays available when a verified link exists.
  Dialogs and menus remain scrollable on short screens.
- A finger on empty scripts space pans. A finger on a block keeps the normal
  drag/edit behavior. Hand mode pans over blocks. Two fingers pan and pinch
  around their midpoint using the engine's real scale, limited to 50–250%.
  Scroll bounds follow the existing editor. Navigation never writes VM code.
- A second finger before a block is grabbed converts the pending touch to
  navigation. During an actual grab it cannot reinterpret or prematurely
  finish the drag. Cancellation/rotation/backgrounding clears pending gestures
  and long-press timers; an interrupted grab finishes at its last location.
- Successful palette drops collapse the palette, including insertion into an
  existing stack. Scrolling the palette, failed drops and editing keep it open.
- The connection sheet stays open during an attempt, shows asynchronous native
  errors with retry, and cancels an unfinished attempt when closed. Only the
  verified VM handshake closes it automatically; socket readiness is insufficient.

## Acceptance

Exercise trusted touch events against the actual pinned engine at narrow and
large phone dimensions in both orientations. Check menu/palette/focus cycles,
touch sizes, viewport bounds, pan and anchored pinch, zoom limits, coordinate
accuracy, project serialization, block drag and stack insertion, palette
scrolling, interrupted gestures and repeated connections. Check navigation
does not call script synchronization. Keep browser emulation, Simulator tests
and physical acceptance distinct. No physical phone or board is available in
this Windows task; no hardware is flashed or contacted.

The native Simulator CI must compile and run the app, retain the existing
WebKit/native private-address validation test, and cover collapsing/restoring
controls and a real pinch. Changes are committed and pushed on the existing
feature branch, with remote SHA and exact-head CI verified before handoff.

Local [validation](../evidence/2026-11-01/iphone-touch/validation.json) and the
[six-size touch report](../evidence/2026-11-01/iphone-touch/touch.json) retain the
tested overlay hashes. Captures show the [workspace](../evidence/2026-11-01/iphone-touch/375x667.png),
[labeled menu](../evidence/2026-11-01/iphone-touch/menu.png),
[palette](../evidence/2026-11-01/iphone-touch/palette.png), and
[hidden controls](../evidence/2026-11-01/iphone-touch/focus.png).
All captures use desktop emulation. Native results belong to the matching
commit's CI run and its small/large Simulator result bundles.
