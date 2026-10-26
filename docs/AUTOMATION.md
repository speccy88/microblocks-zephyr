# Portable clock, timers and steps — local contract

Separate services and libraries: Clock & Timers (`clock:*`) and Steps &
Transitions (`steps:*`). Existing JSON, media and p4 namespaces retain their
indices. Native Zephyr supplies monotonic uptime. RTC hardware, NTP, IANA
timezone databases and automatic DST changes are not implemented by this stage.
Manual wall time is explicitly identified as manual and initially invalid.

## Clock and timers

Wall time uses POSIX UTC with ISO text `2026-10-26T09:00:00Z`; accepted years
1970–2399, Gregorian dates, no leap second. A configured offset in minutes
(-840..840) defines local time. It is a fixed offset until explicitly changed;
it is not a named timezone. A future RTC/NTP provider can update the same clock.

Eight timers, generation-checked references. Modes: repeating monotonic interval
(10 ms..24 h), one UTC deadline, or daily local hour/minute. Every timer has at
most one pending notification. Further firings coalesce and increment a
saturating missed counter. Reading readiness does not consume it; take consumes
it. Stop clears pending state; restart explicitly rearms. Delete invalidates
the reference. Stop All releases all timers and invalidates their references,
so repeated program starts do not exhaust the slots. Timers do not actuate anything.

Intervals are unaffected by wall time or timezone changes. Wall deadlines and
daily schedules require a valid clock. Invalidating wall time suspends them and
clears pending notifications. Forward jumps use an explicit skip/once policy:
skip records the missed occurrence, once retains one notification. Repeated
polls, backward jumps and fall-back offset changes cannot emit the same daily
local-date occurrence twice. Restart explicitly resets that watermark. A
spring-forward gap follows the same skip/once policy. Changes of offset are
clock jumps, not automatic DST. Monotonic regressions are rejected without
mutating state. Exact seconds are text to avoid SmallVM integer overflow.

## Steps and transitions (GRAFCET inspired)

One graph per library instance: 16 numbered steps, 24 numbered transitions.
Each transition has source/target step groups, an input condition and optional
minimum active time. Configuration is frozen while running. Start activates
initial steps; at least one is required. Stop/reset make every step inactive
and clear conditions/events; clear also removes configuration.

Scan is explicit. It snapshots active steps and conditions, selects enabled
transitions in ascending transition ID, and rejects later conflicts sharing a
source step. Independent transitions fire together. All selected sources are
deactivated, then all targets activated (activation wins). New targets cannot
enable another transition in that scan. Entering a target resets its elapsed
time, including a self-loop. Conditions are cleared after each scan, requiring
fresh input values before the next scan. Entry/exit/fired reporters describe
the latest scan and are cleared by the next scan/stop/reset. No automatic scan,
pin write, callback or physical action occurs.

This deterministic subset is not IEC 60848 compliance or a safety controller.
Fork/join groups are logical masks, with simple one-step blocks as the primary
UI. The main example changes a displayed logical state only.

## Acceptance plan

1. Portable C cores with fixed storage, overflow-checked time and explicit errors.
2. Fake-clock tests: invalid clock, normal time, forward/backward jumps,
   changed offsets/DST-like gaps and repeats, coalescing, stale references,
   stop/restart/delete, timer bounds and saturation.
3. Step tests: initial state, no cascade, conflicts, parallel fork/join,
   minimum time, self-loop, invalid groups, frozen configuration and reset.
4. Separate MicroBlocks libraries and examples, local packaging and native
   compile checks. Actual disconnected-editor screenshots.
5. Physical timing/GC/VM responsiveness and RTC/NTP/network tests remain separate
   gates. No firmware installation or public publication in this local stage.

## Local verification and reproduction

The host fake-clock and logical-scan tests pass with AddressSanitizer and
UndefinedBehaviorSanitizer (`python3 tools/test_automation.py`, Linux GCC).
Both native Zephyr P4 profiles compile. The station postlink checker verifies
the entire 32 MiB flash map, including the mapped Whistle model, hosted assets
and settings; no overlap was found. The carried-forward JSON suite passes 62
cases, 10,000 malformed inputs and bounded-workspace exhaustion checks.
Canonical repository validation passes 50 tests; its existing Windows CRLF
provenance caveat is recorded in `p4-existing-validation.json`.

Package the local editor with `tools/package_p4_ide.py` and hosted assets with
`tools/package_p4_hosted.py`, using the pinned source and profile commands in
the P4 [START_HERE](../boards/waveshare_esp32p4_wifi6/START_HERE.md). Select
**Steps + timer: logical state only** in **Projects & board**. It defines two
steps, alternates for six one-second timer events, displays the active state,
then deletes the timer and stops the graph. It contains no physical outputs.
The approved RAM acceptance image contains these primitives. Their physical
timing/GC tests remain a separate gate; see the release validation matrix.

The actual disconnected MicroBlocks 2.5.8 editor loads both separate libraries
and the example at normal 1280 x 720 zoom, without palette clipping or script
overlap. This proves import/rendering, not board execution. Host/build/editor
evidence is in `evidence/2026-10-25/p4-automation-*.json`. Physical timing, VM/GC stress,
RTC/NTP and automatic timezone rules are still unverified or unimplemented.
