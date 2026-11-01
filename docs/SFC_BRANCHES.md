# Native OR / AND branches — implementation specification

Historical preimplementation design. The worker architecture and tighter limits
are specified in [SFC_BRANCHES_IMPLEMENTATION.md](SFC_BRANCHES_IMPLEMENTATION.md).
Use that document for current behavior and validation status.

Keep the sealed serial native editor and all prior graph/action data. This work
uses a separate source copy. No main/shared branch, runtime dependency, firmware,
physical board or existing SD data may be changed.

The existing sequence/step/transition blocks remain. Add native, standard-style
blocks for OR split, guarded alternative, OR merge, AND split, parallel branch
and AND join. Split blocks hold branch definitions; matching merge/join blocks
name a shared Boolean transition variable. A parallel split requires a preceding
shared transition; an OR split may additionally have one. Ordinary user commands
remain inside step setup/loop sections, never between structural flow nodes.

AND activates the first step of every branch together in the chart state. All
first-step flags are published before setup actions run. At convergence, every
branch's final step must be active AND the shared join transition Boolean true.
An early final step stays active, continuing its loop while the others catch up.
OR selects exactly one enabled alternative, by branch order from top to bottom
when several are true. It waits if none is enabled. An OR merge accepts the chosen
branch's final step and its shared merge transition; unchosen branches never run
setup. Conditions remain persistent shared variables, not consumed events.

Branches are structured and paired; each branch starts and ends with a step.
Interior serial transitions and nested paired splits/joins are allowed. Step
variables must be unique in a chart and disjoint from all guard variables. Empty,
single-branch, mismatched, dangling or interleaved structures are rejected. Bounds
remain 16 steps and 24 edges; the actual VM's 1000-byte chunk guard can impose a
smaller program-specific compiled limit, which must be tested and stated.

The branch compiler lowers to ordinary SmallVM operations and private locals;
no new firmware primitive is required. It keeps one owner for chart state.
Each logical cycle runs setup for entered steps, samples guard variables once,
selects transitions from the old active mask with ordered source consumption,
runs loop for steps that remain waiting, updates/publishes masks, then yields.
Newly activated steps cannot cascade in the same cycle. Setup runs once for each
entry. This mirrors the retained C engine's activation/consumption rule; use that
unchanged engine as an independent oracle where applicable.

Parallel means logical concurrent SFC activity with cooperative action dispatch,
not one OS thread per step. Blocking user action code delays this chart's next
action/scan; other MicroBlocks tasks still follow their VM scheduler. Step flags
are ordinary shared variables and the group of flag writes is not an atomic
external snapshot. Stop/return/error cleanup limits of the serial prototype stay
explicit. Full Rockwell compatibility, arbitrary unstructured graphs, preemptive
actions and hardware execution are not claimed.

Graphics use native MicroBlocks command/variable slots and explicit single/double
horizontal bar icons for the four structural directions. Validate the vector
geometry and serialization. Real browser opening remains a separate acceptance
step: this executor lacks the supported graphical runtime. Never bypass the old
HTTP or browser restrictions to obtain a screenshot.

Acceptance includes real compiler/save-reload, normal serial regression, true
AND activation and delayed join, early-true join condition, branch-loop progress,
OR no-choice and competing choices, shared transition gating, nested structure,
counter-based setup-once/reentry, persistent Booleans, ordinary VM execution under
sanitizers, invalid-structure cases and explicit compiled-size rejection.
