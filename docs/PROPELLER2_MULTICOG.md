# Native P2 cog execution contract

The P2 extension keeps the main VM and IDE receiver on their existing cogs.
Named, zero-argument MicroBlocks functions can be launched on another explicitly
selected physical cog. Each worker has its own interpreter error/sleep state,
Task stack and guarded native C stack. A reporter returns the actual cog ID.
This must be real hardware execution; a global lock around whole interpreter
runs is not an implementation of parallel execution.

The first implementation supports scalar/control worker code: integer and
Boolean variables, arithmetic, comparisons, loops, waits, ordinary function
calls and explicitly whitelisted P2 scalar primitives. Heap allocation,
lists/byte arrays, broadcasts, printing and peripheral primitives on workers
fail explicitly until their concurrency and ownership contracts are implemented.
They remain available to ordinary scripts on the main cog. Immutable string
literals may name a function or shared variable; workers may not adopt heap
objects from shared variables.

Normal MicroBlocks variables live in shared HUB RAM. Individual reads/stores
and the native `change variable by` instruction use a hardware lock. A separate
read followed by arithmetic and a store is still a multi-instruction operation;
it is not atomic. Named scalar read/write/add blocks provide an explicit shared
variable interface. The main collector pauses workers at opcode boundaries
before forwarding roots; code/name edits stop workers before changing persistent
code. Stop-all, reset and live editing must never leave an interpreter running
against changed code or cleared memory.

Existing GPIO and Smart Pin ownership stays on the main cog. Workers must not
change their own DIR/OUT registers: floating a pin on one cog cannot release a
driver owned by another. Autonomous Smart Pins can continue while worker cogs
compute; main scripts can exchange numeric commands/results through shared
variables. This is not a claim of arbitrary peripheral access from every cog.

Acceptance before a physical PASS:

- Build Eval, original Edge and EC32MB with the pinned native FlexC toolchain.
- Launch two different functions on distinct requested physical cogs and record
  their actual IDs and simultaneous progress while USB ping stays responsive.
- Run exact shared-variable increments from multiple cogs and verify N times M.
- Exercise main-cog allocation/GC and list mutation while scalar workers run;
  verify roots, results and worker stack canaries.
- Reject unsupported worker allocation/I/O rather than execute it unsafely.
- Stop, restart, live-edit and reset with no stale worker or lock ownership.
- Measure native-stack usage and retain canaries at both ends. FlexC's cog-start
  macro does not enforce its stack-size argument.

The code, tests and dated evidence determine implemented/validated status.
This document is the implementation contract, not a physical test result.
