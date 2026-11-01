# Project save/reopen and the matrix default fix

The local overlay now preserves `unoqMatrix` library defaults when saving a
project. Upstream `specDefaultString` treats an unknown slot type as nil and
trims trailing nil defaults, so the workspace image survived while a reopened
palette lost its original image. The adapter routes only this custom type
through upstream string quoting and rejects a missing serializer hook.
Other slot types and all pinned upstream engine bytes stay unchanged.

The repository also declares its existing Node utilities as CommonJS in a
private root `package.json`, with no dependencies or install scripts. This
prevents Windows Node from searching beyond a WSL network-share root for a
parent package configuration. The initial full run hit four such UNC lookup
errors; all 65 inspected tracked JavaScript utility files had no static ESM
imports/exports. This metadata changes no browser script or upstream engine.

Seven checks in `tests/js-project-roundtrip.test.cjs` use actual upstream
project/parser/compiler classes in fresh isolated contexts. They preserve a
mixed `01234567` pattern, leading zeros, seven embedded modules (six MicroDuck
plus a non-hardware identity fixture), 141 functions and three scripts. They
check canonical repeated saves, coordinates, independent copies/defaults and
compilation of all 144 functions/scripts while disconnected.

## Actual graphical and file evidence

The fixed editor opened the self-contained fixture from a temporary read-only
loopback server with no VM, board or service connection. Fred completed the
native Save dialog and saved `ProjectRoundtrip.ubp` in his Windows Documents
folder. After he returned control, the existing file was located through the
Windows Documents known-folder setting; its original bytes were left intact.
No download or Save action was repeated after that handoff.

The actual downloaded file is 38130 bytes with SHA-256
`a413df58ad324f6e44901a8d7105aded21548a0a20025ddc6251f8f19ec6285e`,
exactly matching the independently generated canonical project. A byte-identical
local fixture copy was reopened through the actual Project -> Open from URL
command. The saved project name, mixed matrix, restored palette default, typed
depth expression, arithmetic expression and all seven library categories were
visible. The screenshot and file receipt retain this exact scope.

Automatic download-event and clipboard handling had timed out before the
handoff. Neither automation success nor an approval denial is claimed. The
earlier temporary server was subsequently observed stopped; its cause was not
established. A failed URL read was shown rather than bypassed. It was resumed
only after confirming the old process absent, then the same saved file loaded
successfully. Historical fetch errors and partial missing icons during that
interruption must not be reported as an error-free initial page load.

## Boundaries

This establishes one representative save/manual-dialog/file/reopen path. It
does not establish automatic native dialog control, clipboard export, autosave,
browser privacy/storage policy, undo/redo, every project/library, arbitrary
matrix sizes, connected-runtime persistence or physical device compatibility.
The existing real-Pi execution evidence remains from the earlier checkpoint;
this slice connects no VM and runs no robot or P4 command. No Zephyr build.

The bounded loopback server is stopped after acceptance. Main, GP, the P4 owner
checkout and paused SFC work remain unchanged. See the
[P4 integration assessment](JS_P4_INTEGRATION_PLAN.md) for the next required
profile/compiler/transport/view work and owner-coordination boundary.

[Dated evidence](../evidence/2026-10-27/js-project-roundtrip/README.md) records
the full validator outcome, exact source/package identities and cleanup.
