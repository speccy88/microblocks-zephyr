# Bounded RGB camera preview

This checkpoint adds normal and simple packed RGB24 pixel blocks to the existing
immutable frame path. Their explicit unit is `rgb24_bt601_limited`. They use the
same capture/release and unavailable semantics as raw pixels. Camera Lab now has
12 modules and 229 functions; ordinary and Starter bundle contents are preserved.

The browser converter samples UYVY directly into at most 160 by 160 RGBA pixels
(102400 output bytes), without a full-resolution RGB intermediate or upscaling.
Input is capped at 16 MiB and must match exact geometry; partial or extra bytes
are errors. Optional reported rotation changes presentation only. One canvas is
owned; replacement, error, Clear, hiding and exit clear it. Temporary RGBA arrays
are zeroed after drawing. Browser-owned canvas storage is additional to the output
array; these are buffer bounds, not a measured whole-process memory ceiling.

Pollen's pinned conversion/indexing source and license are attributed in the code.
The local dimension fit uses deterministic integer half-up rounding. Color values
match the reviewed BT.601 limited-range implementation, not measured calibration.
The browser lab uses only a fixed fictional card; it has no live URL, file import,
capture loop, VM link, recording or robot command.

Graphical checks in the in-app browser passed: stored 8 by 4 preview, optional
90-degree rotation to 4 by 8, downscale to 2 by 4, truncated-frame error clearing
the earlier image, successful recovery, and explicit Clear. The rotated marker
and black/white/red/blue bands were inspected visually. Screenshots and AX states
are retained. Native decoding, physical footage, responsive viewport coverage,
hidden-page behavior and per-block VM image rendering were not graphically tested.

The first sandbox preview listener was not reachable from the browser and was
stopped. Inspecting that tab's generated data-URL error page was refused by browser
URL policy; it was not bypassed. The separately approved host-loopback server then
served the original HTTP fixture successfully. No firewall or security settings
changed. The owned preview tab and server were closed after the checks.

Focused validation passes 22 Unix/native camera tests, 3 actual pinned JS library
and compiled VM tests, and 3 preview tests (including six Node conversion/lifecycle
cases). A compiled RGB failure found a real generic extractor defect: its 16-byte
unit bound rejected both RGB and the existing degrees_clockwise unit. The bound
is now 32 bytes with extraction and overlong-unit regressions. An earlier test
wrapper expected TAP while Node selected a human reporter; the wrapper now
requests TAP explicitly. Failed and successful logs are retained.

The first complete 599-test run had one environment failure: Windows Node's
`--test` worker could not reopen the WSL replica's UNC script path. A direct-run
probe then exposed package lookup traversing above the WSL share. The wrapper
now copies the exact two test inputs into a temporary directory with an explicit
CommonJS package boundary and executes `node:test` directly with its TAP reporter.
It still requires all six cases to pass. No assertion or deadline was removed.

The [continuous-video assessment](../../../docs/MICRODUCK_CONTINUOUS_VIDEO.md)
separates finite media.frame, browser WebRTC and the outbound media.stream API.
No continuous path or stream mutation is enabled. Inline MicroDuck image output
still needs a bounded VM-to-editor transport; the existing P4 RPC is not an
upstream MicroDuck interface. Mediad audio remains unsupported by the reviewed API.

No Pi operation, physical camera, movement, publication, shared-main change or
reboot occurred. The denied complete-installer reboot is still not retried.
Final full-validator results and frozen-source hashes are in the separate receipt.
