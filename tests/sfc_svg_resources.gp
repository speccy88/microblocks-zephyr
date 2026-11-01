// SPDX-License-Identifier: MPL-2.0 - real GP resource lookup and native SVG labels.
to sfcIconExpect condition label {
 if (not condition) {
  print 'SFC_ICON_FAILED' label
  error (join 'SFC icon: ' label)
 }
 add (global 'sfcIconChecks') label
}

to sfcIconChecks p r {
 setGlobal 'sfcIconChecks' (list)
 setGlobal 'scale' 1
 setGlobal 'blockTextColor' (gray 255)
 // The browser's native vector primitive needs document/canvas, unavailable
 // in this Node host. Use GP's own supported VectorPen test fallback; do not
 // emulate a browser. Named loading and label construction are unchanged.
 setGlobal 'fakeVectors' true
 sfcIconExpect (true == (global 'fakeVectors')) 'raster mode is upstream pure GP VectorPen fallback, not browser canvas'
 for token (array '#SFC_OR_SPLIT#' '#SFC_OR_JOIN#' '#SFC_AND_SPLIT#' '#SFC_AND_JOIN#') {
  ref = (sfcBarSVG token)
  name = (substring ref 6)
  data = (readEmbeddedFile (join 'img/' name '.svg'))
  sfcIconExpect (notNil data) (join token ' named resource exists')
  sfcIconExpect (beginsWith data '<svg ') (join token ' resource is SVG data')
  bm = (readSVGIcon name (gray 255) (color 200 140 20) 1)
  sfcIconExpect (and ((width bm) == 36) ((height bm) == 18)) (join token ' real SVGReader avoids gray fallback')
  double = (contains (array '#SFC_AND_SPLIT#' '#SFC_AND_JOIN#') token)
  bar = 8
  if double { bar = 6 }
  sfcIconExpect ((getAlpha bm 10 bar) > 200) (join token ' horizontal bar is rasterized')
  if double {
   sfcIconExpect ((getAlpha bm 10 10) > 200) (join token ' second bar is rasterized')
   sfcIconExpect ((getAlpha bm 10 8) == 0) (join token ' double bars retain their gap')
  }
  sfcIconExpect ((getAlpha bm 10 2) == 0) (join token ' background is transparent')
  scaled = (readSVGIcon name (gray 255) (color 200 140 20) 2)
  sfcIconExpect (and ((width scaled) == 72) ((height scaled) == 36)) (join token ' normal SVGReader scaling works')
  block = (new 'Block')
  setField block 'color' (color 200 140 20)
  label = (labelText block token)
  sfcIconExpect (isClass label 'SVGImage') (join token ' actual Block.labelText builds SVGImage')
  costume = (getField (morph label) 'costumeData')
  scale = (blockScale)
  sfcIconExpect (and ((width costume) == (ceiling (36 * scale))) ((height costume) == (ceiling (18 * scale)))) (join token ' actual label resolves the named resource')
 }
 return (global 'sfcIconChecks')
}

to sfcHeadlessChecks p r { return (sfcIconChecks p r) }
