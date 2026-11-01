# Linux ARM64 acceptance contract

This is a native Linux port, independent of Zephyr and of Raspberry Pi GPIO.
The initial executable must use the official v417 bytecode and IDE protocol,
headless scheduling, a local PTY, and a persistent program directory. A future
network bridge must default to loopback. HTTPS Pages must never silently connect
to an insecure LAN WebSocket.

Source: SmallVM `2071df569623ba9cdcd6f8106b61796e047df38b` (v417), using the
existing file hashes in `dependencies/smallvm-v417.json`. The audited mirror is
`speccy88/uno-q-microblocks` at `70690291ac44a5c3a50dce572ee0c29ba99dc57f`.
MPL-2.0 applies to SmallVM and modifications to its files.

Acceptance requires native AArch64 compilation, arithmetic, variables/lists,
upload/start/stop, bounded scheduling, reconnect, program save/restore, reboot,
resource measurements and repeat-install/upgrade tests on the real Pi. A binary
header check, x86_64 execution or mocked test does not establish physical PASS.

The pinned VM is not automatically 64-bit safe: `vm/mem.h` defines `OBJ` as
`int *`, while object headers and payload sizes use four-byte words. On LP64,
`FIELD()` indexes eight-byte pointers. A port must audit allocation, fields, GC,
persisted code and integer conversion together. Merely dropping `-m32` or
suppressing pointer warnings is not an ARM64 port.

Package format: exactly `smallvm`, `manifest.json`, `LICENSE`, and optionally
`NOTICE`. The manifest identifies `linux-aarch64`, release version and canonical
source commit. No archive links, traversal, special files, duplicate members,
unknown members, or unbounded payloads are allowed. The installer checks the
archive's out-of-band SHA-256 before extracting anything. A user-level systemd
service is opt-in, runs from the persistent data directory and does not alter
other services or enable user lingering. Uninstall preserves all programs.

Release gate: no ARM64 release is ready until real Pi acceptance passes. The
installer deliberately requires a pinned version and independently supplied
archive digest. There is no `latest` fallback or invented tested artifact.
