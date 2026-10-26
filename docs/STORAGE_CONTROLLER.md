# File controller lifecycle — local integration stage

This extends the tested RAM dispatcher through the actual P4 editor adapter and
VM routing. The earlier local stage described below used host tests with the
generated production adapter, real SerialTransport and native controller with
an explicitly synthetic serial provider. They do not prove a board transfer.
The later authorized USB installation and genuine GP file transfer passed;
see [physical acceptance](STORAGE_PHYSICAL.md) and the [release boundaries](P4_RELEASE_2026_10_26.md).

## Decisions before implementation

- The existing controller owns the serial port/WebSocket. Storage adds no second
  connection. Extension217 responses are consumed before the GP input queue.
- Connecting the board makes file access available, but sends no storage request.
  The user explicitly selects Connect files. A bounded open handshake returns a
  session bound to the current controller; close, link loss, owner transition,
  expiry and monotonic rollback cancel owned staging and invalidate the grant.
- OPEN9/CLOSE10 use the existing MBFS/MBFR v1 envelope with an empty payload.
  OPEN has session0 and a nonzero random client nonce in token; response echoes
  the nonce and supplies the grant. Repeated identical OPEN can return its grant;
  a different nonce cannot replace an active session. CLOSE must match the grant.
  Session/nonce values are guards, not authentication. Existing transport access
  policy still governs the ability to program/read the board.
- No automatic mutation retry, auto-reconnect, erase or format. A lost commit
  acknowledgement remains uncertain. A new file session requires explicit action.
- The native controller and ordinary storage primitives share one RAM store.
  Native frame dispatch/expiry/reset run only on the VM thread. No ISR/network
  callback accesses file state. Hosted transport transitions explicitly close
  the grant; USB IDE disconnect and idle expiry provide bounded cleanup.
- Browser link epochs prevent old callbacks, replies or asynchronous file edits
  from changing a replacement connection. Disconnect clears loaded file bytes,
  draft UI, object URLs and pending state; it does not silently write drafts.
- The local application test must exercise generated adapter routing, actual
  serial queue code, full frames, handshake, replacement links, stale responses,
  cancellation and repeated files. No browser download is retried.

Physical USB timing and explicit reconnect/reset are now covered by the follow-up.
Cable loss, network arbitration and completed browser downloads remain unverified.

## Local verification and reproduction

The integration test executes the generated P4 adapter and production
`SerialTransport` against the native storage-to-VM bridge. Only device selection
and byte streams are synthetic. Replies use the pinned SmallVM sender, extracted
after checking its source hash. This caught and corrected the earlier host
harness's mistaken request-style reply terminator. No hardware is selected.

1. Run `python3 tools/test_storage_controller.py` under Linux GCC. It builds the
   bridge with ASan/UBSan, the verified sender and a synthetic stdio endpoint.
2. Run `python3 tools/test_storage_dispatch.py` for the lower-level sanitized
   dispatcher/codec harness. Set `MB_FILES_HOST` to its `wire-host` executable
   and `MB_FILES_APPLICATION_HOST` to `build-artifacts/storage-controller/application-host`.
   Windows Node additionally accepts `MB_FILES_WSL=Ubuntu-26.04`; set `PYTHON`
   to the existing workspace Python executable for adapter generation.
3. Run `node --test tests/device_files.test.js tests/device_files_wire.test.js
   tests/device_files_application.test.js tests/p4-transport.test.cjs
   tests/portal-core.test.cjs tests/portal-adapter-guard.test.cjs`.
4. Run canonical repository validation and build both P4 profiles. The station
   build checks the complete application/model/assets/settings flash layout.

Current results: 12 sanitized native bridge scenarios and 47 affected Node tests
pass, including output backpressure before mutation, owner replacement, duplicate
opens, stale session/reply rejection, repeated file operations, cancellation,
disconnect, rollback/expiry, and old serial/WebSocket callbacks. The canonical
suite passes 61 tests with unchanged upstream bytes; the Windows checkout's
pre-existing FruitJam CRLF/provenance issue is not rewritten.

The actual GP editor's disconnected controls and explicit synthetic-fixture
edit/save/refresh/reopen flow pass. The screenshot labels the fixture. This UI
check does not replace the synthetic-stream protocol tests or prove a physical
transfer. The previous interrupted browser download remains unverified and was
not retried.

Both native profiles now link the controller hooks. The station profile initially
overflowed internal SRAM by 624 bytes. Moving the CPU-only 1712-byte workspace
and 640-byte response buffer to existing PSRAM placement fixed the build without
shrinking queues or removing features. The linked ELF confirms both in external
RAM. Station static internal SRAM is 391488 / 393216 bytes: only 1728 bytes of
linker margin remain. This is not a measurement of runtime heap/stack headroom.
Physical concurrency/timing/GC acceptance is still required after installation
is authorized. No DMA or ISR uses these buffers.

Follow-up: the [storage memory audit](STORAGE_MEMORY_AUDIT.md) moved CPU-only
controller metadata too, recovering 32 bytes after alignment. Station now uses
391456 internal bytes. The remaining 1760 bytes form the automatic libc malloc
arena, separate from the 32 KiB system heap; this is not validated runtime headroom.
The larger memory risk is unresolved and feature expansion remains paused.

The later [HTTP](HOSTED_MEMORY_AUDIT.md) and [RPC allocator](HOSTED_RPC_MEMORY.md)
audits supersede those intermediate map totals: station internal use is 383792
bytes and its libc arena is 9424 bytes. USB physical storage/resource tests do
not validate that station arena or companion decode pool on hardware.
