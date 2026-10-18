# Bounded USB-local Wi-Fi setup

The user controls the final submission in a local masked interface. Saving a
Windows credential is a separate action from sending it to the positively
identified Fruit Jam. Do not read the vault password from an agent command.
The local GUI may access the selected vault entry only inside the user's
explicit target-specific Connect action, after verifying USB identity and the
board setup protocol. It never returns a password to chat, CLI arguments,
diagnostic files, VM bytecode or program snapshots.

This stage adds association and DHCP only, using the restored official NINA
3.3.0 protocol. Embedded HTTP/WebSocket/IDE service remains a separate stage.
No automatic coprocessor access or credential resend occurs at boot. Credentials
are transient on RP2350; reconnect after a cold reset requires another local
submission until a separately designed board storage option is implemented.

## Protocol

Use the existing SmallVM file-extension message 205, index 0, as a dedicated
Fruit Jam control envelope. This target has no generic file-transfer service.
The long-message body is `FJNW`, protocol byte 1, opcode byte, little-endian
32-bit nonzero request ID. Probe=1 and cached-status=3 require exactly ten
bytes. Join=2 adds SSID length, key length and those exact byte sequences.
SSID is 1..32 UTF-8 bytes; WPA key is 8..63 bytes, or 64 hexadecimal bytes.
Embedded NULs and malformed lengths are rejected. No payload is executed or
stored as VM code. Responses use message 205 and non-secret JSON with request
ID, command result and cached status; they never echo credentials or SSID.

Decode/copy is bounded, and the VM thread never performs SPI or association
waits. The existing worker owns SPI and handles one operation at a time.
It sends NINA 0x11 with exactly two bounded parameters, polls 0x20 for connected
status 3, then reads 0x21 with three four-byte IP/netmask/gateway parameters.
The association/DHCP deadline is 45 seconds with yielding between polls; every
CS/BUSY wait retains its existing one-second limit. Zero, broadcast and multicast
IP addresses do not count as DHCP success. No static IP override is sent.

Clear pending/local credential copies and the SPI frame on every completion or
error. Clear the consumed VM envelope before returning to the runtime. Retain
only status/error/IP and ordinary firmware identity, and keep responses within
available VM output capacity without waiting for a stalled controller.

## Acceptance

- Real C malformed-envelope and NINA framing tests cover bounds, exact lengths,
  multiple parameters, guard bytes and output zeroing.
- A real VM harness proves message 205 never creates or changes code records,
  and malformed commands cannot submit credentials.
- Compile the native target and refresh exact source/artifact hashes.
- User clicks the local target-specific action; record non-secret submission
  receipt and actual association/IP status. Test USB arithmetic/reconnect and
  saved code CRCs during and after association. Wrong-password/timeouts must
  produce bounded errors without resetting the interpreter or exposing values.
- Preserve the C6 image and current RP2350 program store. No sensor, audio,
  card formatting or unrelated board is part of setup.

## Verified checkpoint, 2026-10-18

Source `95c4b70ee8c8a9fb4ecd7e178b4a4386d9522752` compiled and was
programmed with SWD verification. ELF SHA256 is
`f8ec218acf73f0f66911f19164fe6b30492ad55938e99f5733c2cbb44492911d`.
The real C parser harness passes 193 checks; the real VM harness covers
control-envelope dispatch, zeroing, malformed input and program isolation.
See [build provenance](../evidence/2026-10-18/fruit-jam/wifi-build-verification.json).

The user clicked **Connecter ce Fruit Jam avec le Wi-Fi du coffre Windows**
in `tools/provision_fruit_jam_wifi.py` after saving their reusable Windows
credential separately. The GUI verified USB serial `E46570978F1E5A34` on COM8
and setup protocol 1 before its click handler read and transmitted the values.
Association and IP assignment completed in about 3.8 seconds. NINA 3.3.0 reported
connection status 3, IP `192.168.1.7`, mask `255.255.255.0` and gateway
`192.168.1.1`; no static-IP command was sent. Its canonical MAC is
`58:e6:c5:f5:a3:58`.

Seven USB arithmetic checks returned 12 during association. Chunk 0 retained
CRC `297d191b`, USB reconnect passed, and a subsequent independent USB probe
reported the same ready/IP state. The user confirmed the displayed connection
with an IP. The [sanitized physical receipt](../evidence/2026-10-18/fruit-jam/physical-wifi-association.json)
contains status and provenance only; no credential values or flash dumps.

This is one successful physical association. Wrong-password/timeouts have not
been physically exercised. Board credential storage, automatic boot reconnect,
TCP/HTTP/WebSocket and the standalone IDE remain pending. The assigned IP is
not yet an IDE URL. The C6 firmware was not flashed or reset during setup.
