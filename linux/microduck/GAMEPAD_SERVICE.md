# Read-only padd observations through the normal gateway

Spec-first continuation after eff609f. Connect the existing bounded observed
gamepad state model to an explicitly configured padd socket and normal Gateway.
Use Pollen API45/5def2f3e protocol and padd tap implementation. Production API44,
existing simulation blocks, primitive indices and all movement/security settings
remain unchanged. No input-device opening, pairing, bindings, drive or robot RPC.

Send pad.input params{} first without hello. Check path ownership/permissions,
inode and SO_PEERCRED against the configured numeric UID before writing; this is
transport consistency, not daemon/hardware attestation. Read at most16 pad.report
notifications within0.35s/16KiB lines, then close. Attached descriptors can be
cached: their value/pressed fields are not current readings. Keep codes, names,
declared ranges/flat/fuzz and device IDs for discovery, but controls start unobserved.

Events update only their declared control. Held state survives empty frames.
Kernel after_drop, socket drop counts and nonconsecutive sequence numbers
invalidate controls; only later clean events restore each control. Detach and
reattach clear old state; independent IMU reports do not create pad state. This
does not measure radio freshness, calibrate controls, infer a centre or authorize
movement. at_us is kernel CLOCK_REALTIME Unix microseconds; since_us is optional
signed64 and can be negative; sequence, not wall time, orders reports.

Four retained/in-flight snapshots per adapter, five-second TTL, explicit release,
cancellation cleanup and clock-regression invalidation. A quiet pad with an
Attached descriptor can yield a metadata-only snapshot with zero observed frames;
capture-ok means a retained handle, not known/live controls. No Attached and no
frames yields waiting; detach yields detached; rejection/timeout/event cap remain
explicit. Scalar reads never resubscribe or extend lifetime.

Local microduck.gamepad capture/axis/button/control/metadata/release wrappers:
axis raw, declared-span position0..1000, last observed event sequence; button
pressed and event sequence;1-based declared control discovery for code/name and
axis min/max/flat/fuzz. Metadata: seq, kernel at_us, signed since_us, frames,
axis_count, button_count, device_name, bus/vendor/product, observation_state.
Unknown/dropped/unobserved/unsupported/overflow has no extractable value. Raw
i32 values outside the VM's signed31 range are explicit out_of_range. Position
uses int64 arithmetic; it is a fraction of declared span, not calibration.

Append a GC-safe gamepadReading primitive. Envelopes require source padd,
origin local_ipc and false hardware-verification/movement flags, with no simulation
member. local_ipc is transport only; fixture input is explicitly fictional.
Normal tofd decoders must reject padd and old simulation decoders keep their gates.

Add a separate Gamepad editor library/read-only discovery example, strict Python
client/gateway routes, private explicit daemon:padd path/UID config and labelled
protocol-faithful fixture. Test schema/loss/quiet discovery/exact clocks/UTF8/bounds,
normal CLI/client/VM/GC, lifecycle/cancellation, editor profile isolation, full
local validator and real Pi ordinary/sanitizer suites with fictional input.
Physical gamepad/radio, graphical, source identity/permissions and deployment
remain unverified. No denied operation or approval loop is retried.

## Try discovery and readings with fictional input

On Linux with Python3.11+, start a fresh private fixture:

```sh
python3 linux/microduck/gamepad_gateway_fixture.py --directory /tmp/gamepad-gateway-NEW
```

The printed JSON explicitly labels simulation:true and provides the normal
gateway socket. Run the current VM using its usual private program directory
and --microduck-socket set to that path. Import MicroDuck and Gamepad, then open
gamepad.ubp in the MicroDuck editor package. The example discovers declared codes
before reading them; it assumes no A/B button mapping or stick/trigger meaning.

Capture once, check that the handle is known, then inspect axis/button counts
and1-based code/name discovery. Axis raw/position and button pressed records can
still be unobserved. The window observation state waiting means no control frame
was observed, not that descriptors are unavailable. Empty frames preserve held
observations; dropped state stays unknown until a later clean event for that
control. A known false/zero requires an actual event. Use known-reading-value
only for statusok, and release the snapshot when finished.

All records are [status,value,unit,origin]. local_ipc describes the adapter path;
this fixture's input is always fictional. It is not a physical/radio test or a
safe-to-drive indicator. at_us is kernel Unix microseconds, event/frame sequence
is u64 and since_us is optional signed64; exact decimal strings preserve their
precision and negative intervals. Declared span position does not apply flat,
fuzz, centre or calibration. Descriptor names are bounded UTF8,128 bytes.

The finite window ends at its deadline/event bound. With a descriptor it can
retain a metadata-only snapshot; without one it reports waiting/event_limit.
IMU reports are independent and do not create pad controls. Four slots expire
after five seconds without renewal on read. Ctrl-C closes owned sockets/readers;
private metadata remains. Use a new fixture directory for the next run.

## Explicit source after shipping inventory

The normal gateway accepts --gamepad-config pointing to a private same-user
regular JSON file containing exactly version1, daemon:padd, the inventoried
absolute socket path and expected numeric server UID. No shipping values are
guessed here. Source owner/parent permissions/inode/SO_PEERCRED are checked before
sending pad.input; no group, device or service permission is changed.

```sh
python3 linux/microduck/gateway.py --config /absolute/private/gateway.json --gamepad-config /absolute/private/gamepad.json --socket /absolute/private/gateway.sock
```

The existing version1/upstreams config may be empty with this adapter configured.
Head/depth/gamepad can coexist, with four slots per adapter and normal gateway
client limits. Python Client.call admits only the reviewed wrapper methods;
raw pad.input, device paths, pairing/bindings and arbitrary forwarding are refused.
A standalone adapter/service installer and shipping-image acceptance remain open.
See the [pinned audit](tests/gamepad-service-source.json) for source facts/hashes.

## Verified checkpoint

421 full local tests and24 focused tests passed with no skips. Fresh ordinary
and ASan/UBSan builds on RPI5 each passed209 selected tests, including55 native
adapter cases. All gamepad/robot input is fictional. Seven editor profiles were
packaged and checked; graphical import/compilation remains unverified.
See [evidence and remaining gates](../../evidence/2026-10-27/microduck-gamepad-service/README.md).
