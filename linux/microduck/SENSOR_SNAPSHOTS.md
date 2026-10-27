# Coherent simulated depth and gamepad snapshots

Spec-first increment after361ceb9. Keep physical movement disabled and all
providers fixed fictional Unix services. Existing first-frame JSON wrappers
remain available; the ordinary gateway, BLE and camera transports are unchanged.

## Behavior and acceptance

A capture stores one validated8x8 tof.frame, not64 separate requests. A bounded
private store holds at most four snapshots in total (depth and pad, including
in-flight captures), expires them five seconds after completion and uses random
32-hex opaque handles. Handles grant no authentication or persistent access.
They are process-local resources, not source frame identities; seq/timestamps
remain exact decimal strings. Reads never refresh expiry or contact a daemon.
Explicit release removes the snapshot; missing, expired or wrong-kind handles
return unavailable status and no values. Busy capture returns no handle.

Depth row reads select1..8 from that immutable frame and return eight raw
distances/statuses plus the same handle/sequence. A native decoder produces
eight ordinary [status,value,unit,origin] readings, using source Frame.zone
semantics. All rows of a retained handle are coherent. Unknown/failed/no-target
zones are not zero. MicroBlocks can retain these rows after release; they are
historical observations, not live safety or obstacle-avoidance authorization.

Pad capture opens a single pad.input subscription for at most0.35seconds and
16 notifications. It accumulates observed EV_ABS/EV_KEY updates across frames;
a button remains held when a later frame has no event for it. Attachment
metadata provides ranges/codes only: pinned padd Shared.frame_report does not
update its retained Attached report, so its initial values cannot prove current
held state to a late subscriber. Controls not observed in this window remain
unobserved. A detach clears state; drop counters/after_drop or sequence regression
invalidate retained values until a later clean event explicitly restores that
control. Sequence gaps also invalidate the cache conservatively. A new attachment
starts a fresh state. IMU reports do not refresh pad controls. Transport failure,
refusal and no pad/frame produce explicit error/waiting states.

Snapshots report the number of observed frames, last exact sequence/time and
per-control last event sequence. Local age measures retention since capture,
not source/radio freshness. No automatic drive binding or live pad reader runs
after the bounded capture. This is usable held-state within a finite observation
window, not a continuous dead-man service or a controller readiness signal.

Native sensorSample helpers use existing four-field reading records. Raw values
must fit the VM's signed31 range; otherwise out_of_range remains explicit.
An axis position helper computes0..1000 of the device's declared min..max span
with integer arithmetic. It does not infer stick centre, dead zone, direction,
trigger semantics or calibrated velocity. Buttons are Boolean; only status ok
can be extracted by the existing readingValue primitive.

Add captureTof, capturePad, depthRow, padAxis, padButton and release local
sensorSim wrappers, exact selectors and token validation in Python/native C.
Add sensorSample and sensorRow native decoders at the end of primitive set22;
keep existing primitive names/indices. Package the version1.1 separate library
with capture/row/state/numeric blocks and a read-only example. No automatic
replay, infinite stream, real endpoint, credential or production allowlist change.

Test immutable frame coherence, row bounds, capacity/in-flight reservations,
expiry/release, forged/wrong-kind handles, errors, dropped/gapped/reordered input,
held/released buttons, unknown metadata-only controls, exact counters and numeric
boundaries. Exercise actual VM bytecode, moving GC and typed decoding against
simulated services, package all seven profiles, run tools/validate.py and the
selected JavaScript regression. Build and run the applicable sensor/native tests
on the real Pi when reachable; never retry the previously denied numeric suite
or Edge operation. Pi execution uses fake robot data and opens no robot devices.
