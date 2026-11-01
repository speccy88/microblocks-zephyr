# Bounded motion simulation contract

## Scope before implementation

Implement API44-shaped twist notifications against an internal simulated
reliable, ordered control service, plus native MicroBlocks job wrappers in a
separate clearly named simulation library. There is no physical movement path,
live WebRTC/GATT transport, motor bus access, robot enable/init, policy change,
credentials or generic command forwarding. Existing production gateway and BLE
allowlists remain unchanged and continue to reject robot.move.

Pinned primary source: Pollen MicroDuck
96b89d8613f06722c1d64ce75ab0d7124fed9d8f. duck-ipc-proto/src/lib.rs defines
robot.move as a notification with vx/vy in m/s, positive forward/left, and vyaw
in rad/s, positive left. mediad/src/route.rs permits it over control; btd refuses
it. The current mediad browser uses reliable ordered control, 10Hz, full stick
0.3m/s and 1.5rad/s, with a zero twist on release. The unreliable teleop channel
and its ordering protocol are deferred in this source; do not invent them.

These stick numbers are client bounds, not verified physical safety limits.
robotd owns arbitration, configured safety/deadman and the 50Hz loop. Do not
reimplement gait, integrate distance, infer applied movement or report robot-ready.
The source-default deadman 500ms is documentation, not a commissioned guarantee.

## Local simulation interface

The local methods microduck.motionSim.status, microduck.motionSim.run and
microduck.motionSim.cancel are project simulation wrappers, NOT Pollen methods.
Only the dedicated explicit motion-simulation backend implements them. The real
gateway rejects them. The internal simulated control service accepts only the
documented robot.move notification, never a transport/provider supplied by a
caller or arbitrary RPC. It records requested intents without modelling physics,
policy enable, applied motion, safety decisions or real network delivery.

The backend reuses the existing simulator's fresh private Linux directory,
same-UID Unix gateway, peer checks and mock health service. A small protected
factory hook preserves the existing read-only simulator by default. The motion
subclass adds only local interception; motion methods never call an Upstream.
It accepts no real robot/control endpoint. Default startup disables even mock
motion; --allow-motion is an explicit opt-in to simulated intent recording.

run requires exactly four integers: vx_mm_s and vy_mm_s in -300..300,
vyaw_mrad_s in -1500..1500, and duration_ms in 100..2000. It also requires Boolean
confirmed:true in that request and the backend opt-in. Missing, extra, duplicate,
Boolean-as-number, floating, nonfinite or out-of-range members are refused before
the first simulated frame. The native C validator enforces the same input bounds
and confirmation before creating a job; there are no new primitive-set indices.

An accepted run is a finite lease, not a promise that a robot moved. Emit the
first source-shaped notification immediately, then at 100ms intervals, and a
single zero at expiry/cancel while the simulated channel remains writable. No
overlapping lease, queue, auto-arm, reconnect or replay. Cancellation with no
active lease is a no-op. It never means emergency stop or camera/robot power-off.
An accepted lease can outlive a stopped VM script, at most its two-second bound;
Stop All cancels job waits and cannot undo an accepted request.

## Resource and failure acceptance

1. Construction/status sends no frame. Explicit opt-in and per-request confirmation
   are separate gates; a health result is not either gate. The new UBL inputs
   default to unconfirmed and the example performs only a status read.
2. Local wrapper requests use existing JSON limits, numeric IDs and jobs. SI
   notification output is bounded compact NDJSON with exact documented keys,
   no id, finite numbers and no application ACK claim. Client-local lease IDs
   and confirmations are not added to the upstream envelope.
   RPC replies are compact summaries bounded to 760 bytes including a maximum
   numeric-ID envelope, with only the last notification. This fits native VM
   reporter messages. The full bounded history remains internal to the model.
3. Bound a process to 128 accepted leases, 4096 frames and the last 64 frame records.
   Bound the active callback to one. A late tick must not catch up with stale
   commands: end the lease when the send gap reaches the 250ms local policy limit.
   This is a conservative simulation-client rule, not a claimed robot limit.
4. Drop, write failure or full frame budget ends the lease, clears its callback
   and never retries the requested nonzero twist. Preserve not_sent versus
   unknown where the internal fault fixture can establish it. Attempt at most
   one final zero when writable; local cleanup is not a physical-stop guarantee.
5. Async private-socket tests exercise real peer checks and the actual wrapper,
   while all control frames remain internal. Deny robot.move on the ordinary
   gateway and prove local simulation dispatch cannot forward it upstream.
6. Execute the actual updated native client/VM against the simulated backend,
   including bounds, confirmation, default-deny, status, lease and cancel.
   Use a newly built/hash-verified sanitizer VM; earlier binaries lack these
   local method names and cannot stand in for this revision.
7. Package the separate Motion Simulation library only into the MicroDuck editor.
   Preserve the six other GP profiles and all connection flags. Document UBL
   graphical compilation/execution as unverified until it is actually exercised;
   bytecode/primitive tests do not fill that gap.

## Remaining real-world gates

All values and frame deliveries are simulated. Native Linux VM/Unix execution is
real, but physical MicroDuck, new-revision Pi/ARM64 execution, trusted live motion
transport, current video visibility, authentication/authorization, controller
arbitration, configured safety/deadman, gait and physical stopping are unverified.
Do not expose real motion because a simulation gate passed. The camera observer
remains receive-only and sends only media.video. No denied operation or blocked
Edge-control action is retried. Shared main and the active P4 checkout stay intact.

## Trying the explicit lab

On an authorized Linux development host, create a new private backend directory:

```sh
python3 linux/microduck/motion_simulator.py --directory /tmp/microduck-motion-NEW --allow-motion
```

The printed metadata and motion-simulation.json say simulation:true and
physical_movement_enabled:false. Omitting --allow-motion leaves even the internal
intent recorder disabled. There is no robot/control endpoint argument. Do not
point these wrappers at a real daemon or widen its permissions: the ordinary
gateway rejects them and no live motion adapter is supplied.

Run a newly built VM containing the local simulation method names, with a fresh
private program directory and the printed private gateway socket:

```sh
smallvm --data-dir /absolute/private/programs --microduck-socket /tmp/microduck-motion-NEW/gateway.sock
```

Use the MicroDuck editor profile. It embeds the existing MicroDuck library and
the separate Motion Simulation library, whose run block defaults to false for
confirmation. The microduck-motion-simulation example reads only status on its
start event. The health example remains unchanged. A status summary reports the
explicit simulation opt-in, last recorded notification, lease, counters and
unknown applied movement; it is not a safety or readiness signal.

The native prefix methods use the existing four job slots and ten-second reply
deadline. The local backend acknowledges a bounded lease immediately; that reply
does not wait for expiry and is not a robot.move application ACK. Use the cancel
simulation block to end a lease explicitly, then inspect status. Closing a script
or its pending job cannot roll back a lease the backend already accepted. The
backend stops its own remaining lease callback on shutdown and removes only
owned sockets, retaining its private metadata files.

## Validation scope

Focused suite: tests/test_linux_microduck_motion.py. It exercises exact envelopes,
integer bounds/confirmation, deterministic clocked leases, failure/no-replay,
real private Linux sockets and CLI lifecycle, plus actual sanitizer-built VM
bytecode through the native job adapter. Its four native cases test successful
status/run/cancel, valid boundary values, invalid inputs before I/O, backend
default-deny and ordinary-gateway rejection. Packaging tests verify that the
library and status-only example are actually embedded in the MicroDuck GP data.

The first native reply probe exposed the VM reporter-message size limit; replies
now carry a compact last-frame summary while full bounded history remains local
for test evidence. No stored native JSON string limit or global reporter limit
was loosened. Source audit: tests/motion-source.json. A fresh sanitizer build and
manifest are required because platform/microduck.c now knows these local names;
the earlier viewer/typed binaries cannot validate this revision.

Graphical UBL compilation/execution and the new revision on Pi/ARM64 have not
been exercised. Earlier real Pi tests remain historical evidence for their exact
binary/source hashes. They are not reused as new motion-block acceptance. Before
any release, regenerate the native ARM64 candidate, paired libraries and final
provenance, run the applicable authorized Pi tests and coordinate with P4 work.
The simulated control recorder is not a live SCTP, WebRTC, robotd or physics test.
