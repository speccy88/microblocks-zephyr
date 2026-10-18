# Stability and RTC acceptance - 2026-10-18

Retain commit `8011c5f6dcbc8074db1d7703a550a1e10e2d4ee7` and its local
hash-verified firmware as the recovery checkpoint. No firmware changes during
the first stability run; no changes to Windows networking or credentials.

## Delivered-image stability run

Run at least 30 minutes against the actual COM4 board over the existing LAN.
The repeatable Python workload uses two initially vacant VM chunk IDs and
unnamed test variables, records the original program privately, and removes
only its own chunks on exit. All original chunk CRCs must remain unchanged.
One authenticated controller owns the VM; graphical load tests stay disconnected
while that workload runs. Graphical reconnect/program checks follow it.

Pass requires at least 40 complete workload/reconnect cycles, exact 12-to-13
bytecode edits, 50 allocated RTC-string reports and 500 ordered outputs per cycle,
four complete 148-asset hash/header
audits, and monotonically increasing board uptime with no reset. Raw allocator
free space must remain above 2 KiB and settled final free space must be within
1 KiB of the initial settled value. Record every sample, peak and residual trend;
allocator values exclude static arrays and the fixed VM object arena.

Separately capture at least 12 fresh loads of the actual GP editor, with all
requests completed, board-only origins, no network failures or JavaScript errors.
Do not count HTTP asset audits as graphical loads. Finish with real graphical
reconnect, execution and saved-program readback, keeping the working editor open.
Any failure is retained as evidence and investigated before a new PASS run.

## Next original board feature: initialized RTC

The existing spec includes RTC blocks, but the current firmware only reports
an unset clock. Add a UTC date/time setter with integer, calendar and range
validation, a board-library block and actual PCF85063A readback/ticking tests.
Reject invalid dates before I2C writes. Verify host-time readback, progression
over an interval, and retention across a COM4 software reset. A physical battery
retention/power-removal test remains outside that result.

Build on the pinned Zephyr/Arduino/SmallVM sources, app-only flash without
erasing program/settings partitions, verify the write hash, and repeat the
core wireless/graphical checks. Do not advance SD, BLE, audio or external pins
in this pass. Physical LCD readability and button presses remain pending.

## Bulk-transfer repair after the first stress runs

The eight-client image stalled three browser icons until idle timeout and the
VM workload stopped after seven cycles. The twelve-client/RTC image completed
21 VM cycles with zero transport errors, original CRCs preserved and no settled
heap loss, but an overlapping full asset audit exposed an incomplete WASM
response. Its retry recovered only after about60 seconds. Both failures remain
in the evidence directory; neither is a complete stability PASS.

Next send mapped-flash assets in at most2048-byte HTTP chunks, retaining headers
only on the first chunk and yielding1ms between chunks so network servicing can
run. Track completed/aborted transfers without scanning or locking all sockets.
Keep the same content hashes, gzip and security headers. Repeat overlapping
bulk audit/browser loads before counting a new full 30-minute window.

## User-shortened acceptance supersedes the long-run target

The user requested stopping repetitive 500-output tests and using 50 for basic
checks. The streamed image completed 689.703 seconds and 22 complete cycles
before cooperative stop; the raw stopped FAIL report is preserved unchanged.
Five full 148-asset audits passed, original chunks were restored, and the clean
window had zero observed resets, WebSocket errors, asset aborts or settled heap
loss. Three fresh editor loads have complete traces; one trace with a collector
gap is excluded even though its browser resources completed. Two earlier
overlapping bulk loads also passed. Raw chunk framing and content hashes pass
for both GP WASM and the large data bundle.

The graphical follow-up read one variable and three chunks from the board,
edited the demonstration to repeat 50, reconnected without a pairing prompt,
and emitted exactly 1..50. Default checks now use 50 outputs and one arithmetic
and RTC sample per cycle; larger stress is opt-in. This closes targeted HTTP
acceptance, with no 30-minute or long-term stability claim. See
`evidence/2026-10-18/targeted-http-acceptance.json`.

Audio output is the next user-requested feature; its driver and audible result
require separate evidence.
