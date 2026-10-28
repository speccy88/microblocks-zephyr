# P4 full-profile source build from available licensed inputs

2026-10-28: **cross-build PASS**, never flashed or run on a board. This is a new
isolated build, not a reproduction of the installed owner image. The protected
P4 checkouts, COM ports, existing SDK, live site, GP branch and paused SFC remain
untouched. Product P4 and build-tool trees are byte-identical to 9ba2f25.

## What compiled

Native Zephyr P4 camera/audio, station-hosted transport, bounded neural runtime,
Whistle, Okay Nabu KWS, SD storage, saved boot, Wi-Fi retry/latency and compatibility
diagnostic profiles compile together. All 790 Ninja steps finish successfully in
1064.719s including setup. The default camera/audio source profile is retained;
the private recorded Whistle fixture is deliberately omitted.

Four post-build checks pass: VM task/native-stack placement, the isolated RPC
allocator pool, whole flash/model/assets layout, and Whistle image placement.
All **seven** patched Zephyr source files match the sealed owner-export hashes.
The reviewed patch series was applied only to the new clone.

| Output | Bytes | SHA256 |
|---|---:|---|
| Raw application |15,312,480|`1d01461c5efb7c80584f8360fd22e2d84b486d66c0133324fa759212dddd86e0`|
| ELF |29,962,240|`2bf98347eabd8a42bc9c62f2324e88e2adaf7cbed19582e28bc1b494b9e44781`|
| Regenerated GP assets, 165 files |3,571,877|`8b4af32a80ccddd02e4fd1cc4404c590c0d8a7530a5ff64aeffa4efe950fd02e`|

The application ends at 0xe9c660 before the 0xfe0000 asset boundary. Assets end at
0x13480a5 before settings at 0x1fe0000. The 14,515,887-byte Whistle model remains
mapped in flash, not copied to PSRAM. VM task data use 5240 bytes in external
memory; main 16 KiB, Whistle 64 KiB and HTTP 6 KiB native stacks are internal.
These layout checks do not establish boot, runtime memory margins or performance.
Linker SRAM use is 382,880 bytes of 384 KiB (97.37%), leaving a 10,336-byte libc
arena. Runtime high-water marks and margins require separate hardware testing.

## Legitimately available inputs

- Zephyr `a915b2f12675b48b16d56653ea145dcd8f20cbbf`, Espressif HAL
  `b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`, and the reviewed native patch series.
- Project-local official Zephyr SDK **1.0.0 / GNU 14.3.0**, with the already installed
  esptool 5.6.0 selected only in this build process's PATH. No original SDK edits.
- SmallVM v417 sources from the existing exact Git pin; TFLM
  `43b2a106a391dd8a099ac47f2ae858630a397264` read from the existing optional module.
- The 22 Apache-2.0 Whistle source files were fetched and hash-checked against
  `dependencies/p4-whistle.json`. The existing licensed D4 model, outside the
  protected P4 checkouts, matches its required SHA256 exactly.
- The official pinned Okay Nabu model and license were retrieved from
  [the upstream repository](https://github.com/esphome/micro-wake-word-models/tree/40ff33f57f8fc6ad71a75ef085abbf742495b225).
  The 60,264-byte model matches
  `0689abe1912a95a3318a0d8cb2e67bad0cbcfe3e24dd6e050c75debddfb6f891`.
- Current GP editor assets were regenerated from the existing verified upstream
  cache. No fixture recording, credentials, firmware dump or model weight was
  added to Git. The generated configuration has no nonempty SSID/PSK/password value.

The first isolated attempt reached TFLM compilation but hit its 600-second build
deadline. Its completed objects disappeared when WSL stopped; the attempted
resume detected the missing build directory and executed no compiler. A fresh
build in the dedicated persistent directory
`/home/fred/microblocks-js-p4-build-5ng6uxl3` then completed. This was an environment
and build-duration issue, not a compiler failure or an approval denial. Raw logs
preserve both attempts. No pre-existing VM or hardware process was killed or reused.

## Remaining boundaries

The installed owner application's SHA is different. Exact reproduction would need
its private audio fixture, retained asset blob and owner-reported SDK 1.0.1.
Those inputs were neither invented nor substituted. A clean-machine public build
also needs a reviewed acquisition/derivation recipe or immutable artifact for the
four-decoder-layer model: this build uses a legitimately available existing local
file matching the pin, not an invented public download URL for that derived file.
The [pinned upstream model source](https://huggingface.co/Cactus-Compute/whistle/tree/741118687e1f008f06d1351a402a731274789790)
does not by itself document that local D4 derivation.

The raw output has not received the release revision guard, been installed,
booted, or tested with physical P4 USB/WSS, camera, PCM, inference, KWS, SD or
networking. No silicon compatibility or graphical hardware claim follows from
compilation. Physical owner reconciliation and approved release/deployment remain
separate. The hardware image and models stay in ignored build storage.

[Build command and receipt](build-receipt.json),
[post-build checks](post-build-checks.json),
[owner SDK comparison](owner-sdk-comparison.json),
[clean pinned TFLM/HAL identities](optional-source-pins.json),
[input provenance](public-input-provenance.json),
[verification](verification.json), and [raw logs/configuration](raw-build-logs.zip).
The previous **541-test / zero-skip** validation is recorded in
[the Pi/editor checkpoint](../js-pi-readback/README.md); this evidence-only follow-up
changes no product or test source.
