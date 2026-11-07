# P2 mode libraries

New P2 projects open **P2 Simple IO** first. The version-0.12 package uses
47 small palettes rather than the previous five broad libraries. Each mode
palette has at most 10 ordinary blocks; generic register access is separated
into **P2 Advanced**. P2 Core contains only shared pin-result controls and menu choices. Board, cogs
and shared values have their own palettes.

## Start with simple I/O

- **Set digital output pin high** selects normal logic output and sets its level.
  Use false for low. This replaces a previous Smart Pin mode on that pin.
- **Set digital input pin bias** selects plain input, pull-up or pull-down.
- **Digital input pin bias is high?** sets that input mode before reading it.
  False means low or a rejected pin/setup. Check **pin usable?** when diagnosing.

These blocks use the existing checked native pad/Smart Pin primitives, including
reserved-pin checks. Changing a mode releases previous peripheral/capture use
on that pin before reconfiguring it. No X/Y/WRPIN values are needed.
Reading with this simple block intentionally changes the pin to input. For a pin
already running another mode, use **IN flag (keep mode)** instead.

## Choose the signal or measurement you need

| Purpose | Libraries |
|---|---|
| Digital I/O | P2 Simple IO |
| Clock and duty outputs | P2 Frequency, P2 NCO Duty |
| PWM | P2 PWM Sawtooth, P2 PWM Triangle, P2 PWM Feedback |
| Servo and finite outputs | P2 Servo, P2 Pulse, P2 Transition |
| Encoder and counting | P2 Quadrature, P2 Gated Count Up, P2 Count Up Down, P2 Count Rises, P2 Count Highs, P2 Difference Counter |
| Input timing | P2 State Timing, P2 High Timing, P2 Event Timing, P2 Period Timing, P2 Window Timing |
| Friendly measurements | P2 Measurements (loads High/Period Timing automatically) |
| Serial communication | P2 UART, P2 Sync Serial; P2 Serial Data loads automatically |
| ADC | P2 ADC, P2 External ADC, P2 ADC Snapshot, P2 ADC Scope |
| Analog outputs | P2 DAC, P2 DAC Noise, P2 DAC Dither; raw specialist modes P2 DAC Random Dither and P2 DAC PWM Dither |
| Input conditioning | P2 Level Input, P2 Logic Input, P2 Input Filter |
| Existing capture APIs | P2 SINC Stream, P2 Scope Capture, P2 Bit Capture, P2 Internal Record; P2 Capture Control loads automatically |
| Pin value repository | P2 Repository |
| Board and workers | P2 Board, P2 Cogs, P2 Shared Values |
| Results and registers | P2 Core, P2 Advanced |

Individual files are in **Libraries > P2**. Importing one installs its dependencies
and shared menu choices automatically. Mode setup blocks already call the checked
native initialization primitives, which set the mode, direction, routing and
required X/Y registers. Use the friendly frequency/duty/timing inputs rather than
raw register blocks. Some specialized modes still need parameters such as a B-pin
offset, ADC circuit or sample period. A setup that returns false was rejected;
changing a register manually is not a workaround for that failure.

Capture, DMA, USB and external-clock features retain their existing limits and
validation status. Reorganizing their blocks does not resume stopped development
or establish physical support. No firmware change is required: these blocks use
the installed extension-8 APIs and remain interactive VM bytecode.

## Existing projects are preserved

The canonical compatibility file is
`boards/propeller2/integration/P2_Hardware.ubl`. All 79 previous function bodies
and block selectors/specifications remain unchanged; three Simple IO wrappers
bring the package to 82 functions. The compatibility file is retained for old
projects and tests, not loaded alongside the new default libraries.

An ordinary saved **P2 Hardware** library is reorganized by moving its existing
function/specification objects. Function IDs, code and custom definitions are
not replaced by new versions. New Simple IO definitions are not silently added
to old projects. Stateful/implementation libraries and mixed layouts are left
alone. Existing projects containing the previous **P2 Core, P2 Signals, P2 Serial,
P2 Analog, P2 Capture** libraries, including saved subsets, remain unchanged.
Export valuable customized libraries before an explicit **Load target blocks**
refresh. No organization step contacts, resets or writes to a board.

## Acceptance and limits

The [acceptance plan](PROPELLER2_MODE_LIBRARIES_PLAN.md),
`tests/test_p2_mode_libraries.py` and `tests/p2-usability-compile.test.cjs` cover
unique retained APIs, small palettes, automatic dependencies, all-function
compilation, monolithic identity/ID preservation and saved five-library/subset
preservation. Headless tests are not graphical or physical acceptance.

The earlier [grouping acceptance record](../evidence/2026-11-04/propeller2/grouped-library.json)
contains hardware results for the old five-library layout only. New Simple IO
wrappers and this palette arrangement have not been physically tested.
