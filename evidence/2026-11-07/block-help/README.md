# Shared custom block Help validation

803 custom selectors have authored reference entries. The actual pinned
`BlockMorph.hasHelp()` and `BlockMorph.openHelp()` methods were exercised in
the repository's headless DOM/canvas fixture against all 803 selectors. Every
call selected the correct encoded local help URL and `_blank` target. Upstream
`setUserLED` Help remained unchanged, and the project identity and dirty flag
were unchanged. A new primitive-only library received the explicit fallback.

This is **headless logic evidence, not graphical/browser acceptance**. The
supported UI tool reported no available browser. Native context-menu rendering,
real new-tab navigation, keyboard focus, mobile readability and visual layout
were therefore not verified. No raw browser-control workaround was used.
No board was connected, reset, flashed or programmed for these checks.

Commands run:

- `python tools/block_help.py`: 803 selectors validated.
- `python tools/validate.py`: 707 total tests, 305 executed/passed and 402
  explicitly skipped (OK).
- `node tests/block-help.test.cjs`: safe text rendering, routing, fallback and
  project nonmutation checks passed.
- `node tests/block-help-engine.test.cjs <composed-test-site>`: actual pinned
  engine hooks passed for all 803 selectors, headless only.
- `python -m unittest discover -s tests -p test_block_help.py -v`: five tests
  passed, including missing-content build failure and deterministic cache keys.
- `node tests/p2-usability-compile.test.cjs <composed-test-site>`: all 82
  functions compiled, all 47 palettes imported independently with automatic
  dependencies, and the usability fixture compiled to 100 chunks/14 scripts.
  Monolithic function objects/IDs and old five-library/subset/mixed layouts
  were preserved; explicit refresh produced 82 unique functions.

The composed local test package's help assets, script tags, file index and
build receipt were refreshed and checked. All 31 pinned engine hashes were
unchanged. `results.json` records exact help asset hashes, pinned engine hashes
and skip reasons. The full catalog loads only in a help tab; the editor loads
the small selector index plus the hook. Authored strings use text nodes rather
than HTML, and opening Help neither executes examples nor changes a project.

Full validation logs remain outside the repository. The skips primarily require
Linux private sockets/process/filesystem semantics, real native VM toolchains,
pinned upstream source caches or optional dependencies unavailable here. A
passing offline suite does not replace those skipped checks or hardware tests.

Publication preparation was repeated on the verified remote base `a8dd0bf`,
with only the Help/Smart Pins diff. The original local `eb53dc1` history was
preserved. Unpublished volatile-toolkit, VM, firmware, hardware-status and CI
changes were excluded; the Help features have no dependency on them. The
initial Windows checkout converted pinned source files to CRLF; their original
LF bytes were restored and the complete suite passed without changing hashes
or weakening checks. The 707-test result above is for this isolated tree.

The user authorized GitHub access and fetch succeeded. This pre-publication
evidence does not yet claim push, CI, deployment or live-site success. Normal
push-triggered CI is distinct from a manual Pages retry; no manual retry or
board access was performed.
