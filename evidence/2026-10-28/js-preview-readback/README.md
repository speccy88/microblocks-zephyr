# Refreshed eight-target JavaScript preview

The local preview includes the corrected readback adapter from the real Pi
graphical checkpoint. It has eight targets: Raspberry Pi 5, MicroDuck Rockchip
RK3566, Fruit Jam, Waveshare S3 RLCD, Propeller 2, ESP32-P4, XRP and UNO Q.
The Pi target needs no robot services; MicroDuck and UNO Q retain their existing
placeholder/connection restrictions.

**5,704 output files** are hash-verified. All **1,071 archived GP fallback files**
are preserved byte-for-byte. Each profile verifies 550 pinned upstream source
inputs, with all 31 engine files unchanged. All eight packages include readback
adapter SHA256 `703b92381bd8cc0831ccdc407a03005ef8a8f21523832f15d72942f6deb05fab`.

The P4 hub description now reflects implemented inline image/audio views and
their fixture testing, while keeping physical JavaScript hardware acceptance
pending. This is the only product change after the preceding Pi/P4 checkpoint;
no runtime or dependency upgrade is involved.

The final unchanged validator passes **541 tests, zero failures, zero skips** in
318.383s, with all **2,476 frozen inputs** matching afterward in both source and
replica. The real Pi graphical results and their fictional robot-data boundary
remain in [the earlier evidence](../js-pi-readback/README.md). Other board hardware,
physical MicroDuck, live control/camera commissioning and unsupported mediad
audio are not validated by this static package.

Local archive (ignored build storage, **not deployed or published**):

`build-artifacts/js-all-targets-pi-readback-20261028.zip`

48,417,087 bytes; SHA256
`f15d839f70ad1d6a6f858704dfeb31a25a72643762553ba87c603f323524ab2f`.

[Archive receipt](archive-receipt.json), [full validation](full-validation-receipt.json),
[final verification](verification.json), and [raw manifests/logs](validation-and-manifests.zip)
record the exact inputs and outputs. The ZIP's CRCs and member list are verified.
The GP baseline is recovered from the earlier verified eight-target package's
preserved-file manifest; the existing source trees are not edited or deleted.

The live site, main, GP, protected P4 worktrees/ports and paused SFC are unchanged.
This is a reviewable development preview, not a physical acceptance or release
claim. New commits and their screenshots/logs/lab metadata are still local.
