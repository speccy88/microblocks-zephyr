# MicroDuck Web Bluetooth

The API-44 client implements upstream JSON-RPC NDJSON framing, IDs, bounded UTF-8
reassembly, sequential acknowledged GATT writes, version read, subscribe-before-
write, timeout/abort handling and fresh authentication state after reconnect.
Its [command compatibility table and pinned source links](MICRODUCK_PROTOCOL.md)
distinguish client support, upstream transport permission and real availability.

The real portal panel opens the browser chooser only after a user gesture and
reports discovery/API version. It performs no RPC write. At the reviewed
upstream revision, pairing is off by default and the application PIN does not
establish link confidentiality. Web Bluetooth cannot attest this to the client.
Its transport therefore has immutable `confidential: false`: real PIN and Wi-Fi
credentials are refused. No checkbox bypasses this gate. Use the robot's trusted
local console for Wi-Fi until a verified confidential mechanism is available.

Client methods for identity, networking, sound, robot functions and updates are
tested against mocks, with mutations requiring confirmation and API permissions.
That code coverage does not make protected methods usable over current real BLE.
Continuous locomotion/camera require another officially supported transport and
are excluded. The browser cannot execute SSH or install software directly.

The standalone commissioning simulation exercises the real JavaScript RPC client
with an in-memory fictional backend. It has no physical BLE or network transport,
no credential entry and no installation command. Reset clears its state. Its
confirmed mock actions are fictional; they must not be presented as robot tests.
See the [simulation guide](../linux/microduck/docs/commissioning-browser.md)
for startup and test details.

Use a supported browser in a secure context for physical Web Bluetooth. iPhone
Safari does not provide the normal Web Bluetooth workflow. The real chooser,
pairing/encryption settings, shipping API version, radio fragmentation and
disconnects still require arrival testing. Respect browser security warnings;
do not weaken certificate, mixed-content or local-network controls.
