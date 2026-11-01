# Bounded update progress observation

## Scope and source contract

This is a read-only browser watch, not an update operation or a replacement for
the protected update.apply/rollback/select confirmation flow. It uses the same
RpcClient and transport permissions. Real Web Bluetooth remains confidential:false;
PIN authentication and all other secret transmission remain blocked there.

Reviewed upstream is Pollen commit
96b89d8613f06722c1d64ce75ab0d7124fed9d8f:

- updater/src/ipc.rs, Server::stream_progress: replay latest progress, then send
  update.progress notifications until the peer closes. No ordinary reply is sent.
- duck-ipc-proto/src/lib.rs, Phase and Progress: component, phase, optional
  percent and optional detail. Percent is 0 through 100 where meaningful.
- btd/src/session.rs, every_notification_in_a_stream_reaches_the_client: these
  notifications are forwarded over BLE; the PIN gate still applies.

## Acceptance contract before implementation

1. Ordinary request('update.subscribe') refuses with STREAM_REQUIRED before any
   write. Explicit watchUpdates handles the no-reply protocol instead.
2. Starting is explicit, authenticated and exclusive. No automatic connection,
   authentication, retry, replay, update, rollback, download or service change.
3. ATT writes remain sequential, acknowledged and at most 20 bytes. Progress
   arriving before the final ACK is retained within the event bound and is not
   exposed until all ACKs succeed. ACK success means bytes were written, not that
   the daemon accepted or completed an operation.
4. A watch uses the normal write-ACK timeout, then a 60-second observation lease
   by default, at most five minutes, and at most 128 notifications by default
   (configurable 1 through 256). Unrelated notifications count toward the bound.
   Timeout, event limit, abort, drop or explicit stop closes the client. No
   unsubscribe RPC is invented. Reconnection/authentication is explicit.
5. Matching remote errors, malformed frames/typed fields, oversized lines and
   invalid UTF-8 are refused. Unknown phases are not treated as success. There is
   no terminal-success notification in the reviewed enum; idle or 100 percent
   must never be labelled a completed or healthy update.
6. Expose only bounded typed component/phase/percent/origin metadata. Arbitrary
   detail text is omitted rather than retained or exported. Keep at most eight
   visible samples in the console and no durable history. Server simulation
   markers do not prove physical measurement or transport confidentiality.
7. The existing raw console excludes the streaming method. A separate Watch
   progress button consumes any staged confirmation and blocks other requests
   while observing. Stop watching closes the session, without cancelling or
   rolling back an updater operation. Teardown/replacement drops stale callbacks.
8. The in-memory fixture emits source-shaped, explicitly fictional progress only.
   Tests execute actual framing/RpcClient/controller/panel modules with mocks;
   they do not contact BLE, a robot daemon, a network or native Edge control.

## Validation boundary

Automated mock and repository validation must pass before this work is marked
implemented. Actual radio/session/update behavior, graphical browser acceptance,
shipping firmware and production Pages remain separate unverified gates.

## Implemented interface

RpcClient.watchUpdates({onProgress,onEnd,signal,durationMs=60000,maxEvents=128})
returns a promise for a frozen {stop,snapshot} handle after the acknowledged
writes finish. snapshot returns phase, acknowledgement/notification counters,
limits and final local endCode; it never contains request parameters or detail
strings. A watch keeps exclusive client ownership. Ordinary requests, a second
watch and authentication are refused BUSY while it is active.

onProgress receives a frozen {component,phase,percent,detailOmitted,origin}.
Known phases come from the reviewed snake_case enum. A missing optional percent
becomes null; invalid values are refused rather than clamped. origin is either
simulation for an explicit true marker or unmarked, never a physical assertion.
Unrelated well-formed notifications are ignored but consume the event budget.
The exclusive watch observes daemon work that is already running or initiated
elsewhere by an authorized client. It does not run concurrently with another
request on this RpcClient, and never queues an apply/rollback for later replay.

onEnd is called once after an initiated watch ends, including failure during
the starting write. The record contains only code, acknowledged, notifications
and accepted. End codes include WATCH_STOPPED, WATCH_TIME_LIMIT, WATCH_EVENT_LIMIT,
CANCELLED, DISCONNECTED, TIMEOUT, WRITE_FAILED, malformed-frame codes and redacted
REMOTE_numeric errors. Preflight refusals send nothing and do not call onEnd.
Stop is idempotent. Consumer callback errors cannot prevent cleanup. The normal
generic notification callback is not invoked during this dedicated watch.

Starting resolves after ACKs without claiming remote subscription acceptance.
A finite lease can end before the caller awaits its handle; inspect snapshot
and onEnd. An updater stream error after starting is reported through onEnd,
not a fabricated delayed result. A matching ordinary success reply is invalid
for this notification-only method. Partial writes, transport loss and cancellation
never trigger a retry. The existing onNotification path for ordinary RPC calls,
including notifications emitted during update.apply, remains unchanged.

The console has a separate read-only watch panel and eight-sample ephemeral
view. It consumes prior review/confirmation and disables competing requests.
The fixed in-memory fixture replays fictional idle then advances through a
bounded source-shaped progress sequence on explicit clicks. Its metadata and
requests remain bounded, and no update action is dispatched. Session replacement,
page exit and teardown close the watch and discard its samples. None of these
paths invokes native Edge control, radio discovery, a daemon or a network.

Run the new protocol suite with the existing console suites:

~~~sh
node --test tests/test_microduck_updates.cjs tests/test_microduck_protocol.cjs tests/test_microduck_console_core.cjs tests/test_microduck_console_fixture.cjs tests/test_microduck_console_panel.cjs
~~~

This does not provide continuous motion, camera streaming, real secure BLE
authentication or shipping-firmware validation. The reviewed integration candidate
remains immutable; this follow-up must be integrated and revalidated separately
after P4 coordination.

## Acceptance result

The selected Node command passes 169 tests with zero skips, including 30 new
checks: 19 protocol/source-audit tests, one controller ownership test, three
fixture tests and seven mock-panel tests. The required Linux validator passes 181
tests with zero skips. The final seven-profile portal rebuild preserves all GP
code hashes and connection flags, packages the exact watch sources and retains
connect-src none for the console. No native VM, UBL, portal transport, daemon or
installer implementation changed, so no new Pi hardware run is claimed.

[Validation](tests/update-watch-validation.json), [source audit](tests/update-watch-source.json),
[fictional scenario](tests/update-watch-scenario.json) and
[packaging](tests/update-watch-packaging.json) preserve the exact scope and hashes.
The scenario receives 19 fictional notifications, retains eight typed samples,
records no mutation, and stops locally without claiming an updater outcome.
Full [Node output](tests/update-watch-node.txt) and
[repository output](tests/update-watch-linux.txt) are retained with original
capture hashes and declared CRLF-to-LF conversion in the validation report.
