# Raspberry Pi: local mobile editor

The Pi can serve the touch editor and its `/ws/vm` endpoint from one local HTTP
origin, for example `http://192.168.1.105:8877/`. Select Connect in Safari; this
mode has no login or session key. It intentionally uses unencrypted HTTP/WS on
the trusted LAN. Other LAN devices can program the VM or read/change traffic.
The network owner must approve the exact listener before activation.

The public GitHub Pages editor is unchanged. No browser security exception,
certificate, router rule or firewall change is needed. The separate server binds
one explicit private IPv4 address, filters a private /24 or narrower client range,
checks exact Host and Origin, keeps one controller and expires after 30 minutes.
The default `bridge.py` stays loopback-only.

Build the mobile assets into a fresh directory:

```sh
python3 tools/package_pi_lan_editor.py --source /path/to/verified/js-preview/waveshare --output /path/to/pi-editor
```

Start an already tested native SmallVM in a new private data directory. The VM
publishes its PTY discovery record; it never listens on the network. Select an
existing data directory only when explicitly resuming its programs. With that
VM running, activate the approved listener using the pinned WebSocket environment:

```sh
python3 linux/arm64/lan_editor.py --activate \
  --bind 192.168.1.105 --port 8877 --allow-clients 192.168.1.0/24 \
  --editor /path/to/pi-editor --vm-executable /path/to/smallvm \
  --pty-info /private/new-session/pty.json
```

The executable and private data must be outside the asset directory. No persistent
service is installed. Exiting the server closes its own listener; VM lifecycle is
owned by its launcher. A 30-minute session launcher must also stop only its own VM.

The Pi touch compiler adds the Linux primitive-table alias at index 3. General
programming and SFC use ordinary SmallVM bytecode; no GPIO or MicroDuck hardware
capability is added. The headless VM treats the interpreter's internal display-off
cleanup as a no-op; explicit display operations still report unsupported.

Validation distinguishes real Pi execution in a desktop mobile viewport from a
physical iPhone/Safari test. The latter remains pending until performed on the
phone. See the dated LAN acceptance evidence for exact results and session expiry.

## Verified checkpoint, 2 November 2026

The physical Pi passed actual compiler uploads, `5 + 7 = 12`, live editing to
`6 + 7 = 13`, project export/import, stop, reconnect, CRC readback and execution
after reconnect. Edge ran at 390 × 844 with a real WebSocket; no VM replies were
simulated. All served engine files retained their pinned upstream hashes.
Physical iPhone/Safari acceptance remains pending.

The temporary user-approved session started at 01:54:52 UTC and expires at
02:24:52 UTC. It uses fresh data and a native AArch64 binary with the headless
cleanup fix. No previous programs, Caddy, router, firewall or trust settings were
changed. No persistent service was installed.

The main validator passed 235 tests with 290 platform/dependency skips; seven
LAN tests passed in memory on the Pi and four package tests passed in Node.
See [acceptance evidence](../evidence/2026-11-02/pi-lan/acceptance.json).
