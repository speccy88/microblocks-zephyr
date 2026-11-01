# SmallVM scheduling evidence

These are read-only observations of the preserved source snapshots, not a
measurement of the firmware currently installed on Fred's P4.

P4 source: `combined-evidence/stage/build-artifacts/p4-sources/smallvm/vm` in the
task workspace; pinned SmallVM commit `2071df569623ba9cdcd6f8106b61796e047df38b`.

* `interp.h:25`, `:62`, `:107`: MAX_VARS 128, MAX_CHUNKS 255, MAX_TASKS **10**.
* `interp.c:436`: dispatch has no instruction time slice. `:714-720`: backward
  jumps yield. `:739-747`: a false backward wait-until yields and uses strict
  `trueObj` semantics. `:812-824`: waits above 30 microseconds suspend; shorter
  waits busy-wait. `:825-836`: positive millisecond waits suspend, zero does not.
* `interp.c:1395` and its task-selection loop: runnable/woken tasks are selected
  round-robin; a native C primitive runs synchronously until it returns or uses
  the VM sleep mechanism. There is no OS-thread preemption between primitives.
* `runtime.c:250-279`: startTaskForChunk refuses an already-running chunk. Full
  capacity prints `No free task entries` and returns; there is no pending queue.
* `runtime.c:307-320`: startAll first stops/resets tasks, then starts start hats
  and condition hats. It is not a general broadcast start.
* `interp.c:139-145`, `runtime.c:367-377`: broadcast starts matching broadcast
  hats and zero-argument function hats. The sender does not join their completion;
  an already-running receiver is not started again.
* `interp.c:630-635`: halt marks the task unused; `:793-802`: returning a reporter
  result may suspend for output space. Generated workers use halt on completion.

P4 snapshot SHA-256:

```
interp.h  ff94118f0aba88500a6a3a1aaee63cedfa3e5c855735c99bc2354f9ec7eaf735
interp.c  73fe8829d0b3e7394a5660c8a433ef317e4ffb08376b6bc0b25bd2fe5404c78e
runtime.c d12c4c258b34555dbbf5e7e50770b4af0cec1b7ba282dadc3a6fd57002685f3b
```

The prepared Linux port adds a **256-opcode** budget (`interp.c:429-436`, `:450`)
and vmSlice (`:1420-1490`). It still cannot preempt a blocking native primitive.
Its interp.c hash is
`cfc8c6e4fdda966644edc6f102f81809e81567177d9af49a72d89c80db003653`.
This Linux-only budget must not be attributed to the preserved P4 source.

Two independent scripts are easy to start, but do not implement a Grafcet join:
the SFC coordinator must also publish all activations, track final-step readiness,
gate the common transition and release the continuation exactly once. The new
prototype uses existing VM tasks for actions and an explicit coordinator for that
fork/join state. A step variable means active state; a transition variable is a
persistent Boolean condition. They are not task handles or one-shot events.
