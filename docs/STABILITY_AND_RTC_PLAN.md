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
