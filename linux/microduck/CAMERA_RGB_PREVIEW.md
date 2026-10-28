# Bounded RGB preview and typed pixel contract

Extend the committed finite camera snapshots without adding a capture loop or
changing raw Y/U/V semantics. Pollen commit 96b89d8613f06722c1d64ce75ab0d7124fed9d8f,
`uyvy/src/lib.rs`, supplies the BT.601 limited-range integer conversion and the
inverse 0/90/180/270-degree index mapping. Preserve the Apache-2.0 attribution.

Add `rgb` to the existing checked pixel request. Return one packed RGB24 number
with unit `rgb24_bt601_limited`; zero is valid black. Missing, expired, malformed
and out-of-range readings remain unavailable. This is an interpretation matching
the pinned implementation, not measured color calibration. Native decoding must
reject mismatched units and values outside 0..16777215. Normal and simple RGB
blocks share the same immutable capture/release path and coexist with raw blocks.

Provide a reusable browser UYVY-to-RGBA preview converter accepting only validated
geometry and an exact Uint8Array, at most 16 MiB. Fit inside a maximum 160-pixel
long side, never upscale, and allocate only the destination pixels. Apply reported
rotation only when explicitly selected. Use deterministic integer half-up sizing;
do not claim exact equivalence to every upstream f32 rounding boundary. Missing or
truncated input is an error, never a fabricated black region. The maximum RGBA
output is 102400 bytes. A renderer owns one canvas, clears the prior pixels before
replacement/error, and clears on hiding, page exit or explicit Clear. No result
history, image export, URL input, fetch, live capture or timer-driven recapture.

The graphical lab uses fixed fictional UYVY test cards with explicit fixture labels
and manual conversion controls. It tests rendering and errors only. It does not
connect the browser to the VM, imply per-block inline image output, or turn the
existing camera observer into a native video decoder. Keep that integration gap
visible. Existing library formats and the ordinary/Starter bundle contents stay
unchanged; only the optional Camera Lab gains RGB blocks.

Acceptance: exact known colors/clipping, all rotation corners, aspect ratio,
downscale-only behavior, malformed/detached/oversized input, bounded allocations,
clear/error lifecycle, normal and simple RGB on the actual sanitized VM through
faithful Unix fixtures, actual JS import/compile/reopen, and a graphical fixture
check when supported. Run the unchanged full validator. No Pi changes, physical
camera, actual robot commands, shared-main change, publication or denied reboot.

Assess continuous video against pinned `mediad/src/session.rs`, `stream.rs`,
`pipeline.rs` and the existing WebRTC observer. Local `media.frame` closes after
one snapshot. `media.stream {}` is status; a URL starts an outbound stream and
`url:null` stops it. Those mutations and a receiver destination are outside this
read-only slice. Document trusted signaling, codec/native-decoder acceptance,
bounded queue/drop handling and shipping commissioning as remaining gates.
