# Connected steps and transitions â€” bounded graphical stage

Historical design/validation slice. The current native v4 entry point is
[SFC.md](SFC.md), including paired OR/AND branches and reproducible build/test commands.

Historical graph-stage scope below. This copy adds execution-plan authoring and
logical action export as specified in [SFC_INTERFACE.md](SFC_INTERFACE.md).
The graph JSON format remains separate from the complete execution draft.

## Baseline and intent

Work is isolated from the sealed P4/Pi checkpoint and active Pi checkout.
The existing portable `common/automation/steps.c` engine remains authoritative:
16 steps, 24 transitions, explicit scans, AND source/target masks and conflict
priority by transition number. Its API, primitive indices and firmware stay
unchanged. This stage adds a modular authoring graph and export to the existing
MicroBlocks library, not an industrial controller implementation.

Reference: Rockwell **1756-PM006L-EN-P**, September 2024, official
[Sequential Function Charts manual](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm006_-en-p.pdf),
printed pp. 22â€“24, 47, 53â€“58. The earlier supplied copy could not be resolved;
the official revision is explicitly identified rather than assumed identical.
The manual describes pin-to-pin wiring, alternative-path priorities, concurrent
paths that synchronize, and return wires. These guide this stage's interaction.

## Deliverable contract (written before implementation)

- Add/select/move/delete named steps and transitions. The initial step has a
  second outline; connections are directed and alternate step/transition.
- Click output/input pins in either order. Reject missing endpoints, same-kind
  links, same-direction pins and duplicate links atomically. Deleting a node
  removes its links. Keep independent JSON draft import/export and undo/redo.
- Draw routed return wires. A transition with multiple input steps is an AND
  join; multiple output steps form an AND fork. Multiple transitions competing
  for a step are alternatives, with explicit lowest-transition-ID priority.
  Moving nodes changes layout only; it never changes priority.
- Validate before starting/exporting: bounded unique IDs, finite grid positions,
  exactly one initial step in this graphical subset, complete transition ends,
  reachable steps, bounded labels, delays and document size. Preserve incomplete
  editing drafts and show actionable errors. Do not silently repair imports.
- Explicit local simulation: start, one scan with an explicit monotonic advance,
  stop/reset. Read fresh Boolean inputs every scan. Snapshot old active steps;
  no cascading in one scan. Independent transitions fire together; source
  conflicts resolve by ID. Activation wins simultaneous removal/addition, and
  target entry times restart. Minimum source time must hold for every source.
- Export a real `.ubp` project using the existing Steps & Transitions library.
  Fresh conditions come from ordinary Boolean MicroBlocks variables; no `eval`,
  arbitrary expression injection, GPIO/output action, implicit connection or
  implicit program execution. The generated project is a separate explicit
  import in an opt-in disconnected editor package.

## Scope and differences

The editor and simulation are local software. This is not full Rockwell or
IEC compatibility: priority is numbered, not automatic left-to-right; all scans
use the prototype's existing snapshot rule; a terminal active step waits until
reset. No action qualifiers, stored actions, subcharts, forces, stop elements,
online editing, pause/resume semantics, automatic topology safety proof or live
board monitoring is added. JSON is the authoring format; `.ubp` export is one-way.
Linux/Pi execution of these P4 primitive indices is not claimed.

## Acceptance criteria

1. Model, invalid editing/import, AND/OR/return graphs and deterministic export
   tests, including ID 16/24 and timing boundaries.
2. Generated configurations and preview scans compared against the actual
   unchanged C engine under ASan/UBSan, including seeded varied graphs.
3. DOM interaction tests for connection creation/deletion, draft preservation,
   running-state locks, export and explicit project replacement.
4. Package the genuine pinned GP 2.5.8 editor with an isolated opt-in UI; verify
   graphical edits and actual import/rendering while disconnected. Keep the
   user's board-hosted editor and drafts untouched.
5. Run repository validation. No P4 flash/test, Pi/robot use, merge or publication.
   Preserve the sealed checkpoint archive and installed-image recovery file.
