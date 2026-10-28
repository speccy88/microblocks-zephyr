# Read-only robotd health and state through normal Gateway

Spec-first continuation after f56748c. Use Pollen API45/5def2f3e HealthResult,
SubscribeParams/Result, RobotState and robotd dispatch/control-loop implementation.
Preserve the API44 production pin, existing raw health/typed simulation paths,
primitive indices, all mutation guards and source/security settings.

Explicit private version1/daemon:robotd/path/expected numeric uid config selects
the reviewed source. Check canonical socket parent, owner/mode/inode and Linux
SO_PEERCRED before writing. This is transport consistency, never hardware or
process attestation. Send hello(api_version45), require numeric API version and
record it diagnostically without rejecting a different version. Then send either
robot.health{} or robot.subscribe{hz:1..50}. For state require acceptedbool and
one robot.state notification. Close after the finite capture, error or cancellation;
no reconnect, background reader, model lookup, device or robot command.

Capture deadline0.5s, lines16KiB, four total retained/in-flight health/state slots,
five-second TTL and explicit release/regression invalidation. Health and state
are distinct immutable snapshots; no claim that separate captures share a tick.
Local wrapper methods microduck.robot.capture(kind health or state plus Hz),
microduck.robot.read(handle,kind,field,index,component), release(handle). Invalid kind,
selector or handle is explicit; scalar reads do no I/O and never renew lifetime.

State reuses the reviewed29 selectors and fixed units; exact u64 counts/ns stay
strings, absent/null/empty optional telemetry is not_reported, t_ns0 unavailable.
Requested and applied movement remain distinct. Schema-default omitted limit
count is marked ipc_default, never a physical observation. No FK/calibration,
pose transform, inferred velocity/current direction or freshness authorization.

Health supplies27 typed selectors: the existing18 diagnostic fields plus reason,
control_loop.ticks, control_loop.missed, motors.hottest and five CPU throttle
readings. The CPU fields level/max_level use exact count64 decimal text;
khz/max_khz use exact kHz64 decimal text, preserving the full u32 domain without
signed31 truncation. These are clock ceilings, not instantaneous frequency.
The throttled predicate matches upstream: level>0 or max_khz>0 and khz<max_khz.
Absent optional CPU sections/keys stay not_reported even though upstream serde
may default them; the derived predicate requires its three source operands.
No frequency, throttle level or hottest-joint identity is inferred from heat.
The declarations are present in pinned API44 commit96b89d8613f06722c1d64ce75ab0d7124fed9d8f
(`duck-ipc-proto/src/lib.rs`: HealthResult, MotorThermal, CpuThrottle).
Preserve finite measurements, missing
versus zero/false, nested required members and documented degraded/bus/IMU defaults.
Health u32/u64 counters and ms age use exact decimal strings, not truncation.
IMU state uses source FROZEN_RUN25 with missing/frozen/converged/not_converged
precedence. A healthy verdict or convergence is diagnostic, never safe to move.
Defaults have explicit source_defaulttrue and ipc_default origin after native
verification. UTF8 diagnostic text is bounded128 bytes; no arbitrary remote error
text is echoed. Missing reason is not_reported; oversized text has no value.

Append robotReading primitive, strict source robotd/local_ipc envelope checks and
GC-safe [status,value,unit,origin] rendering. It must reject simulation markers,
wrong sources, malformed units/indices/types/default claims and oversized text.
Old decoders retain their source gates. Provide Robot library, read-only example,
normal Gateway CLI/Python wrappers and a clearly labelled protocol-faithful fake
service fixture. Check source/RPC/UID/error/lifecycle/default/precision/VM/GC,
package isolation, full local validator and fresh ordinary/sanitizer real Pi
execution with fake input. Physical robot, graphical and shipping deployment remain
unverified. No security/network/service/reboot changes, physical motion, main or
push, denied retries or invented CLI composite diagnostics.

## Use with explicitly fictional input

On Linux Python3.11+, start a new private directory:

```sh
python3 linux/microduck/robot_gateway_fixture.py --directory /tmp/robot-read-NEW
```

The printed simulation:true metadata provides the normal gateway socket. Run
SmallVM with its usual private program directory and --microduck-socket set to
that socket. Import MicroDuck and Robot in the MicroDuck editor package; open
robot-read.ubp. Capture health or state, test microduckReadingKnown, read from the
handle, then release with microduckRobotStateRelease (works for either kind).
Records are [status,value,unit,origin]; extraction refuses non-ok records.
Health counters/ms64 and state ns/count64 are exact strings. ipc_default marks
schema defaults; local_ipc describes transport, never physical identity/freshness.
No health/state value is motion authority, and separate captures are not one tick.
Ctrl-C closes owned source/gateway sockets. Metadata remains; use a new directory.

After shipping inventory, provide a private same-user regular robot.json with
exact version1, daemon:robotd, inventoried absolute socket path and numeric uid.
Do not guess source identity or change daemon/device permissions.

```sh
python3 linux/microduck/gateway.py --config /absolute/private/gateway.json --robot-read-config /absolute/private/robot.json --socket /absolute/private/gateway.sock
```

The version1/upstreams config may be empty with this adapter configured. Existing
head/depth/gamepad readers can coexist. This option adds only the three reviewed
wrapper methods, never raw subscribe/arbitrary forwarding or a control allowlist.
robot.health is not the composite robotctl health report: CLI version/health also
reads software, camera, remote/account and board diagnostics. No shell parser,
robotctl dependency or physical readiness conclusion is supplied. Review
[upstream hashes](tests/robot-service-source.json) before shipping commissioning.
A standalone installer and trusted editor/Pages transport remain separate gates.

The21 selected health fields are partial HealthResult coverage. CPU throttle,
hottest-joint identity and missing-servo IDs are not wrapped yet. The29 state
selectors also do not imply every new protocol field is available. No model or
calibration is fetched; inspect advertised ordering separately before interpreting
joint/link indices on shipping hardware.

## Verified checkpoint

446 full local tests and24 focused tests passed with zero skips. Fresh ordinary
and ASan/UBSan RPI5 builds each passed233 selected tests,61 native cases each.
All service input is fictional; seven editor profiles were verified. Graphical
compilation/execution remains unverified.
See [evidence and remaining gates](../../evidence/2026-10-27/microduck-robot-service/README.md).
