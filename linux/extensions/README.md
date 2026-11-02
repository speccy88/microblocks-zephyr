# Python domain blocks for Linux SmallVM

Use normal **Data** blocks: SQLite execute/query/rows, HTTP GET/POST, MQTT
publish/subscribe/next message, and the optional temperature/humidity example.
The application starts Python automatically. User programs contain no RPC,
request IDs, polling jobs or process commands. The shared JavaScript overlay
adds these blocks to the palette and includes their ordinary implementation
library only when a block is used. Empty projects stay empty; saved projects
retain their implementation library. Upstream engine files remain unchanged.

This requires native Linux and Python 3.11+, available through its hosted editor. GitHub
Pages alone cannot start Python on a Pi. This feature does not give an iPhone
browser USB serial, Bluetooth, or arbitrary access to Linux hardware.

## Useful first program

Open `Examples/Python/SQLite readings.ubp` in the packaged editor, connect the
Linux VM, and press Start. The program creates a readings table, inserts a bound
label/value pair, reads the latest five rows and counts them. A separate
heartbeat continues while SQL runs. Change `room` and `21500` in the ordinary
list block and run the stack again. The number is example data, not a sensor
measurement. Use SQLite rows and normal list/item blocks to access cells.

Parameters take a normal MicroBlocks list; blank means an empty list. SQL text
and values travel separately. Each call is one transaction; use explicit calls
for separate statements. Data persists in the configured private SQLite file.
Rows, columns, cell lengths, SQL length, SQLite value sizes, execution time and
encoded results are bounded. The limited-result block identifies omitted rows.
SQL extension loading, external databases, PRAGMA and user transactions are
disabled. These are conservative application limits, not a sandbox for Python.

## Application integration

The existing managed Pi `lan_service.py` supports an optional installation
setting in its private `service.json`:

```json
"python_extensions": {
  "profile": "python-profile.json",
  "state": "python-state",
  "interpreter": "/usr/bin/python3"
}
```

Copy `profiles/pi5.json` to that private profile path. Ship `python_runtime.py`
beside `lan_service.py` and the `linux/extensions` and `linux/microduck` Python
packages below that code directory. Use the candidate native binary containing
the generic Linux primitives and the editor produced by
`tools/package_python_extension_editor.py`. Keep the Pi updater's required
runtime capabilities in sync: older binaries must not replace a Python-enabled
runtime (package a tested candidate with `linux/arm64/package.py
--python-extensions` and require `python-extensions` in `service.json`). No
change to its existing Caddy listener, firewall or Origin checks is
needed. Preserve the existing program directory and keep Python state separate.
If an existing MicroDuck socket is configured, explicitly retain it as
`microduck_gateway` in the Python profile; the launcher refuses to discard it.

The managed application owns the service and all extension worker processes.
End users only open the app and place blocks. A separate foreground development
launcher is provided for isolated acceptance sessions:

```sh
python3 linux/extensions/launch.py --config linux/extensions/profiles/pi5.json \
  --state /private/app/python --binary /private/app/native/smallvm \
  --editor /private/app/editor --data /private/app/program --port 8876 \
  --session-python /existing/approved-venv/bin/python
```

That launcher reuses the existing loopback session; it does not install a
service or change network settings. Add `--resume` only for its existing program
directory. The optional session interpreter retains its venv symlink path;
plugins run in the main launcher's Python environment. For managed installations
the configured interpreter selects the environment for Python extensions.

## Optional capabilities

SQLite uses Python's standard library. HTTP uses the official `requests`
package, imported only when first used. Configure an `http` extension with
factory `linux.extensions.plugins.http:Extension`, a fixed `origin` setting and
a supervisor timeout (for example 3 seconds). Plain HTTP needs `allow_http:true`.
Use normal header/value blocks in a list; blank headers means none. Response
blocks expose status, headers, body, encoding and truncation. Redirects are
returned rather than followed, environment proxy/netrc credentials are disabled,
TLS verification remains enabled, and response/body/deadline bounds apply.
Binary bodies use explicit base64 encoding. Only a local fixture is contacted
by the tests. No public endpoint, credential or dependency is installed for you.

MQTT uses optional official `paho-mqtt` 2.x. Configure `mqtt` with factory
`linux.extensions.plugins.mqtt:Extension` and an explicit broker `host`; TLS is
on by default (port 8883). It has a separate Paho network thread, at most 16
subscriptions and 64 queued messages, bounded UTF-8 payloads, a dropped-message
counter, and publish acknowledgement limits. The normal publish block uses
QoS 0; the plugin also supports explicit QoS 1. QoS 0 means sent, not delivered.
Subscription success means queued, not SUBACK. Automatic reconnect/replay is
disabled. A timed-out publish discards its client and reports unknown delivery.
Authentication, persistent sessions and broker commissioning are not supplied.
The current MQTT tests are explicit API fixtures, not a real broker test.

The disabled `climate` profile illustrates Blinka + Adafruit SHT4x. Enable only
after installing the official compatible packages and checking the actual
board, wiring, address and bus. No physical sensor result is claimed. MicroDuck
has an explicit unvalidated pin-map gate: sharing RK3566 with Radxa Zero 3W
does not establish pin compatibility. Do not set `BLINKA_FORCEBOARD` to guess.

## Add another Python capability

A trusted local profile selects `module:factory`, settings and a 0.1–8 second
supervisor deadline. The wire cannot choose modules, executable Python or paths.
The factory receives `(settings, Context)` and exposes
`operations = {'name': callable}`. Each callable accepts an arguments dictionary
and returns a bounded JSON-compatible value. `close()` is optional. For example:

```python
class Extension:
    def __init__(self, settings, context):
        self.operations = {'double': lambda args: args['value'] * 2}
```

Add ordinary `.ubl` domain functions that hide `pythonCall`, using native JSON
helpers internally; no new C primitive or transport route is needed. Plugins
are trusted code running as the application user, isolated for responsiveness,
not security sandboxing. Their stdout is kept out of the protocol.

Each plugin has its own persistent process and accepts one operation at a time.
At most four native jobs and four service requests are active. A slow or blocked
plugin cannot stop the SmallVM scheduler or another plugin. The service kills
its owned process group on deadline and never automatically repeats an operation.
Stop/disconnect, timeout or a crashed worker can leave an unknown write outcome;
they do not prove rollback. Later explicit calls can start a fresh worker.
Missing service, operation, dependency or device stops the calling script with
an actionable editor message instead of returning an invented measurement.

MicroBlocks signed 31-bit integers, booleans, strings and nested lists roundtrip
natively. Larger integers and decimal JSON values keep exact JSON text. Objects
remain opaque result text behind domain accessor blocks. JSON null is the text
`null`; the advanced type accessor distinguishes it from a missing field.

## Validation and source APIs

See `SPEC.md` and the dated acceptance evidence for actual tested targets.
`tests/test_python_extensions_vm.py` requires a real native binary and the
output of `tools/compile_python_example.cjs`; absence is reported as a skip.
CI requires these tests to run on native x86-64 and ARM64, with ASan/UBSan.
`tests/python_extensions_browser.py` exercises real visible blocks, the normal
Start control, an edited parameter and the real VM through an exact-port local
SSH forward. Browser automation on Windows is not a physical iPhone test.

Primary API references: [SQLite](https://docs.python.org/3/library/sqlite3.html),
[Requests](https://requests.readthedocs.io/en/latest/user/advanced/),
[Paho v2](https://eclipse.dev/paho/files/paho.mqtt.python/html/client.html),
[Blinka](https://docs.circuitpython.org/projects/blinka/en/latest/).
