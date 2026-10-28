# Optional SD worker stack measurement

A fresh minimal camera/audio/SD link at9c60ae6 found an undefined
z_impl_k_thread_stack_space_get reference. The pinned Zephyr implementation in
kernel/thread.c:1180..1347 is compiled only when CONFIG_INIT_STACKS and
CONFIG_THREAD_STACK_INFO are both enabled. The SD worker called it unconditionally;
profiles enabling diagnostics hid this dependency.

Call it only under the same two-symbol guard. Otherwise report unused_stack0
with stack_error=-ENOTSUP, explicitly unavailable rather than a measurement.
Keep completed worker ownership, stack release, cancellation and file semantics
unchanged. Do not enable optional diagnostics implicitly in minimal profiles.

The actual worker host suite must link/run with the diagnostic implementation
omitted, either prerequisite enabled alone, and both enabled. Retain all25
worker lifecycle cases and allocation/release assertions under ASan/UBSan.
The file-worker suite must still pass. Retry the fresh isolated P4 link with
the same SDK/profile and retain exact command, source hashes, config and output
hashes. No flash, board session, original SDK or private media input is involved.
