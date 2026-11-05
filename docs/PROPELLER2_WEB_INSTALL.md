# Propeller 2 browser installation contract

The web installer will use Web Serial in desktop Chrome or Edge on HTTPS (or
loopback). A user explicitly chooses one P2 USB adapter. No other serial port
is opened. Check for the running P2 SmallVM first; an already running VM does
not need installation. A non-P2 VM response must stop the installer.

If the VM does not respond, installation requires an explicit module selection:
Eval Rev C, original Edge, or Edge with 32 MB RAM. FTDI USB IDs and the ROM
version cannot identify that module. The selected board is reset only after
the user starts installation, then must answer the P2 ROM identification probe
before any image is transferred. Wrong/absent identification aborts the load.

RAM loading transfers and runs an image without programming the boot image.
**The VM itself may initialize or format its littlefs project-storage volume
in flash at offsets 2–8 MB, even after a RAM load.** The installer must explain
this before either operation. Flash installation additionally replaces the
boot program. Existing programs and projects should be backed up first.

Use pinned, hash-checked native firmware and the documented ROM serial
protocol. Persistent installation needs the separate flash-programmer payload;
it is not a RAM transfer with a different label. The previously tested
single-stage flash path is the reference; the fast two-stage path timed out on
this board. Bound reads, writes and cancellation; show transfer errors.

After RAM transfer, verify the actual VM version and selected module identity.
After flash programming, additionally reset and verify boot from flash. Do not
claim flash persistence solely from download completion. Do not automatically
use the normal editor connection for verification: it can synchronize and
replace the stored project. Offer the editor after a read-only identity check.

Tests must distinguish mocked Web Serial/browser behavior, execution of the
same loader logic against the physical P2, and an actual browser-to-board
chooser/transfer. The earlier interactive browser guard is not permission to
retry that chooser. Fred's standing erase/flash authorization covers his
identified test P2; it does not authorize other connected devices.

Protocol references: [loadp2 source](https://github.com/totalspectrum/loadp2/blob/c20afedd4253d09da449fa740f8d4304481fc560/loadp2.c),
[flash programmer source](https://github.com/totalspectrum/loadp2/blob/c20afedd4253d09da449fa740f8d4304481fc560/flash_loader.spin2),
the [Parallax ROM booter](https://github.com/parallaxinc/propeller/blob/master/resources/FPGA%20Examples/ROM_Booter_v33k.spin2),
and the [native board storage and installation notes](../boards/propeller2/README.md).

RAM uses the ROM's `Prop_Txt` Base64 command at 115200 baud with an embedded
checksum and requires the explicit `.` acknowledgement. The reviewed 468 KB
images need about 54 seconds on the wire. Hex at that baud exceeds the ROM's
60-second completion window; both the initial prototype and the official
single-stage loader failed that diagnostic without an acknowledgement. Staying
at the VM baud avoids closing and reopening a RAM-only program to change baud.
Flash uses `Prop_Hex` at 460800 baud with the pinned programmer, followed by
identity and reset/boot verification at 115200. RAM transfers whose predicted
wire time exceeds 55 seconds are refused.

Real Windows testing found that an immediate COM12 probe could miss a running
VM; a one-second settle before the same native query returned its identity.
Web Serial now waits one second after opening and deasserting DTR/RTS before
sending VM requests. Opening a USB serial port can restart a board, so this
also avoids querying during a possible ROM startup window. The electrical
reset waveform was not measured.

The installer is linked from the launcher and P2 editor. Images for all three
modules are rebuilt from pinned compiler sources in CI, compared against the
reviewed hashes, and packaged with the separate flash programmer and license.
No firmware binaries or board project backups are checked into Git.
The same pinned-source compiler preparation was exercised locally on Linux
(Ubuntu 26.04 under WSL): all three output hashes matched the reviewed Windows
images byte for byte. The direct compiler targets need their build directory
created before Make; the preparation script now does that explicitly.

Physical acceptance on 2026-11-04 used COM12, FTDI serial `A500507HA`, and the
known Edge32 target. The production `loader.js` ran through the guarded native
serial bridge: RAM checksum and VM identity passed in 55.684 seconds; flash
installation, VM identity and reset/boot passed in 40.063 seconds. Three resets
were recorded, plus three earlier RAM diagnostic resets. The native firmware
source and image were unchanged. Existing board project bytes were backed up
privately before these tests. See the committed acceptance evidence.

On 2026-11-05, new explicit authorization covered real Windows browser tests.
The published installer at source commit `51f1317` passed the real Edge
156.0.4314.58 serial chooser, COM12 RAM transfer with ROM checksum/running
identity, and flash transfer with reset/boot verification. No browser security
protection was disabled or bypassed. A four-byte RAM-only idle loop created
the no-VM starting state for flash testing; it neither drives pins nor writes
flash, and survived a separate serial reconnection. See
[the browser acceptance record](../evidence/2026-11-05/propeller2/browser-installer.json).

Headless Edge tests still distinguish their synthetic Web Serial provider from
this physical acceptance. They cover failure, cancellation, explicit module
selection/storage acknowledgement and mobile layout. The Eval and original
Edge images are compiled and hash-checked; their physical installation is
untested. No independent analog or peripheral acceptance follows from a
firmware installation test.
