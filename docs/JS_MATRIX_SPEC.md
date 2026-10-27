# GP slot compatibility: bounded first port

Preserve the pinned official JS sources and runtime. A separate local slot
adapter must expose legacy `b` library specs as JS reporter blocks without
changing the saved spec or its boolean value. Graphical testing discovered
that upstream otherwise omits these palette entries.

Port the inspected, fixed UNO Q 13x8 widget, not an inferred arbitrary-size
variant. Its ABI remains an ordinary String of exactly 104 row-major digits
`0` through `7`. Null/empty initializes zeros; invalid input must leave the old
pattern unchanged. Preserve presets, 1-based GP hit-testing, gaps/dropdown
exclusion, drag interpolation, scaled layout and independent copies.

Integrate through a separate JS prototype adapter so slot construction,
defaults, parsing, printing and copying use actual upstream classes. Verify
round-trip serialization and literal compilation, plus legacy predicate
palette inclusion. Do not register/guess a UNO Q native primitive-set index,
connect its hardware, or change its firmware. The Linux profile remains Linux.

Headless geometry/drawing-command tests are not graphical or hardware proof.
Record any actual graphical checks separately. Shared main, P4 and paused SFC
remain untouched. Keep the change and its provenance in an isolated checkpoint.
