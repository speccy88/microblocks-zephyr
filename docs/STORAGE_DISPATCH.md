# RAM file revisions and bounded dispatcher

This local increment extends the existing portable RAM store. It does not enable
a board connection, filesystem, network service, Flash or SD. Existing Storage
block names and primitive IDs remain compatible. Installation/publication holds
remain in force; all integration tests use synthetic host data.

## Decisions before implementation

- Every committed file receives a nonzero monotonic 30-bit revision. Delete and
  slot reuse never reuse a revision during a store lifetime. Reboot invalidates
  both volatile files and connection sessions. Revision exhaustion refuses new
  writes; it never wraps. Cancelled writes do not alter file revisions.
- Conditional begin uses revision zero for create-only, or the exact current
  revision for replace. Legacy explicit replace captures the current revision
  internally. Commit checks that captured revision again. Versioned reads check
  the revision on each chunk; stale data is never silently combined.
- Store and dispatcher share a single execution owner, intended to be the existing
  VM thread. No locks or host allocation are hidden in the portable core.
  A future network thread must enqueue bounded requests, not call it concurrently.
- A trusted connection owner attaches one session. Session tokens and request
  IDs never wrap. Each valid request consumes a strictly increasing ID; repeats
  are rejected, not replayed. Tokens are lifecycle guards, not authentication.
  The outer USB/WebSocket controller must enforce ownership and authenticate
  access according to its existing policy.
- One staged write is owned by the session. Disconnect, 30 seconds without a
  valid request, or monotonic-clock rollback cancel only that session's staging.
  They preserve completed files and do not cancel an unrelated VM write.
- Bounded operations: capabilities, list, stat, revision-bound read, conditional
  begin, sequential append, finish/commit and cancel. RPC chunks are 512 bytes
  within the store's 1024-byte maximum. Up to eight metadata records are copied.
  Replies never retain pointers to request, GC or store memory.
- A local codec uses reserved extension type217 in the existing MicroBlocks
  frame envelope. It is tested with injected send/receive callbacks and the
  same C dispatcher. The subsequent [controller stage](STORAGE_CONTROLLER.md)
  adds the actual editor and VM hooks locally; installation remains held.
  No second serial port or WebSocket is opened.

## Acceptance

ASan/UBSan: revision reuse, stale reads/replaces, zero/maximum bounds, commit and
cancel, owner isolation, replay, timeout/clock rollback, Stop All interference,
malformed packets, out-of-order chunks and canaries. Test actual JS file client
against a compiled C host harness through injected frame callbacks, including
binary/Unicode roundtrips and lifecycle failures. These are host integration
tests, never RF, USB or physical storage evidence. Rebuild both native profiles
and run canonical regressions, without flashing. The browser download test
interruption is not retried by this increment.

## Integration boundary

`common/storage/{storage,dispatcher,wire}.c` contains no filesystem, socket,
allocator or OS calls. The dispatcher is initialized once per volatile store
lifetime. Reconnect uses `mb_files_close` and `mb_files_open`, not reinitialization.
The controller must invalidate pending frames and grants after reboot,
close, or ownership changes; a numeric session alone is not authorization.

The codec reserves extension 217. Editor requests use
`251, 217, 0, body_length_plus_one_LE16, body, 254`. Actual SmallVM replies use
`251, 217, 0, body_length_LE16, body`, with **no terminator**. Request bodies start
`MBFS`, version 1, operation, request ID, session, token, argument, count,
path length and a zero reserved byte. Integers are little endian. Response
bodies start `MBFR`, version, operation, request ID, session, status and a zero
reserved byte. Request bodies are at most 538 bytes; response capacity is 640.
Variable fields must exactly match the declared size. No raw pointer, struct
padding or JSON is serialized. The wire header files and codec define the layout.

`web/device-files-wire.js` implements the existing abstract Client request API
using injected complete-frame send/subscribe callbacks and a trusted session
grant. It does not open a serial port, socket or browser connection. Close
rejects outstanding requests and removes its subscription; native close/expiry
must be called by the connection owner. Wire revisions use canonical `rN` text
at the JS boundary and 30-bit integers on the wire. Received bytes are copied.

The controller stage now packages this module and accepts extension217 in the
P4 runtime. Explicit grant/close, expiry polling and VM-thread dispatch share
the existing transport and RAM store. A successful cross-build is not installed
or physical proof; the current board firmware predates these hooks.

Correction to the earlier dispatcher-only harness: it initially encoded replies
with request-style length/terminator. That roundtrip proved only agreement
between two test peers. The controller tests now extract the verified pinned
SmallVM sender and exercise the generated production adapter, covering the
actual asymmetric framing. Historical evidence is retained, not relabeled as
physical or application compatibility proof.

## Reproduce local checks

1. Under Linux GCC, run `python3 tools/test_storage.py` and
   `python3 tools/test_storage_dispatch.py`. The latter builds a sanitized C
   harness at `build-artifacts/storage-dispatch/wire-host`.
2. Set `MB_FILES_HOST` to that executable, then run
   `node --test tests/device_files.test.js tests/device_files_wire.test.js`.
   Windows Node can use `MB_FILES_WSL=Ubuntu-26.04` with the Linux executable
   path; the harness readiness marker separates WSL startup from RPC timeouts.
   Only synthetic bytes travel over child-process stdio. There is no board fallback.
3. Run the repository `python3 tools/validate.py`. On the existing Windows
   checkout, unchanged FruitJam CRLF/provenance hashes still fail direct
   validation; the workspace canonical-validation helper uses unchanged HEAD
   bytes plus all current edits in a disposable tree without rewriting that port.
4. Rebuild USB and station profiles using the existing P4 build instructions.
   The station postlink check validates the full app/model/assets/settings map.

New firmware installation and real controller/board acceptance are separate,
held work. Flash/SD, archives, browser download completion, device timings and
concurrent hardware behavior are not validated by this local increment.
