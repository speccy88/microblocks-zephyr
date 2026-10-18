# Native Fruit Jam IDE implementation checkpoint

The bounded TCP/HTTP/WebSocket implementation and all 147 real MicroBlocks
2.5.8 assets compile and are installed. **Standalone physical acceptance is
pending.** The verified graphical baseline remains the earlier local USB bridge.

Installed source: `39ef50966df24a028a5c16f943f75f2e9b1dc707`.
ELF SHA256: `82a33524f88aa119c7b65f72342013bf0eedc335968d0a2c3324dbe4941be931`.
Link allocation is 3,625,484 bytes of the existing 4 MiB app partition and
253,768 bytes of internal RAM. PSRAM is not mapped. Verified, patched editor
files occupy 3,510,850 compressed bytes. No ELF segment overlaps VM snapshots.

The server serializes complete SPI command/reply exchanges with diagnostics.
Its six documented NINA slots support one listener, up to four HTTP transfers
and one VM controller. Socket IDs, request sizes, partial sends, frame sizes
and timeouts are bounded. HTTP assets stream from flash in at most 2 KiB writes.
Host/Origin/key/version checks protect upgrades. Masked binary/continuation and
control frames share one VM controller; USB DTR takes priority. Network clients
cannot submit Wi-Fi credentials. `networkStatus` exposes progress/error counters,
never credentials. These design properties still need full physical acceptance.

## Measured results

- Native build and ARM Secure ELF/UF2/load-bound inspection: PASS.
- Real C protocol harness: PASS, 2,303 checks, including RFC6455 accept hash,
  request validation, every TCP split of a maximum frame, malformed lengths,
  SPI bounds/guard bytes and socket ID limits.
- Real VM harness: PASS, arithmetic, 50 ordered outputs, fragmentation,
  control-envelope isolation and simulated I/O.
- SWD install and USB/code regression: PASS. Chunk 0 retains CRC `297d191b`;
  arithmetic returns 12. Private firmware/VM-store backups remain outside Git.
- Live identity/IP cycles: PASS, NINA 3.3.0, MAC `58:e6:c5:f5:a3:58`, last
  assigned IP `192.168.1.7`.
- First physical `/api/status` response on source `163ea8c`: PASS. The next
  WebSocket connection timed out. Subsequent TCP connections and one ping also
  failed, despite NINA still reporting association. USB, SPI and code CRCs passed.
- Source `39ef509` shows a progressing worker, live listener, no clients and
  no SPI/protocol error while incoming connections time out. This does not
  establish working TCP service or a graphical IDE load.
- One explicit AirLift/shared-idle-codec reset succeeded without reflashing
  C6. NINA then reported status 254 and no IP. Reassociation awaits the user's
  local Connect action; no vault value is read automatically.

The positively identified host USB bridge on `127.0.0.1:8768` was stopped
before standalone validation. Other boards/ports, sensors, audio output and
SD writes were not accessed. Exact commands, hashes, resource records and both
passing and failed physical attempts are under `evidence/2026-10-18/fruit-jam/`.

Next acceptance is network recovery, the 147-asset integrity audit, WebSocket
arithmetic/editing/50 outputs/stop/variables/fragmentation/reconnect, USB takeover
and credential-path rejection, followed by the actual graphical editor from
board flash with the host bridge stopped. Reboot/autostart and automatic Wi-Fi
boot recovery remain separate. No board credential storage or vault replay is enabled.

## Radio-awake recovery experiment

After a fresh explicit user-requested retry, association and DHCP passed again
on source `91fd2fc`; native HTTP status, WebSocket upgrade/ready and one VM ping
passed, but the full VM sequence and later connections timed out. This does not
establish a working IDE. The previous disconnect-reason value 202 remains cached
even while connected and must not be reported as a current failure.

The next controlled experiment sends NINA command 0x17 with value zero once
before starting/resuming the listener. The official 3.3.0 handler maps this to
`WIFI_PS_NONE`. This increases radio power use to minimize incoming latency;
it neither changes Wi-Fi security nor resubmits credentials or resets the C6.
A bounded ACK is required before the listener can start. Expose the ACK state
in `networkStatus`. Keep the existing SPI serialization, socket/request bounds
and USB priority. Acceptance requires repeatable HTTP/VM traffic and the complete
asset audit; a command ACK alone does not prove the experiment fixed the issue.

References: [NINA 3.3.0 handler](https://github.com/adafruit/nina-fw/blob/3.3.0/main/CommandHandler.cpp)
and [ESP-IDF 5.3.1 station sleep](https://docs.espressif.com/projects/esp-idf/en/v5.3.1/esp32c6/api-guides/wifi.html#station-sleep).

## SPI boundary follow-up

The radio-awake source `6109239` passed the complete physical VM acceptance,
including 50 ordered outputs and USB takeover. The three-worker asset audit
verified 60/147 assets, then timed out and lost native NINA identification with
error -5. The first failed asset was `/gp_wasm.data`; no complete graphical
load is claimed. A subsequent local GUI Connect click was recorded at
20:13:41 UTC, after SPI errors had already been observed; it failed at the
version query and cannot be treated as the cause of the earlier failures.

The next source closes an identified mutex gap: the diagnostic worker's final
CS release and BUSY sample must hold the same SPI mutex as network commands.
For read-only version identification only, capture the four MISO bytes clocked
during the request. An exact padded `EF 00 EE 00` stale error reply indicates
that transaction consumed an earlier error reply instead of submitting the
query. In that one case submit the non-secret version query once more before
reading its response. Do not retry writes, joins or credentials. Record the
number of recovered stale errors without logging frames or credential values.
This is a bounded phase-recovery experiment, not a claim that the sustained
transfer fault has been fixed.

## Bounded write-response follow-up

The single-client largest asset still failed on source `1c9b3cd`; a subsequent
read-only SPI phase recovery succeeded again and retained the same association.
The pinned Adafruit driver allows ten seconds for ready-low response preparation.
Increase only the response preparation budget for socket write command 0x44
from one to ten seconds; retain the one-second select ACK and other existing
bounds. Latch the first failing command, phase and error so later cleanup errors
cannot conceal the first fault. On a socket error, try at most two read-only
version probes under the same SPI lock to restore phase alignment. Return the
original socket error; never replay the failed write or a credential command.
The VM remains on its own thread. Full physical asset and focused VM acceptance
are still required after this change; the prior timeouts are retained.
