# P2 pin configuration and Smart Pin extension contract

WRPIN D[20:8] configures the pad circuit; D[5:1] selects its autonomous
operation. They must remain separate inputs in the generic block. Full-width
hexadecimal inputs retain all register bits. Named modes compose both layers;
configuration success is distinct from measuring the resulting signal.

The extension adds named setup for every non-USB operating mode, named pad
configurations, raw 13-bit pad setup, non-acknowledging Z reads, and unit-aware
pulse, transition, PWM, UART and DAC blocks. The existing calibrated ADC block
remains the initial high-impedance 1x receiver. USB needs ownership of two pins
and a protocol implementation; it remains unsupported and is never tried on
the four hardwired pairs.

Pin operations remain on the main VM cog, including requests from worker cogs. Configure while DIR is low and
explicitly trigger pulse/transition/repository modes after enabling DIR.
Stop-all clears both hardware and tracked mode. Reading Z uses RDPIN to
acknowledge or RQPIN to observe without acknowledgement; ordinary digitalRead
still takes GPIO ownership and must not be used as a Smart Pin reader.

On the owner's wiring, only one pin of each pair may drive at a time. Release
both before reversing. Acceptance starts with GPIO both directions on all
four pairs, then NCO/count/pulse timing, PWM ratios, UART bytes and DAC/ADC
transfer. DAC-to-ADC loopback validates monotonic transfer/ratios, not calibrated
absolute voltage, linearity, noise or bandwidth. Configuration-only tests for
other modes must be recorded separately from these signal tests.

Register semantics follow the [official silicon documentation](https://docs.google.com/document/d/1gn6oaT5Ib7CytvlZHacmrSbVBJsD9t_-kmvjd7nUR6o/edit)
linked by [Parallax](https://downloads.parallax.com/propeller-2-documentation/),
and constants from the pinned FlexProp 7.7.0 `smartpins.h`. Pulse and transition
Y writes during reset are lost, so these modes require a post-enable WYPIN.
UART receive results are MSB justified. UART readiness reports space for a new
word; it does not mean the final stop bit has left the pin.

The dated hardware manifest and evidence determine what is actually validated.

| Mode family | Exposed interface | Current signal evidence |
|---|---|---|
| Normal pad/GPIO | Named circuit and raw D[20:8], explicit drive/high | Both directions on all four pairs |
| Repository | Integer store, generic full-width value | Full-width write/read round trip |
| DAC noise/random dither/PWM dither | Noise sample clocks; 16-bit requested level and dither choice | Noise DC mean and both dither monotonic transfers; resolution/spectrum unmeasured |
| Pulse/transition | Microsecond intervals and count | Exactly 100 rises from 100 pulses / 200 transitions |
| NCO frequency/duty | Hz frequency; duty per 1000 and base clocks | Frequency timing and 0/25/50/75/100% high-clock ratios |
| PWM triangle/sawtooth/SMPS | Hz/duty; feedback PWM with separate A/B offsets | PWM ratios and digital feedback inhibition/resumption; no converter circuit |
| Quadrature/register up/register up-down | Integer clock window and B offset | Quadrature reversal and gate-low/high exact counts |
| Rise/high counting | Clock window and optional B subtraction | Rising counts, high-clock ratios and differential counting |
| State/high/event/period/window timing | Event/period counts, minimum window clocks and named triggers | State/high duration, period/window ticks/highs/counts and missing-event timeout |
| ADC internal/external/scope | Checked sample bits, accumulator/capture setup, scope filters/thresholds | Internal DAC transfer, synthetic external data/clock, latest bit snapshots and scope samples/triggers; SINC accumulators configuration only |
| Synchronous transmit/receive | Word width, full-width hex word and B clock offset | Separate pairs at 1/8/9/16/31/32 bits |
| Asynchronous transmit/receive | Baud, bytes, nonblocking read/try-write | 115200 8N1, full byte range and empty-read result |
| USB host/device | Unsupported; single-pin API rejects it | Not attempted |

Mode setup success and the tracked WRPIN value are not register readback or
waveform proof. Feedback power conversion needs a suitable external circuit;
this wiring cannot establish an SMPS controller's performance. High ADC gains,
DAC impedances and comparator thresholds also need appropriate analog inputs
and instrumentation before being described as calibrated or validated.


## Revision 4 implementation and acceptance plan

Add checked, unit-aware setup for DAC noise and 16-bit random/PWM dither,
NCO duty per 1000, and feedback PWM in Hz/duty with separate A/B offsets.
Retain all existing raw block signatures. Add explicit routed configuration,
event/timeout and period/window trigger fields, ADC sampling/filter/capture
choices with documented valid period powers, and scope filters/thresholds.
The main cog continues to own all pin requests from workers.

Acceptance builds all variants and tests the compiled library helpers on the
EC32MB. Use one driver per hardwired pair. Check DAC dither monotonic transfer
through high-impedance ADC1x, NCO high-clock ratios, digital A/B feedback gating,
gated counting, timing/timeout behavior, synchronous word widths, external ADC
mode using a synthetic bitstream/clock, and internal scope samples/triggers.
Repeat USB, worker objects/scalars and existing Smart Pin regressions after
flash boot. Record configuration-only cases independently. Do not infer SMPS
power-converter behavior, external ADC electrical performance, continuous
SINC2/SINC3 processing, contiguous bit capture, or analog/clock accuracy from
these tests. USB remains unsupported and untested on the wired pairs.


Revision-4 setup bounds and interpretation:

- NCO duty accepts 0..1000 and base periods of 1..65536 clocks. The hardware
  fraction is quantized to 32 bits; 1000 maps to 0xffffffff and can have one low
  base period per 2^32 updates. It is not a fixed-frequency PWM waveform.
- DAC16 accepts requested levels 0..65535 and sample periods 1..65536 clocks.
  PWM dither requires a multiple of 256 clocks. These are averaged adjacent
  8-bit DAC levels; accepting a 16-bit value does not establish 16-bit accuracy.
- Feedback PWM takes Hz and duty/1000 plus A/B offsets -3..3. Configure the
  separate feedback receivers appropriately. A high inhibits the next cycle;
  B high cuts the current cycle. Wiring tests only exercise digital logic.
- Event sensitivity 'high' counts high input clocks; 'rise' and 'edge' count
  transitions. Timeout quantities are clock counts, not event counts. Period
  measurements specify an A-to-B trigger pair. A minimum-clock window finishes
  the period already in progress, so its actual duration can exceed the minimum.
- ADC sample bits 2..14 select a period of 2^(bits-1) clocks. These describe
  hardware sampling format, not measured precision. Sampling is raw; use the
  ordinary calibrated analogRead for its calibrated 10-bit conversion. Setup
  alone does not wait for filter settling or external clocks.
- ADC accumulator/capture setup takes a period power: sample 1..13, SINC2
  accumulator 3..13, SINC3 accumulator 4..9, bitstream 0..5. The typed path writes
  the matching period after X, avoiding an accidental zero Y period override.
  SINC2/SINC3 results are rolling 27-bit accumulators and require timely software
  differencing, rollover handling and startup discard (third/fifth sample).
  Those continuous consumers are not implemented or physically validated here.
- Latest-bit capture exposes one unbuffered snapshot of up to 32 bits. It does
  not promise contiguous history. External mode uses Schmitt/logic data and a
  routed clock, rather than enabling an internal analog circuit on the data pin.
- Scope offers 68/45-tap Tukey and 28-tap Hann filters. Arm/trigger thresholds
  A/B are 0..63: A <= B arms below A and triggers at/above B; A > B arms at/above
  A and triggers below B. Read Z for a raw 8-bit sample and IN for the trigger.
  Multi-pin SCOPE-pipe/streamer recording and frequency response are untested.

The [revision-4 acceptance](../evidence/2026-11-03/propeller2/modes-acceptance-flash-boot.json)
records actual results and limits. Existing raw register blocks retain their
signatures; additional convenient counter/serial blocks appear in the normal
palette. Browser execution remains separate from compilation and serial tests.
