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

The installer is linked from the launcher and P2 editor. Images for all three
modules are rebuilt from pinned compiler sources in CI, compared against the
reviewed hashes, and packaged with the separate flash programmer and license.
No firmware binaries or board project backups are checked into Git.

Physical acceptance on 2026-11-04 used COM12, FTDI serial `A500507HA`, and the
known Edge32 target. The production `loader.js` ran through the guarded native
serial bridge: RAM checksum and VM identity passed in 55.684 seconds; flash
installation, VM identity and reset/boot passed in 40.063 seconds. Three resets
were recorded, plus three earlier RAM diagnostic resets. The native firmware
source and image were unchanged. Existing board project bytes were backed up
privately before these tests. See the committed acceptance evidence.

The real installer UI is tested in headless Edge with synthetic Web Serial,
including failure, cancellation, explicit module/storage acknowledgement and
mobile layout. **An actual browser USB chooser/transfer remains unverified**:
the earlier interactive browser denial has not been retried or bypassed.
The Eval and original Edge images are compiled and hash-checked; their physical
installation is untested. These limits do not become physical PASS from a
mocked browser test.
