# Eight-target JavaScript editor checkpoint

Local isolated branch `codex/js-editor-migration-20261027`, based on `bee8cee`.
No publication, hardware connection, firmware build/flash, new Pi execution,
security/network change, reboot or paused SFC implementation occurred.

## Verified

- All eight explicit profiles package from JS pin
  `5564b1e42d6790360450ebf11c9eb33a1c6877f2`. The audit rehashed all 5,648 output
  files, including each profile's 550 upstream files and 1,071 unchanged GP files.
  Combined uncompressed artifact: 215,082,486 bytes. Site manifest SHA-256:
  `da98d72316355feae60d2f2de306f0dd581d49694e3274cc2adb39422d379f28`.
- Actual pinned library import, compiler, block morphs and serializer pass for
  six board bundles, including exact raw source copies and canonical round trips:

| Profile | Modules | Functions compiled | Native palette specs compiled |
|---|---:|---:|---:|
| Fruit Jam |1|0|4|
| Waveshare RLCD |1|0|14|
| Propeller 2 |1|3|17|
| ESP32-P4 |10|59|114|
| Production XRP RP2350 |5|53|0|
| UNO Q reference |1|3|6|

  XRP's native operations occur in ordinary function bodies; zero native palette
  selectors does not mean zero compiled library behavior. Every function fits
  the tested chunk bound, and no unknown operation/expression was skipped. P2's
  used instruction numbers also match the preserved native v405 dispatch.
- Five enabled board profiles pass the **actual pinned connection class** with
  fragmented USB version responses. Version/board identity precedes Stop All
  and the editor synchronization hook. Wrong identity closes the session before
  either; UNO Q makes zero provider requests. P2 requires 405, the other four 417.
  These are protocol fixtures, not physical USB acceptance.
- Fourteen USB ownership/queue checks and ten provider/firmware-policy checks
  pass in the full suite. Cancellation, cleanup failures, read-side disconnect,
  byte-view copies, receive/output bounds, ordered 63-byte fragments, stale
  queued uploads and malformed board identities are covered. P2 DTR stays false.
- Real local IAB graphical acceptance shows all eight hub entries, all ten P4
  library categories and its camera palette, the production XRP palette and
  dependencies, and the UNO Q matrix/reference palette with connection disabled.
  The three editor tabs report no captured warning/error console entries. A
  semantic category click timed out without changing selection; a fresh
  screenshot-grounded normal click selected the camera category. No denied
  Edge action, long CDP retry or hardware chooser was used.
- **498 tests, zero failures, zero skips**, 246.425 seconds in the unchanged
  `tools/validate.py`; 247.675 seconds including wrapper overhead. The local
  Linux native fixture SHA remains
  `695fc61a5d4ed119704eb84e4828b738816667d53bb9b4b83d06e350222c02a1`.
  This does not add ARM64/Pi or hosted-CI evidence.

The authored Clock/Storage libraries used unsupported `while` selectors in
both pinned SmallVM compilers. They now use equivalent supported `repeatUntil`
loops. Quoted GP function names are included in the missing-dependency guard;
the pinned production XRP and its four dependency files remain verbatim.

## Reproduction and evidence limits

Build with `tools/package_js_site.py` as described in
[JS_SIDE_BY_SIDE.md](../../../docs/JS_SIDE_BY_SIDE.md). `build-audit.json`, the
actual-class fixture JSON, browser AX/console records and screenshots record
the accepted artifact. The owned 127.0.0.1:18899 preview and four test tabs were
closed; pre-existing sessions were preserved.

The full Linux replica copied and byte-verified 2,206 frozen repository inputs
before running validation. The verified copy ledger and original input ledger
still match every corresponding working file after validation. The temporary
WSL replica was absent on post-run inspection, so **no post-run replica rehash
is claimed**. The validator completed successfully and its untrimmed log and
receipt were retained. Text receipts and the log are normalized only from
captured UTF-8/newlines to UTF-8 LF; original and archived hashes are in
`evidence-hashes.json`. No lines or records were removed. The vendored upstream
library whitespace remains byte-exact and is excluded from the authored-file
whitespace check; its manifest hashes are verified separately.
New evidence files were added after validation; tested implementation files
were not edited afterward.

This artifact copies an existing local GP build unchanged. Its earlier
Windows-generated P4 text-encoding caveat remains; a future public build should
use the verified Linux UTF-8 pipeline, not publish this Windows GP copy blindly.

## Remaining work and publication

P4 message extensions, inline image/audio views, NN/files browser interfaces,
board-hosted network/WSS transport, physical board acceptance and later P4 owner
reconciliation remain unfinished. UNO Q and MicroDuck are offline placeholders.
Pi service/reboot and actual MicroDuck hardware acceptance remain separate.
The old ordinary Steps & Transitions library is imported unchanged; paused SFC
graph/editor development was not resumed. Continue daemon integration and the
coexisting simple/advanced MicroDuck libraries after the editor migration.

No approval was pending or denied in this slice. A read-only remote check still
reported main `6e2b4f9`, GP `3905dc1`, migration `2c060b7`. Nothing new was pushed.
This checkpoint includes screenshots, logs and local lab paths; publication of
that payload is outside the earlier exact-checkpoint approvals and requires its
own scope review. See the [migration matrix](../../../docs/JS_TARGET_MIGRATION_STATUS.md).
