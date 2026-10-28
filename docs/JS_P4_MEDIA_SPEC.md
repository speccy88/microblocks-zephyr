# JavaScript per-block P4 media

Continue the isolated `a2d2275` checkpoint. Keep native firmware, GP, the live
site, protected P4 hardware/checkout and paused SFC unchanged. Use the existing
identified service broker and preserved RPC208/209 contract, not a new port.

Negotiate protocol1, bounded native slots/budget,160x90 images,128000 audio
frames and512-byte reads before instrumenting code. A session change cancels
pending work and clears pixels, PCM, playback and URLs. Track bounded known
sites only, reject stale session/token/request replies and short/invalid data,
and release native tokens after copied results. No camera/recording RPC is
introduced: snapshots observe the results of blocks the user executes.

Each explicit run negotiates a fresh session before recompilation. A cleared or
stopped view rejects late notifications, even before the next run. Unsupported
media firmware leaves ordinary execution available without instrumentation.

For visible producing expressions, append `mediaSnapshot(handle,site,session)`
without changing their handle or evaluation order. Hidden library bodies and
disconnected compilation remain unchanged. Use monotonic page-local site IDs;
never copy IDs or media into another block, project text, autosave or readback.
Readback must unwrap validated generated snapshot calls and prefer the target's
native namespace over its generic set alias. Unsupported wrappers fail visibly.

Actual Morphic block children provide collapsed/expanded image and audio views,
aspect ratio, a clear expired state and explicit Play/Pause. Controls cannot run
the parent block. First results expand; explicit collapse persists across reruns.
Scrolling/clipping/dragging use the actual block hierarchy. Copies, deletion,
undo, project replacement, zoom, reruns and disconnect require lifecycle tests.
Cache limits remain eight results, two audio clips and1 MiB of accounted media;
zero/release buffers and revoke URLs on eviction. Never autoplay or save media.
Accessible DOM controls operate the same block views. They do not introduce a
second result cache. Native images fit within160x90 at the current block scale.

Test actual pinned compiler/decompiler/morphs and protocol-faithful fixtures,
including nested producers, named helpers, stale replies, source/serialization
invariance, copy/undo and bounded disposal. Add graphical acceptance using
explicitly labelled stored fixtures, with no physical camera/microphone claim.
Run the unchanged full validator and retain failed as well as final evidence.
