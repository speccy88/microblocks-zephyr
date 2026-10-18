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

Status: implementation in progress; no association/DHCP PASS claimed yet.
