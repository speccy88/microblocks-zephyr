# Pi5 source installer and Blinka acceptance â€” 2026-11-02

Source payload: af4a4fa0fa2a198fdaceca79aae34b4e65dc2483, downloaded directly
from this project's GitHub source archive, SHA256
4b916287c527a4e25f6e66ef70d090c15b998bd01a379b818e5a2c3a1d871bbd.
No native ARM64 release was invented or published.

On the actual Pi5 / Debian13.4 / Python3.13.5 / GCC14.2, a new private prefix
installed all sixteen hash-locked official PyPI dependencies, detected Pi5,
built native VM417 and composed the exact reviewed mobile editor with Python
blocks and browser update UI. Its binary SHA256 is
d60102ce79a73f79ee63d094e79c0803e64fdfb8cb4949a688639e9e89d09a2b,
identical to the existing tested native VM. Self-test and 50 real protocol
repetitions pass; see native-protocol.json.

38 Linux tests executed with no skips (8 Blinka, 16 full installer, 9 LAN
Host/Origin, 4 runtime/recovery, 1 preview extraction). Full lifecycle service
operations are explicit fixtures. The generated unit separately passes the real
systemd parser on the Pi and Linux test host; it was not installed/started.
Seven bootstrap hash/archive/launch tests and five freshly packaged Node web
adapter tests pass. Windows offline validation: 614 tests, 360 environment
skips, no failures.

Actual repeat installation reuses its environment/release. Actual source update
from 5cccb552f50af780464f29842e2d9f8f80f68f0a to the payload passes GitHub's
descendant comparison and preserves a private data marker, SQLite row22600 and
profile byte-for-byte. A real older-source selection is refused. Uninstall
removes only its launcher; all test data, databases, profile, Python environment
and both code releases remain. These were isolated acceptance data, not Fred's
program. See prepared-source.json and update-uninstall.json.

At the initial installer checkpoint, Fred's existing service retained PID11244
and /usr/bin/python3 for its Python worker. In the subsequently authorized
existing-service follow-up, only `python_extensions.interpreter` was changed
to the verified Blinka environment. A preflight confirmed no editor controller
or backend connection. Configuration, program and Python state were backed up
privately; the existing owned service restarted to readiness in 0.485 seconds.
Its new supervisor is PID12541 and Python service child PID12543 uses the
selected venv. Boot enablement, Caddy/port80, native VM417, program, profile,
base unit and drop-in are preserved. No additional listener, router/firewall,
trust, group or I2C change was made. See existing-service-blinka.json.

The actual port80 editor in a phone-sized Edge test context compiled 26 native
chunks for a normal SQLite query/rows/list reporter with bound parameter22600.
It remained disconnected from the user's VM and uploaded no user program.
A separate private native VM executed that bytecode against the existing live
Python worker, returned22600, and shut down. The live program and SQLite file
retain their exact SHA256 hashes. The existing port80 programming WebSocket
separately answered a read-only version request with v417 Linux ARM64.
No Python worker or native VM was mocked; this was not a physical iPhone test.
See existing-service-e2e.json. The disabled climate call returns an explicit
extension_missing/rejected response, without creating a hardware object.

All nine GitHub workflows on 9612848c5afa00b023da536463eb296d879a6d96,
including both iPhone Simulator sizes, completed successfully; see
ci-9612848-complete.json. Fresh source installations select their own isolated
environment for the new service.

No physical sensor driver, I2C/GPIO object, sensor test, fresh OS installation,
new-service boot or physical iPhone test is claimed. Optional climate/HTTP/MQTT
plugins remain disabled. Native VM421 was not installed.
