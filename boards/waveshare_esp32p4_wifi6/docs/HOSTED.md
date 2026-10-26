# Native Zephyr station-hosted target

AP was canceled by Fred on 2026-10-26. Both USB-only and station-hosted
targets remain. They share SmallVM, camera/image/audio/Whistle, bounded NN
and inline media APIs. The hosted target uses C6 SDIO, DHCP on the approved
existing Wi-Fi, P4-flash editor assets and one VM WebSocket. It has no AP
interface, routing, Internet sharing, Bluetooth or cloud inference.

The station image and assets cross-built, passed complete flash-map/model
checks, and were flashed/hash-verified on COM5. Credentials from the one
local masked dialog were saved and verified by NVS readback. Station mode
and start completed, but WifiSetConfig request 284 received no reply and
SDIO returned -116. No DHCP address or HTTP/browser pass is claimed.
USB remains available. The encrypted handoff is retained for verification;
there is no new prompt, Windows network change or C6 firmware replacement.

## Build

Use the exact pins/SDK in START_HERE and apply the complete native patch
series with tools/apply_p4_zephyr_patches.py. Patch 0005 opts into compatible
post-init MAC reads and station-only start on explicit connection. Other
boards keep their original behavior. No foreign companion NVS is loaded.

Package with tools/package_p4_hosted.py --ide-source
build-artifacts/p4-sources/ide --output build-artifacts/p4-station-assets.

From west, build the P4 Zephyr app with:
- EXTRA_CONF_FILE=profiles/station.conf;profiles/neural.conf;profiles/whistle.conf
- EXTRA_DTC_OVERLAY_FILE=profiles/c6-sdio.overlay;profiles/hosted.overlay
- P4_TFLM_SOURCE and ZEPHYR_EXTRA_MODULES pointing to pinned TFLM
- P4_HOSTED_ASSETS_DIR pointing to the generated station assets
- P4_WHISTLE_MODEL and P4_WHISTLE_FIXTURE to the verified local inputs.

The old hosted.conf filename is a station-only compatibility alias.
Revision-guard zephyr.bin, then use the COM5-only application/assets flash
helpers under current authorization. The asset helper requires whole-layout
evidence. Neither helper touches COM12, C6 firmware or the settings region.

| Region | Begin | End, exclusive |
|---|---|---|
| Application and mapped model | 0x2000 | 0xfe0000 |
| Editor assets | 0xfe0000 | 0x1fe0000 |
| Approved station settings | 0x1fe0000 | 0x2000000 |

## Provisioning and transport

See NETWORK_STATION.md for the already-approved single DPAPI handoff.
tools/provision_p4_station.py --execute refuses non-station firmware before
decrypting. It sends credentials only to COM5, verifies NVS persistence under
key 0x42 and prints status only. There is no HTTP credential endpoint or
credential-read operation. Onboard NVS is not described as encrypted flash.

After DHCP succeeds, open the actual board address on the existing LAN.
Host/Origin must match its address. One controller owns programming; USB has
a refreshed activity lease and WebSocket is accepted only when that lease
expires. VM-thread parser resets retain RAM code. Programs do not currently
survive power loss. Plain LAN HTTP may lack browser WebSerial; keep the
separate HTTPS/localhost USB editor available.

Acceptance still needs station association/DHCP, reboot reconnection, actual
board-served asset hashes, genuine GP/WebSocket execution, controller
exclusion and cleanup. USB generated-image/NN/media/Whistle regressions are
separate evidence. No camera capture is repeated pending lighting confirmation.
