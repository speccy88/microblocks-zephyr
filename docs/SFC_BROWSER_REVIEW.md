# Native SFC branch prototype: browser review

This is the preserved genuine GP 2.5.8 editor with opt-in native SFC blocks.
Hardware connection is disabled. It is a review build, not production firmware.

The v4 build fixes the gray icon squares: four named SVG resources are embedded
in GP and included under `img/`. Each stroke has a separate path for GP's SVG
parser. Check that all four split/join icons show the correct single/double bars,
with no gray square or accidental diagonal connector. Use a fresh preview folder
for this build so the prior engine/data files are not mixed with the update.

Use a supported static browser preview in the reviewing environment. The builder
does not start a server or deploy firmware. Hardware connections stay disabled.

1. Open `index.html` through that environment's supported static preview.
2. Import `sfc-native.ubp` through the normal MicroBlocks project file control.
   It demonstrates three AND branches, each with setup/loop and a final step.
3. Inspect the native block shape, fonts, variable slots and double split/join
   bars. Expand a split with the normal MicroBlocks affordance. Import examples
   `sfc-and-6.ubp` and `sfc-or-6.ubp` to inspect counts above two.
4. Inspect single-bar OR alternatives and the shared merge transition in
   `examples/sfc-or-3.ubp`; inspect nesting in `examples/sfc-nested.ubp`.
5. Edit a condition variable and a setup/loop body; save under a new filename,
   then reopen it and compare branch count, nesting and content.
6. Capture the actual editor and visible branches. Screenshots must be labelled
   as browser authoring checks; this disconnected build cannot prove VM or P4
   execution, runtime green highlighting or physical I/O.

The real compiler has accepted ten valid examples, rejected 21 invalid ones,
and passed 43 headless GP checks. The real Linux SmallVM execution suite passes
152 assertions across ten cases, including join gating, reentry and task-pool
exhaustion. No P4 or full browser acceptance result is implied by those tests.
The new compiled SmallVM chunks are compared byte for byte with those validated
outputs. The added icon tests exercise real GP lookup/label construction and 37
pixel assertions using GP's software VectorPen fallback. The native browser
canvas path still needs this visual review; no browser shim is packaged.

Known limits: two to six branch slots; at most eight step workers across branch
charts; the pinned SmallVM has ten task entries. Large actions can exceed the
1,000-byte compiled chunk guard. OR priority is displayed order, top to bottom.
The current block layout nests native C-slots vertically; it is not a full
horizontal Grafcet drawing. Native rendering/edit/save/reopen still needs this
browser review. The sealed sequential editor remains a separate unchanged ZIP.
