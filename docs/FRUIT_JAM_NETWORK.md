# Fruit Jam standalone network stages

The requested goal is the actual MicroBlocks IDE served by Fruit Jam over
Wi-Fi, with binary VM WebSocket transport and persistent programs. The current
loopback IDE is a verified USB baseline; it is not the standalone endpoint.
The working USB-local setup reads the selected Windows credential only inside
the user's explicit target-specific Connect action.
SHT4x investigation remains cancelled and inactive.

## Stage A - identify the AirLift protocol

- Identification itself does not enter the UART bootloader, erase or upload
  firmware. After the initial timeouts the user reported earlier coprocessor
  experiments and explicitly requested restoring WiFiNINA; see the separate
  [restoration procedure and evidence](FRUIT_JAM_AIRLIFT_RESTORE.md).
- Configure only SPI1 MISO28/SCK30/MOSI31, manual CS46, BUSY3 and shared reset22.
  GPIO0 remains input/pull-up and is the RP2350 USBBOOT button. The schematic
  places ESP32-C6 BOOT9 on shared I2S/ESP IRQ23, with an external 10k pull-up.
  The initial diagnostic left IRQ23 untouched. A temporary input/pull-up probe
  confirmed it high, without resolving the initial handshake timeout. The
  current explicit reset path configures it as input/pull-up before reset.
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
- The implemented USB-local setup uses a target-specific native GUI and a
  separate binary control envelope, as [specified here](FRUIT_JAM_WIFI_SETUP.md).
  The user selects their saved network in that local flow, outside chat/logs.
  Do not read or reuse
  the Waveshare's private credentials without separate explicit approval.
  Avoid embedding credentials in commands, commits, artifacts or URLs.
- Keep setup secrets out of uploaded VM bytecode: code snapshots are automatic.
  Use a separately framed board-control extension dispatched without creating
  code records, with exact magic/version/length checks and cached status ACKs.
  Wipe transient credential copies after the worker consumes them. The local
  GUI has no HTTP server. A future browser setup page would require same-origin
  POST, loopback binding and no request-body logging.
- A remembered network requires a visible setup choice and a separate checked
  configuration-storage boundary; do not assume factory NINA association
  persists over power loss. Decide the storage format/partition only after the
  actual firmware behavior is known. Never overlap app or VM snapshots.
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
  PSRAM and IR each require their own evidence. The three physical button
  presses/releases now have a separate passing record.

## Primary protocol references

- [Adafruit Fruit Jam Wi-Fi guide](https://learn.adafruit.com/adafruit-fruit-jam/wifi-test)
- [Adafruit ESP32SPI driver](https://github.com/adafruit/Adafruit_CircuitPython_ESP32SPI)
- [Adafruit WiFiNINA fork](https://github.com/adafruit/WiFiNINA)
- [Adafruit NINA firmware](https://github.com/adafruit/nina-fw)

Reference revision/hash records accompany implementation. The pinned Zephyr
target stays the runtime; factory Arduino/CircuitPython examples are protocol
and wiring references, not replacement firmware to flash on this board.

## Historical Stage A checkpoint

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

Stage A was compiled at `71f28917bf78cd9e69f18b5e2adafebc6653a188`, with
ELF SHA256 `6710409f15e340c0e1d7c691dd9f40a67774b43432e8c8d96f39d6608a62f378`.
The real C framing harness passed 36 checks and the VM harness passed. The
image was programmed with verification. Initial identification, explicit reset
and a GPIO23 input/pull-up probe all timed out at the version handshake, with
zero successful queries. A bounded slower SPI version-only probe also saw no
E0 response. These are failed physical AirLift results, not a Wi-Fi PASS.
USB arithmetic and the current program CRC remained intact after those tests.
The user's later WiFiNINA restoration request is tracked separately, preserving
the earlier failed evidence and the distinction between flashing, protocol
identification, network association and standalone IDE acceptance.

After official Fruit Jam NINA 3.3.0 restoration, three native SPI cycles passed
version/MAC/status framing, with all nine queries successful. USB arithmetic,
reconnect and the current program CRC passed. At that checkpoint the MAC formatter
reversed the reply bytes and needed correction at the next coordinated build;
the actual six bytes match the independent UART identity. Version is 3.3.0 and
the raw connection status was 254. Association, DHCP and sockets were pending.

## Current provisioning checkpoint

Source `95c4b70` adds bounded WPA association and three-parameter IP parsing,
cached setup status, transient credential wiping and a Fruit Jam-only runtime
guard for malformed/partial control frames. Its MAC formatter preserves reply
byte order, verified as `58:e6:c5:f5:a3:58`. Native compilation, C parser tests
and real VM security/regression tests pass. Existing Waveshare source is unchanged.

The user explicitly clicked Connect in the local GUI. NINA 3.3.0 reached
connection status 3 and assigned `192.168.1.7`, with netmask/gateway reported
and no static-IP command. Seven USB arithmetic checks, saved program CRCs and
reconnect passed. See [the setup checkpoint](FRUIT_JAM_WIFI_SETUP.md) and its
sanitized receipt. TCP socket service and the standalone IDE are still pending;
no HTTP endpoint is claimed at that IP. No boot-time credential replay/storage
is implemented yet.

The pinned manifest contains 147 original assets, 17,282,925 raw bytes and
3,512,571 gzip bytes. This suggests the compressed editor can fit in the 4 MiB
application partition alongside native code, but patched-asset generation and
the final linker bounds still decide that. No partition expansion is assumed.
