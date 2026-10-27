# Raspberry Pi 5 and MicroDuck delivery status

Evidence date: 2026-10-27. This work is isolated from the active P4 checkout.
No ARM64 release or updated GitHub Pages deployment has been published.

| Requirement | Status | Evidence or remaining gate |
|---|---|---|
| Native SmallVM v417 on Pi 5 | Implemented and physically tested | AArch64 GCC builds, ASan/UBSan, real bytecode and PTY, [core evidence](../linux/arm64/tests/README.md). |
| IDE arithmetic, loop, reconnect, browser project restore | Implemented and physically tested | Actual graphical editor and Pi execution, screenshots in core evidence. |
| Local installer, reinstall, upgrade, uninstall | Implemented and physically tested | Private test prefix, actual binary, programs preserved; [adapter installer evidence](../linux/microduck/tests/pi5-adapter-installer.json). |
| Program autostart after VM process restart | Implemented and physically tested | Acknowledged durable code survived process termination; this is not OS reboot acceptance. |
| Optional user service | Implemented and simulated | Unit generation/lifecycle tests use a systemctl mock; actual user-service startup remains untested. |
| Full OS reboot and Windows SSH persistence | Implemented but untested | No reboot performed. The Windows agent is automatic and fresh-process SSH works; actual reboot is a separate check. |
| Release artifacts and corresponding source | Implemented, local candidate only | Deterministic archives, native evidence binding and hashes; [release contract](../linux/arm64/RELEASE.md). No public download URL verified. |
| Pi/MicroDuck board selection and install command generation | Implemented and simulated | Local portal and validation tests; copy remains disabled until reviewed artifacts are published. |
| HTTPS Pages to device network transport | Blocked | Trusted WSS endpoint/certificate and actual browser local-network behavior not commissioned. Pi loopback editor through existing SSH tunnel is physically tested. |
| Web Bluetooth discovery panel | Implemented and simulated | Mock chooser/version/cleanup tests; physical radio and browser/device compatibility untested. |
| API-44 BLE JSON-RPC client | Implemented and simulated | Mock framing, IDs, ACK writes, auth/permission/timeouts; [coverage](MICRODUCK_PROTOCOL.md). |
| Advanced browser JSON-RPC console and full protected-command UI | Not yet implemented | Validated client methods exist, but no arbitrary raw console is exposed. Real command UI awaits a reviewed confidential transport; the standalone lab is a bounded fixture surface. |
| Real BLE PIN authentication/Wi-Fi provisioning | Blocked | Shipping BLE confidentiality cannot be attested. PIN is not encryption; no real secrets are sent. |
| Browser commissioning controls | Implemented and simulated | Standalone, explicitly fictional simulation; no physical transport or credential inputs. See browser commissioning guide when merged. |
| JSON-RPC local gateway | Implemented and simulated | Real Unix sockets and peer identities; robot daemon replies are mocks. |
| Native MicroDuck primitive adapter | Implemented on physical Pi with simulated robot | Real VM bytecode, moving GC, jobs, gateway, errors, timeouts and graphical health block. [Adapter evidence](../linux/microduck/tests/README.md). |
| Sensor, battery, sound and skills on actual MicroDuck | Implemented but untested | API envelopes and simulated replies implemented; no physical device available. |
| Continuous locomotion/camera/direct motor control | Not implemented | Outside the selected BLE/local gateway surface; preserve robotd controller and use supported future transport. |
| Scalar battery/sensor and universal robot-ready blocks | Not yet implemented | Full optional health/battery JSON is available; exact units/readiness semantics require shipping API/hardware validation. Do not invent readings. |
| Shipping MicroDuck OS/API/socket ownership | Blocked | Inventory and authoritative permission checks on arrival; never guess daemon UIDs or change permissions to force access. |

Milestone A is partially complete: native Pi execution is verified, while the
published installer/reboot gates remain. B awaits coordinated Pages/release
publication. C has a tested mock protocol core and an explicit real BLE security
gate. D has native Pi end-to-end tests against simulated daemons. E has a
commissioning checklist; it is not a physical compatibility claim.

Start with [Pi installation and tests](RASPBERRY_PI_5_INSTALLATION_TESTING.md),
[port design](LINUX_ARM64_SMALLVM_PORT.md), [Web Bluetooth](MICRODUCK_WEB_BLUETOOTH.md),
[JSON-RPC](MICRODUCK_JSON_RPC_INTEGRATION.md), [robot installation](MICRODUCK_INSTALLATION.md),
and [Christmas hardware checks](MICRODUCK_CHRISTMAS_HARDWARE_VALIDATION_CHECKLIST.md).
The [integration plan](LINUX_MICRODUCK_INTEGRATION_PLAN.md) records ordering,
shared-file conflicts and the publication gates.

| Brief section | Implementation/evidence map |
|---|---|
| 0-1: access and repository review | Verified strict-host SSH, Pi inventory, pinned upstream sources and existing capability/packaging contracts; no credential material in Git. |
| 2/5: portal and copied install | Seven profiles, validated release/target command generator, local packaging and Node/UI tests; published/copy acceptance is pending. |
| 3: native VM | Offset arena, strict transformations, PTY/persistence, bridge and real Pi/graphical evidence. |
| 4/8: installer/release/Pi | Real private-prefix lifecycle and self-tests; local deterministic source/binary candidate; service/reboot/publication gates remain. |
| 6: browser BLE | API-44 compatibility table and mock tests; discovery UI; real secret operations blocked; bounded fictional commissioning lab. |
| 7: robot integration | Checked Unix gateway, native jobs, UBL and real Pi execution against simulated daemon responses. |
| 9: Christmas preparation | Explicit Unix/browser simulators, six requested guides, status matrix and hardware checklist. |
| 10: browser security | Strict real BLE confidentiality gate, trusted WSS configuration only, tested SSH-loopback editor. |
| 11: tests/CI | Required validator plus dedicated native CI workflow; actual hosted runs pending. [CI scope](LINUX_CI.md). |
| 12-13: delivery/autonomy | Isolated local commits, auditable evidence/candidates, independent parallel work; shared publication held for P4 coordination. |
