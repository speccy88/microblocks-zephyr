# JavaScript editor migration: first staging slice

The user chose to preserve the GP editor on `gp` and develop the JavaScript
editor toward main. This slice is isolated on
`codex/js-editor-migration-20261027`; it does not replace or publish main.
The local `gp` preservation ref starts at
`3905dc1808f65dad65d5a37b05990f74cc4fca83`. Later P4/SFC owner checkpoints
must be integrated separately before claiming all GP work consolidated.

## Behavior and acceptance

- Pin the official Codeberg JavaScript editor independently of the existing
  GP 2.5.8 assets and SmallVM v417. Keep both runtime and GP pins unchanged.
- Package only verified Git blobs. Resolve a fixed list of upstream asset
  aliases from the Git tree, never filesystem symlinks. Keep upstream engine
  files byte-identical; put local compatibility code in a separate file.
- Add a user-initiated, bounded, same-origin loopback WebSocket port for the
  existing verified Linux bridge. No discovery, remote listener, credentials,
  automatic program start, firmware flashing or service installation.
- Register `linux` as set 3 and `microduck` as set 22 on a private compiler map.
  Refuse unknown named primitive sets instead of silently encoding set zero.
- Test the actual pinned compiler and connection sources with the adapter.
  Demonstrate arithmetic and a harmless MicroDuck status reading on the real
  Pi VM through the bridge when available. Headless JavaScript execution is
  not graphical editor acceptance or physical robot validation.
- Include reproducible source/provenance, license notices and an explicit
  candidate-update workflow. Upstream updates must not move a manifest or
  shared branch implicitly. Offline checks must detect changed/missing blobs.

## Scope and integration gates

This is an experimental Linux/MicroDuck editor profile. P4 custom media slots,
UNO Q matrix slots, GP portal APIs, SFC UI integration, custom restore behavior,
browser graphical acceptance, deployment/autostart and release remain separate
gates. No generic P4 compatibility is implied by a stock project importing.
Keep all sealed P4/SFC checkpoints and active owner work; coordinate before
merging or publishing. Do not upgrade the VM to follow editor development.
