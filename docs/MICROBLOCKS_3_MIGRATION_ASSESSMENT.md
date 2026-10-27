# MicroBlocks 3.0 migration assessment

Read-only review on2026-10-27; no dependency, VM, editor or release was upgraded.
The [official announcement](https://microblocks.fun/blog/2026-10-27-microblocks-3.0/)
describes an upcoming pilot/alpha, a complete JavaScript/CSS editor engine built
on Snap components, and compatibility for existing projects/libraries/materials.
That compatibility promise is useful; our custom integration still needs tests.

Current pins: MicroBlocks2.5.8 editor assets from
70690291ac44a5c3a50dce572ee0c29ba99dc57f in dependencies/ide-assets.json;
SmallVMv417 at2071df569623ba9cdcd6f8106b61796e047df38b in
dependencies/smallvm-v417.json. The Linux LP64 port keeps compact32-bit objects,
persisted words and bytecode, with audited native-address boundaries. Its core
and persistence patchers deliberately reject changed source hashes/anchors.

## What is reusable and what must change

| Boundary | Observed evidence and migration work |
|---|---|
| Blocks and projects | Standard .ubl/.ubp format is promised compatible. Our libraries and Pollen service adapters should be reusable; custom namespace compilation, typed records and every example still need actual3.0 compile/run checks. No physical or graphical compatibility has been demonstrated. |
| Editor packaging | Current tools unpack gp_wasm.js/data and patch MicroBlocksCompiler.gp/API.gp with exact anchors. The [pure-JS preview](https://microblocks.fun/run-pilot/purejs.html) loads separate engine/mb-*.js files. This requires a new packaging/import adapter, asset/notice hashes and profile verification; the old GP patches cannot simply target the new files. |
| Compiler registration | Reviewed engine/mb-compiler.js has primitive sets0..21, no microduck or linux aliases. Our MicroDuck native set is22 and Linux aliases io. New compiler registration is required: its unknown-name path defaults to set0. Validate emitted bytecode against known VM scenarios, rather than accepting a visually loaded block. |
| Transport | Reviewed engine/mb-comm-port.js supplies serial/BLE/Boardie. Our Pi uses a private VM gateway plus a loopback/trusted WebSocket bridge. A JavaScript comm-port adapter and lifecycle/backpressure/disconnect tests are needed. Existing WSS/browser local-network gates remain; no warning bypass or port80 assumption. |
| Application API | Reviewed engine/mb-jsAPI.js retains project.save and board.vmVersion. Our portal.serialize/portal.load and Linux/MicroDuck library/example routes are absent and need equivalents. Restore, connection/board capabilities and autonomous scripts after IDE disconnect require acceptance tests. |
| VM update | An editor rewrite alone does not establish a requirement to replace v417. First test a separately pinned3.0 editor with this VM. If it requires newer firmware, audit and rebase LP64/GC/persistence/numeric patches and run fresh sanitizer/ordinary Pi acceptance. Do not disable hash guards or assume a native64-bit port is merely removing -m32. |
| Install behavior | The announcement adds an install offer when a board does not answer. Preserve Linux/board capability gating so a Pi transport failure does not suggest an MCU firmware install. Existing board-specific install flows need separate review. |

Assessment: likely straightforward reuse of service/block content, with meaningful
editor packaging/compiler/transport integration work. It is not a drop-in swap.
The shared bytecode/protocol design and retained API endpoints help, but an effort
estimate needs a stable3.0 source pin and a small compiled loopback prototype.

The parent's separate upstream review reports matching checked opcode/message
IDs, plus new board hooks and primitive sets in newer VM sources. That supports
the editor-first approach but is not this branch's end-to-end acceptance. A later
VM update must audit hooks and set indices as well as LP64 patches. The reported
absence of a queue lock in the non-Arduino boardHooks path also needs an explicit
Zephyr concurrency review. No Zephyr/P4 change or hardware access occurred here.

Suggested sequence, not yet performed: add a separate pinned3.0 experimental
profile; compile a Linux arithmetic block and one read-only MicroDuck reading;
verify namespace22 and bytecode, persistence/reconnect/restore; run library,
transport, seven-profile, sanitizer and real Pi acceptance; then coordinate
publication. Keep current2.5.8/v417 available during acceptance.

## UNO Q matrix and P4 image results

This review reads only this isolated repository and its pinned editor assets,
not the active P4 checkout, COM5/COM12 or a board. Later owner changes may differ.

| Feature | Stored/VM behavior | Custom editor/transport migration |
|---|---|---|
| UNO Q matrix input | Pinned UNO_Q_Hardware.ubl uses ordinary String patterns passed to custom native unoq matrix primitives. UnoQMatrixSlot emits104 brightness digits0..7 in row-major13x8 order; it is not a new VM bitmap object. Preserve that literal/native ABI and map unoq to the board's native set. | Pinned BlockSpec.gp recognizes the custom unoqMatrix slot and Block.gp includes UnoQMatrixSlot in argument/copy/layout handling. The slot paints, edits/drags and supplies presets in GP. Reviewed3.0 slots/specs contain stock microbitDisplay, but no unoqMatrix. Port an equivalent JS slot, spec dispatch, hit-testing, resizing/copy/undo/serialization hooks. Stock project compatibility alone does not implement this custom renderer. |
| Custom-size matrix variants | This pinned copy is explicitly fixed13x8; a newer arbitrary-size variant is not verified here. If another owner added dimensions or a different literal format, inspect that exact source before estimating parity. | A generic width/height JS grid can be planned, but must preserve the actual dimensions, pixel order, brightness levels and saved literal metadata. Test multiple non-square sizes, boundary painting, drag strokes, presets, copy/undo and project/autosave round trips. Do not assume the stock5x5 renderer already supports it. |
| P4 capture/resize/conversion | P4_Camera.ubl is standard library syntax wrapping this project's custom native p4 primitives. image_primitives.c dispatches camera_request/result, image_resize/grayscale/tensor and handle release; common/image/image_store.c owns portable images. With the runtime unchanged these need no editor-driven camera/resize rewrite, but namespace p4/io and argument/return ABI must compile correctly in3.0. PPA/asynchronous behavior remains firmware-specific. | Library import and compiler aliases need porting; a valid numeric handle alone does not provide a graphical preview. New editor compatibility has not been demonstrated. |
| Explicit image preview/export | Existing native preview protocol and web/p4-camera.js operate on copied/bounded data through the shared VM byte stream. Preserve handle lifetime, chunk framing/session/error semantics and browser-only export. | Adapt the connection adapter to the JS comm port. Keep message dispatch and JS cache/decoder reusable where contracts match; reconnect and resource disposal need testing. |
| Per-block inline previews | Native mediaSnapshot(handle,site,session) preserves the original result while retaining an immutable copy;208/209 messages share the existing connection. Scripts may release original handles. | tools/patch_p4_media.py injects compiler p4MediaTrace, Block.gp layout fields, GP API routes and Scripter stepping; web/p4-media.gp owns P4MediaView drawing/textures. These are GP-specific and need JS compiler/block/Morphic counterparts. web/p4-media-core.js wire/cache code and HTML controls can be adapted, not assumed drop-in. Preserve separate block/site identity, evaluation order, collapse/expiry, aspect ratio, viewport clipping, release/reconnect and bounded caches. |

Image result pixels/cache/site IDs must remain outside saved project expressions
and3.0's new autosave data. Test generated capture/resize/grayscale pipelines
with distinct per-block results, immediate handle release, collapse/rerun/eviction,
project restore and transport reconnection before any physical camera acceptance.
Existing native/PPA validation does not establish3.0 rendering. No matrix,
P4 source or transport implementation was modified for this assessment.

Reviewed local evidence: [inline-result contract](../boards/waveshare_esp32p4_wifi6/docs/INLINE_RESULTS.md),
[P4 library](../boards/waveshare_esp32p4_wifi6/integration/P4_Camera.ubl),
[GP hooks](../tools/patch_p4_media.py), [GP view](../web/p4-media.gp) and
[native primitives](../boards/waveshare_esp32p4_wifi6/zephyr/src/image_primitives.c).
The review receipt hashes pinned UNO Q virtual files and these isolated sources.

[Review receipt](../linux/microduck/tests/microblocks-3-source-review.json) records
the official announcement/preview and four engine-source URLs, byte counts and
SHA-256 values. Sources were read as text, not executed. The preview is moving,
not a stable commit pin. Web indexing could not retrieve the fresh announcement;
direct verified HTTPS succeeded. This review performed no upgrade or graphical
operation and does not establish3.0 compatibility.
