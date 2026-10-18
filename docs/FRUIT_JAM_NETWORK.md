# Fruit Jam standalone network stages

The requested goal is the actual MicroBlocks IDE served by Fruit Jam over
Wi-Fi, with binary VM WebSocket transport and persistent programs. The current
loopback IDE is a verified USB baseline; it is not the standalone endpoint.
No network credential is requested or reused before setup is functional.
SHT4x investigation remains cancelled and inactive.

## Stage A — preserve and identify the factory AirLift

- Keep the ESP32-C6 factory firmware. No UART bootloader, erase or firmware
  upload is part of identification.
- Configure only SPI1 MISO28/SCK30/MOSI31, manual CS46, BUSY3 and shared reset22.
  GPIO0 remains input/pull-up; refuse a reset while BOOT is pressed rather
  than driving that input high. IRQ23 remains untouched.
- GPIO22 also resets the TLV320 codec. Perform Wi-Fi initialization before
  codec configuration; keep audio muted/idle while bringing up the shared
  reset. This is a dependency, not a reason to revisit the external sensor.
- Begin at 1 MHz, mode 0, 8 bits, with a mutex, fixed buffers, bounded waits
  and explicit CS release on every error. Follow Adafruit's ready-low idle,
  CS assertion, ready-high acknowledgement, command and response sequence.
- Query only firmware version (0x37), MAC (0x22) and connection status (0x20).
  Validate E0/header/reply/count/length/EE framing. Never print credential
  parameters, whole frames containing secrets, or existing stored settings.
- Physical acceptance: repeatable version and status responses, correct
  length/framing, no lost USB arithmetic/reconnect, and no coprocessor flash.

## Stage B — bounded socket service and secure provisioning

- Implement socket allocation, TCP listen/accept/status, bounded receive,
  partial send and close using the verified factory protocol. Confirm actual
  firmware limits rather than assuming plain ESP-AT or ESP-Hosted behavior.
- Keep at most four HTTP clients and one active VM controller. Bound each
  request/header/frame and every timeout. Stream assets in small chunks;
  release stalled clients. Use exact Content-Length/type/encoding headers.
- Build a USB-local setup page only after transport works. The user enters
  the chosen network through that page, not chat or logs. Do not read or reuse
  the Waveshare's private credentials without separate explicit approval.
  Avoid embedding credentials in commands, commits, artifacts or URLs.
- Association, DHCP and reconnect must produce actual status/IP evidence.
  No Wi-Fi success is inferred from a command ACK or detected coprocessor.

## Stage C — embedded real IDE and VM ownership

- Store the pinned real GP MicroBlocks editor and Fruit Jam library in board
  flash. Preserve licenses and asset hashes. Never substitute a toy editor.
- Serve HTTP and /ws/vm directly through AirLift sockets, with bounded binary
  queues, WebSocket masking/fragmentation/control-frame handling and a single
  controller. USB and WebSocket ownership changes cancel partial streams
  without losing saved programs.
- Keep the VM sliced/yielding; network work must not block it during slow
  socket operations. Prefer a network worker and bounded shared queues.
- Physical acceptance: fresh browser load with host USB bridge stopped,
  arithmetic/edit result, one exact 1..50 output run, stop, variable
  inspection, reconnect, reload and reboot/autostart with CRCs retained.
- Record remaining hardware limits separately: DVI, USB host, audio, SD,
  PSRAM, IR and physical button presses each require their own evidence.

## Primary protocol references

- [Adafruit Fruit Jam Wi-Fi guide](https://learn.adafruit.com/adafruit-fruit-jam/wifi-test)
- [Adafruit ESP32SPI driver](https://github.com/adafruit/Adafruit_CircuitPython_ESP32SPI)
- [Adafruit WiFiNINA fork](https://github.com/adafruit/WiFiNINA)
- [Adafruit NINA firmware](https://github.com/adafruit/nina-fw)

Reference revision/hash records accompany implementation. The pinned Zephyr
target stays the runtime; factory Arduino/CircuitPython examples are protocol
and wiring references, not replacement firmware to flash on this board.

## Prepared Stage A implementation

`airlift.c` uses an idle diagnostic worker, manual active-low CS and 1 MHz SPI1.
`nina_protocol.c` only creates the three allowed identification commands and
rejects unexpected counts, commands, lengths and terminators. BUSY waits are
limited to 1 second; START-byte retries to ten 10 ms pauses. Buffers are fixed,
and chip select is released on errors. No coprocessor access occurs until an
explicit VM diagnostic request. There is no automatic reset or retry.

- `[fruitJam:airliftIdentify]` requests identification without reset.
- `[fruitJam:airliftResetAndIdentify]` separately requests shared GPIO22 reset
  then identification. It refuses reset if the BOOT button is pressed and
  never drives GPIO0. The codec must remain idle before this diagnostic.
- `[fruitJam:airliftStatus]` reads cached results. State 0 is idle, 1 queued,
  2 running, 3 complete and 4 failed. Stages 1..4 are preparation, version,
  MAC and connection status. A successful query does not establish association.

Reference revision: `64f4695cc4457df0718e1a6460082381359c3562`. The MIT notice and
per-file hashes are retained. The parser harness exercises the real C against
truncated, oversized, malformed, delayed and error replies. The physical script
requests three identifications and verifies USB arithmetic, code CRCs and
reconnect. A shared reset requires its explicit command-line option.

This Stage A source is **prepared, not yet compiled or physically validated**.
The installed peripheral image and the remote USB checkpoint remain unchanged.
The previous build report describes that image; it is intentionally not
regenerated to pretend the new source has already been built. A new coordinated
ARM build, parser/VM tests and fresh artifact hashes are required before flash.

The pinned manifest contains 147 original assets, 17,282,925 raw bytes and
3,512,571 gzip bytes. This suggests the compressed editor can fit in the 4 MiB
application partition alongside native code, but patched-asset generation and
the final linker bounds still decide that. No partition expansion is assumed.
