# Real-compiler and VM verification specification

Historical design/validation slice. The current native v4 entry point is
[SFC.md](SFC.md), including paired OR/AND branches and reproducible build/test commands.

Preserve the preceding sealed interface/export checkpoint. No GUI/browser,
serial port, board, dependency update or shared branch operation belongs to
this slice. Use the exact packaged GP 2.5.8 WASM engine/compiler in an offline
Node process. Replace only its virtual startup script with a test entry point;
the original packaged files remain unchanged. Node's bundle references an
unlinked NODEFS symbol: use MEMFS for that empty `/external` mount, never mount
the host filesystem. No window/document or network/device API is provided.

Use the real MicroBlocksProject parser, SmallCompiler and SmallRuntime byte
generation. A minimal uninitialized scripter supplies its project and embedded-
library catalog without creating morphs or opening a connection. Record which
catalog is used, exact input/runtime hashes, compiler messages, chunk IDs,
global variable IDs, native-set indices, bytecode and sizes. Reject unknown-op
warnings, parser errors, truncation and chunks above the real runtime's 1000
byte guard. Test the actual generated program and bounded worst cases.

If possible, load these real compiled chunks into the existing portable
SmallVM under sanitizers through its actual local PTY protocol. Add only a
host-test adapter for the unchanged step C engine when the portable VM lacks
the Zephyr-only primitives. Preserve primitive-set indices and fake only the
explicit deterministic clock; never substitute a new interpreter for this
claim. Compare logical requests and reset/priority/parallel behavior with the
validated JS engine. Hardware timing remains unverified.

The parent now plans to retain GP on a separate branch and move toward the
JavaScript editor on main. This slice changes no branch or dependency; provide
a checkpoint inventory of portable JS, GP-specific UI/export/patches, native
P4 transport/primitive work and test harnesses for that later transition.

## Discrepancies reproduced with the real compiler

The prior export used GP-host `waitMSecs`, which SmallCompiler reported as an
unknown operation and skipped. Both graph and execution exporters now use the
actual `waitMillis` opcode (33). A 16-step/24-transition plan also compiled its
single reset function to 1070 bytes, exceeding SmallRuntime's 1000-byte guard.
Definitions are now grouped into helper functions of at most eight native
configuration calls, with false returns propagated to the reset block.
The prior sealed checkpoint is retained intact, including the failing source.
