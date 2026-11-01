# Native branch icons: named resources

Cloud review of the v3 editor showed gray squares in place of the bar icons.
The old mapping returned inline XML after `#SVG#`. GP's normal Block.labelText
passes that suffix as an icon name to newSVGImage/readSVGIcon, which loads
`img/<name>.svg`. Missing data produces a 10 by 10 gray bitmap. The older tests
only checked the XML and label prefix, so they did not exercise this contract.

The fix maps each marker to a stable resource name (`#SVG#sfc-or-split`, etc.)
and packages all four files under `/img/` in the GP embedded filesystem. The same
resources are included in the browser archive's `img/` directory. The normal
SVGReader handles their scale, foreground color and cache; no rendering API or
graph compiler semantics are changed.

The real GP software-render test also exposed that this SVGReader interprets
later `M` commands inside one path as connecting lines. Each stroke is now its
own path element, avoiding accidental diagonals and keeping the double-bar gap.

Acceptance: verify embedded/external resource bytes, exercise the real GP
labelText/readSVGIcon lookup, assert proper dimensions and distinguish single
and double bar raster geometry where supported, compile all regression cases,
compare generated SmallVM chunks byte for byte with the v12 validated outputs,
and run the required full repository suite. Full browser rendering is reviewed
separately in the supported cloud browser. Do not deploy to hardware.

The Node host has no document/canvas: invoking GP's browser vector primitive
there fails with `ReferenceError: document is not defined`. Pixel/label tests use
the upstream VectorPen's `fakeVectors` test flag (pure GP software fallback),
without browser emulation. They prove named lookup and geometry through the real
SVGReader and Block.labelText; native browser rasterization still needs review.
The test flag is not included or enabled in the packaged editor.
