# Matrix project save/reopen checkpoint

The local GP-slot overlay now preserves the custom matrix library default
through the complete upstream project serializer. A regression first showed
that workspace pixels survived while `specDefaultString` dropped the default
for an unknown slot type. Only `unoqMatrix` now uses upstream String quoting;
the other slot types and the pinned upstream source remain unchanged.

Seven focused checks in `tests/js-project-roundtrip.test.cjs` use actual
upstream project, parser, block and compiler classes in fresh contexts. They
cover repeated canonical saves, all eight brightness digits/leading zeros,
script positions, palette defaults/copy isolation, seven modules, 141 functions
and compilation of 144 functions/scripts with no VM connection.

Fred completed the native Save dialog manually and reported that he saved
ProjectRoundtrip.ubp in Documents, then returned control. Windows' Documents
known-folder setting located the existing file; its bytes matched the canonical
project exactly. No download or Save action was repeated after that handoff.
The 38130-byte file has SHA-256
`a413df58ad324f6e44901a8d7105aded21548a0a20025ddc6251f8f19ec6285e`.
The original file was not modified. The copy here is the same self-contained
non-hardware fixture whose contents were generated independently.

The exact bytes were copied into the owned static fixture directory and opened
through the actual Project -> Open from URL UI. The restored project name,
mixed matrix, palette default, typed reading, arithmetic and all seven library
categories were visible. `downloaded-reopened.jpg` is the actual browser capture;
the earlier `generated-project-reopened.jpg` records the generated fixture.
`file-and-gui-receipt.json` records hashes and the manual/automated boundary.

Automatic download-event and clipboard calls timed out before handoff. The
earlier static server was later confirmed absent; its cause was unknown. A
visible read failure and historical fetch/icon errors occurred before the
server was resumed. Only after confirming the old process stopped was the
same loopback-only endpoint restored; the saved project then returned HTTP200
and opened. This is not an error-free initial-load claim or automatic native
file-dialog acceptance. `cleanup.json` confirms the recovery server stopped.

The full-validator result and source snapshot are recorded separately in this
folder after completion. Assertions, deadlines and exclusions stay unchanged.
`package-receipt.json` identifies the verified pinned package and local overlay.
`p4-assessment-source-hashes.json` binds the read-only
[P4 plan](../../../docs/JS_P4_INTEGRATION_PLAN.md) to preserved sources only.

No VM, robot, P4 or UNO Q connection occurred in this slice. Existing Pi
execution evidence remains from the earlier checkpoint. Autosave, clipboard,
undo/redo, arbitrary sizes and other projects remain separate acceptance gates.
Main, GP, the protected P4 owner checkout and paused SFC were not changed.
