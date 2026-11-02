# Pi5 source installer and Blinka acceptance — 2026-11-02

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

Fred's existing permanent service retains PID11244, its native binary/program,
Caddy/port80 and configuration. Port80 answers HTTP200. No extra listener or
boot service was activated, no router/firewall/trust/group/I2C setting changed.
Its interpreter remains /usr/bin/python3; the separate Blinka environment is
installed and verified but is not selected for that older service. Fresh source
installations select their isolated environment for their new service.

No physical sensor driver, I2C/GPIO object, sensor test, fresh OS installation,
new-service boot or physical iPhone test is claimed. Optional climate/HTTP/MQTT
plugins remain disabled. Native VM421 was not installed.
