# SFC logical execution plan, version 1

Historical design/validation slice. The current native v4 entry point is
[SFC.md](SFC.md), including paired OR/AND branches and reproducible build/test commands.

The execution contract below is preserved. [SFC_INTERFACE.md](SFC_INTERFACE.md)
now adds a complete draft interface and logical action export. The former
graph-only import remains strict; an additional explicit execution-JSON import
handles actions. Firmware and real-GP execution remain unverified for this slice.

Specification recorded before implementation. This independent layer composes
the connected graph with explicit transition priority, logical action requests
and an administrative restart. It adds no firmware primitive, GPIO operation,
GUI handler or live-board connection. The previous graph editor/export remains
graph-only; an execution plan is a different document and is rejected by that
editor instead of losing its action data.

## Reference and scope

Reference: [Rockwell 1756-PM006L-EN-P, September 2024](https://literature.rockwellautomation.com/idc/groups/literature/documents/pm/1756-pm006_-en-p.pdf),
printed pp. 23, 26, 28, 41â€“45, 47 and 57. The earlier supplied copy was not
recoverable; this is the official public edition. Relevant requirements are
OR selection with configurable order; concurrent paths with a rendezvous;
step-bound N/P1/P0 events; stored S with R; no automatic terminal restart.

This is a bounded adaptation. It publishes Boolean requests at scan boundaries,
not Logix action bodies, A/Q status, postscan or last-scan callbacks. In particular
N is the **new active state** after a scan. Rockwell Boolean Q's last-scan rule
does not describe this boundary signal. No device is switched by R or by any
other qualifier here. The caller must implement and validate any physical use.

## Document and priority

An execution plan has exactly `version:1`, `graph` (complete graph v1), `signals`
and `bindings`, and optional `priority`. Signals are `{id:1..16,label}`; labels
are bounded to 48 printable Unicode code points. Bindings are
`{step,signal,qualifier}`; only N/P1/P0/S/R are accepted. There are at most 64
unique bindings, with defined steps and signals. Empty signal/binding sets are
valid. Duplicate IDs/bindings, unknown properties and unsupported qualifiers
are errors. JSON is limited to 128 KiB. Inputs are fresh Booleans indexed by
the original graph's transition IDs.

`priority` is an exact permutation of the transition IDs. Its first member has
highest priority when transitions consume overlapping sources. Omission means
ascending ID, preserving the graph prototype. This explicit global ordering
does not infer left-to-right priorities from geometry. Independent enabled
transitions still fire together. The compiler publishes an ID-to-native-slot
mapping; the actual C core's existing ascending-slot algorithm remains intact.
Entered sources cannot cascade through a join in the same scan. All join sources
must already be active and each must satisfy its minimum elapsed time.

## Requests after a successful logical operation

For each signal, all matching bindings contribute by OR:

| Qualifier | Contribution |
| --- | --- |
| N | step is active after the operation |
| P1 | step was entered in this operation |
| P0 | step was exited by a transition in this operation |
| S | entry of its step sets a stored request |
| R | active reset step clears that signal's stored request |

Stored state is `(previousStored OR entrySets) AND NOT activeResets`. R wins
over a simultaneous S and only clears the stored contribution, not independent
N/P1/P0 contributions. After an R, S rearms on a new entry of its storing step.
This resolves otherwise ambiguous simultaneous operations deterministically;
it is our contract, not a claim about all Logix scheduling configurations.
Pulses last one successful operation; repeated scans clear them. A self-loop
has both entry and exit events. Shared N requests remain set while any bound
parallel step is active. A terminal step remains active until explicit action.

`start(now)` requires a stopped chart and publishes initial entry actions.
`stopAndClear()` cancels the whole logical chart and clears requests, stored
state, events and step timers without synthesizing P0. It is an administrative
cancel, **not a Rockwell Stop element** (which can retain stored actions).
`restartAt(step,now)` cancels old state, activates the chosen defined step,
restarts its entry time and publishes its entry actions. `resetInitial(now)`
does the same at the configured initial step. Old stored state is cleared;
a target S binding can immediately store a new request. No old P0 is emitted.
This reset is a defined application policy, not an implementation of SFR.
The configured initial step never changes. Invalid configuration, inputs,
backwards time and invalid restart targets leave prior state intact.

## Implementation and acceptance

The JS execution layer and portable C action kernel must agree on all state
fields over structured and seeded traces. The C fixture uses the actual
unchanged `steps.c`, compiled with ASan/UBSan. Test explicit OR priority,
independent branches, delayed AND readiness, N/P1/P0/S/R truth tables, same-
signal sharing, reset dominance, terminal state, self-loop and atomic failures.
Run existing Node suites and `python3 tools/validate.py` as regressions. Retain
source hashes, exact commands, test logs and an immutable delta checkpoint.

Non-goals: timed action qualifiers L/D/SL/DS/SD, P, stop elements, nested SFCs,
pause/resume, online edits, forces, action code, GP/UBP action export, live P4
validation, full Rockwell/IEC equivalence. No Zephyr integration/build is
claimed for this host-only slice. Existing SD/P4/Pi checkpoints stay unchanged.

## Local use and reproduction

Run `node tools/sfc_trace.cjs examples/sfc/actions-and-reset.sfc-plan.json
examples/sfc/actions-and-reset.trace.json` (one command). It reads local JSON
and prints a full trace. Active masks are 1, 6, 8, 1, 0; requested signal masks
are 1, 3, 4, 1, 0. It performs no I/O beyond those file reads and stdout/stderr.
Only the current explicit operation contributes pulses; no real-time timer runs.

On Linux with GCC: `python3 tools/test_sfc_execution.py` builds and runs the C
unit/fixture tests. Then set `MB_SFC_EXECUTION_HOST` to the produced absolute
`build-artifacts/sfc-execution/host` path and run
`node --test tests/sfc-execution.test.js`. On Windows, also set `MB_SFC_WSL`
to the WSL distribution and use a `/mnt/c/...` fixture path. The fixture never
falls back to a connected device. Build `tools/build_sfc_native_fixture.py`
and set `MB_SFC_HOST` similarly for the previous graph's C parity test.

`common/automation/sfc_actions.{h,c}` is portable, fixed-size and allocation-free.
Initialize it with the graph's defined-step mask and declared-signal mask, add
validated bindings, then seal it before starting. Call apply once after each
successful step-core operation. Clear on administrative cancellation; use
`mb_sfc_restart` for the atomic restart policy. Sealing prevents subsequent
configuration edits. Caller-owned structs must retain valid initialized data.
The new kernel is not included by firmware CMake or exposed by VM primitives.
