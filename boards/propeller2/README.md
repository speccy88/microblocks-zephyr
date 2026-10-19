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

The P2 portal keeps DTR/RTS deasserted so a Prop Plug does not hold P2 in reset.
Choose **Propeller 2** in the portal, select Connect, then the correct FTDI
port. The firmware reports its exact variant; the P2 Hardware library loads
automatically. Browser project saves and `.ubp` import/export use the shared
portal implementation. Named saves, autosave, restore and reload recovery
have been verified in Edge; file import/export remains untested for P2. Wi-Fi and
board-hosted editor controls are absent for this port.

For the bounded hardware test, install `pyserial==3.5` and
`websocket-client==1.9.0` in a Python environment, then run:

```text
python tools/test_propeller2_usb.py --port COM12 --usb-serial A500507HA --board edge32 --reboot --evidence build-artifacts/propeller2/usb-test.json
```

Those port/serial values are the observed Windows device in this acceptance
run. Supply the exact observed values for another device. The test replaces
the P2 project with non-actuating test code; `--reboot` assumes the matching
VM has already been installed into boot flash.

## Smart Pin blocks

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
version is not relabeled. Other newer-editor features need their own tests.
Networking, secondary UART, NeoPixels, PSRAM object
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
