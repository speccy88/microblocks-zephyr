# P2 mode-library acceptance plan (2026-11-07)

## Behavior
- Replace the five broad default palettes with small, explicit mode libraries.
- Add Simple IO: digital output high/low, plain input, input with pull-up or
  pull-down. Each operation initializes the mode using checked native primitives.
- Keep all existing selectors and function bodies byte-for-byte (apart from
  adding new wrappers). Raw X/Y/register configuration belongs in Advanced.
- Generate dependencies from cross-library function references, plus P2 Core
  for shared choices. Importing one mode must compile with dependencies alone.
- Monolithic saved libraries are reorganized by moving existing objects and
  retain function IDs. Previously saved five-library layouts/subsets remain
  unchanged; no replacement of their definitions is automatic.

## Non-goals and safety
No firmware/VM/protocol changes, board connection, resets, flashing, stored
program changes, revived DMA/external-clock/USB development, or new physical
claims. Existing reserved-pin and capture-ownership checks remain authoritative.

## Acceptance
1. Every canonical selector and function appears exactly once in generated
   libraries; original function bodies/specs are retained.
2. Every mode library imports and compiles independently through the real pinned
   editor; all cross-library calls resolve through generated dependencies.
3. Simple IO compiles; static tests verify primitive arguments and checked native
   paths reset Smart Pin mode/direction. Hardware electrical behavior untested.
4. Legacy monolithic object identities and function IDs survive organization;
   five-library saved projects/subsets, custom/stateful layouts remain intact.
5. No default mode palette exceeds 10 visible blocks (Advanced excepted).
6. Run focused Python/Node tests and tools/validate.py; report unavailable checks
   or pre-existing failures without claiming PASS.
