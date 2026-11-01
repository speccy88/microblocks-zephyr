# Typed MicroDuck library migration checkpoint

This extends the isolated JS editor staging work, preserving the independent
official source pin, GP branch and existing v417 runtime. Shared main, P4 and
paused SFC work were not changed. No publication or hardware action occurred.

## Tested implementation

The package generates the official JS file browser's required `files.txt`.
`Libraries/MicroDuck Linux.ubl` coherently imports six normal modules: MicroDuck,
Head IMU, Depth, Gamepad, Robot and Pad IMU. All six original library byte streams
are retained exactly, with source hashes and bundle offsets. Missing MicroDuck
function dependencies now fail visibly in the local compatibility layer.

`host-import.json` records seven focused checks using the actual pinned editor
file-open/import, filesystem, project, parser, block morphs, functions and
compiler. A DOM/canvas fixture supplies test-only layout surfaces; it is not a
browser and makes no graphical claim. All 140 functions compile with distinct
IDs; the maximum size is 400 bytes, below the stock 1000-byte limit. The earlier
ten compiler/transport checks remain passing. Seven focused Python tests and
the full unchanged repository validator (472 tests, zero skips/failures) pass.

## Actual Raspberry Pi evidence

Both final private sessions use the unchanged ordinary AArch64 VM with SHA-256
`22387aeabb91c99041b13c07a453233496eb80f771881e5143394b1618f24d84`, Node
22.22.2 and the existing verified loopback bridge. Each session uploads all
140 compiled functions with the actual upstream code manager's CRC
acknowledgement. Only the probe's own code/data/processes are touched.

- `pi-no-gateway.json`: twelve executed checks preserve known zero, unit,
  simulation origin, unknown and invalid health data, and typed errors for
  Head IMU, Depth, Gamepad, Robot health and Pad IMU capture without a gateway.
- `pi-simulated-sensors.json`: thirteen executed checks include the same health
  cases, plus normal depth and gamepad adapters backed by the existing faithful
  fictional Unix streams. Results include 1000 mm, `no_target`, `local_ipc`, raw
  axis code 0 value 1583 and false known-value predicate for unreported code 1.

Every final served file and probe/service source is checked against local
SHA-256 values in `pi-input-hashes.json` (597 files). Each receipt confirms its
own children stopped. No sensor value here came from a physical MicroDuck or
gamepad. `local_ipc` describes transport only; the source fixture is fictional.
The normal gateway has mutations disabled and no real robot upstream.

## Failures retained

`earlier-attempts.json` retains the completed failures and diagnostic evidence.
The first health probe supplied a raw object; the VM correctly required the
JSON-RPC envelope and returned invalid. The first gamepad probe requested code
1, which the fixture does not report, then incorrectly attempted extraction.
The VM correctly raised error 32. The final tests use the documented code 0
and explicitly retain code 1 as an unknown-reading case. No runtime check was
weakened. All earlier children stopped before another attempt was made.

## Provenance and remaining gates

`full-validation.json` / `full-validation.txt` describe the final Linux copy
run. Existing verified native code/source and unchanged assertions/deadlines
are used; Node runs through the existing Windows Node/WSL path translator.
`source-checksums.json` binds this slice's implementation/spec files, and
`static-package.json` identifies the deterministic local editor archive.

Graphical interaction, project save/restore, custom GP slots/portal APIs,
positive JS execution of the remaining head/pad IMU and robotd service paths,
mediad transport, physical commissioning and coordinated integration remain
gates. Uploading all functions does not mean executing every function: protected
sound/skill functions are never invoked by this acceptance. No security/network
setting, startup service, OS reboot, physical motion or release is claimed.
No approval, disconnection or process blocks this clean checkpoint.
