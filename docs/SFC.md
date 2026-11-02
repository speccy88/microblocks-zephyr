# Native SFC blocks

The active JavaScript web/mobile implementation is documented in
[SFC_JAVASCRIPT.md](SFC_JAVASCRIPT.md). It uses the actual upstream JS compiler
and normal SmallVM bytecode. The remainder of this page documents the retained
GP implementation and its reference tests.

This opt-in GP 2.5.8 editor adds native MicroBlocks sequence, step, transition,
alternative OR and simultaneous AND blocks. It is independent of the JavaScript
editor migration on `main`. The normal portal and firmware builders are unchanged.

Steps use shared MicroBlocks Boolean variables. Each has **setup**, executed once
on entry, and **loop**, repeated while active. A transition waits for its shared
variable to be Boolean true. Conditions persist; numeric 1 is not Boolean true.
Ordinary blocks belong inside setup/loop, not between flow nodes.

The split blocks use the normal expandable MicroBlocks command slots. Single
bars identify OR and double bars identify AND. Two through six branches are
accepted. AND activates every branch and waits for all final steps and the common
join condition. OR selects one enabled alternative in displayed order, top to
bottom, then waits for that path and its merge condition. Paired nesting is allowed.
This is a native block stack, not a full horizontal Grafcet canvas or a strict
Rockwell-compatible controller.

## Build and review

```sh
python3 tools/build_sfc_preview.py --fetch --output build-artifacts/sfc-editor
python3 tools/test_sfc_compiler.py --editor build-artifacts/sfc-editor --output build-artifacts/sfc-compiler
python3 -m unittest discover -s tests -p 'test_sfc_*.py' -v
```

`--fetch` retrieves only the immutable files and hashes in
`dependencies/ide-assets.json`; omit it when those originals already exist under
`build-artifacts/ide-source`. Choose fresh output directories. The generated
editor has hardware connection disabled, licenses, provenance and example `.ubp`
files. Use a supported static browser preview, import `sfc-native.ubp`, and review
editing and save/reopen. Building does not start a server, publish Pages or flash
firmware. The native SFC workflow uploads an editor/evidence artifact only.

The native editor removes the former graph UI from its generated assets. The
portable graph/action model, optional historical UI, fixtures and export tests
remain in source so their data is preserved. They are not required for native
block authoring or a mandatory export step.

## Runtime and limits

The compiler generates ordinary SmallVM functions: one coordinator and one
cooperative task per step. No new VM opcode or SFC firmware primitive is needed.
At most eight step workers are reserved across branch charts; the pinned VM has
ten task entries, 128 shared variables and 255 chunks. Admission checks actual
worker readiness before setup and fails within 500 ms if the task pool is full.
Each action must cooperate and finish. A blocking C primitive blocks the VM;
called code that stops/errors a worker or never returns can strand a join.

Active steps can appear green through bounded shared-variable reads in the
connected editor. Display state is not stored in projects. The disconnected
preview cannot establish actual live transport or hardware behavior. See
[implementation and remaining limits](SFC_BRANCHES_IMPLEMENTATION.md),
[scheduler source facts](SFC_SCHEDULER.md) and
[named SVG resources](SFC_SVG_FIX.md).

## Validation

The implementation checkpoint passed 152 assertions on real Linux SmallVM
bytecode, including six-way branches, shared joins, reentry, cooperative progress
and actual task exhaustion. The v4 icon fix retained byte-identical chunks for
all ten valid compiler fixtures. It adds four named SVG resources and separates
their strokes for GP's limited SVG parser. The GP lookup/label/pixel checks use
the upstream software VectorPen test backend; native browser rendering is a
separate acceptance check. Hardware/P4 execution is not claimed.

The repository's SFC workflow runs 31 valid/malformed compiler fixtures, 43
headless GP checks, 37 named-icon checks, package tests and retained C/JS model
parity tests. See the committed validation record under
`evidence/2026-11-01/sfc-v4/` for the exact integration base and measured results.
Generated binaries, upstream GP bundles, local credentials and private recovery
files are excluded from Git. The earlier serial/graph documents are historical
design records; this page and the branch implementation document describe v4.
