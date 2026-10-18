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
