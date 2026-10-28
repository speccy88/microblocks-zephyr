# P4 TCP latency investigation

Baseline is guarded f63d1cf7 with editor3b29bdfa. Preserve both compiled files
and the verified installation receipt. Do not replay the earlier timed-out SD
session grant or any uncertain write. Existing SD data and browser drafts stay.

Before production changes, a single WebSocket compared three protocol pings
(worker only) against three native pings (VM). All six succeeded after9.656..
10.500s, with TCP opening15.156s. The latency is common to both paths; it does
not originate in the VM or SD service. Raw measurements are retained locally.

Next diagnostic is opt-in and read-only: P4ST operation8 reads transport timing
counters, and USB-only operation9 reads the C6's existing power-save state via
NET_REQUEST_WIFI_PS_CONFIG. It never sets power save or other RF/network state.
No raw packet payload, address, SSID, credential or persistent identifier is
recorded. Metrics bound socket receive/send durations and VM queue delays;
an uptime sample allows a host/board clock comparison. Normal profiles exclude
these operations. No command/file timeout increase or replay is included.

Acceptance: compile and audit the exact native diagnostic; preserve the prior
pair; verify installation digests before reset; read PS state once, then repeat
the worker-vs-VM ping comparison on a fresh read-only connection. Read counters
after it closes. Only change production behavior after these measurements
identify a supported cause. Any fix must improve strict TCP/ping timing and
allow a fresh file-manager read session within existing deadlines. Never
automatically reconnect or replay file writes after uncertain completion.

Read-only diagnostic results: C6 reports PS enabled, Legacy mode, error0 in22ms.
Host2.031s matched board2038ms. Six worker/VM pings still took9.641..9.750s;
their internal socket receive maximum was11ms, send1ms, VM receive queue2ms
and VM transmit queue7ms. SDIO counters recorded no bus errors, invalid headers
or floating reads. The common delay is outside these processing steps.

Controlled next variant: explicit P4_WIFI_LOW_LATENCY profile, disabled by
default. After successful station setup, read PS state; if enabled, request
volatile PS disable once and read state again. Confirmation is the observed
disabled state, including after a missing setter ACK; never resend the setter
in that boot. Do not expose a remote setter, persist this state, change router/
security/credentials, or flash C6. This keeps the receiver awake and may use
more power. Read-only P4ST11 reports attempt/completion/confirmation metadata.

The A/B test must compare raw strict TCP and worker/VM RTTs, not just tolerate
them in the30s editor window. A fresh SD file-session read must pass its
unchanged3s opening deadline; no old grant or uncertain write is replayed.
If timings do not improve, report that result and keep rollback available.

The controlled variant was installed and fully digest-verified as
`5e692377508b8cc9b0fc2d500941b79948ce6adb97be60c72cedfd71c77993f8`
(15,377,600 bytes at0x2000). Editor3b29bdfa is unchanged (3,570,589 bytes
at0xfe0000); no editor/persistent-settings/SD/C6-firmware write was performed. Native
model bytes and DMA addresses are unchanged. Reset2026-10-27T16:55:06Z.
Compiled2dc380f9 diagnostic and earlier f63d1cf7 pairs are preserved locally.

On that boot the policy observed enabled1/Legacy, requested disable once,
received setter status0 and confirmed enabled0. A separate USB read confirmed
disabled in3ms, and a second read after bulk traffic still showed disabled.
Strict TCP5s/response3s tests then passed: TCP62ms, ready156ms, three worker
pings15..16ms and three VM pings16..32ms. Before disabling PS, the same six
requests took9.641..9.750s; kernel receive/send and VM queue times were small.
These observations support a C6/AP power-save interaction as the cause of the
small-packet delay in this setup; its lower-level radio mechanism was not traced.
The fix changes receiver policy, not application/file timeouts.

Actual GUI opening took89ms. A fresh file-session grant took36ms under the
unchanged3s timer, and the SD view listed zero MBFILES entries successfully.
Only read/session operations were observed; the earlier expired grant and all
file mutations were not replayed. The session was explicitly closed. GUI
manual disconnect/reconnect also passed (second handshake95ms). The earlier
30s opening/heartbeat tolerance remains a fallback; the raw strict tests and
unchanged file deadline demonstrate that the improvement is not that tolerance.

Remaining bounds: retaining receiver wakefulness uses more power; the option
is explicit/default-off. The2,195,829-byte compressed GP data transfer still
took23.485s during read-only SD work, so bulk HTTP throughput was not fixed.
No final-pair SD write, full power removal or long-duration reliability result
is claimed. Router/security/credentials, C6 firmware, existing SD files, browser
drafts and Pi/main remain unchanged.
