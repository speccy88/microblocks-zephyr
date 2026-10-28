# JavaScript Pi readback lifecycle

The 2026-10-28 real Pi graphical test exposed two lifecycle problems in the
pinned JavaScript editor adaptation. Fast explicit evaluations could begin
overlapping initial downloads. Also, reading a program created a fresh code
manager with new function/script slots: the next evaluation could overwrite a
different retained VM chunk and leave duplicate old scripts behind. A simple
model-name reporter failed after readback although it worked before it.

The local adapter retains the upstream editor and VM pins. Explicit evaluations
are serialized per code manager; a failed request remains visible and does not
poison the next request. Replaced projects, detached scripts and replaced
connections cannot inherit a queued run or stale slot identities.

A completed read records function names and script content with their actual
VM slots. The editor's cloned document may change layout, but its variables,
function bodies and script-content multiset must still match. Its new manager
reserves those slots before assigning source-only library functions free slots.
The plan is consumed once, applies only to the same connected port/read generation,
and performs no board writes. Unknown/skipped or duplicate chunks are not guessed
into a slot. Normal explicit edits still use the existing compiler, CRC upload
and bounded board-turn handling.

Acceptance requires the actual Pi VM and graphical editor to import a project,
read it, rapidly execute its reconstructed reporters, serialize/reopen it,
disconnect/reconnect and read/execute it again without duplicate scripts or
primitive failures. The standalone Raspberry Pi 5 profile needs no robot
service. MicroDuck libraries are tested separately in the explicitly labelled
Linux development profile with a protocol-shaped fictional robotd source.
The MicroDuck Rockchip RK3566 placeholder connection gate stays disabled.

The focused actual-class regression suite additionally checks overlapping
downloads, recovery after a failed download, slot preservation through cloning
and layout changes, and rejection after connection/project changes. The prior
adapter is retained as a negative-control test input in the acceptance evidence.

This is project serialization/reopen through the real editor API. It does not
claim a new browser Save dialog/download acceptance, physical MicroDuck model
calibration, physical movement, service/reboot acceptance or a hosted release.
