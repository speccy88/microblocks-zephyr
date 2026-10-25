# Per-block image and audio results

Fred requested inline results on 2026-10-25, in both USB and self-hosted
editors, with the Pages distribution updated as well. This is a required
next UI stage, not an implemented feature of the current global preview panel.

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
