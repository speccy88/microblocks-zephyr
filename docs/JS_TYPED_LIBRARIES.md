# Typed MicroDuck libraries in the JavaScript editor

The staged Linux package now generates the `files.txt` index required by the
official JS library browser. Its `Libraries/MicroDuck Linux.ubl` entry is one
coherent import containing the existing MicroDuck, Head IMU, Depth, Gamepad,
Robot and Pad IMU modules. Importing it is a user action. The package adds no
auto-import or auto-start hook; upstream connection/project synchronization
behavior remains in force.

The six library sources remain byte-identical, including authors, descriptions,
versions, units, error semantics and confirmations. Separate exact sources are
included under `sources/microduck/`; `microduck-libraries.json` records their
hashes and byte offsets in the combined import. The upstream JS source pin and
all engine files remain unchanged. A missing MicroDuck function dependency now
raises a compiler error instead of silently compiling a dummy zero.

The intended picker flow is **Add Library -> MicroDuck Linux**. The actual
editor filesystem lists that entry and its actual `openLibraryFile` import path
has been exercised headlessly. Graphical clicking, appearance and save/restore
acceptance remain unverified. The import bundles dependencies together; do not
mistake an individual source copy for the complete library bundle.

## What was verified

The pinned `MB_editor.openLibraryFile`, `MB_Project`, `MB_Parser`, block morphs,
function representation, compiler, code manager and connection implementation
are used unchanged. A test-only DOM/canvas fixture supplies layout surfaces;
it does not render meaningful pixels, replace parsing/compiler methods, or
establish graphical acceptance. All six modules and 140 functions import and
compile; the largest compiled function is 400 bytes, within the stock 1000-byte
limit. IDs are distinct and all functions receive real VM CRC acknowledgements.

The real Pi executes imported wrapper blocks through the existing v417 VM:

| Input/path | Observed behavior |
|---|---|
| Fictional JSON-RPC health snapshot with battery percent zero | `ok`, integer `0`, unit `0.01%`, origin `simulation` |
| Snapshot without battery | `unknown`; known-value predicate is false |
| Health object without JSON-RPC envelope | `invalid`; it is not silently accepted |
| No configured gateway | Head IMU, depth, gamepad, robot health and pad IMU capture wrappers return typed `error` records |
| Normal read-only depth adapter with fictional tofd stream | 1000 mm at row 1/column 1, `no_target` at row 1/column 2, origin `local_ipc` |
| Normal read-only gamepad adapter with fictional padd stream | Declared axis **code 0** reports raw 1583; unreported code 1 stays unknown |

`local_ipc` identifies the transport, not a physical sensor. The source fixture
identifies its device as simulated; no actual MicroDuck, gamepad, movement,
camera or BLE path is used. Code 0 is a Linux input code here, not a one-based
axis ordinal. Captures are explicitly released; absent data is never coerced
to zero. Existing protected sound/skill functions are compiled/uploaded as
part of the unchanged base library, but are not executed by these tests.

## Reproduction

```sh
python3 tools/package_js_editor.py --source /exact/pinned/git-cache \
  --output /new/path/js-editor
node tests/js-typed-libraries.test.cjs /new/path/js-editor
JS_EDITOR_UPSTREAM=/exact/pinned/git-cache NODE_BINARY=node \
  python3 -m unittest discover -s tests -p test_js_editor_migration.py -v
```

For a private real Linux VM, `tests/js_editor_pi_probe.py --typed-libraries`
selects the typed-block probe; adding `--simulated-sensors` starts only the
existing fictional sensor fixture and a mutation-disabled normal gateway.
Supply its other explicit root/binary/digest/environment arguments as described
in the script. It creates no service, credentials, firewall rule or networking
configuration, and stops only its own child processes.

See the [typed migration evidence](../evidence/2026-10-27/js-typed-libraries/README.md).
Remaining work includes graphical library/project acceptance, GP portal and
custom-slot migration, mediad's separate camera/audio limitations, independent
P4 consolidation and physical MicroDuck commissioning. This slice changes
neither shared main nor the paused SFC work and publishes no release.
