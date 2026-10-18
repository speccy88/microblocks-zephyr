# Explicit AirLift firmware restoration

The user reported earlier coprocessor experiments and explicitly requested
restoring WiFiNINA on the Fruit Jam ESP32-C6, providing the
[official update guide](https://learn.adafruit.com/adafruit-fruit-jam/upgrading-airlift-firmware).
This authorizes the requested coprocessor update and supersedes the earlier
identification-only restriction. The prior SPI timeouts remain historical
evidence; they do not establish which firmware was previously installed.

Use the official `NINA_ADAFRUIT-fruitjam_c6-3.3.0.bin` release, not the ESP32
variant. Verify its release SHA256 before programming at offset zero.
Preserve a complete private backup of the current RP2350 flash, the MicroBlocks
program CRCs, and the ESP32-C6 flash before writing the coprocessor. Flash dumps
may contain private configuration and must remain outside Git and public logs.

The official serial passthrough temporarily replaces the RP2350 application.
Extract only its secure ARM application blocks for SWD. The downloaded UF2 also
contains an absolute-family preamble at `0x10ffff00`; do not program that block
through SWD because the final flash sector belongs to MicroBlocks storage.
The extracted application occupies `0x10000000..0x100170ff`, with affected flash
sectors ending at `0x10017fff`. Preserve those exact sectors for restoration.

Use the positively identified Fruit Jam USB port at 115200, `--chip esp32c6`,
and `--before no-reset`, as specified by the guide's passthrough method. Check
chip identity, flash size and security status before reading or writing. Do not
change eFuses, override security checks, or erase the entire device. If flash
backup is unavailable, report the reason before proceeding with an update.

Acceptance requires a verified firmware write, restoration and verification of
the original MicroBlocks application sectors, unchanged VM storage and code
CRCs, working USB arithmetic/reconnect, and repeatable native SPI version/MAC/
status queries. A successful firmware upload alone does not prove Wi-Fi
association, DHCP, socket service or a standalone IDE. No credentials are read
or sent as part of this restoration. No SHT4x or other board is accessed.

Restoration and physical protocol checks passed. Complete private backups were
made for both chips: 16 MiB RP2350 and 4 MiB ESP32-C6. The official 1,626,112-byte
firmware matches release SHA256
`be9e75c08a4409b6721167cc4c8200180eb4322c89b6848b8fa2573bc77e53f6`.
Writing and separate flash verification succeeded. The original 98,304 bytes
of affected RP2350 sectors were restored and verified; the full 256 KiB VM
store was byte-identical before the subsequent diagnostic uploads. The saved
program CRC `0:297d191b`, arithmetic 12 and USB reconnect passed.

Three native SPI identification cycles each completed all three queries with
version `3.3.0` and raw connection status 254. No association or DHCP check was
performed. The six MAC bytes match the UART identity, but the compiled native
formatter reverses their order: its text is `58:a3:f5:c5:e6:58`; the canonical
address is `58:e6:c5:f5:a3:58`. NINA 3.3.0 `getMACaddr` copies bytes directly;
the next coordinated native build should preserve `data[0]..data[5]` when
formatting this firmware's reply. The currently installed source and its build
hashes remain unchanged, with this presentation issue recorded explicitly.

On Windows, esptool 5.6.0 initializes DTR false, while the official TinyUSB
passthrough needs DTR asserted. Passing a positively identified, pre-opened
serial object with DTR true into esptool's official API enabled communication.
The C6 entered ROM download using GPIO23 BOOT9 low and an explicit GPIO22 reset
pulse. No eFuses were changed. The earlier failed SPI evidence is retained.

See [restoration evidence](../evidence/2026-10-18/fruit-jam/physical-airlift-nina-restoration.json),
[three native identification cycles](../evidence/2026-10-18/fruit-jam/physical-airlift-after-nina-restore.json)
and [official file provenance](../evidence/2026-10-18/fruit-jam/airlift-restoration-provenance.json).
The `coprocessor_flashed:false` field in an individual identification request
means that query did not flash; the separate restoration record reports the
preceding coprocessor update as true.
