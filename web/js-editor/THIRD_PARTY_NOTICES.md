# Pinned JavaScript editor: notices and source

This experimental package uses the official MicroBlocks source repository:
https://codeberg.org/MicroBlocks/smallvm . `source-manifest.json` records the
exact commit, Git blob IDs, SHA-256 digests, original paths and sizes. The
matching source is available at that commit; the engine is included unchanged
in source form. Local integration sources are in `web/js-editor/` of the
MicroBlocks-Zephyr migration branch. Keep these notices with redistributed files.

- MicroBlocks editor engine and relevant local adaptations: MPL-2.0; preserve
  each source header. The upstream notice and full MPL text are under
  `licenses/upstream/`.
- `engine/mb-blocks.js`: Jens Moenig's source header explicitly licenses this
  Snap-derived file for MicroBlocks under MIT (26 August 2026) and contains the
  complete permission notice.
- `engine/morphic.js`: its source header explicitly records Jens Moenig's
  MIT license for use in MicroBlocks (17 October 2026), alongside the original
  Snap AGPL notice. Preserve the complete header, including both statements.
- `lib/marked.umd.js`: MarkedJS / Christopher Jeffrey, MIT, with its upstream
  copyright header retained.
- `lib/FileSaver.js`: Eli Grey, MIT, with its upstream copyright header and
  license source link retained.
- `lib/usbDfuDevice.js`: Silicon Witchery AB, ISC; full notice in that source.
- Local packaging tools: MIT, see `licenses/LOCAL-MIT.txt`.
- The production XRP, PID, Encoded DC Motors, Servo, Distance (HC-SR04) and
  UNO Q reference libraries are exact copies from the existing GP asset pin
  `70690291ac44a5c3a50dce572ee0c29ba99dc57f` of
  https://github.com/speccy88/uno-q-microblocks . Their author/version notices
  remain in the source. `target-libraries.json` records the original asset
  paths, containing-asset hashes and each copied file's hash. They retain the
  MicroBlocks MPL-2.0 distribution terms; the full license is packaged above.

Source headers and individual asset notices govern their respective files;
the repository's root MPL notice does not replace third-party notices. This
package does not contain a firmware image, GP WASM runtime or a new VM build.
No release/publication or legal review is claimed by staging it locally.
