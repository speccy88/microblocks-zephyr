# Bounded local camera frame blocks

Implement the pinned API44 `media.frame` endpoint as a separate binary reader,
following [MediaFrameHeader](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/duck-ipc-proto/src/lib.rs)
and [mediad's snapshot client](https://github.com/pollen-robotics/microduck/blob/96b89d8613f06722c1d64ce75ab0d7124fed9d8f/mediad/src/snapshot.rs).
Exchange hello/API44, then media.frame without parameters; read one bounded JSON
header and exactly its declared bytes. Never put the raw method in generic NDJSON
control forwarding. Explicit private config selects mediad socket and expected
numeric UID; existing inode/peer/permission checks remain mandatory.

Accept tightly packed UYVY only, even width, positive dimensions, exact
width*height*2 bytes, at most16MiB, rotation0/90/180/270 and unsigned128 Unix-us
timestamp. Reject mismatched API, malformed geometry, truncated/extra tails and
overlong headers. One3-second transaction deadline; no retries or streaming.
Four retained/in-flight slots, five-second immutable snapshots, explicit release,
cancellation and shutdown cleanup. At most64MiB retained raw pixels. Read requests
return small JSON records, never a full image through SmallVM's JSON buffers.

Provide normal capture, metadata, raw Y/U/V and interpreted RGB pixel blocks. Coordinates are
1-based stored-image x/y, with no rotation, resize, calibration or
orientation inference. U and V are shared by a horizontal two-pixel pair; Y is raw
8-bit luma, not lux or a calibrated perception score. Exact captured_at_unix_us is
a decimal unsigned128 string; zero remains reported zero and is not freshness.
Errors, timeout, expired handles and out-of-bounds coordinates are unavailable,
never black/zero. local_ipc means transport, not physical camera validation.

Keep the existing normal and Starter bundles unchanged. Add one optional Camera
Lab import containing Starter plus Camera and Simple Camera libraries, allowing
simple brightness capture/read/release and advanced coherent-frame blocks in
the same project. All mutation helpers remain simulation-only. No actual camera,
robot motion, audio, WebRTC, file recording or network configuration is involved.

Acceptance: faithful fragmented Unix binary fixture, malformed/timeout/UID/API
and resource-limit tests; actual native VM strict typed extraction and GC tests;
actual pinned JS import/compile/save/reopen and representative execution of simple
and advanced blocks together. Physical camera and graphical acceptance remain
separate gates; do not disturb the running Pi installer/reboot test service.

Configure only after independently checking the actual shipping socket and UID.
The optional `--camera-config /absolute/private/camera.json` uses the same private
file checks as other readers, with exactly `version:1`, `daemon:"mediad"`, `path`
and verified numeric `uid`. It is separate from the generic upstreams config.
No socket, permission, group or daemon setup is performed by this adapter.

Import **MicroDuck Camera Lab** in the development/MicroDuck JS profile. It includes
the existing ten Starter modules plus Camera and Simple Camera:229 functions total.
The ordinary six-module and ten-module Starter imports remain byte-for-byte
unchanged. `camera.ubp` demonstrates both levels. Use the shared reading-known,
status and value helpers; release a captured frame when finished. Repeating a
simple brightness call takes another snapshot, while advanced reads share one.

Tests run with synthetic 4x2 UYVY samples over real Unix sockets and the actual
sanitized native VM. The JS test uses pinned editor import/compiler/morph classes
and serialized project reopen, not a graphical browser. No new Pi binary was
installed and the existing Pi service/reboot checkpoint is untouched. Raw and
packed RGB pixel reading are implemented. The [bounded RGB preview](CAMERA_RGB_PREVIEW.md)
has graphical fixture acceptance in a separate lab, without a VM-to-editor image
connection. Inline image output, native video playback, continuous capture and
physical camera acceptance remain unimplemented/unverified. RGB24 uses the pinned
BT.601 limited-range interpretation, not measured color calibration.
