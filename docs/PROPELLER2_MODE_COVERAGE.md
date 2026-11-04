# P2 operating-mode and convenience-block audit

This audit covers every WRPIN D[5:1] value. D[20:8] pad circuits are a separate
layer. A named setup block is not full protocol, waveform or analog-performance
acceptance. All physical evidence is for EC32MB; Eval/Edge builds alone do not
establish physical operation. Existing saved raw/helper signatures are retained.

The 31 non-USB names in the operation menu represent 30 distinct nonzero mode
values: repository and DAC noise share value 1, depending on the DAC/pin setup.
Normal mode 0 has the pad/GPIO blocks. USB value 27 remains unavailable. Thus
the remaining convenience gaps were options within modes, rather than omitted
non-USB operating-mode setup functions.

| D[5:1] | Hardware operation | Convenient setup / data blocks | Physical evidence and limits |
|---:|---|---|---|
| 0 | Normal pad/GPIO | standard digital I/O, pad circuit, level/logic/filtered input, debounce; raw pin/ADC DMA | Four pairs both directions; threshold response; 64 Boolean truth cases; four filter banks; full-clock DMA patterns, continuous divided sampling and recent-history records. Feedback-output/analog performance separate. |
| 1 | Repository / DAC noise | store value in repository; DAC noise sample clocks/circuit | Full-width repository round trip; noise DC mean. Spectrum unmeasured. |
| 2 | DAC random dither | DAC16 with PWM dither false | Monotonic averaged transfer, not 16-bit accuracy. |
| 3 | DAC PWM dither | DAC16 with PWM dither true | Monotonic averaged transfer; period multiple of 256 clocks. |
| 4 | Pulse | high/low microseconds and count | Exact 100 rising edges. |
| 5 | Transition | microseconds and transition count | 200 transitions produce 100 rises. |
| 6 | NCO frequency | frequency in Hz; timed square wave | Period/high-clock ratios; timed normal release, including a worker through GC. No independent clock reference or sound test. |
| 7 | NCO duty | duty per 1000 and base clocks | 0/25/50/75/100% ratios. |
| 8 | PWM triangle | triangle PWM in Hz/duty | Period/duty ratio. |
| 9 | PWM sawtooth | sawtooth PWM in Hz/duty or percent; servo pulse and mapped endpoints | Percent endpoints/ratios; 500..2500 us signals at 20 ms frames and mapped endpoints. No servo motion validation. |
| 10 | PWM SMPS | feedback PWM Hz/duty and separate A/B offsets | Digital and analog-comparator inhibit/cut/resume. No power converter. |
| 11 | Quadrature | quadrature B offset/window | Two pairs, forward/reverse exact counts. |
| 12 | Register up | gated count-up B offset/window | Gate-low/high counts. |
| 13 | Register up/down | count-up/down B offset/window | Direction/gate behavior in checked-mode tests. |
| 14 | Rising-edge counter | count rises; difference counter; filtered rises; millisecond window | Exact rises and A-minus-B; filtered rejection; 100 rises in 100 ms at 1 kHz and valid zero counts. |
| 15 | High-clock counter | count highs; difference counter | Duty and differential high-clock counts. |
| 16 | State duration | time states in clocks | State-duration samples. |
| 17 | High duration | time high pulses in clocks | High-duration samples. |
| 18 | Event duration / timeout | time events; timeout clocks/sensitivity | Event counts and running/stopped clock timeout. |
| 19 | Period duration | measure periods: clock ticks | Multiple periods and A/B trigger choices. |
| 20 | Period high clocks | measure periods: high clocks | High-clock accumulation. |
| 21 | Minimum-window duration | measure window: clock ticks | Completion includes final whole period. |
| 22 | Minimum-window high clocks | measure window: high clocks | High-clock accumulation over actual window. |
| 23 | Minimum-window periods | measure window: periods | Count over actual window. |
| 24 | Internal ADC | ADC sample; SINC2/SINC3 streams; bit capture; scale references | Five gain response curves; modular filters and bounded capture. No ENOB/bandwidth/absolute accuracy. |
| 25 | Externally clocked ADC/data | external sample; external SINC stream; finite/continuous external bit capture | Synthetic digital data/clock only; continuous ring with host/worker consumption and GC; 1 MHz retained overflow. External converter not attached. |
| 26 | ADC scope | scope input; immediate/triggered/continuous scope group | Two selected receiver channels together, ring wrap/GC/timeout. Not independent four-channel analog performance. |
| 27 | USB pair | unavailable, raw single-pin path rejects it | Never attempted with the pair jumpers installed. Requirements below. |
| 28 | Synchronous transmit | existing sync TX; full-width word TX with clock/bit-order/continuous options | Selected widths 1..32, both edges, independent crossed bit-order reversal, reset-primed three-word transmission and buffer guards. |
| 29 | Synchronous receive | existing sync RX; word RX before/at selected edge, normalized hex | Selected widths 1..32, both sample choices/clock edges and normalized bit order; no external SPI-peripheral claim. |
| 30 | Asynchronous transmit | existing byte UART; 1..32-bit words, inversion, send hex, busy | Selected widths 1..32, both polarities, independent idle/bit-period measurements and hardware busy; no absolute baud reference. |
| 31 | Asynchronous receive | existing byte UART; 1..32-bit words, inversion, normalized hex/false | Selected widths 1..32, both polarities, zero/full/MSB values and empty-read behavior with a P2 partner; no external UART device. |

The [revision-4](../evidence/2026-11-03/propeller2/modes-acceptance-flash-boot.json),
[revision-5 capture](../evidence/2026-11-03/propeller2/capture-acceptance-flash-boot.json)
and [converter response](../evidence/2026-11-03/propeller2/converters-acceptance-flash-boot.json)
records contain the actual measurements and their scope. The
[word serial/logic acceptance](../evidence/2026-11-03/propeller2/serial-options-acceptance-flash-boot.json)
records the revision-6 expansion. The
[filter and continuous-capture acceptance](../evidence/2026-11-03/propeller2/filters-capture-acceptance-flash-boot.json)
records revision 7. A configured WRPIN value is not a signal PASS.

WRPIN F (D[23:21]) is separate from the operating mode and pad circuit. The
revision-7 bank configuration, input/debounce, filtered counter and advanced
filtered Smart Pin blocks expose it with shared-bank ownership checks. All
79 target-library functions compile with the pinned JavaScript engine. Revision
8 streamer capture reads normal pin IN through logic/Schmitt or ADC pad setup;
it does not replace the mode-24 Smart Pin ADC/SINC paths. Its page-granular
pretrigger record has an explicit high/low trigger boundary and chronological
readback. See the [acquisition contract](PROPELLER2_SMART_PINS.md) and
[DMA/recent-history acceptance](../evidence/2026-11-03/propeller2/dma-acceptance-flash-boot.json).

Library 0.10 adds the [output/measurement conveniences](PROPELLER2_SMART_PINS.md#library-010-output-and-measurement-conveniences)
on unchanged extension-8 firmware. Its focused acceptance covers only PWM,
servo signals, internally timed measurements, readiness/count windows and worker
services. The owner has stopped further DMA, USB Smart Pin and external-clock
work; completed code and its historical evidence remain preserved.

## Hardware and software still required

- **USB:** remove the hard short between both pins of the chosen even/odd pair.
  Even is DM, odd DP. Route them separately as a USB differential pair to a
  suitable connector with ground, suitable ESD/series termination and safe VBUS
  handling. A host needs current-limited 5 V VBUS power; a device needs suitable
  VBUS sensing/power handling. Never connect VBUS to a P2 GPIO. ASIC USB mode has
  its own pull-up/pull-down behavior; it does not justify adding conflicting
  external pulls. Full speed requires a system clock above 48 MHz; the current
  180 MHz clock satisfies that bound. A packet/endpoint or host stack, PID/CRC,
  enumeration, control transfers, scheduling and tests are still software work.
  A USB Smart Pin setup alone does not implement USB. Use a known host/device
  and preferably a USB analyzer for acceptance; none is assumed attached here.
- **External delta-sigma converter:** a real clock/data converter with documented
  logic levels, clock edge/rate, reset/reference and analog input connections;
  level translation if required. Confirm its data/clock format matches mode 25.
  Synthetic GPIO patterns establish only the digital/filter path. SPI/I2S ADCs
  require their own framing/driver rather than being labeled delta-sigma input.
- **SMPS:** a separately designed low-voltage converter with a suitable gate
  driver, switching device, inductor, diode/synchronous switch, capacitor,
  current sense, voltage feedback, protected/current-limited supply and load.
  GPIO must not directly drive a power stage. Test loop stability, fault response,
  efficiency and transients with an oscilloscope and suitable probes. DAC-fed
  comparator gating does not establish any of those properties.
- **Analog pad performance:** known reference/source, suitable source/load
  impedances and calibrated voltage/time measurement. Higher ADC gains load the
  source and clip; loopback curves do not establish nominal gain, DAC resistance,
  threshold/hysteresis, feedback-output stability or noise/ENOB/bandwidth.
- **Acquisition limits:** one session is shared by bits, SINC, scope and DMA.
  The ordinary ring has 1023 usable entries; DMA reserves in-flight space and
  retains six 128-word pages with no consumer. Internal DMA runs continuously
  until stopped or full. Its recent-history trigger samples a level at page
  boundaries; sample-accurate edge triggering, external-clock DMA and multi-pin
  DMA are not exposed. These remain software work, distinct from unavailable
  external instruments. The <=1 MHz external Smart Pin bit service remains
  independent. A 115200-baud host link cannot carry the 22.5 MB/s full-clock
  single-input stream at 180 MHz; sustained full-clock export requires a faster
  sink and its driver. Current divided-rate continuity and full-clock retained
  records do not establish that export bandwidth.
- **Global input filters:** four banks are configured and physically exercised.
  A changed setting is refused while tracked user pins select that bank; release
  all its consumers first. Filter reports are software shadow settings, not a
  hardware register readback. They do not provide independent time calibration.

Semantics follow the [official silicon reference](https://docs.google.com/document/d/1gn6oaT5Ib7CytvlZHacmrSbVBJsD9t_-kmvjd7nUR6o/edit)
linked by [Parallax](https://downloads.parallax.com/propeller-2-documentation/).
The browser URL-policy denial remains separate: no Windows browser interaction
or alternate route is part of this audit or these serial hardware tests.
