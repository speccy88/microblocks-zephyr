# Native headless platform contract

This platform links the actual pinned SmallVM interpreter and runtime. It does
not implement an alternate interpreter, SDL, WiringPi, Zephyr, GPIO, or a network
listener. The PTY is a local binary transport for the official IDE protocol.

Acceptance: monotonic timing; a private, current-user-owned data directory;
exclusive process ownership; a unique PTY JSON discovery file; real bytecode
upload/arithmetic/variables/stop; code CRC; process restart persistence;
corrupt-file refusal without erasure; and no busy spin while idle. Cross-host
tests must report their actual architecture and never imply physical Pi tests.

`smallvm --data-dir /absolute/private/directory [--pty-info /same/directory/info.json]`
starts the headless runtime. The directory must exist or its parent must exist;
it is created with mode 0700 and must be owned by the current user. A lock stops
two processes from modifying the same program. The PTY JSON file is exclusive
and mode 0600, and is removed on graceful exit. It contains the PTY slave path,
PID, transport and VM version. No global fixed `/tmp` pathname is used.

`--self-test` creates its own unique private temporary directory, sends official
upload/run/get-variable messages through the actual PTY and checks arithmetic
executed by the linked interpreter. It never loads or alters the user's normal
program. A successful startup without those results is not a self-test PASS.

`linux.c` implements native timing, PTY transport and persistent code-file hooks.
The core must use `USE_CODE_FILE` and call `initCodeFile(flash, capacity)` when
restoring its arena-backed code store. The returned count includes the S header.
The full record stream is validated before the core sees it. Complete updates
use a private temporary file, fsync, atomic rename and directory fsync. The two
record-header words are staged until the payload arrives; compaction's
`clearCodeFile` stages the new S header until its following payload write.
Unexpected corruption causes a nonzero exit and leaves the existing file intact.

`main.c` uses `vmSlice(1)` supplied by the bounded interpreter patch. It calls
`processMessage()` every iteration and polls the PTY for at most 10 ms while no
task runs; waiting tasks are checked at least every millisecond. There is no
unauthenticated LAN listener. Unsupported hardware primitives raise the official
`primitiveNotImplemented` VM error. Hardware pin counts report zero.

The Python integration runner is `tests/linux_arm64_protocol.py --binary PATH`.
It launches only the supplied local executable in disposable directories. It
never uses SSH or accesses a serial board. Program persistence is process
restart persistence; a physical Pi reboot and graphical IDE remain separate
acceptance gates.

The runner records CPU ticks and resident memory from its own child process over
a bounded 0.5-second idle interval before uploads. This is a point-in-time idle
sample, not a memory-leak or sustained-load test. It records the actual host
architecture and identifies sanitizer overhead as a comparison limitation;
instrumentation must be taken from the binary's external build manifest.
