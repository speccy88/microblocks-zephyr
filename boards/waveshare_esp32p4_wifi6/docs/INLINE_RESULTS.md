# Per-block image and audio results

Fred requested inline results on 2026-10-25, in both USB and self-hosted
editors, with the Pages distribution updated as well. This is a required
UI stage, implemented in the pinned GP renderer and the P4 snapshot protocol.
See the dated acceptance evidence for the exact physically tested boundary.

Image-producing blocks (capture, resize, grayscale, RGB conversion and future
transforms) show their own most recent output snapshot beneath the actual
block. With no result they remain collapsed. The first result expands the
preview by default; an accessible +/minus control changes visibility without
executing the block. Preserve an explicit collapse on later results within
the session. Preserve aspect ratio and readable block layout.

Native handles can be released immediately by scripts. Therefore previews
must use bounded copied result snapshots tied to the executing block/site,
not retain raw VM/native pointers or substitute the latest global image.
Bound thumbnail count/bytes and browser decoded-image memory. Expired
snapshots show a clear state and never display another block's result.
Project reload starts with no cached image. Cached results are not project
source, autosave contents or automatic network/cloud uploads.

Audio-producing blocks use the same expansion rules, with duration and
accessible Play/Pause controls. Playback happens only after an explicit
browser click, without starting a new recording or using a board speaker.
Preserve PCM sample rate/channels when creating local audio blobs. Bound
audio snapshot memory, stop old playback and revoke blob URLs on eviction,
rerun, project replacement/reload and disconnect as appropriate. Never
autoplay, save private clips to Git or upload them to a service.

Test the real GP block renderer and actual executed pipelines: several
distinct producing blocks, no-result state, first result, user collapse,
repeat execution, stale handles, layout/scrolling, reload, short/silent/normal
audio, play/pause/replay and cache cleanup. A separate fake card gallery does
not satisfy inline block rendering. USB and WebSocket transports share the
same result/snapshot contract. Acoustic quality and recognition accuracy
remain separate physical checks.

## Implementation and bounds

The genuine GP Block owns a P4MediaView child, outside its project expression.
The compiler wraps each visible producing expression with a transparent native
`mediaSnapshot(handle, site, session)` call. The original handle and evaluation
order are preserved. Library helper internals without a visible block are not
duplicated into result views. Runtime site IDs are monotonic within the page;
media, IDs and session state do not enter saved `.ubp` source.

The VM thread copies a thumbnail (at most 160 x 90, preserving aspect ratio)
or at most 8 seconds of 16 kHz mono PCM into four immutable native slots with
a shared 512 KiB limit. Scripts may release their original image/audio handle
immediately. A bounded eight-event queue announces site/token pairs. Each
read checks the session, site, token, offset and 512-byte maximum; an evicted
token fails rather than aliasing another result. Disconnect and Stop All
clear native copies; Stop All retains the negotiated session for recompilation.

Message 208 carries capability/session/metadata/read/release requests; message
209 announces results. Both use the existing VM byte stream, so USB and a
future board WebSocket use the same protocol. This does not establish that
the C6 network target or board-hosted assets are operational.

The browser retains at most eight results, two audio clips and 1 MiB of
accounted media (image bytes plus decoded RGBA, or WAV bytes). GP keeps at
most eight result-view references so eviction also clears deleted blocks in
undo history. Incoming audio becomes a local Blob URL; replacement, eviction,
project replacement/reload and disconnect stop playback and revoke URLs.
Rerunning stops and expires old audio before the new recording. Image pixels
are drawn by GP; the HTML overlay supplies accessible controls at those actual
block coordinates. Controls are clipped with the script viewport and hidden
behind the project/camera panels. No result control executes a block.

`tools/test_p4_results.py` runs portable ownership/error/reuse tests under
ASan/UBSan. `node --test tests/p4_media_core.test.js` checks wire fields, exact
known pixels, WAV sample rate/length and bounded cache disposal.
`tools/test_p4_media_usb.py --execute --evidence PATH` tests physical COM5
snapshots using generated images without taking a camera picture.
