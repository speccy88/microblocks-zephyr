# Propeller 2: native FlexC VM and browser USB editor

This port runs SmallVM directly on the P2 with FlexC. It does not run Zephyr,
ArduinoCore-Zephyr, Wi-Fi, or a web server. The existing browser portal hosts
the editor and talks to the P2 through Web Serial at 115200 baud.

## Implementation contract

The recovered v405 native port is the starting point. Preserve the recovery
archive separately; only the required MPL-2.0 C/header sources are retained
under `native/`. `recovery-provenance.json` records their original hashes.
Existing Waveshare, Fruit Jam and XRP images and libraries stay independent.

Acceptance requires a native build for all three variants, binary version/ping,
arithmetic and live editing, fragmented upload with matching CRC, reconnect,
and project recovery after reset. Smart Pin acceptance distinguishes argument
validation and configuration from externally measured waveforms. No waveform,
ADC accuracy, external bus, servo or speaker claim follows from a successful
build or register write. Physical results belong in the capability manifest.

## Choose the exact module

| Build | User pins | Default LED | Reserved |
|---|---|---|---|
| `eval` (Eval Rev C) | P0–P57 | P56 active low | P58–P63 |
| `edge` (original P2-EC) | P0–P57 | P56 active high | P58–P63 |
| `edge32` (P2-EC32MB) | P0–P39 | P38 active high | P40–P57 PSRAM, P58–P63 |

The FTDI VID/PID and P2 ROM version do **not** identify the module variant.
Confirm the module marking before installing. PSRAM is reserved and is not
used as VM object memory. The pin argument is always one pin, never a P2
multi-pin alias. Both friendly and raw Smart Pin paths check the same limits.

## Build and install

Use the official portable [FlexProp 7.7.0 release](https://github.com/totalspectrum/flexprop/releases/tag/v7.7.0).
No graphical IDE is needed. From the repository root:

```text
python tools/build_propeller2.py --flexcc /path/to/flexcc --board edge32 --output build-artifacts/propeller2
loadp2 -p COM12 -b 115200 build-artifacts/propeller2/vm_propeller2_edge32.bin
loadp2 -p COM12 -b 115200 -l 460800 -SINGLE -FLASH build-artifacts/propeller2/vm_propeller2_edge32.bin
```

RAM loading still initializes a littlefs volume at flash offsets 2–8 MB on
first boot when there is no valid volume. Installation therefore needs the
owner's authorization to replace that region as well as the boot image.
Project code is stored there independently of the boot firmware. Test scripts
must not contain unattended external-output actions. To boot from flash with
a recoverable serial programming window, remove the SD card and set FLASH ON,
up-arrow OFF, down-arrow OFF. Do not enable both arrow switches.

On the tested FTDI/P2 combination the default fast `-FLASH` path timed out
while writing its boot stub. Use the explicit single-stage command above;
its successful download must still be followed by a real reset/version check.
The original recovered image also stalled during the first littlefs file
creation. This port keeps littlefs but supplies a bounded software SPI block
device on P58-P61, with a three-second flash-busy timeout and strict 2-8 MB
address bounds. The toolchain's original smart-pin flash driver is not used
for the code store. This version uses 4 KiB erase blocks to reduce metadata
compaction latency during live edits. Its initial mount formats incompatible
old 64 KiB-block volumes in the already-authorized 2-8 MB region; export a
valuable old project before upgrading. The VM record format and atomic rename
are retained.

The [current JavaScript editor](https://speccy88.github.io/microblocks-zephyr/js-preview/propeller2/)
keeps DTR/RTS deasserted so a Prop Plug does not hold P2 in reset. Connect the
correct FTDI port, then choose **Load target blocks** for the P2 Hardware library.
The firmware reports its exact variant. Normal connection stops the VM and
synchronizes the browser project, which can replace the board's stored project.
Export valuable work before using that connection workflow.

**Open from board** on an already connected board now reads its project directly,
without clearing it or asking for a reconnect. The shared adapter also refuses
an unverified identity or a port that changed while another transfer was pending.
With no board connected, the existing action arms a read for the next connection.
Firmware and upstream editor engine bytes are unchanged by this fix.

The [2026-11-03 JavaScript acceptance record](../../evidence/2026-11-03/propeller2/js-acceptance.json)
covers real Edge Web Serial, P2 library identity, arithmetic/live editing, a local
`.ubp` save, reconnect, one hardware reset with matching stored CRCs, and the
connected-board readback regression/fix. Browser file import remains blocked by
the automation extension's file-access setting and is not a physical PASS.
The [legacy GP portal](https://speccy88.github.io/microblocks-zephyr/legacy/index.html)
retains its separate named-save/autosave/reload evidence below. Wi-Fi and
board-hosted editor controls are absent for P2.

For the bounded hardware test, install `pyserial==3.5` and
`websocket-client==1.9.0` in a Python environment, then run:

```text
python tools/test_propeller2_usb.py --port COM12 --usb-serial A500507HA --board edge32 --reboot --evidence build-artifacts/propeller2/usb-test.json
```

Those port/serial values are the observed Windows device in this acceptance
run. Supply the exact observed values for another device. The test replaces
the P2 project with non-actuating test code; `--reboot` assumes the matching
VM has already been installed into boot flash.

## Physical cog workers and shared variables

Extension revision 1 adds real physical cog workers. Define a zero-argument
function, then use **P2 try run function on cog** and check its Boolean result.
Cog 0 runs the ordinary VM; cog 1 receives IDE serial data on the tested board.
Those cogs, unknown functions and occupied cogs are rejected. Workers use their
own interpreter state, VM stack and guarded 8192-byte native stack.

Extension revision 3 adds rooted strings, lists and byte arrays, ordinary
function calls with object arguments/results, foreach, and main-cog services for
object and pin operations. Supported object operations include newList, at,
atPut, size, sum, makeList, range, addLast, delete and newByteArray. Allocation
and mutable-object work execute on the main cog; arithmetic and control still
run concurrently on the selected physical workers. The allocator rejects direct
worker calls. Printing, broadcasts, random, dynamic calls, worker management,
unaudited named primitives and I2C/SPI opcodes remain refused with error 27.
See the [execution contract](../../docs/PROPELLER2_MULTICOG.md).

Normal global variables and objects live in shared HUB RAM. Reads, stores and
**change variable by** use a P2 hardware lock. Worker stacks, pending service
results and deferred returns participate in GC marking and forwarding.
**P2 atomic change list item by** performs one indivisible element update on
the main cog. Separate read, calculation and store operations do not form an
atomic increment. An individual list operation is serialized with other main
operations; shrinking a list during a foreach can produce a checked index error.

Pin requests from workers execute on the main cog. **P2 current cog** still
reports the worker's physical cog. The advanced DIR reporter can demonstrate
that its own GPIO registers remain untouched. Autonomous pin state can outlive
an individual worker, as it can outlive an ordinary function: explicitly release
it when needed. Toolbar stop-all/reset releases main-owned pins. Code/name edits
stop workers before relocating code, including workers waiting for a service.

The [scalar acceptance](../../evidence/2026-11-03/propeller2/cogs-acceptance-ram.json)
records distinct cogs, 15000 exact shared-word increments and lifecycle checks.
The [object acceptance](../../evidence/2026-11-03/propeller2/objects-acceptance-flash-boot.json)
adds two workers retaining objects across eight GCs, resizing a shared list to
1002 items, exactly 3000 atomic element increments, Unicode/list/bytearray
foreach, object returns, isolated OOM/byte errors and recovery, routed pin
ownership, timers, pending-request cancellation, ten rapid return/reset cycles
and intact stack canaries. These checks passed after flash boot. This scope
is physically tested on EC32MB; other variants have build evidence only.

The current P2 target library is copied from canonical source into the Pages
package after verifying the pinned engine archive. Its provenance manifest
records the library hash and extension requirement; the upstream editor engine
remains pinned. Existing v405 images need the new extension firmware for these
blocks. The VM protocol version remains v405.

To reproduce the physical worker test with the exact device identified above:

```text
node tools/compile_propeller2_project.cjs /path/to/reviewed/js-preview/propeller2 tests/fixtures/propeller2/cogs-scalars.ubp /path/to/compiled.json
python tools/test_propeller2_cogs.py --port COM12 --usb-serial A500507HA --board edge32 --program /path/to/compiled.json --evidence /path/to/cogs-test.json
node tools/compile_propeller2_project.cjs /path/to/reviewed/js-preview/propeller2 tests/fixtures/propeller2/cogs-objects.ubp /path/to/objects.json
python tools/test_propeller2_objects.py --port COM12 --usb-serial A500507HA --program /path/to/objects.json --evidence /path/to/object-test.json
```

This replaces the board's stored test project. The JavaScript compiler harness
uses the actual pinned compiler with a test DOM; hardware execution is checked
separately by the serial test.

## Smart Pin blocks

Extension revision 2 adds separate pad and operating-mode setup, all 24 named
pad presets, a full 13-bit D[20:8] pad field, and named setup for every non-USB
operating code. Pad presets cover logic/Schmitt/feedback/comparator circuits,
ADC references and gains, four DAC impedances/ranges and level comparators.
Use raw pad bits for drive strength, inversion, synchronous input and embedded
DAC/comparator level combinations. The raw Smart Pin block additionally retains
full A/B routing, inversion and filtering bits.

The library has separate mode blocks, including unit-aware pulse/transition
microseconds, PWM Hz and duty per 1000, UART baud/bytes, 8-bit DAC levels,
integer-clock counting and quadrature, plus advanced mode-specific register
blocks for dither, SMPS, event/period/window timing and ADC capture. Boolean
**try** blocks report rejected arguments. Older command wrappers remain for
project compatibility; prefer the Boolean forms when failure must be handled.
The generic named setup accepts X/Y hex strings for all 32 bits, or positive
VM integers supplied by the higher-level wrappers. B offset selects an adjacent
user pin from -3 to +3; out-of-range/reserved sources are rejected.

Pulse and transition microsecond intervals must fit 16 clock-count bits
(364 microseconds at 180 MHz; the pulse high+low interval shares that limit).
PWM frequencies are quantized to hardware clock/frame counts. UART is a
nonblocking 8N1 interface with a one-word hardware receiver: read promptly;
`-1` means no word is ready. Transmit acceptance means a word was queued,
not that its final stop bit has finished. `quiet Z` uses RQPIN and leaves the
ready flag intact. Ordinary digitalRead takes GPIO ownership and reconfigures
an active Smart Pin; use the dedicated readers to retain its mode.

On EC32MB, [wired-pair acceptance](../../evidence/2026-11-03/propeller2/smart-pins-acceptance-ram.json)
passes GPIO in both directions on all four pairs, exact finite pulse and
transition counting, NCO period/high timing, both PWM ratios, quadrature in
both directions, synchronous serial on two pairs, UART bytes including 128-255,
and monotonic DAC8-to-calibrated-ADC1x transfer. These loops establish transfers
and ratios; they do not establish absolute voltage/clock accuracy, analog
linearity, noise or bandwidth. ADC startup settling was extended after the
first conversion was observed returning its reset value.

Revision 4 adds checked DAC noise/16-bit dither, NCO duty per 1000, feedback
PWM in Hz/duty with separate A/B offsets, named event/timeout/period/window
triggers, checked internal/external ADC sampling and bit snapshots, and scope
filters/thresholds. Existing raw signatures are retained. Selected counter and
serial convenience blocks are now in the normal palette. See the
[extended mode acceptance](../../evidence/2026-11-03/propeller2/modes-acceptance-flash-boot.json)
and [setup bounds](../../docs/PROPELLER2_SMART_PINS.md).

The extended tests distinguish digital feedback gating from an actual SMPS
power converter, synthetic external ADC bits/clocks from an external converter,
and averaged DAC transfer from 16-bit resolution. SINC2/SINC3 accumulator setup
has configuration-only evidence; timely software differencing and continuous
capture are not implemented or validated. Other analog gains, DAC impedances,
comparator thresholds and analog dynamic performance need suitable inputs and
instrumentation.
USB is unsupported and is rejected by these single-pin APIs. No USB test is
attempted on the hardwired pairs. Generic stream-audio DAC stubs also remain
unsupported; use the explicit P2 DAC blocks. See the
[mode contract](../../docs/PROPELLER2_SMART_PINS.md).

All 42 current library functions import and compile with the pinned JavaScript
engine. The earlier revision-2 library rendered in real Windows Edge; the
current revision-4 library has no graphical execution acceptance. The additional
revision-2 browser connection attempt did not complete USB selection and was
closed while cleanup remained pending. This is a graphical rendering check,
not a revision-2 browser execution PASS; see the
[editor check](../../evidence/2026-11-03/propeller2/smart-pins-editor-check.json).
A later connection attempt was stopped by the Computer Use URL-policy guard;
the click/chooser outcome is uncertain and no current extension execution
through Edge was established. See the [current blocker](../../evidence/2026-11-03/propeller2/objects-editor-check.json).
The full serial hardware tests above remain independent of that limitation.

`P2 configure Smart Pin` takes a pin, a named mode, and X/Y register values.
Modes are input, pull-up, pull-down, NCO frequency/duty, PWM sawtooth/triangle,
count rises and count highs. Input modes release output; counting modes have
output disabled; NCO and PWM modes intentionally drive the chosen pin.
X/Y are **hardware register values**, not milliseconds or percent. Use the
separate frequency-in-Hz and standard PWM blocks for those units.

`P2 start Smart Pin raw mode hex` accepts 1–8 hexadecimal digits for WRPIN,
X and Y, optionally prefixed by `0x`. This preserves all 32 bits, including
bit 31, beyond MicroBlocks' signed 31-bit integer range. It starts a nonzero
Smart Pin mode and can drive hardware when P_OE or pad settings enable output.
Normal GPIO mode and paired USB mode are rejected on this advanced path;
use standard GPIO blocks for normal I/O. Nonlocal A/B inputs may reference
only user pins. Use **release** to stop the mode and float its pin.

Read Z as hex for all 32 bits or as a signed 31-bit VM integer for arithmetic.
Ready reads the hardware IN flag without clearing it; reading Z acknowledges
it through RDPIN. Mode hex reports the last configured WRPIN value tracked by
this API, not a hardware configuration readback. Generic GPIO/ADC/PWM/bus
operations take ownership of their pins; configure the Smart Pin again after
using one of those operations. Configuration is restored by startup blocks,
not by an independent register snapshot.

Mode encodings and X/Y behavior follow Parallax's official
[Propeller 2 documentation](https://www.parallax.com/pages/documentation/) and
[PNut's official constant table](https://github.com/parallaxinc/P2_PNut_Public/blob/master/p2com.asm).
For example P_NCO_FREQ is `00110b << 1` = `0x0c`, P_PWM_SAWTOOTH is
`01001b << 1` = `0x12`, P_COUNT_RISES is `01110b << 1` = `0x1c`, and
P_OE is `01b << 6` = `0x40`. These agree with `smartpins.h` from the pinned
FlexProp release. Electrical limits remain those of the module.

## Current limitations

The retained native core is v405. The pinned real GP 2.5.8 editor displays its
normal v405-versus-v417 notice; acknowledging it allows the tested arithmetic
and live-edit workflows. No minimum-version check is bypassed and the VM
version is not relabeled. The JavaScript P2 profile explicitly accepts native
v405; its bounded acceptance is recorded above. Other newer-editor features need their own tests.
Networking, the generic stream-serial API, NeoPixels, PSRAM object
storage and one-click browser firmware installation are unsupported.

## Recorded physical acceptance (2026-10-19)

The matching historical FTDI adapter record identifies EC32MB Rev B; ROM G
and flash JEDEC `00ef7018` were observed on Windows COM12. All three original
images rebuild byte-for-byte; final modified images compile for all variants.
Only EC32MB has current physical execution evidence.

The [bounded acceptance record](../../evidence/2026-10-19/propeller2/usb-acceptance.json)
passes ten `5+7=12` runs, editing to `5+8=13`, 50 ordered outputs, a 1019-byte
fragmented packet with matching code CRC, reconnect, and a real hardware reset
without RAM reload. Stored CRCs and arithmetic survive; saved startup code
restores a variable and an input-only Smart Pin configuration. All P40-P63
reservations, negative pins and multi-pin aliases are rejected. The longest
upload CRC wait in this run was 0.719 seconds.

These results exercise the physical VM and flash through the serial protocol.
The real GP 2.5.8 editor loads the P2 library and renders its command blocks.
The [real browser acceptance record](../../evidence/2026-10-19/propeller2/browser-acceptance.json)
also passes Edge Web Serial on COM12: `5+7=12`, live editing to `5+8=13`,
named project save, autosave, restoration of the original `5+7` project,
full page reload, named-project recovery, and a new USB connection that runs
the recovered project as `12`. The user selected COM12 in the native browser
chooser; normal portal controls and canvas blocks performed the tests.
This acceptance used the local preview; published assets are audited separately.
No external output waveform or attached peripheral behavior was measured.

The initial graphical attempt also showed an editor-response timeout during
autosave. The packaged GP source successfully serializes and reloads the P2
library in a headless native GP test. The shared request wrapper now pauses
its timeout while the tab is hidden and removes its own timed-out GP queue
entry, preventing repeated autosaves from accumulating stale work. Browser
testing then caught and fixed the Window receiver required by native timers.
Named saves and autosave succeeded after that fix. The earlier headless record
is historical evidence for its recorded source hashes; the browser record
identifies the final tested adapter sources.
