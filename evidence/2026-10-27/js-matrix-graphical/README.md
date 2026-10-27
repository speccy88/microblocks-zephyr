# Scoped graphical acceptance and GP matrix adapter

The pinned JavaScript editor was operated in a new in-app-browser tab through
a private loopback bridge to the real Raspberry Pi SmallVM. This is scoped
graphical acceptance, not full editor parity or physical MicroDuck/UNO Q tests.

## Observed browser and Pi checks

- The actual Add Library picker imports the coherent six-module MicroDuck bundle.
- The health wrapper reports that JSON-RPC is not configured; the typed head IMU
  wrapper returns an explicit error record. Missing services are not zero data.
- Legacy predicate entries appear after the overlay fix; configured? evaluates
  to false on the real Pi.
- A separate identity-function fixture renders the fixed 13x8 matrix. Dragging
  a palette block, painting its first pixel and evaluating it returns the
  edited ordinary String on the Pi without changing the palette template.
- The preset menu opens, Clear affects only the workspace instance, and its
  next evaluation displays the 104-zero String.

The seven raw JPEG screenshots are byte-preserved browser captures; their
hashes and sizes are in `screenshots.json`. `js-gui-import.jpg` shows the six
modules; `js-gui-predicate.jpg` shows false; `js-gui-head-result.jpg` shows the
error record. `js-gui-matrix-value.jpg` and `js-gui-matrix-zero-value.jpg` show
the actual Pi results before and after Clear. Original capture filenames had
`.png` extensions despite JPEG encoding; these copies correct only the suffix.

`gui-input-hashes.json` verifies 570 GUI assets and the pre-existing Pi VM
binary. `gui-scope.json` states the exact scope and final delta. The test-only
`matrix-fixture.ubl` is not shipped; it uses no native UNO Q primitive. The
production package is identified separately in `static-package.json`.
`browser-errors.json` contains the final error/warning snapshot (empty).
`cleanup.txt` records that this session's VM and bridge stopped. The temporary
Windows SSH forward was identity-checked and stopped too. Existing GP sessions,
security/network settings, P4 hardware and paused SFC work were not changed.

## Reproducible checks and limits

The final unchanged validator passed **473 tests, zero failures and zero skips**
in 214.618 seconds (216.125 seconds including the validator wrapper).
`full-validation.log`, `full-validation.json` and `validation-summary.json`
record the final run. All 2028 captured input files were hash-verified against
the Linux replica; `validation-inputs.json` retains that snapshot. This README's
final-result wording and new receipts were added afterwards; executable/test
sources were unchanged. Text logs use LF; `log-normalization.json` preserves
their original and saved hashes.

The seven matrix checks use actual pinned upstream classes with a headless
DOM/canvas fixture: strict 104-digit String validation, six exact GP presets,
cell boundaries/gaps, copy isolation, interpolated strokes, scaled geometry,
legacy predicate palette inclusion, parsing and literal compilation.
The final guard that ignores an initial gap press was added after the GUI
checks and covered by the headless regression; it was not repeated graphically.
The focused migration suite contains eight Python tests, including the actual
compiler/compatibility (10), library-import (8) and matrix (7) Node checks.

An earlier complete full-validator run passed 473 tests with no failures or
skips before the final gap guard. A later run was interrupted by connection
loss and confirmed absent before recovery. The first recovery stopped during
preparation because documentation no longer matched its captured hashes; no
tests ran in that attempt. The final result and exact input hashes are retained
in separate receipts/logs here. Test assertions, deadlines and exclusions were
not weakened. Local Linux native tests rebuild disposable native test executables
and also exercise a verified existing ASan/UBSan binary. The production Pi VM
and Zephyr targets were not rebuilt. `preset-provenance.cjs` separately compares
all six presets with the hash-verified GP virtual source; its result is in
`preset-provenance.json`.

Graphical save/export/reopen/autosave, undo/redo, continuous drag strokes, all
presets/zoom levels, arbitrary matrix dimensions, remaining positive service
paths and physical robot/UNO Q acceptance remain unverified. No motion, BLE
secrets, runtime upgrade, publication or shared-main change was performed.

The pre-commit branch/remote/worktree inventory is `branch-inventory.json`.
It distinguishes the already committed ARM64 work, preserved GP history and
the independently owned P4/SFC checkpoint whose latest status is uninspected.
No push was attempted; remote tracking refs are cached observations only.
The read-only connected GitHub check in `repository-metadata.json` confirms
the configured repository is public; it does not authorize a push.
