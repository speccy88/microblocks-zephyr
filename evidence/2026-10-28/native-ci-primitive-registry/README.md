# Native CI fixture registry repair

The published `77bf00d` workflow passed GitHub validation and started both native
architecture jobs. Both failed at the native MicroDuck harness registration
assertion: the fixture still required nine primitives while production registers
21. Offline validation and XRP scheduler jobs passed. The public log-download API
returned HTTP403; job status and local reproduction are recorded separately.

The unchanged sanitizer harness was reproduced locally and failed at that exact
assertion before its socket fixtures. The repaired fixture retains the set name,
index and exact entry count, and checks every expected primitive name in order
with a non-null callback. Production primitives, source pins, sanitizer settings,
timeout, sockets, cancellation and moving-GC checks remain unchanged. This is an
explicit ABI contract, rather than accepting an arbitrary larger count.

Local harness and full-validator results are retained with this checkpoint.
They do not make the earlier hosted run successful. No newer change is published
under the approval that covered only `77bf00d`; hosted acceptance of the fixture
repair remains pending.
