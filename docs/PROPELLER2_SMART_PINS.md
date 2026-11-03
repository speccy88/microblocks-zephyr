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

All operations remain on the main VM cog. Configure while DIR is low and
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
| DAC noise/random dither/PWM dither | Separate mode setup, X period/Y level | Configuration only |
| Pulse/transition | Microsecond intervals and count | Exactly 100 rises from 100 pulses / 200 transitions |
| NCO frequency/duty | Hz frequency and separate duty register setup | Frequency period/high timing; duty mode configuration only |
| PWM triangle/sawtooth/SMPS | Hz and duty/1000; separate feedback setup | Triangle/sawtooth 25% ratio; SMPS configuration only |
| Quadrature/register up/register up-down | Integer clock window and B offset | Quadrature +20 then 0 after reverse; gating configuration only |
| Rise/high counting | Integer clock window | Finite rising-edge count; high counting configuration only |
| State/high/event/period/window timing | Separate mode blocks; clock/trigger registers | Period and high timing; remaining variants configuration only |
| ADC internal/external/scope | Separate mode setup; calibrated ADC1x reader | DAC transfer with internal ADC1x; remaining modes configuration only |
| Synchronous transmit/receive | Word width, word and B clock offset | Four 8-bit words, separate data/clock pairs |
| Asynchronous transmit/receive | Baud, bytes, nonblocking read/try-write | 115200 8N1, full byte range and empty-read result |
| USB host/device | Unsupported; single-pin API rejects it | Not attempted |

Mode setup success and the tracked WRPIN value are not register readback or
waveform proof. Feedback power conversion needs a suitable external circuit;
this wiring cannot establish an SMPS controller's performance. High ADC gains,
DAC impedances and comparator thresholds also need appropriate analog inputs
and instrumentation before being described as calibrated or validated.
