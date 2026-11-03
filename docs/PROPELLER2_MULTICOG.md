# Native P2 cog execution contract

The P2 extension keeps the main VM and IDE receiver on their existing cogs.
Named, zero-argument MicroBlocks functions can be launched on another explicitly
selected physical cog. Each worker has its own interpreter error/sleep state,
Task stack and guarded native C stack. A reporter returns the actual cog ID.
This must be real hardware execution; a global lock around whole interpreter
runs is not an implementation of parallel execution.

Revision 3 supports scalar/control execution plus rooted strings, lists and
byte arrays. Audited object instructions and named primitives execute through
main-cog services. Workers retain their own interpreter, arithmetic/control,
waits, ordinary calls and timers. Printing, broadcasts, random, dynamic calls,
worker management and unaudited primitives remain refused. These restrictions
do not disable ordinary main-cog scripts.

Normal MicroBlocks variables live in shared HUB RAM. Individual reads/stores
and the native `change variable by` instruction use a hardware lock. A separate
read followed by arithmetic and a store is still a multi-instruction operation;
it is not atomic. Named shared-value read/write and numeric add blocks provide
an explicit interface. Atomic list-element add is one main-cog operation.
The main collector pauses workers at opcode boundaries before marking and
forwarding all roots; code/name edits stop workers before changing persistent
code. Stop-all, reset and live editing must never leave an interpreter running
against changed code or cleared memory.

Existing GPIO and Smart Pin ownership stays on the main cog. Workers must not
change their own DIR/OUT registers: floating a pin on one cog cannot release a
driver owned by another. Worker pin requests run on the main cog. Autonomous
Smart Pins can continue after their requesting function ends; release them
explicitly when required. Toolbar stop-all/reset releases main-owned pins.

Acceptance before a physical PASS:

- Build Eval, original Edge and EC32MB with the pinned native FlexC toolchain.
- Launch two different functions on distinct requested physical cogs and record
  their actual IDs and simultaneous progress while USB ping stays responsive.
- Run exact shared-variable increments from multiple cogs and verify N times M.
- Exercise main-cog allocation/GC and list mutation while scalar workers run;
  verify roots, results and worker stack canaries.
- Reject direct worker allocator calls and unaudited primitives.
- Stop, restart, live-edit and reset with no stale worker or lock ownership.
- Measure native-stack usage and retain canaries at both ends. FlexC's cog-start
  macro does not enforce its stack-size argument.

The code, tests and dated evidence determine implemented/validated status.
This document is the implementation contract, not a physical test result.

## Revision 3 object and peripheral services

Workers may retain strings, lists and byte arrays when every live worker stack,
pending service result and pending return event participates in GC marking and
forwarding. Workers pause only at dispatch boundaries or while waiting for a
service with no copied heap references on their native C stack. Shared-word
lock waits must not announce a GC safepoint after copying an object argument.

The main cog remains the only allocator and mutable-object operation owner.
Each worker publishes one request using arguments on its rooted Task stack.
The main loop services audited list/byte-array operations and selected pin
operations, publishes a rooted result and its error, and the worker resumes.
Arithmetic/control instructions still execute concurrently on their physical
cogs. This serializes individual heap/peripheral operations, not whole tasks.
An explicit atomic list-element add is one service operation; separate at/add/
atPut instructions are not an atomic increment.

Allocation fill values also need a temporary GC root on the main C stack.
String character extraction must copy bytes before allocating its result.
Any allocator call that escapes the worker service path must fail before
touching allocator state. Unaudited named primitives, broadcasts, printing and dynamic calls remain
refused. Foreach retrieves its next value through the main service, including
allocating Unicode characters from a string. Shrinking the source list can
raise a checked index error.

Acceptance adds heap references held only in worker locals across repeated
main GC, list allocation and resizing with concurrent worker access, nested
objects and exact atomic list totals, byte-array read/write, worker waits and
nested calls, deferred object returns, routed pin ownership and stop/edit/reset
while requests are pending. Revision-2 serial and Smart Pin regressions remain
required. No expanded support is established by this contract alone.

## Revision 5 native acquisition jobs

A free worker cog can run a fixed firmware acquisition callback instead of a
MicroBlocks function. The two uses are mutually exclusive. The callback has a
separate pending/active lifecycle, uses the same guarded native stack, and is
joined by explicit cog stop, stop-all and code edits. It must hold no OBJ or
heap pointer and must not allocate, mutate the VM heap or drive DIR/OUT. GC
pauses interpreter workers; it need not pause these numeric-only producers.
This exception is restricted to audited firmware callbacks, not arbitrary user
native code or concurrent heap access.

The capture job owns acknowledgement of selected Smart Pin inputs while the
main cog retains pad/direction configuration. Reassigning a leased pin first
stops and joins the job. Scope uses cog-local SETSCP/GETSCP and CT1; SINC and
bit capture use RDPIN. Raw data crosses a static HUB ring, and read reporters
allocate list/byte-array results on the main cog. A VM worker can consume those
results through the existing rooted service path and scale raw integer samples
on its own cog. See [capture contracts](PROPELLER2_SMART_PINS.md#revision-5-streaming-contract)
for period, timeout, overflow and transport bounds.
