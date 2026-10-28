# P4 JavaScript service checkpoint

Local migration follow-up to `87d70ed`. No publication, firmware build/flash,
physical board/Pi execution, camera/audio capture, network/security configuration,
reboot, protected P4 checkout/COM5/COM12 access or paused SFC work occurred.

## Implemented

- Bounded dispatch for the preserved P4 image/media/neural/files response IDs,
  interleaved with ordinary VM messages. Each consumer receives a copy. Wrong
  bounds disconnect the session; pre-identity service traffic is dropped.
- Typed device-files controller, wire/client and actual dialog share the
  identified VM connection. Explicit RAM session opening, conditional writes,
  cancellation/uncertainty semantics and unavailable Flash/SD remain intact.
  The production package includes no browser file fixture.
- Neural backend/catalog/local-model controls use the existing native dense
  protocol and current blocks. Every asynchronous action owns its connection
  generation; a reconnect cannot receive an old action's next request. Model
  metadata, artifact bounds and browser SHA-256 are checked before upload.
  Errors and timeouts remain errors; no actuator binding or cloud fallback.
- An explicit P4 WSS option accepts only a bounded `wss://.../ws/vm` endpoint
  without credentials, query, fragment or control characters. It preserves
  browser TLS verification, waits for `ready`, then verifies board/version
  before program/service writes. No endpoint is stored and no real endpoint
  was contacted. A trusted board TLS endpoint is not commissioned by fixtures.

The P4 native and existing GP service sources inspected here match public main
`6e2b4f9`; their files remain unchanged. No newer P4 branch was published at
inspection. A newer unpublished owner checkpoint is still unknown. The preserved
media implementation originates at `3063bf1`; the JS engine remains independently
pinned to `5564b1e42d6790360450ebf11c9eb33a1c6877f2`.

## Verified

**501 tests passed, zero failures/skips, 266.566 seconds** in the unchanged full
validator. The producer also rehashed all **2,231 source inputs in both working
tree and test replica after validation**, before exiting; every digest matched.
The wrapper including that check took 274.271 seconds. `summary.json`, the full
untrimmed log, source ledgers and runner record this exact revision.

Eight new protocol/lifecycle checks and five synthetic WSS checks exercise the
actual pinned connection/CommPort classes. They cover fragmented/interleaved
ordinary and extension replies, native size boundaries, pre-identity data,
handler isolation, request validation, reconnects, stale closures, unavailable
neural backend and uncertain timeout semantics.

The native file bridge additionally executes the real portable C storage,
dispatcher, wire/controller/protocol, and the sender extracted from the verified
v417 runtime, under ASan/UBSan with leak checking. Through the actual JS
connection and synthetic USB it opens a session, reads capacity, writes/reads
exact bytes, refuses an existing path and conditionally replaces the correct
revision. This is a **native C service fixture**, not physical USB or an entire
P4/SmallVM hardware execution claim. The final log records:

- Runtime source SHA-256: `d12c4c258b34555dbbf5e7e50770b4af0cec1b7ba282dadc3a6fd57002685f3b`.
- Extracted sender SHA-256: `21c3c71bce5b86e4561b21daab17866a23fa1ff2d0108c50ca34524b3d57d211`.
- Final sanitized fixture SHA-256: `75a2117a772862c074338519a140b4ecfbca40b687af19595509acd345050d11`.

Actual local IAB acceptance renders the file dialog and neural controls,
rejects disconnected neural actions, disables disconnected file actions, and
shows RAM as temporary with Flash/SD unavailable. The UI rejects an insecure
`ws://` address before socket creation. All ten existing target library categories
still import. Captured browser warning/error logs are empty. The URL input's
Playwright fill failed; the supported native value/click actions succeeded.
No Edge retry, hardware chooser, certificate bypass or download loop was used.
The one owned preview tab and PID-verified local server were closed.

The P4 package audit verifies 589 files, all 550 upstream files, and ten exact
service-source copies. Its build-manifest SHA-256 is
`ba180a8522e8cf4eb863310292a05997ee711a516f5e6f7d7b40cda347670027`.

## Earlier failures retained

The first full run had one failure among 501 tests: WSL did not forward the
temporary binary-path environment variable to Windows Node, so no native child
started in that check. Explicit JSON arguments and an explicit WSL executable
path fixed the harness without changing environment/security settings. Focused
runs then exposed two more fixture assumptions: missing browser AbortController
and a call to nonexistent `Client.open` instead of `Client.read`. Both were
corrected. The focused native bridge and final full run pass.

Failed logs/receipt and the first input ledger remain alongside the final
results. The first-to-final source delta in `summary.json` contains only those
three test/helper files; product sources did not change during these corrections.
Archived text is normalized only to UTF-8 LF, with original/archive hashes;
no lines or records were removed. Screenshots remain byte-exact. New evidence
files were added after validation; tested implementation inputs stayed unchanged.

## Remaining boundaries

Inline per-block image/audio views, transparent compiler tracing, media wrapper
readback/lifecycle and broader target-specific decompiler/library restoration
acceptance remain unfinished. No camera/PCM bytes or actual TFLM inference were
obtained through this new browser revision. Real USB/WSS, C6 networking, TLS
commissioning, current-owner firmware reconciliation and physical acceptance
remain separate gates. Continue those editor tasks before the queued MicroDuck
daemon and coexisting beginner/advanced libraries.

Nothing was pushed and main, GP and the live site remain unchanged. No approval
was pending or denied in this slice. This checkpoint contains lab paths/logs and
screenshots; publication is outside the earlier exact-payload approvals.
See [the service spec](../../../docs/JS_P4_SERVICES_SPEC.md) and
[migration matrix](../../../docs/JS_TARGET_MIGRATION_STATUS.md).
