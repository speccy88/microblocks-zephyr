# Main consolidation - 2026-11-01

The user requested one coherent development branch, `main`, retaining only
`gp` as a separate legacy line. Existing branch names are retained as historical
references; deleting them was not authorized. Future work belongs in `main`.

## Inventory before integration

| Remote branch | Head | Distinct work to preserve |
| --- | --- | --- |
| main | a651529d24c3f7ae10c6f9f5acd884c1dda57641 | Published mobile website and board asset packaging |
| codex/mobile-web-20261101 | a651529d24c3f7ae10c6f9f5acd884c1dda57641 | Already in main |
| development/fruit-jam | 91a4dad2766e36d2737754cadb164492661c6e6e | Already an ancestor of main |
| development/waveshare-rlcd | 8616af6f59256ef251622ac70ab802ea2d7b2b53 | Already an ancestor of main |
| codex/js-editor-migration-20261027 | 2c060b7f4e9153dd7213d9b7c2a479810577eb51 | JavaScript migration, Linux/Pi/MicroDuck source, tools and evidence; included in iPhone history |
| codex/iphone-wireless-20261101 | e10a5ee90bd2f5b04b6bc9245d806764c3df2483 | Native iPhone shell, Wi-Fi transport, editor packaging, simulator tests |
| codex/sfc-native-v4-20261101 | 19640cf765146cfa4a3025b744bcb069f239c0fb | Three SFC commits beyond shared historical ancestry: native blocks, configurable branches, compiler/runtime tests |
| gp | 3905dc1808f65dad65d5a37b05990f74cc4fca83 | Legacy branch, explicitly excluded from branch integration and updates |

The JS/iPhone and SFC lines share older ancestry with `gp`; preserving their
dependencies retains that shared source history. This does not advance or merge
the legacy branch itself. The frozen published GP assets remain pinned.

Two linked local worktrees existed: the clean iPhone worktree at `e10a5ee`, and
the mobile web worktree with the ongoing language, palette and pinch fixes. A
local `codex/mobile-language-20261101` reference had no unique commits and was
never pushed. All ongoing edits were carried into the local checkout of the
existing remote `main`. No worktree, branch, commit or uncommitted edit was deleted.

## Integration contract

Preserve all distinct source and evidence, reconciling shared mobile files in
favor of the newer browser/native implementation. Keep one shared touch UI for
the native app, Pages and optional board assets. Native transport and browser
transport must retain separate explicit capability checks. Keep legacy GP
deployment pins and board safety rules intact. SFC remains its documented native
GP extension and disconnected preview; this consolidation does not pretend it
has been ported to the JavaScript editor or validated on hardware.

Review conflict resolutions and overlapping workflows. Run the full validator,
actual touch/browser regressions, native SmallVM protocol checks, SFC compiler
and runtime checks, and iPhone Simulator CI. Confirm every non-GP remote head is
an ancestor of final main. Push main without force, verify exact-head CI and
the supported Pages deployment, then inspect public assets and mobile behavior.
No flashing, hardware deployment or security configuration changes are included.
