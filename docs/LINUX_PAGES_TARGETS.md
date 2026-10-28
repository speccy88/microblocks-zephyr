# Linux targets in the public portal

The Board selector adds Raspberry Pi 5 and MicroDuck Rockchip RK3566.
Their separate editors are at `preview/editor/raspberry-pi5/microblocks.html`
and `preview/editor/microduck/microblocks.html`. Existing five editor folders
are preserved by the composition step; the ongoing JS migration is separate.

Pi 5 is a standalone Linux SmallVM target. Its Linux Core library adds no GPIO
or robot peripherals. The public HTTPS editor requires a trusted WSS bridge;
the separately tested Pi-hosted editor can use a loopback SSH tunnel.

MicroDuck is an experimental disconnected placeholder for exploring blocks.
Normal read-only preparations include robotd health/state, coherent tofd depth
and head IMU, padd axes/buttons/discovery and gamepad IMU batches. They were tested
on Pi with protocol-faithful fictional services; the physical robot is unverified.
Libraries labelled Simulation provide packet previews, motion, telemetry and
media preparation. They do not establish applied movement or live robot authority.
Mediad native camera pixels and live relay remain incomplete; the reviewed API
does not supply usable audio transport. Sound playback is a distinct robotd API.

The Pages build exports approved public Linux commit
`2c060b7f4e9153dd7213d9b7c2a479810577eb51` and applies one explicit status-text
overlay in a temporary export. Connection guards are unchanged. The generated
`linux-preview-manifest.json` records source commits, overlay hashes and all
static file hashes. No test evidence, credentials or lab screenshots are deployed.
