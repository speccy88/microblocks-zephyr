# SFC in the active JavaScript web editor

The default web editor, phone layout, optional board web assets, Linux JS package
and bundled iPhone editor share `web/js-editor/sfc-core.js` and `sfc-editor.js`.
They extend the pinned upstream JavaScript editor; its engine files and v417
runtime remain unchanged. The legacy GP implementation and branch stay separate.

Choose **Control** for the seven SFC blocks. Create shared variables in
**Variables** first. Select a distinct variable for each step and select shared
Boolean conditions for transitions. Step blocks contain ordinary **setup** and
**loop** command sections. Setup runs once on activation; the loop repeats while
active and yields between completed passes. Only Boolean `true` enables a
transition; numeric `1` does not. Conditions remain true until your code changes
them. Examples are included in the normal project picker under **Examples/SFC**.

Inside a sequence, connect steps using transitions. Put ordinary actions inside
setup/loop rather than between flow blocks. A terminal step needs a transition
to finish the sequence. The single-bar OR split chooses the first true branch
in displayed order. The double-bar parallel split activates all branches. Use
the normal small expansion arrows for two through six branches. Finish every
branch on a step, immediately follow the split with its matching merge/join,
then the next step. AND needs a preceding transition and waits for every final
step's setup plus the common join condition. OR may also have a common preceding
transition. Paired splits can nest, subject to the worker budget.

The compiler reads each guard once per scan, chooses transitions from the old
active set and waits for departing workers to finish an action iteration. Newly
activated steps cannot cascade in that scan. The unchanged portable C engine is
the stable-state reference. Branch charts compile into normal hidden MicroBlocks
functions and private shared variables in the marked `_SFC workers` implementation
module. That module is regenerated at compilation; keep your source in the native
blocks. Save/reopen, undo, locale rebuilds and repeated compilation retain them.

Limits are checked before variable names or code are uploaded: eight step workers
across charts, ten worker/script tasks, 128 shared variables, 256 code chunks,
24 transition edges/guards per chart, and the actual 1000-byte padded wire bound.
Serial sequences use inline code. Branch charts belong in top-level scripts,
outside user functions. Worker actions cannot capture enclosing locals, contain
nested flow blocks, or directly return/stop their task. Unknown actions fail.
Generated `_sfcN_` names are reserved. Every step has one chart owner and step and
guard roles must be disjoint.

While a top-level chart runs, real shared-variable replies color active steps
green. Reads are limited to four per 250 ms and expire after 1500 ms; they are
individual observations, not an atomic snapshot. Stop/error/disconnect/reload
clear the display. Clicking a running owner to stop it also stops its workers
and clears owned public flags through the existing transport. A raw VM stop,
disconnect or error is not a guaranteed output cleanup. A called function or
native primitive that never returns cannot be preempted cooperatively; use
global Stop/reset for recovery. Serial code inside a user function compiles,
but active-step coloring is limited to top-level chart scripts.

SFC does not extend connection support. Pages remains offline editing for the
current plain-HTTP boards. Program through a supported board's own website, or
the native iPhone LAN bridge. Safari has no generic Web Serial/Web Bluetooth
path here. Raspberry Pi's current bridge remains loopback-only; exposing a LAN
listener or changing TLS trust requires a separate reviewed change.

## Reproduce checks

Use a fresh output directory for every evidence run. `EDITOR` below is a
verified packaged JavaScript profile from the reviewed site.

```sh
node tools/test_sfc_js_compiler.cjs "$EDITOR" build-artifacts/sfc-js-compiler
python3 tools/build_sfc_native_fixture.py
python3 tools/test_sfc_branches_vm.py --binary "$SMALLVM" --host build-artifacts/sfc-native/host --reports build-artifacts/sfc-js-compiler --output build-artifacts/sfc-js-branches-vm.json --compiler javascript
python3 tools/test_sfc_native_vm.py --binary "$SMALLVM" --compiled build-artifacts/sfc-js-compiler/serial-legacy.json --output build-artifacts/sfc-js-serial-vm.json --compiler javascript
python3 tests/sfc_js_browser.py --site "$SITE" --output build-artifacts/sfc-js-browser --browser /usr/bin/google-chrome
python3 tools/test_sfc_js_browser_vm.py --binary "$SMALLVM" --editor "$BOARD_HTTP_ROOT" --output build-artifacts/sfc-js-browser-vm --browser /usr/bin/google-chrome
python3 tools/validate.py
```

The mobile CI builds the sanitized real SmallVM, compares all ten branch cases
with the unchanged C engine, and tests real browser WebSocket uploads and live
state. Pages checks compilation and desktop/phone editing before publication.
These are host and browser tests, not physical board or physical iPhone results.
