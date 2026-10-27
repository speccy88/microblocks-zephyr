# Browser commissioning simulation

This lab is explicitly fictional. It exercises the actual API-44 JavaScript
RPC client with an in-memory backend, sequential 20-byte request writes and
seven-byte response fragments. It cannot connect to a robot, BLE, the Linux
simulator or a network endpoint. It has no PIN/password input, caller-supplied
transport, raw command console, install command or persistent storage.

From the repository, serve `web/microduck` on loopback with an ordinary local
static server, then open `simulation.html`. The built portal also packages it at
`microduck/simulation.html`, linked from the MicroDuck discovery card.

```sh
python3 -m http.server 8878 --bind 127.0.0.1 --directory web/microduck
# Open http://127.0.0.1:8878/simulation.html
node --test tests/test_microduck_simulation.cjs tests/test_microduck_simulation_panel.cjs
```

Click Start SIMULATION to create a session. Identity, documentation-only IP,
open demo SSID, battery and advertised skills are fictional. Joining that demo
network and recording sounds/skills each require a fresh, specific checkbox.
Changing selections or refreshing invalidates staged confirmation. There are
32 action slots, 256 requests and 64 retained method/ID trace entries per session.
No actual sound, network change or movement occurs. End/restart discards action
history, fake IP and prior authentication state. The page's CSP has
`connect-src 'none'` and no external assets.

The 2026-10-27 local Edge graphical check followed the actual packaged portal
link, started the lab, displayed fictional API-44 identity/battery/skills,
confirmed a fake network join, recorded `chirp` and `simulation_bow`, and verified
each checkbox/action button was reset. Ending and restarting removed the fake
IP and all three action records. [Screenshot](../tests/browser-commissioning.png)
and [scoped report](../tests/browser-commissioning.json) retain this evidence.
Fourteen new Node tests cover protocol, lifecycle, limits, tampered choices and
mock DOM controls. These are browser/mock results, not physical robot acceptance.

Real discovery is the separate Bluetooth panel. Real authentication/provisioning
remains blocked by unverified link confidentiality. Linux native robot blocks
use the separate private Unix gateway and explicitly simulated daemons; their
[Pi evidence](../tests/README.md) does not come from this page. Firmware updates,
rollback, direct motors, continuous movement and emergency stop are not simulated
controls here. Actual commissioning follows the
[hardware checklist](../../../docs/MICRODUCK_CHRISTMAS_HARDWARE_VALIDATION_CHECKLIST.md).
