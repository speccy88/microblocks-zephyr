# Native OR and AND branches

This isolated prototype extends the existing native GP MicroBlocks blocks. It
preserves the sealed sequential editor, old graph/action data, P4 firmware and
the active Pi worktree. No dependency upgrade or hardware deployment is included.

The sequence contains steps, transitions and paired split/join blocks. Ordinary
commands belong inside a step's **setup**, run once on entry, or **loop**, repeated
while active. Step state and transition conditions remain ordinary shared
MicroBlocks variables. Only Boolean `true` enables a transition; numeric 1 does
not. Conditions persist and are never automatically cleared or consumed.

## Native forms and Grafcet rules

`sfcAnd` has two initial command slots. The normal MicroBlocks expansion control
adds more branches, up to six accepted by this compiler. It uses a double-bar
icon; `sfcAndJoin` uses the corresponding convergence icon and a variable slot.
`sfcOr` similarly expands pairs of condition-variable and branch-command slots,
with single-bar split and merge icons. This is a native block stack with command
slots, not a separate graph application or a full horizontal Grafcet renderer.
Actual browser layout and editing still require visual acceptance.

An AND split requires a shared transition immediately before it. When enabled,
all branch entry steps become active together. The join waits for **every**
branch final step to be active, its setup to finish, and the common join variable
to be true. An early final step stays active and repeats its loop while waiting.

An OR split may have a common preceding transition. It selects exactly one true
alternative, in displayed order from top to bottom. It waits when none is true.
The OR merge waits for the selected final step and the merge condition; it never
activates unselected alternatives. OR priority is deterministic prototype
behavior, not a claim of strict Rockwell compatibility.

Every branch starts and ends on a step. Serial transitions and nested paired
OR/AND structures are supported. Empty paths, fewer than two or more than six
branches, mismatched joins, ordinary interleaved commands, duplicate step
variables and step/guard role conflicts are rejected. Step state has one chart
owner across the project; transition variables may be shared across charts.

The saved examples are `integration/sfc-native.ubp` (three parallel paths with
intermediate steps), `sfc-or-3.ubp` and `sfc-nested.ubp`. The preceding sequential
example is retained as `sfc-serial.ubp`.

## Execution and limits

The compiler generates ordinary MicroBlocks functions in `_SFC workers`, plus
private shared variables. One coordinator owns the active-state mask and one
SmallVM task per step executes actions. There are no SFC opcodes, OS threads,
FreeRTOS tasks or Zephyr workers added by this feature. Task creation uses
SmallVM's existing broadcasts to zero-argument functions.

Workers report readiness before any setup can run. Admission waits at most
500 ms; failure clears activity and aborts the calling chart instead of falling
through to subsequent commands. The coordinator publishes all public step flags
before publishing the shared mask that releases new setup actions. Worker
activation uses that mask, so another task switch cannot release only part of an
AND split. External readers can still observe the individual public flag writes
in progress; their group is not an atomic external snapshot.

Each coordinator cycle reads each guard once, selects transitions from the old
active mask, and consumes each source at most once. New targets cannot cascade
in the same cycle. It asks departing workers to finish their current action
iteration and acknowledge before changing their active mask. A `waitMillis` in
one action therefore yields to other branch workers and ordinary scripts.
Workers yield at least once per loop. Terminal completion clears public flags
and waits up to 500 ms for worker shutdown, then yields before immediate
reentry. Workers halt without producing a reporter result. A cleanup timeout
prevents reuse until reset. The real Linux SmallVM suite passes 152 assertions,
including cooperative progress, admission failure, C-oracle state comparisons
and immediate reentry. It is not a measurement of P4 execution or timing.

Pinned source limits are ten SmallVM task entries, 128 shared variables and
255 chunks. This prototype admits at most eight step workers total, and rejects
projects where workers plus top-level event scripts exceed ten. All step workers
are reserved even when their steps are inactive, so OR graphs also consume this
budget. Dynamic script starts can still exhaust the pool; the runtime readiness
check handles that separately. Limits are 24 edges and 24 guard variables per
chart. Programs must also fit the existing 1,000-byte transfer chunk check;
large action bodies can exceed it even within the structural limits.

The generated names are reserved. Existing user data with a colliding module,
variable or function namespace is rejected, including collisions in libraries.
Generated functions are stored with the normal project and refreshed from the
native source; repeated compilation is checked for stable serialization.

Chart declarations are supported in top-level scripts, including ordinary repeat
cycles, not inside user functions. Actions should use shared variables and their
own locals; capturing an enclosing script's local variables is unsupported.
Direct return, stop-task, stop-other-tasks and nested SFC flow commands in an
action are rejected. A called user function can still stop/error the worker or
never return: such actions can strand a chart's transition acknowledgement and
are not a supported cancellation mechanism. No automatic replay is attempted.

Stopping the owner through the editor generates stop requests for its workers
and clears its public activity. The request plan is tested offline; actual
transport cancellation remains unverified. Red stop/reset is the recovery path
for a worker stuck in user code. A synchronous blocking C primitive blocks the
VM until it returns; cooperative task scheduling cannot preempt it. Long native
operations must supply a yielding/asynchronous implementation independently.

Private status is 1 during admission, 2 running, 0 successful completion, -1
admission failure, -2 cleanup timeout and -3 cancellation. Reset is required
after -2. There is not yet a dedicated graphical failure panel.

## Validation status

Real GP compiler, canonical save/reload, serial regression, configurable counts,
nested structures, rejection cases, native spec/variable slots, bar geometry and
live-state display logic are tested locally. The executable test runner passes
152 assertions across ten cases using the preserved real SmallVM and unchanged
C-engine oracle. It verifies join gating, competing OR conditions, setup-once,
reentry, cooperative progress and actual task exhaustion. The first launch was
denied before execution; new explicit resume evidence permitted one accepted
retry. History and GUI tooling limits are recorded in the task checkpoint.
Neither P4 execution nor full browser appearance is claimed.
The required full `tools/validate.py` run also passes all 370 tests, with no
failures or skips, in owned Linux fixtures using the preserved sanitized VM.
