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

Pad configuration and GPIO DIR/OUT remain on the main VM cog, including requests
from interpreter workers. A native capture job may own input reads and
acknowledgements as described below. Configure while DIR is low and
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
| Global input filters | Four banks, lengths 2/3/5/8, CT tap; routed input, debounce and filtered counters | Short-pulse rejection, exact accepted counts, shared/raw ownership and main-cog worker services |
| Repository | Integer store, generic full-width value | Full-width write/read round trip |
| DAC noise/random dither/PWM dither | Noise sample clocks; 16-bit requested level and dither choice | Noise DC mean and both dither monotonic transfers; resolution/spectrum unmeasured |
| Pulse/transition | Microsecond intervals and count | Exactly 100 rises from 100 pulses / 200 transitions |
| NCO frequency/duty | Hz frequency; duty per 1000 and base clocks | Frequency timing and 0/25/50/75/100% high-clock ratios |
| PWM triangle/sawtooth/SMPS | Hz/duty; feedback PWM with separate A/B offsets | PWM ratios and digital feedback inhibition/resumption; no converter circuit |
| Quadrature/register up/register up-down | Integer clock window and B offset | Quadrature reversal and gate-low/high exact counts |
| Rise/high counting | Clock window and optional B subtraction | Rising counts, high-clock ratios and differential counting |
| State/high/event/period/window timing | Event/period counts, minimum window clocks and named triggers | State/high duration, period/window ticks/highs/counts and missing-event timeout |
| ADC internal/external/scope | Checked samples, native SINC2/SINC3 streams, finite/internal and finite/continuous external raw bits, selected-channel scope | Internal DAC transfer, synthetic external data/clock, modular differences and settling, rings through GC, contiguous patterns and two selected receiver channels/triggers |
| Synchronous transmit/receive | Full-width words, clock/sample edges, bit order, B offset and continuous priming | Separate pairs at selected widths 1..32, both edges/sample choices and primed multiword transfers |
| Asynchronous transmit/receive | Baud, bytes/1..32-bit words, polarity, nonblocking read/try-write and busy | Full byte range and selected widths 1..32 in both polarities, fractional timing and empty-read behavior |
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
  Revision 5 adds the bounded native consumers described below.
- Latest-bit capture exposes one unbuffered snapshot of up to 32 bits. It does
  not promise contiguous history. External mode uses Schmitt/logic data and a
  routed clock, rather than enabling an internal analog circuit on the data pin.
- Scope offers 68/45-tap Tukey and 28-tap Hann filters. Arm/trigger thresholds
  A/B are 0..63: A <= B arms below A and triggers at/above B; A > B arms at/above
  A and triggers below B. Read Z for a raw 8-bit sample and IN for the trigger.
  Revision 5 adds multi-pin GETSCP recording. Streamer DMA and frequency
  response remain untested.

The [revision-4 acceptance](../evidence/2026-11-03/propeller2/modes-acceptance-flash-boot.json)
records actual results and limits. Existing raw register blocks retain their
signatures; additional convenient counter/serial blocks appear in the normal
palette. Browser execution remains separate from compilation and serial tests.


## Revision 5 streaming contract

Add a native, heap-free capture job on an explicitly selected free worker cog.
Main-cog DIR/OUT and configuration ownership remain unchanged. The native job
alone acknowledges its input while active; ordinary acknowledgement/X/Y access
must refuse, and reconfiguration/release must stop and join the job first.
Stop-all, reset, code edits and explicit cog stop cancel jobs. Native sampling
holds no OBJ pointers and continues during moving GC and other VM workers.

SINC2/SINC3 continuously consume 27-bit accumulators, apply one/two modular
software differences, discard startup samples and optionally decimate delivery.
Use a static single-producer/consumer HUB ring; overflow stops acquisition and
preserves buffered data instead of silently overwriting it. Bound native periods
and buffer reads; state/counters expose completion, cancellation, overflow,
clock timeout and timing failure. SINC values are raw counts with an explicit
full-scale denominator, not calibrated voltages or measured ENOB.

Raw bit capture is a finite contiguous burst, up to the buffer capacity, returned
as little-endian bytes retaining every bit. Internally clocked 32-bit snapshots
need a dedicated FCACHE loop with a whole-burst timing check. Externally clocked
capture is admitted for bit clocks up to 1 MHz, with cancellation/timeout while
waiting. Continuous unbounded raw-bit transport and streamer DMA remain
separate work; a finite contiguous burst must not be called an endless stream.

Acceptance builds all variants, checks both SINC orders with synthetic external
bits and real DAC/ADC transfer, verifies modulo wrap and startup settling,
continuity/decimation/overflow, GC and worker progress, and stop/reassignment.
Exercise finite bits with a repeating 31-bit-period source so skipped 32-bit
words change phase; check internal burst timing and all-ones/MSB preservation.
Repeat USB, worker and existing pin regressions after flash boot. Converter
circuits, absolute accuracy and noise/bandwidth need separate hardware evidence.

### Using the capture blocks

One native capture session leases a free cog 2..7. It refuses a cog already
running a VM function, and VM functions cannot replace its cog while active.
The producer uses no VM objects, never drives DIR/OUT, and continues while the
main cog collects the heap. Main-cog services allocate returned lists/bytes;
an ordinary worker can consume them and use the pure integer scaling reporter.
The session uses a 1024-word ring with **1023 usable entries**. A new session
clears the preceding buffer; stop preserves it. A full ring stops acquisition
with `buffer full` and retains its contents. Decimation reduces delivered data,
not the frequency at which native SINC accumulators must be acknowledged.

| Blocks | Bounds and returned format |
|---|---|
| Stream ADC / external ADC / stream with circuit | SINC2 internal period 256..8192 clocks, SINC3 256..511; external minimum 16 clocks. Keep every N >= 1, samples 0 means continuous. External bit clock contract <= 1 MHz. |
| Read raw filtered samples | List of up to 1..256 requested values; may return fewer. Read `scale` for P^2 or P^3 full scale. One/two differences use modulo 2^27; discard three/five startup events before delivery. |
| Scale sample ground/VIO to maximum | Clamp and scale an integer sample using measured raw reference counts. Uses a 64-bit intermediate to avoid VM multiplication overflow. References require 0 <= ground < VIO and positive maximum; invalid inputs return false. Reference scaling does not establish absolute accuracy. |
| Capture bits | Finite 1..1023 words of 32 bits. Internal sampling is one bit per system clock; external data uses routed B clock, <= 1 MHz. External limit 0 is continuous and can be drained while active; finite bursts are read after completion/stop. |
| Scope group / triggered scope | First configure selected pins with scope input. Group base is a multiple of four; channel mask bits 0..3 select pins base..base+3. Interval 3..10000 us, frames 0 continuous or positive finite; native API accepts 512..1800000 clocks. Trigger pin must be selected; -1 means immediate. |
| Read capture words as bytes | Little-endian byte array, four bytes per word. Bit-capture oldest bit is bit 0. Scope bytes are pin base, base+1, base+2, base+3; unselected bytes are zero. Read active scope rings while acquiring. |
| Capture state / capture field | State: idle, running, complete, canceled, buffer full, clock timeout, timing failure. Inspect available, emitted/raw, cog, local DIR, scale, wraps and timing fields. Counters are positive 30-bit diagnostics and can wrap. |

Scope uses a cog-local SETSCP/GETSCP pipe with CT1 interval scheduling, not the
streamer. Only selected receiver pins are leased; other pins in the group may
remain DAC sources. Trigger wait times out; after triggering the acquisition
runs on its timebase. The native loop detects missed deadlines before arming
CT1, preventing an elapsed compare value from delaying cancellation for a
full counter wrap. Scope output timing describes frame cadence, not independent
conversion bandwidth or filter delay. Internal native bit bursts have an
elapsed-clock continuity check and are bounded below 0.2 ms at 180 MHz.
Revision 7 adds continuous external raw-bit transport. Continuous internal
full-clock capture, programmable pretrigger history and streamer/DMA acquisition
remain unimplemented.

The current v405 USB object preview sends at most 32 list items or 100 bytes.
For complete host test readback, request at most 32 SINC samples or 24 capture
words (96 bytes) per reporter. VM code can consume the larger returned objects;
the wire preview is not a full object-transfer protocol. Drain often enough or
increase decimation/interval: 115200-baud USB cannot carry native ADC bit rates.

The advanced capture primitive accepts an optional tenth pad-circuit argument.
The friendly circuit block exposes internal ADC ground/VIO/floating and
1x/3x/10x/30x/100x choices through the existing pad menu. External capture
accepts only logic/Schmitt. Invalid pad combinations fail before pin changes.
Input-only level blocks expose all four level-comparator pad presets with
8-bit thresholds and DIR disabled. Feedback-output behavior is separate from
comparator input response.

### Physical acceptance and remaining dependencies

The revision-5 capture and converter records distinguish firmware behavior
from analog performance. SINC2/SINC3 DAC transfer, exact synthetic external
zero/full-scale counts, rollover and settling, continuous worker consumption
through five GCs, retained overflow, clock timeout and lifecycle cancellation
are tested. The 1 MHz external capture checks every bit against a 31-bit-period
pattern across 512 words. Internal bursts check elapsed timing through 1023
words; this timing check does not independently measure the ADC bitstream.
Scope records selected receiver bytes together, checks zeroed unused bytes,
hardware trigger, continuous ring wrap through five GCs, exact frame accounting,
overflow and missing-trigger timeout.

All four DAC pad circuits have monotonic loopback response. Five ADC gains
have input-response curves, including loading/clipping; reference and gain
SINC streams are exercised. Four level-comparator circuits switch on either
side of three threshold codes with output disabled. DAC-fed comparator A/B
inputs inhibit/cut/resume feedback PWM. These tests do not establish nominal
gain, DAC source resistance, threshold accuracy, hysteresis, feedback-driver
stability or power-converter regulation. Higher-gain input impedances can load
the DAC source; only the 1x receiver is used for the initial high-impedance
transfer test. USB remains unsupported. External converter protocols, actual
SMPS circuitry, independent voltage/time references and noise/bandwidth/ENOB
measurements require additional hardware. The browser guard remains in force;
compiler and serial acceptance do not establish graphical execution.

## Revision 6 serial and input-logic contract

The mode audit finds no missing non-USB operating-mode setup entry. Remaining
feasible convenience gaps are variable-width serial words, clock polarity and
sampling choice, full-width receive normalization, TX completion and input
Boolean routing. Add checked 1..32-bit asynchronous and synchronous word APIs,
retaining the byte UART and existing raw signatures. Async supports normal or
inverted line polarity and the chip's fractional bit period where applicable.
Sync supports rising/falling clock, receive before/at edge, software MSB-first,
and reset-time priming for continuous transmission. Sending is nonblocking;
hex words retain bit 31. Empty receive returns false, valid data returns eight
hex digits. Async busy reads its hardware C flag without acknowledgement.

Metadata belongs to main-cog I/O ownership, clears on release/reset/reconfigure,
and is invalidated by raw X writes. Workers request these operations on the
main cog. Expose normal, input-only pass/AND/OR/XOR routing with separate A/B
offset and inversion; global filter timing remains unchanged. Acceptance uses
only one driver per wired pair: P4->P5 async, P0->P1 sync and P2->P3 clock,
then P0/P2 sources into P1 routed logic. Verify widths through 32 bits, both
polarities, sync sampling/bit order, primed multiword transmission, async busy,
invalid arguments, metadata invalidation, worker services and stop cleanup.
USB, external converter protocols, power regulation and analog accuracy need
their separately documented hardware; these serial/logic tests prove none of
those functions.

Word-serial details:

- Async bit periods must be 4..65535 system clocks. Periods below 1024 clocks
  use the hardware's 1/64-clock fraction; larger periods use whole clocks.
  Baud is a requested rate quantized against the system clock, not a measured
  absolute rate. Each word has one start and one stop bit, with 1..32 data bits;
  these helpers do not add parity or a framing-error detector.
- Sync TX loads its first word while DIR is low. Continuous mode requires a
  second word buffered before clocks begin; subsequent writes must keep up with
  the external clock. The start/stop option allows word replacement before the
  first clock. Send returns false when the typed buffer cannot accept a word.
  It does not create an unbounded software queue or autonomous word streamer.
- Sync RX's before/at-edge choice follows P2 sampling semantics. The TX changes
  output two internal clocks after its selected edge; this is not a complete
  SPI controller with chip-select or all external-device timing guarantees.
- Read returns the completed word, right-justified and optionally reversed for
  MSB-first. `00000000` is a valid string; false means no completed word or an
  invalid typed setup. Hardware has one receive-result slot, so read before the
  next word replaces it. Poll with a bounded timeout rather than assuming the
  clock generator has completed when its setup command returns.
- Existing raw Z reads retain their MSB-justified behavior. Raw X writes
  invalidate typed width metadata. Raw Y writes update typed TX buffer tracking;
  raw data is not subjected to the typed MSB transformation. Releasing,
  reconfiguring or using stop-all clears metadata with the hardware mode. The old
  byte UART blocks retain their signatures and are not wide-word decoders.
- Async busy means the shifter is still transmitting through the stop bit.
  Ready means a word can be buffered. Busy uses quiet RQPIN and does not
  acknowledge readiness. The busy block is explicitly for asynchronous TX.
- Input logic leaves DIR disabled and does not alter global filter timing.
  A/B offsets must be -3..3 and stay inside user pins; inversion applies before
  pass/AND/OR/XOR. Use pin IN flag (keep mode), not digitalRead, to preserve it.

The [complete mode audit](PROPELLER2_MODE_COVERAGE.md) maps every operating
value to its block and evidence, and lists exact external hardware and remaining
software dependencies. Capture byte-read defaults now request 24 words (96
bytes), fitting the existing 100-byte v405 preview limit.

## Revision 7 global filtering and external continuous capture contract

Expose four global unanimity-filter banks with lengths 2/3/5/8 and CT taps
0..31 (sample interval 2^tap clocks). Use only HUBSET command class 0x4, never
the clock/debug/reset classes. Initialize documented defaults at VM boot.
The main cog owns filter programming; reject a changed setting while any user
pin's tracked WRPIN F field selects that bank, including generic/raw Smart Pin
consumers. Identical configuration is an idempotent success. Stop-all releases
consumers; bank settings persist until explicit reconfiguration or a hardware
reboot. Read reporters identify shadow settings and users, not hardware
register readback. Add input/routed configuration, a filtered edge counter and
a debounce-in-microseconds helper. Startup/filter settling is explicit, not
hidden in unbounded setup waits. Reserved pins and global IDE serial setup
remain outside this API.

Extend external raw-bit capture to a continuous, heap-free producer with the
existing 1023-entry ring. It keeps full 32-bit words, allows reads while active,
checks stop and missing-word timeout, and stops on overflow while preserving
buffered data. Internal raw-bit capture retains its existing finite fast path;
this is not a claim of continuous internal full-clock capture or streamer DMA.
SINC and GETSCP behavior remain unchanged. Preserve signatures; external bits
limit 0 selects continuous operation. Document the <=1 MHz external-clock
contract and the transport/consumer rate required to avoid overflow.

Acceptance: build all variants; test every bank/length with narrow-pulse
rejection and long-pulse counts, shared-bank retiming refusal, raw consumers,
worker requests, stop/release and unchanged clock/IDE ping/fragmented CRC.
For external bits verify a 31-bit-period pattern across ring wrap, complete
frame accounting, GC and worker progress, retained overflow, clock timeout and
pin/cog/stop/edit cancellation. Test <=1 MHz with controlled synthetic GPIO;
no USB, external converter, analog accuracy or unbounded host-throughput claim.

### Filter use and timing

The bank configuration reporter takes bank 0..3, length 2/3/5/8 and CT tap
0..31. Each sample is separated by `2^tap` system clocks; the output changes
only after the selected number of unanimous samples. Allow startup settling
before relying on the result. A transition can take between `(length-1)` and
`length` sample intervals depending on phase. The debounce helper chooses length
8 and the smallest tap whose seven intervals reach the requested 1..1000000 us.
At 180 MHz a requested 1000 us uses tap 15: 229376..262144 clocks, approximately
1.274..1.456 ms. This is clock-derived quantization, not calibrated timing.

VM hardware startup explicitly restores defaults: bank 0 length 2/tap 0,
bank 1 length 3/tap 5, bank 2 length 5/tap 19 and bank 3 length 8/tap 22.
Configure a bank before attaching consumers. A changed setting returns false
while any tracked user pin selects it; repeating the identical setting returns
true. Release every consumer to retime it. Stop-all releases pins but retains
the bank settings. A hardware reboot restores defaults. `length`, `tap`,
`users`, `sample clocks hex` and `configuration hex` report the VM's shadow,
not hardware register readback. The hexadecimal fields preserve bit 31.

The simple filtered input and debounce helpers use an input-only Schmitt pad.
The advanced input block routes/inverts A and B independently, with checked
-3..3 offsets. F selects the same bank for both muxed inputs; it shares its
field with pass/AND/OR/XOR selection, so these cannot be selected simultaneously.
Use **pin IN flag (keep mode)** rather than digitalRead, which releases the
configuration. The advanced filtered Smart Pin block adds a ninth optional
argument to the existing native configure primitive; saved seven/eight-argument
calls retain their behavior. Raw configurations participate in bank ownership.
The main cog programs the banks and owns pin DIR/OUT even for worker requests.

### Continuous external bit records

**Start external bit stream** uses a free physical cog, the routed B clock,
the existing mode-25 data input and a missing-word timeout of 1..10000 ms.
Each acknowledged result is one full 32-bit word; bit 0 is oldest. Read bytes
while running, at most 256 words per VM call or 24 per v405 wire preview.
One static 1024-word ring has 1023 usable entries. There is one capture session
across all bit/SINC/scope APIs. The producer clears a pending result at startup
and records subsequent completed words; it provides no pretrigger history.
Empty reads return an empty byte array.

The producer uses no OBJ/heap access and continues during GC. It stops before
acknowledging another word when the ring is full, preserving the buffered words.
Missing-word timeout is measured since the last complete word, so a paused clock
within an incomplete word eventually times out. Stop, release, explicit cog stop,
stop-all and code edits join/cancel the producer. A consumer that needs exact
accounting must finish counting its acquired batch before being stopped:
forced worker cancellation can discard a result already removed from the ring.

The <=1 MHz clock contract is a producer-service bound, not guaranteed USB
throughput. Host draining at a 20 kbit/s synthetic source and worker draining
through GC are tested across ring wrap. The 1 MHz test deliberately does not
drain: overflow stops after 1023 retained words, all 32736 bits checked against
the independent-period GPIO pattern. The source and receiver share the P2 clock;
these checks establish continuity/ratios rather than independent clock accuracy
or an external converter's protocol. Inspect state, available, emitted and
maximum gap; `continuous bits` distinguishes this path from finite bursts.

Reproduce with the composed pinned editor and exact observed test device:

```text
node tools/compile_propeller2_project.cjs /path/to/site/js-preview/propeller2 tests/fixtures/propeller2/filter-capture.ubp /path/to/filters.json --p2-library
python tools/test_propeller2_filters_capture.py --port COM12 --usb-serial A500507HA --program /path/to/filters.json --evidence /path/to/filters-test.json
```

This test replaces the stored project and drives only the documented paired
test pins. Supply the exact device identity and wiring for another board.
The compiler harness uses the real pinned engine with a test DOM; the serial
test checks hardware execution separately. Neither is graphical browser
acceptance. The [RAM](../evidence/2026-11-03/propeller2/filters-capture-acceptance-ram.json)
and [flash-boot](../evidence/2026-11-03/propeller2/filters-capture-acceptance-flash-boot.json)
records preserve the actual counts, timing and pattern hashes.
