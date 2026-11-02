# SFC in the JavaScript editor - implementation contract

Work directly in main. Preserve legacy GP and its tests, the official editor
pin `5564b1e`, v417 VM, transport policies and all existing project behavior.
This ports native SFC functionality; copying the GP editor is not a JS port.

## Behavior

Add genuine MicroBlocks command blocks in Control: sequence; step with shared
state-variable, setup and loop sections; shared-variable transition; expandable
OR and AND splits with paired merge/join. Support two through six branches and
paired nesting. Use standard variable and command slots, block dragging, native
expansion, project source, undo, save/reload and phone navigation.

Setup runs once per activation and loop repeats cooperatively while active.
Only Boolean true enables a transition; conditions are level-sensitive and are
not consumed. OR uses displayed top-to-bottom priority. AND releases all entry
steps together and waits for every branch final step, completed setup and its
shared join guard. Read each guard once per scan; newly activated steps cannot
cascade during that scan. Finish an action iteration before acknowledging exit.
Use the GP native branch semantics and unchanged C stable-state oracle as the
reference, including nested paths, admission failure and immediate reentry.

Sequential pairs lower to stock instructions. Branch charts generate ordinary
MicroBlocks worker functions and private shared variables, with no new opcode,
firmware primitive or external scheduler. Retain the task readiness barrier,
500 ms admission/cleanup limits, status and reset behavior. Reserve at most eight
step workers and ten task entries including owners/event scripts; validate 128
shared variables, chunk capacity and the actual 1000-byte transfer bound before
uploading a chart. Generated names are reserved and user collisions fail.

Reject malformed flow, missing/shared-variable shadowing, duplicate ownership,
step/guard overlap, unsupported capture and actions that directly stop or return
their worker. Actions must yield and return; a blocking native primitive or
nonreturning called function is not preempted by this feature. No safety/output
cleanup or physical timing guarantee is inferred.

## Integration and live state

Use separate main-owned JavaScript overlays around unmodified upstream files.
Bundle the same implementation in all reviewed JS web profiles, touch/board
assets and the native iPhone bundle. Preserve board-specific compiler overlays,
readback protection and wireless restrictions. Keep generated functions in a
clearly marked implementation module, regenerated from native SFC source, with
stable repeated compilation and canonical save/reload.

Read real shared-variable values through the existing connection to color active
steps green. Poll at most four variables per 250 ms, expire after 1500 ms, and
clear on stop/error/disconnect/project changes. Never serialize display state or
claim an atomic external state snapshot. Individual owner stop must stop its
workers and clear owned public flags; global stop/reset remains the recovery
path for uncooperative user code. Test lifecycle against actual VM traffic.

## Acceptance and delivery

- Genuine JS parser/compiler: all native serial/branch fixtures, 2/3/4/6-way
  branches, nesting, stable source roundtrip, reserved-name/task/variable/chunk
  bounds and malformed inputs. No silently skipped SFC operation.
- Real sanitized SmallVM: setup-once, repeated loop, live shared conditions,
  Boolean strictness, parallel progress, early join, OR priority, persistence,
  immediate reentry, task exhaustion and controlled stop. Compare stable masks
  with the unchanged C engine; do not substitute a JS execution simulation.
- Actual browsers: native-looking blocks, expansion beyond two branches,
  shared-variable selection, drag/insert, editing/undo, save/reopen, locale,
  active-state rendering and clearing. Cover desktop and realistic phone sizes
  and orientations with existing pinch/pan regressions. Simulator testing does
  not establish physical iPhone behavior.
- Run the full validator and required compiler/native/browser CI on the final
  main head, commit and push, publish through the existing supported Pages
  workflow, then verify the actual public JS and mobile entries. No board flash,
  GP branch update, dependency upgrade, security change or desktop wrapper.
