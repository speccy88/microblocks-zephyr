# Native Whistle implementation contract

Use the Apache-2.0 independent C99 engine at the pinned revision in
`dependencies/p4-whistle.json`, also used by the earlier RLCD project. The
four-layer model is 14,515,887 bytes, read directly from mapped flash. Model
weights and audio recordings never enter Git. This is native Zephyr, with
scalar C int8 kernels first; no Xtensa assembly or IDF task/heap adapter.

The Whistle profile embeds the verified model in the application's read-only
flash segment. Its explicit simple-boot map reserves 0x2000..0xfdffff for the
application (including model), and leaves 0xfe0000..0x1ffffff reserved for a
later asset/storage layout. It has no OTA slot or companion firmware write.
The build must reject an image that exceeds that application boundary.

Memory: reserve a 12 MiB external-PSRAM arena per job, plus at most 128 KiB
independent input PCM (four seconds at 16 kHz mono), a guarded 64 KiB internal
worker stack and existing
VM/audio state. All engine malloc/calloc and ND allocation paths use that
arena. Account requested live/peak bytes separately from arena reservation.
If contiguous reservation fails, return an error requesting image release;
do not discard user handles. All engine allocations and compute batch hooks
check cancellation and a bounded deadline. Allocation failure unwinds only
the dedicated worker's C stack; there are no held OS locks or DMA resources
inside the engine. Release the complete arena after success, error or cancel.

Operations are asynchronous. VM arguments/GC objects never cross to the
worker. Copy immutable PCM on the VM thread before enqueueing. Results are
bounded UTF-8 text copied into a VM string on request. Stop cancels inference;
it does not abort the thread. English/other supported language indices are
explicit; no command keyword bias. Silence returns empty text rather than
claiming recognition. Listening remains off until an audio capture block.

Acceptance sequence:

1. Cross-build native engine, inspect mapped weight address and image bounds.
2. Native P4 inference on the controlled two-second fixture: compare text
   with host baseline, measure latency/peak requested allocation, run VM
   arithmetic during inference, repeat and cancel/reuse without leaks.
3. Microphone PCM handle to text, using the approved Windows speaker phrase;
   retain numeric/text evidence only, keep recording private and release it.
4. Re-run native camera/audio ownership regressions, publish working blocks
   with actual unsupported states and exact source/model reproduction steps.

Native fixture inference returned `The Camera is ready.`, matching the host
baseline, in about 21.75 seconds using scalar int8 C kernels. The first stack
allocation was insufficient: RV32 compiler measurements show nested decoder
frames exceeding 40 KiB (dec_block 13008, dec_step 11552, mlp_rows 10352,
decode_pass 3392, decode 2688, plus callees). The 24 KiB stack could corrupt
the adjacent idle audio stack, causing an instruction-access fault when it
next ran. The corrected profile reserves 64 KiB, initializes stack patterns,
enables stack sentinels, and reports lifetime stack high-water margin. Native
audio transition passes with the corrected image. Actual measured stack
use is 43,964 of 65,536 bytes. The current camera frame/transform/export path
completes but its strict scene-content test fails on a nearly black image;
that quality gate is retained and awaits a lit-scene retest. Image-budget
pressure/recovery is tested independently and does not imply a scene pass.
Track final measured results in the evidence files, not from build success.
