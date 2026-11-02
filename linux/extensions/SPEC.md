# Generic Python extensions for native Linux SmallVM

Work in main; preserve the Pi web task and legacy GP branch. Do not edit the
existing web servers or their running services. Reuse v417 and the existing
bounded, same-user Unix RPC job transport; append generic extension routes and
pure JSON result access without renumbering any primitive. Keep existing robot
method validation and confirmation gates unchanged.

## Contract

A local configuration selects trusted Python factories and board settings. A
factory exposes named operations; adding a plugin requires no C driver change.
The wire selects only configured extension/operation names, never Python source,
imports or filesystem paths. Plugins execute as the user's trusted Python code,
not in a security sandbox. No default TCP listener, broker, credentials, device,
GPIO mapping or externally fetched code is introduced.

Use a separate persistent worker process per extension, bounded requests/replies,
one operation per worker, bounded admission and an enforced supervisor deadline.
A blocked import, SQLite operation or driver cannot block the server or SmallVM.
Timeout kills the owned worker and preserves an unknown mutation outcome; never
automatically replay a request. Later explicit calls may start a fresh worker.
Stop/disconnect does not imply transaction rollback or actuator cleanup.

The application launcher owns the service and worker lifecycle, reusing the
existing session launcher instead of changing its bridge or network policy.
Normal users drag domain blocks. JSON, job IDs, polling, release and process
startup remain internal. A missing service/dependency produces an actionable
editor message and stops the calling script, without inventing a zero reading.

## Initial plugins

- SQLite: a configured database below private application state; one parameterized
  statement per call, bounded SQL/bindings, progress deadline, row/column/cell and
  encoded-response limits. Disable extension loading, ATTACH, PRAGMA and user
  transaction control. Complete or roll back before reporting an outcome. Expose
  ordinary execute/query/rows/cell blocks and a self-contained useful example.
- HTTP: optional official `requests`, configured origin scopes, GET/POST, bounded
  connect/read/total deadlines and streamed response, headers and response data.
  TLS verification stays enabled; redirects cannot bypass configured destinations.
  Test only a local HTTP fixture; no external endpoint is contacted.
- MQTT: evaluate/use official Paho v2 callbacks with a separate network loop,
  bounded subscriptions/incoming queue, explicit drop counts and publish outcome.
  No assumed broker or credentials. Clearly distinguish implementation/fixtures
  from real broker commissioning.
- Blinka: lazy optional official imports and an SHT4x example using board I2C and
  Adafruit's driver. Pi 5 configuration is explicit; no physical sensor PASS is
  inferred. MicroDuck/RK3566 remains pin-map unverified, even though Radxa Zero
  3W shares the SoC. Never force a different board's GPIO mapping.

## Acceptance

Run unit/adverse-input/process-timeout tests and actual JS import/compilation.
Upload the compiled domain-block example to the real sanitized SmallVM: another
task and IDE pings must progress during a deliberately slow worker. Verify SQL
parameters, row limits, errors, persistence, worker restart and no automatic retry.
Then perform a separate SQLite example on the physical Pi 5, with visible blocks,
native VM and Python. Use an isolated application directory/candidate VM and
coordinate before changing the active service. Record exact source/binary and
observations; other Linux hosts and physical Blinka/MicroDuck/MQTT remain untested
unless measured. Validate the full repository, preserve concurrent main commits,
commit/push, and check exact-head CI. No security setting or unknown-source install.
