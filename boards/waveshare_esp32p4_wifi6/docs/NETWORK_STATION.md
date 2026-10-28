# Station mode replaces the AP target

**2026-10-27 local follow-up:** the historical control-path blocker below was
resolved without replacing C6 firmware. Real association, DHCP, served-asset
hashes, VM programming, RAM transfers and the actual board-hosted editor pass.
The bounded SD file manager is installed and tested. The installed opt-in
saved-boot profile reconnects after tested warm resets with no manual station
command. The later bounded recovery profile passes one controlled local loss
with resumed HTTP, read-only SD and VM checks. Initial TCP intermittence and
full power removal remain limits; see [recovery evidence](../../../docs/P4_WIFI_LOSS_RETRY.md).
See [current validation](NETWORK_LIVE_VALIDATION.md) and the
[bounded boot contract](../../../docs/P4_SAVED_WIFI_BOOT.md).

Fred revoked AP work on 2026-10-26 at 01:25 UTC and requested connection to
his existing Wi-Fi. The AP was confirmed inactive by USB status immediately
after that instruction. No new AP attempts are authorized or performed.
Historical AP source/evidence is retained; new builds reject its provisioning
and do not load its saved key or start that mode.

Retain the separate USB image and genuine board-hosted editor. The new hosted
target must use native Zephyr C6 SDIO station control and DHCP, serve assets
from P4 flash, accept same-origin VM WebSockets and preserve single-controller
ownership. The current native station path passes with the unchanged factory
C6 after the synthetic response-540 compatibility check. The AP configuration
failure is historical evidence, not proof station mode works or cannot work.

## Approved credential handoff

Confirm the intended SSID through one local Windows dialog with a masked
password box. Do not put the password in chat, tool output, process arguments,
environment variables, logs, Git, browser storage or Library. Never extract a
stored Windows Wi-Fi password, infer the destination, or reuse the AP key.
The C6 requires an available compatible 2.4 GHz network.

Fred explicitly approved saving station credentials for reboot reconnection
on 2026-10-26 at 01:38 UTC. The single masked Windows dialog was submitted at
01:43 UTC. Its status-only receipt confirms presence and approval; it contains
neither SSID nor password. The handoff is CurrentUser-DPAPI encrypted in the
ignored secrets directory. Do not reopen the dialog or delete this handoff
before verified provisioning. The USB helper checks station firmware before
decrypting; plaintext exists only in its process memory and the approved
board/companion path. No command arguments, environment variables, logs or
plaintext disk file carry credentials. The board uses distinct station NVS
key 0x42, with write/readback verification; the old AP key 0x41 is ignored.
Onboard NVS persistence is not claimed to be encrypted flash storage.

`tools/provision_p4_station.py --execute` consumes only that existing handoff
and named COM5 destination. It never creates a new prompt or falls back to AP.
Only USB can provision; no network credential read/write endpoint exists.
Receipts contain status only. Retain the encrypted handoff until persistence,
association and reboot behavior are verified, then remove it as documented.

## Network behavior and remaining implementation

The station-only profile now cross-builds with camera/audio/Whistle and NN.
Its complete application/model/assets/NVS layout check passes. Physical
association, DHCP and board-hosted programming are separate acceptance gates.
The first physical attempt saved/readback-verified the approved credentials,
started station mode, then failed at WifiSetConfig request 284 with no reply
and SDHC -116. USB remained responsive. This is a control-path failure; no
DHCP/HTTP pass, wrong-password diagnosis or C6 firmware requirement is inferred.
See p4-station-control.json and the successful combined-image NN/media/Whistle
regressions. The installed diagnostic label mentioning AP is stale descriptive
text; the canonical network status and station-only Kconfig show AP disabled.
Board association is requested; Windows association/firewall/security changes
remain outside scope. DHCP determines the board address; `192.168.4.1` is no
longer the target. The hosted adapter now derives `/ws/vm` from the editor's
own HTTP/HTTPS origin, preserving its host and port and selecting ws/wss.
It ignores an arbitrary endpoint field for this profile; remote public-portal
connections still require wss. Native Host/Origin checks use the actual DHCP
address and reject other origins. Offline tests execute the generated adapter
with fake providers for station addresses, HTTPS, USB selection, loopback and
rejected cross-origin/credential/path variants. This is a browser policy pass,
not physical association or a board-served programming pass.
No routing, captive portal, Internet sharing,
cloud inference or microphone listener is implied. The editor/programming
service is available to peers on that LAN; anyone able to use it can invoke
the board's camera/audio primitives. Do not claim a board-hosted pass until
DHCP, actual served assets and genuine GP programming have been tested.
