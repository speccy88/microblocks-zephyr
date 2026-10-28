# Bounded P4 Wi-Fi recovery after link loss

This opt-in follow-up depends on the tested saved-boot profile. Only a real
disconnect after a successful connection arms recovery. Initial boot failure
does not enable a retry loop. The existing credentials, C6 compatibility gate,
station-only mode, editor assets and SD backend are preserved.

The whole boot has a budget of three recovery attempts. Delays before attempts
are 5,15,45 seconds, measured with Zephyr monotonic uptime; success never
refills that budget. Duplicate disconnects/wakes cannot shorten the delay or
add attempts. Association and DHCP retain their 30-second waits. A failed
recovery must stop DHCP and confirm a board-local disconnect before another
attempt; ambiguous cleanup halts recovery until restart. Local assets/driver/
resource failures halt rather than repeatedly consuming hardware requests.

Disconnect immediately clears the published address and invalidates the old
WebSocket owner. Session cleanup remains on the VM thread. USB remains usable;
SD operations, drafts, uploads and VM commands are never replayed. Existing
server startup is reused after reconnect, with a fresh DHCP address. Stale
DHCP or disconnect events during an attempt cannot falsely mark it ready.

Host acceptance exercises the actual worker with a virtual clock: complete
backoff/exhaustion, duplicate events, successful recovery, flapping, failed or
missing cleanup, stale DHCP/disconnect races, default-off behavior and no NVS
write. ASan/UBSan, the native build, memory/layout guards and root validation
must pass before any installation.

For physical acceptance, a separate diagnostic-only profile may add one
USB-only board-local disconnect per boot. It must not be available through
WebSocket and must return an acknowledgement before the worker acts. It does
not change the router, host networking, security, C6 firmware, credentials or
SD files. The final normal recovery build excludes this test action. If this
cannot be done safely, retain the present installed firmware and explicitly
report that physical link-loss recovery remains unverified.

Keep the installed `cc533266f45f1b76be5606ef6608a74611f7f87a919e7630775c6ccd87849ec3`
application and unchanged assets recoverable. All work stays in the new task
snapshot. Do not repeat the denied Git check in the old folder or modify
shared main, Pi or MicroDuck. Produce a narrow delta against this saved-boot
baseline and an integration checkpoint for the Pi owner.

## Status and control contract

P4ST operation0 retains the existing bounded network-status schema. Operation7
adds a separate read-only response: retry_used, retry_remaining, retry_active,
retry_pending, wait_ms, loss_events and test_enabled. No credential or network
name is returned. Budget remaining is distinct from active recovery: a local
precondition or ambiguous cleanup can halt with unused attempts remaining.

Only the separate loss-test profile recognizes operation6. It reserves one
test use under the state lock, sends the acknowledgement, then wakes the
existing worker to request a local disconnect. WebSocket callers are rejected.
The normal retry profile has no operation6 handler. The compatibility probe is
not repeated during recovery, and saved settings are not loaded again.

The existing HTTP server is reused, with its30-second client inactivity bound;
the loss callback closes the old VM WebSocket owner immediately. Browser drafts
remain in the editor under the existing disconnect protections. Reopening a
browser VM/file connection after recovery still requires an explicit action.
No file write, upload, program command, camera or microphone action is retried.

## Native build and physical checkpoint, 2026-10-27

After desktop reconnection, both build logs ended with Ninja interrupted.
No builder/Ninja remained, and the last compiler entry disappeared before
either directory was resumed. Interrupted logs are retained; no uncertain
hardware operation was repeated.

Diagnostic guarded image:
`82e16d2688abb3ec1b2065c95e394ee2ae198298306da55cc6a88eb733c6d53b`
(15,376,192 bytes). Normal guarded candidate, excluding the test action:
`a4e49b75d390a4c24ca011662b5c80972d6b1c3447f69d5d33cecae1df1cad56`
(15,375,952 bytes). Both native builds and layout/model/DMA/memory guards pass
against Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`, SDK1.0.1.
Libc retains10,464 bytes above its unchanged8,192 guard; system heap remains
32,768 bytes. Editor assets remain the exact3,570,557-byte image
`30ef126cdbc1ff67ccc5b34e59089afea0680490f4d1d4f1541a758383d0cfe1`.
Commands, logs and compiled rollback files remain outside Git under this
task's `retry-evidence/`. No device backup was read.

The diagnostic image was installed once with full old/new digest checks.
Exactly one USB-only local disconnect request was accepted. The host reader
then tried to parse its empty acknowledgement as JSON and stopped. The reader
was corrected; the request was never resent. Same-boot inspection confirmed
one loss event, one attempt consumed, two remaining, no pending/active retry,
and station ready. Read-only SD listing returned zero MBFILES entries, error0,
during an HTTP200 editor-data transfer with matching hash (21.92s).

Initial WebSocket TCP attempts timed out before VM upload. HTTP continued to
respond with COM5 closed and native controller none. Plain TCP plus upgrade
returned native ready. A controlled fresh HTTP-status request followed by
plain TCP/WebSocket passed the native version, ten arithmetic runs returning12
and an edit returning13 on that same recovered boot. Controlled scripts and
component receipts remain outside Git; shared VM/portal implementations are
unchanged. The experimental client is excluded from the integration patch.
Initial TCP intermittence remains unresolved: this is neither
a fixed default-client claim nor sustained connection reliability evidence.

Combined acceptance preserves every component and incomplete receipt. No
additional loss trigger, reboot, SD mutation or credential provisioning was
used to obtain these checks. The90.4s resumed observation includes host
recovery and is an upper bound, not measured reconnection latency. Exact
5/15/45s hardware backoff timing, exhaustion, router outage and full power
removal remain untested. Virtual-clock tests of the actual worker cover those
bounds and cleanup failures:544 checks PASS under ASan/UBSan across four
profiles; actual transport ownership cleanup adds32 PASS. Root checks68 PASS.

The normal application `a4e49b75d390a4c24ca011662b5c80972d6b1c3447f69d5d33cecae1df1cad56` is now installed, fully digest-verified,
and accepted after its installation reset. Its operation7 status reports
test_enabled=false, retry_used=0; the diagnostic phase string is absent from
the guarded binary. Automatic boot, HTTP asset hash, read-only SD listing and
ten WebSocket arithmetic runs/edit13 pass. Acceptance uses the controlled
HTTP-status/plain-TCP client path described above. The earlier TCP failures
remain a limit, not an all-client reliability pass. Original cc533266 rollback
and matching assets remain preserved. See
[curated results](../evidence/2026-10-27/p4-wifi-loss-retry-summary.json).

The final fresh board-hosted GP editor loaded from the unchanged assets, but
its graphical Wi-Fi VM connection was not confirmed in the current in-app
browser. Board Wi-Fi WebSocket was selected and status remained Disconnected.
The actual screenshot is retained outside Git. Native protocol acceptance
does not replace that missing graphical connection check.
