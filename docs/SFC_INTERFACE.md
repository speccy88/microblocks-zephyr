# SFC actions in the authoring interface and export

Historical design/validation slice. The current native v4 entry point is
[SFC.md](SFC.md), including paired OR/AND branches and reproducible build/test commands.

This copy includes the real-compiler corrections documented in
[SFC_REAL_COMPILER.md](SFC_REAL_COMPILER.md): SmallVM uses `waitMillis`, not the
GP-host `waitMSecs`; large setup routines are split below the actual per-chunk
limit. Earlier interface-only test claims remain historical scope below.

Specification before implementation. Work in a fresh copy of the sealed graph
and execution checkpoints. Preserve P4/Pi sources, firmware and SD data. No
browser operation, retry of the uncertain GP import, or device access belongs
to this stage. Existing connection-disabled packaging remains mandatory.

The interface edits a whole execution-plan draft: graph, declared logical
signals, N/P1/P0/S/R bindings, and an explicit transition priority permutation.
Signals are numbered A1..A16. All changes, including graph deletion with its
affected bindings, participate in one bounded undo/redo history. Deleting a
signal removes only its bindings; undo restores them. Removing or adding a
transition reconciles priority without reordering surviving transitions.
Incomplete graphs remain saveable drafts, while preview/export require the
existing complete-graph validation. Runtime editing is locked.

Persist whole plans under a new browser key. Read a legacy graph as an initial
plan only if no new plan exists; never rewrite the old key. Invalid saved data
is preserved until an explicit edit/load. Execution JSON is the complete
portable document. Graph JSON is an explicitly labelled graph-only view;
loading graph-only JSON over action data requires a warning/confirmation.
Invalid JSON stays in its textarea and never replaces the current draft.

Preview uses the already validated execution engine, with visible logical
signal requests and stored state, priority controls, administrative cancel,
restart at a defined step and reset to the configured initial step. Inputs
and time remain explicit. No signal controls a device.

Export includes priority remapping to native transition slots, logical input
variables `sfc_t<ID>`, requested outputs `sfc_a<ID>`, stored state `sfc_l<ID>`,
and ordinary generated action blocks. Labels remain data and never enter
executable source. S sets on entry, R clears stored contributions after all S
sets, and N/P1/P0 contributions OR together. Reset initializes at the original
initial step; stop clears requests without P0. The existing Steps library is
included byte-for-byte. No new primitive indices or firmware code are added.
Export failures clear request variables before native setup. Native scan errors
stop/clear logical requests. Unsupported primitives can still raise VM errors;
this is not a physical fail-safe or a compatibility claim.

The exported scheduler has one owning scan loop, 50 ms delay per iteration.
It waits before the first scan, preserving initial P1 requests through the
first wait. `sfcStopAndClear` performs the explicit request cleanup. MicroBlocks'
global red stop does not execute that block and can leave request variables
holding their last value; no physical deactivation is promised by those values.
Do not run concurrent native step-control scripts. Stop that loop before using
manual reset/setup blocks. Arbitrary restart-at-step remains preview-only;
there is no equivalent native jump primitive in the validated firmware API.
Real-time hardware timing, VM scheduler interleavings and compilation/execution
in the real GP/controller are unverified until separately demonstrated.

Acceptance: controller DOM tests must exercise action editing, priorities,
whole-plan persistence/history, signal display, locked controls and lossless
imports. Execute generated action code in a separately implemented restricted
GP-subset test interpreter against actual C step snapshots, comparing requests
with the validated JS engine; this is not the GP VM. Retain exact source and
logs. Run all JS suites and required `python3 tools/validate.py` sequentially.
Package the pinned editor without opening a browser and verify script order,
asset hashes and connection-disabled guard. No full Rockwell/IEC claim.
