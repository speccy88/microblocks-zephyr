# Standalone wireless MicroBlocks on Waveshare ESP32-S3-RLCD-4.2

The accepted end goal is one self-contained board running **Zephyr +
ArduinoCore-Zephyr + SmallVM + HTTP/WebSocket**, with the actual MicroBlocks
graphical editor served from its own storage. A computer or phone opens
`http://<board-ip>` and programs the live VM wirelessly. Block edits upload
bytecode; they do not rebuild firmware. USB is for flashing and recovery.

The board should join a configured Wi-Fi network, show its IP on the RLCD,
and offer a bounded, protected AP when no network is available. No external
runtime server or CDN is required. Do not expose the service to the public
Internet. Do not log or commit Wi-Fi passwords or pairing credentials.

## Acceptance sequence

1. Pin and package the real editor/compiler and all required local assets.
   Inspect the existing UNO Q binary WebSocket implementation. Serve assets
   with correct MIME/encoding and browser isolation headers where required.
2. Build the combined VM/Arduino/Zephyr image with explicit memory budgets,
   one active controller, bounded RX/TX queues, fragmented-frame handling,
   disconnect recovery, and an exclusive WebSocket-to-VM transport.
3. Connect a browser to the board's own HTTP server. Upload and execute
   `5 + 7`, receive `12`, edit/re-run, stop/debug, reconnect, and stream 500
   ordered values with matching code CRCs. Retain actual observations.
4. Test persistence and reboot recovery with bounded program storage.
   RAM-only storage is an interim limitation, not final persistence support.
5. Expose convenient display, temperature/humidity, RTC, battery and button
   blocks, followed by SD, radios, audio and other supported peripherals.
   Distinguish implemented, compiled, exercised and visually confirmed states.
6. Use microSD for assets only if necessary. Detect the card first; inspect
   read-only and preserve existing files. Never format a card without explicit
   permission. Prefer compressed flash assets if they fit with adequate margin.

## Current measured constraints

The existing UNO Q editor package contains 147 files totaling 17,282,925
uncompressed bytes, including a 10,903,897-byte GP data package. Raw assets
exceed the 16 MiB flash size. Gzip packaging measured approximately 3.51 MB,
so the IDE fits in onboard flash without microSD. Static assets are served
from mapped flash without loading the package into MCU RAM. The actual
editor/compiler binaries remain upstream MicroBlocks/GP; the board library
and integration endpoints are adapted from the UNO Q source.

The USB SmallVM build is an intermediate recovery/test target. The production
transport must use binary WebSocket, with no shell/log text in its byte stream.
Arduino library compatibility is verified per library; Zephyr target support
alone does not imply complete Arduino compatibility.

## Tested standalone checkpoint

The final 2026-10-17 image passes the actual board-hosted graphical editor flow:
pair, edit 12 to 13, run 500 ordered values, inspect variables, stop, reconnect,
save/autostart after COM4 reset and retrieve the saved bytecode into the editor.
Four fresh browser loads and 148-asset concurrent verification pass. The final
package is 148 files, 3,513,201 compressed bytes. Active graphical/VM allocator
samples and precise flash/PSRAM accounting are in the evidence directory.
This completes the bounded standalone programming checkpoint. Full hardware
coverage and long-duration stability remain separate acceptance work.

## IP display and fallback acceptance limits

Both station and protected-AP startup construct an LCD screen containing the
actual IP and pairing code. Earlier physical boot logs record successful CFB/
display-driver transfers for both paths. The compiled 10x16 font and calculated
line wrapping fit the 300x400 visible bounds. This is driver/layout evidence;
physical pixels, orientation and readability have not been observed.

The earlier protected AP was physically joined, issued DHCP address
192.168.4.10, served the actual editor HTML/WASM and passed authenticated
WebSocket ping and 5+7=12. Station provisioning and the next station boot also
passed. The final full graphical acceptance was performed in station mode.
KEY-at-boot and saved-station startup failure select the same fallback code,
but those two triggers have not been physically exercised. Selection happens
at boot; fallback after a later station disconnection is not implemented.

See `evidence/2026-10-17/network-display-acceptance.json` for exact provenance,
the verified graphical screenshot link and the remaining physical observations.
A person must check the LCD and hold KEY during restart to accept those parts.
No firmware, network settings or credentials were changed during this follow-up.
