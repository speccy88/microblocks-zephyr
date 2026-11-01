# Native SFC blocks â€” bounded first slice

Historical design/validation slice. The current native v4 entry point is
[SFC.md](SFC.md), including paired OR/AND branches and reproducible build/test commands.

The current user direction replaces mandatory graph/export authoring with real
MicroBlocks blocks. Preserve the earlier graph, action engine and sealed exports
as independent experiments. No board or dependency upgrade is part of this slice.

Each step has a shared MicroBlocks Boolean variable, a `setup` command section
executed once, and a loop command section repeated while its following transition
variable is false. A transition names a shared variable, not a value captured when
the block starts. It waits for the actual Boolean true. An already true transition
runs entry once and skips the loop. Conditions remain level sensitive; they are
not automatically cleared. Users may set them in ordinary scripts or step actions.

A native sequence contains alternating step/transition pairs only. Ordinary
blocks belong inside setup/loop sections, not between pairs. A step variable is
true before entry and remains true through the wait; it becomes false on normal
transition completion. A 1 ms native wait between loop passes yields to other VM
tasks; an empty loop uses SmallVM's native wait-until instruction. User actions can themselves wait, so transition
checking occurs between completed loop passes, without preempting an action.
Restarting a sequence clears its own step variables before reentry. It preserves
transition variables. Only one running sequence may own a given step variable.
Every step variable is distinct; transition and step variables must be disjoint.

Use the genuine editor's existing Control block style, variable slots and command
slots, its project parser/serializer, compiler and ordinary SmallVM instructions.
No new firmware primitive is needed for this serial slice. A guarded GP adapter
adds compiler forms; an unmodified editor cannot execute these new forms. The
adapter is opt-in and isolated. Shared variables are required; function parameter
or local-variable capture is rejected. Arbitrary ordinary blocks are accepted
within the action sections subject to MicroBlocks' usual rules.

Acceptance: genuine GP load/save/reload preserves declarations and both action
sections; real compilation emits bounded chunks with no skipped operation; real
SmallVM execution proves entry-once, repeated loop, live variable wakeup, already
true, no auto-consumption, scheduler progress, serial handoff and controlled stop.
Invalid structure, missing/shared-variable shadowing, reuse and dangling steps
must fail compilation. Retain negative test evidence and exact source/binary hashes.

Limits: this is a serial sequence, not the earlier scan engine's fork/join/action
qualifier scheduler or a full Rockwell implementation. No automatic cleanup runs
after red Stop, return, exit-loop, or an error inside user action code; a step
variable can retain its last value. A new sequence entry resets its step flags.
No GPIO/output cleanup or safety behavior is inferred. Graph-to-block conversion,
concurrent SFC branches, dedicated visual docking restrictions, on-screen visual
acceptance and physical P4 execution remain separate work.

The first supplied reference image could not be materialized on this Windows executor:
the current Library helper needs `os.setxattr`, unavailable on Windows, and left
no final file. It has not been visually inspected. The second image was retrieved
with the unchanged current helper under local WSL/Linux (which supports these
attributes), verified readable at the local Windows destination, and inspected.
It shows a green active-step border and green action header. Native step blocks
therefore use a green live display color while retaining their original saved
color and standard MicroBlocks shape. The command-slot arrangement follows the
user's setup/loop description; no custom Rockwell diagram geometry is claimed.

## Live indication

The opt-in GP adapter polls only shared step variables through ordinary read
messages, at most four requests per 250 ms. Multiple active step blocks can be
green simultaneously. This does not add concurrent branch execution to a single
serial sequence. A normal false reply clears the indication; stale values expire
after 1500 ms. Chunk completion/error/stop, global stop, disconnect, project load
and removed blocks clear their live state. An independent stopped-chunk set
prevents GP's delayed generic running highlight from reactivating stale values.
Replies without a pending read are ignored. No live state is serialized.

Polling may miss very brief steps; large projects or slow links can exceed the
freshness bound and show an inactive/unknown state. The ordinary variable wire
protocol has no request epoch, so arbitrary cross-restart reordering is not
provably distinguishable. This is an editor debugging view, not an atomic process
snapshot or a physical-state/safety guarantee. No additional transport, credentials,
write replay, hardware access or firmware change is introduced by the adapter.

The packaged preview uses the genuine GP editor, with the separate graph scripts
removed and hardware connection disabled. Open `sfc-native.ubp` using the normal
project controls, or create shared variables and take the blocks from Control.
The bundle is a local review artifact; graphical opening, drag/drop restrictions
and user visual acceptance are not inferred from the headless tests.
