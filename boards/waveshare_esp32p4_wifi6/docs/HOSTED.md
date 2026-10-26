# Native Zephyr board-hosted target

This profile shares the USB target's SmallVM, camera/image/audio handles,
Whistle worker and inline media protocol. It adds the native Zephyr C6 SDIO
driver, an AP-only radio configuration, HTTP assets in P4 flash and one
binary VM WebSocket. The default USB image does not enable the network stack.

Current implementation is compiled, partition-checked and flashed. Safe
initialization and USB/Whistle regression pass. AP configuration currently
fails with C6 SDHC timeouts after its mode response; HTTP/browser acceptance
is blocked, not passed. See `NETWORK_PLAN.md` for evidence and limits.

## Reproducible build

Use the exact Zephyr/HAL pins and SDK listed in `START_HERE.md`. Apply the
repository's pinned SDK patches using `tools/apply_p4_zephyr_patches.py`.
The AP-only patch is opt-in: other board ports retain their existing behavior.
It initializes C6 Wi-Fi without starting or associating a station. Compatible
MAC queries occur after Wi-Fi initialization; addresses are never diagnostics.

Package the verified editor source:

```sh
python tools/package_p4_hosted.py \
  --ide-source build-artifacts/p4-sources/ide \
  --output build-artifacts/p4-hosted-assets
```

From the configured west workspace, with `REPO`, `MODEL` and `FIXTURE` set to
local paths (the model and fixture are not repository artifacts):

```sh
west build -b esp32p4_wifi6/esp32p4/hpcore -d build-p4-hosted \
  -s "$REPO/boards/waveshare_esp32p4_wifi6/zephyr" -- \
  '-DEXTRA_CONF_FILE=profiles/hosted.conf;profiles/whistle.conf' \
  '-DEXTRA_DTC_OVERLAY_FILE=profiles/c6-sdio.overlay;profiles/hosted.overlay' \
  -DP4_WHISTLE_MODEL="$MODEL" -DP4_WHISTLE_FIXTURE="$FIXTURE"
```

Both model and total-layout checks run after linking. Revision-guard the
actual `zephyr.bin` with `tools/p4_image_guard.py` before authorized flashing.
Run `tools/check_p4_hosted_layout.py` on the guarded image, actual ELF,
generated DTS and assets, saving its JSON with `--evidence`.

## Fixed flash layout and safe provisioning

| Region | Begin | End, exclusive |
|---|---|---|
| Application and mapped Whistle model | `0x2000` | `0xfe0000` |
| Editor assets | `0xfe0000` | `0x1fe0000` |
| AP settings | `0x1fe0000` | `0x2000000` |

The checker verifies all three intervals, actual binary sizes, model section
permissions, physical model location, SHA-256 and a single model copy.
The model is read-only mapped flash; it is not copied into PSRAM.
Asset blobs include lengths, CRC32 and SHA-256. Each deterministic gzip stream
has its own original-file hash in `assets-manifest.json`. The native server
streams 2 KB chunks and sends an explicit gzip header when applicable.

Use the COM5-only helpers `flash_p4_zephyr.py` and `flash_p4_assets.py`, with
current explicit P4 flashing authorization. The latter requires the complete
layout evidence and writes only the asset interval. Neither backs up firmware,
touches COM12, flashes C6 or writes AP settings.

After assets and driver pass safe initialization, the approved AP provisioning
helper creates a unique 16-character key in an ignored local `secrets/` file.
It transmits the key only through USB message 214, then stores it in the P4
settings partition for reuse. The same key can be reprovisioned idempotently;
an accidental different key is rejected. There is no HTTP credential endpoint
or key-read operation. Do not print or publish the private file. Provisioning
requires the separate AP authorization described in `NETWORK_PLAN.md`.

```powershell
python tools/test_p4_hosted_usb.py --execute --evidence <safe-init.json>
python tools/provision_p4_ap.py --execute --private-file secrets/p4-ap-password.txt --evidence <ap-start.json>
python tools/test_p4_hosted_usb.py --execute --require-ap --whistle --evidence <regression.json>
```

## Transport and acceptance

The approved AP is `MicroBlocks-P4`, WPA2-PSK, channel 6, `192.168.4.1/24`,
with two DHCP clients from `.10`. There is no station association, routing,
Internet sharing, DNS interception, captive portal or Windows firewall change.
Saved valid credentials start the same AP after reboot.

Open `http://192.168.4.1/` only after explicitly joining that network. Windows
network association is a separate action; the helpers do not perform it.
The board serves all GP assets locally and accepts `/ws/vm` only with a
matching Host and Origin. One controller owns programming at a time. USB uses
an activity lease, refreshed by normal IDE pings; WebSocket takes ownership
only after the USB lease expires. Parser/session resets occur on the VM
thread and preserve the RAM program. CPU-only WS queues use 16 KB of PSRAM;
UART ISR and DMA buffers remain internal.

Keep the separate HTTPS/localhost USB editor available. HTTP pages on a LAN
address may lack browser WebSerial access; that does not remove physical USB
support in the hosted firmware. Programs currently remain in RAM across
connection changes, not across power loss.

Physical acceptance requires verified AP radio state, DHCP lease, board-served
asset hashes, actual GP startup, binary WebSocket programming, generated image
transform/preview, bounded audio or fixture playback, Whistle regression,
controller exclusion and reconnect cleanup. Camera scene-content retesting
remains on hold pending Fred's lighting confirmation. AP startup alone does
not satisfy the complete browser gate.
