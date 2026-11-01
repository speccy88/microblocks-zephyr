# Native SFC checkpoint and migration boundary

Historical design/validation slice. The current native v4 entry point is
[SFC.md](SFC.md), including paired OR/AND branches and reproducible build/test commands.

This isolated slice follows the user's revised authoring contract: ordinary
MicroBlocks blocks, shared step/transition variables, setup once and loop while
active, no ordinary command between step/transition pairs, and visible active
steps. Earlier graph/editor exports, N/P1/P0/S/R data, tests and sealed checkpoints
are preserved. Nothing is deleted or migrated automatically.

The serial implementation compiles to ordinary SmallVM instructions. It does
not need the earlier numbered-step C primitive set. The existing C scan/fork/join
engine and action kernel are retained unchanged for later explicit graph/concurrent
work; their semantics are not silently substituted for sequential setup/loop.

## Actual verification

The pinned genuine GP 2.5.8 parser, project serializer and SmallCompiler run in an
offline Node process with the unchanged WASM engine. Only its virtual startup is
replaced by the test entry point. The empty external mount is MEMFS; there is no
host mount, browser, serial or network API. Minimal project/scripter objects supply
real project data. Exact input, runtime and output hashes and compiler messages
are retained in `sfc-compiler-work/evidence` outside the source tree.

Real parsing, save/reload equality and compilation pass for the native example,
an empty-loop example and 16 sequential steps (largest chunk 621 bytes). The normal
example's largest chunk is 89 bytes; the empty-loop example is 77. Nine malformed
cases are rejected: misplaced/dangling/empty sequences, ordinary interleaving,
duplicate steps, missing/shared-role variables, and local/parameter shadowing.
The older exporter corrections also pass real compilation: 188 bytes for the
sample's largest function and 716 bytes for the tested capacity fixture.

The genuine compiler exposed three defects missed by the earlier subset tests:
`waitMSecs` was skipped (correct SmallVM form is `waitMillis`), the maximum old
reset function exceeded 1000 bytes (1070), and generic GP printing split adjacent
setup/loop command sections across commands on reload. Corrected wait tokens,
bounded setup helper functions and guarded native-step serialization address
these. Original failing sources/reports are retained. Test harness corrections
are also recorded: an unused empty-loop variable had no VM index, and Start All
needs the v417 compatibility byte 1. These are not claimed as firmware faults.

The final actual compiled native chunks run unchanged, except official wire word
padding, on the retained real SmallVM v417 Linux binary under ASan/UBSan over its
private PTY. Its SHA256 is
`407ffaee8288728c5e6de5aa570fc726bc520c844fe040cd81fceea490a0ff48`.
The two examples pass 35 checks, including setup-once, looping/empty-loop wait,
Boolean true rather than numeric 1, live variable wakeup, serial flag handoff,
no auto-consumption, already-true skip, independent task progress, explicit stop,
restart, CRC readback and native when-started autostart after process restart.
No new native C adapter is used by these native-block tests.

The offline GP live-display tests exercise real variable-message handling,
ephemeral native Block fields, simultaneous active steps, stale/false/removed/
stopped state, late replies, polling budget, saved-source preservation and GP's
real shape recorder. This is not an on-screen screenshot or physical P4 test.

## Preserve for the GP / JavaScript editor transition

| Preserve | Current role | Later editor adaptation |
| --- | --- | --- |
| `web/sfc-native.gp`, guarded compiler/project/pretty-printer patches | Native sequence grammar, shared variable semantics and ordinary VM bytecode | Port the three forms and validation to the new editor compiler; retain project source and real-bytecode fixtures |
| `web/sfc-live.gp`, Block/Scripter/Runtime hooks | Native live green display and bounded read polling | Port rendering/lifecycle hooks; keep variable wire types and stale/stop rules |
| `integration/sfc-native.ubp`, actual compiler and VM tools/tests | Native user-editable program and reproducible acceptance | Keep as cross-editor open/save/execute fixtures |
| `web/sfc/*`, graph/action examples and previous sealed deltas | Portable JS model, former optional graph UI and exporter | Preserve data and semantics; separate old graph UI from the native block authoring surface |
| `common/automation/steps.*`, `sfc_actions.*`, native fixtures | Snapshot scan, priority, fork/join and N/P1/P0/S/R kernel | Reuse only where those execution semantics are explicitly wanted |
| P4 native media/storage/Wi-Fi/throughput and Pi checkpoint | Earlier integrated work and hardware evidence | Reconcile reported immutable checkpoints with owners, without modifying active worktrees |

No shared branch, main, dependency pin, commit, remote or upstream checkout was
changed. This snapshot has no Git metadata. It is a source/evidence checkpoint,
not a published GP branch or a JavaScript-editor migration.

## Remaining limits

Full visual opening/editing/drag/drop/save in a browser, the reference image's
exact geometry, and physical P4 execution/visual updates are unverified. The
first reference image remains unavailable; the second was downloaded with its
Library metadata through the unchanged helper under local Linux and inspected.
No previous denied Git/deletion/browser/hardware operation was retried. A CIM
process-list read was denied by the sandbox; no escalation of that read occurred.
Owned child-test outcomes and logs were checked before continuing.

The disconnected native preview is a local review bundle with the graph scripts
removed. Its project syntax still requires this opt-in editor adapter; an ordinary
unpatched editor may skip unknown forms. Only serial sequences are implemented;
visual support for multiple active steps does not prove concurrent SFC branches.
User action code can wait, return, error or stop; no cleanup/finally or physical
output guarantee is inferred. Polling has bounded freshness and can miss short
steps. The installed P4 and SD contents were never accessed in this slice.
