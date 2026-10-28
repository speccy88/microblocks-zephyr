# Proposed Linux targets on the current public portal

The public Pages workflow publishes `main`, currently `9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226`.
The Linux targets are on the migration branch at `2c060b7f4e9153dd7213d9b7c2a479810577eb51`.
Publishing that branch alone does not update Pages. This proposal does not deploy or change either branch.

Build the stable and migration GP portals separately using each immutable source's
`tools/package_pages.py` and its verified cached GP assets. Compose them using
`tools/package_pages_linux_preview.py --stable STABLE_BUILD --linux LINUX_BUILD
--output PROPOSAL --stable-commit 9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226
--linux-commit 2c060b7f4e9153dd7213d9b7c2a479810577eb51`.

The proposed homepage keeps the existing five GP editor directories byte for byte.
Only the homepage selector and routing script change. Raspberry Pi 5 opens
`preview/editor/raspberry-pi5/microblocks.html`; MicroDuck Rockchip RK3566 opens
`preview/editor/microduck/microblocks.html`. Their dependencies and license notices
live below `preview/`, separate from the stable editor assets. The composed artifact
records both input trees and every output hash in `linux-preview-manifest.json`.
Unexpected stable routing, an enabled MicroDuck connection, overlapping paths or
an occupied output directory fail the composition.

Pi 5 is a standalone Linux target and needs no robot services. The HTTPS public
editor requires a trusted WSS bridge; the tested loopback SSH workflow uses the
Pi-hosted editor. No released installer is advertised by this proposal. MicroDuck
remains a disconnected experimental placeholder for offline editing until physical
hardware acceptance. Neither target connects automatically.

This preserves the current GP public experience while JavaScript editor migration
continues separately. It does not yet replace the homepage with the JS editor, merge
unreconciled P4 work, enable Pages preview deployments, or publish a release.
Review and coordinate an explicit main/workflow change before publishing the
composed artifact. Rebuild against the then-current main commit and recheck all
five editor hashes; do not overwrite a newer public main build with this snapshot.
