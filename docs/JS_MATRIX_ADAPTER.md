# GP slot adapter and first graphical JS acceptance

The local `legacy-slots.js` overlay now exposes legacy `b` palette specs as the
JavaScript editor's reporter blocks and implements the fixed UNO Q 13x8 matrix
input. Upstream engine files and the existing VM/GP source pins stay unchanged.
No UNO Q primitive-set number is registered and no board is contacted.

## Preserved representation

The matrix remains an ordinary String: exactly 104 digits `0` through `7`, in
row-major order, with leading zeros preserved. The inspected GP implementation
is `/runtime/lib/UnoQMatrixSlot.gp` in the pinned UNO Q asset package, commit
`70690291ac44a5c3a50dce572ee0c29ba99dc57f`. Its source SHA-256 is
`136d38e226d44811d551ad9d780557492e3c7a6ef9ef4911fc5338ecf8966b0c`.
Both containing WASM-package asset hashes were verified before inspection.
See `dependencies/unoq-matrix-gp.json`, also included in the candidate package.

Null/empty initializes a clear pattern. Invalid types, lengths, digits or
trailing newlines leave the previous pattern unchanged. The port retains all
six presets, GP's one-based hit-test indices, cell-gap/dropdown exclusion,
interpolated strokes, independent copies and 152x86 scaled layout. It uses the
upstream slot's existing default/copy/printing dispatch through a subclass;
parsing and compiling still consume a plain String. The original `b` spec is
also retained in the project/library data: the palette adapter maps a copy.

This is the inspected fixed-size widget. It does not implement or make claims
about any later arbitrary-size matrix variant, new pixel object, transport,
UNO Q firmware, LED brightness/current, timing or physical display behavior.

## Tests and actual graphical scope

Seven focused matrix checks use actual upstream block/parser/compiler classes
with a test-only DOM/canvas fixture. They verify strict validation, exact
presets, boundaries/gaps, scaled drawing of 104 cells, copy isolation, stroke
interpolation, legacy palette inclusion and print/parse/literal compilation.
The final initial-gap-press guard is covered by this headless regression;
the following GUI checks exercised valid cells and menus, not initial gaps.

Real in-app-browser testing used a separate loopback bridge and private real
Pi VM with no gateway. It did not touch existing GP sessions, the paused SFC
work, P4 or UNO Q hardware. Observed checks:

- Add Library lists the MicroDuck bundle; importing displays all six modules.
- The imported health wrapper executes and displays its explicit unconfigured
  JSON-RPC error. The typed head-IMU capture displays an error reading record.
- The initially missing `b` entries are visible after the local adapter; the
  gateway-configured predicate executes on the Pi and visibly returns false.
- A separate, non-shipping identity-function fixture displays the 13x8 matrix.
  Dragging it from the palette, painting its first pixel and evaluating it
  returns the edited String through the real VM. The palette copy stays intact.
- The actual preset menu opens. Clear changes only the workspace image; its
  next Pi evaluation displays the zero String. Screenshots are retained.

The fixture has no hardware primitive; it returns its input String. The GUI
entry/asset overlay is labelled separately from the deterministic package.
An informational v417-versus-v421 version notice was dismissed; no firmware
update, warning bypass or new runtime was attempted. Browser developer logs
show no error/warning entries after the adapter checks.

Desktop disconnects interrupted an initial launch before process creation and
a later final-guard validation run. Processes and receipts were checked before
resuming. An earlier complete run passed 473 tests; the final source snapshot
and its validation outcome are recorded separately in the evidence index.
The private VM, bridge and identity-verified SSH forward were subsequently
confirmed stopped. No new credential, service or security/network setting was
created. The historical blocked Edge action was not retried: this acceptance
used a newly identified in-app-browser tab and a known private URL.

## Remaining acceptance

Graphical save/export/reopen/autosave, undo/redo, continuous drag strokes,
all presets/zoom levels, dynamic dimensions and real UNO Q deployment remain
unverified. Full MicroDuck graphical coverage and positive remaining daemon
paths remain separate tasks. The import picker's bundle description currently
reflects its last module; it does not yet provide a combined bundle synopsis.
The scope above must not be presented as complete editor or hardware parity.

Run `node tests/js-matrix-slot.test.cjs /verified/js-editor-package` for focused
checks, or the repository validator with the pinned JS cache and Node available.
See [evidence](../evidence/2026-10-27/js-matrix-graphical/README.md).
