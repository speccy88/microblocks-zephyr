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

## Shared mobile conflict review

Compared each complete iPhone-side file against the current main version:

- `iphone-transport.js`: the only difference is an optional bridge argument,
  defaulting to the original `nativeBridge`, passed to the same `NativePort`.
  Native connect/disconnect and receive semantics are preserved.
- `iphone-bootstrap.js`: native export/save, WebKit bridge, keyboard ownership,
  connection verification, busy/error handling and stock run/stop handlers are
  retained. Browser startup/capability branches are conditional on the browser
  profile; absence of that profile follows the native path. Other changes are
  the requested localization, palette controls and canvas/zoom fixes.
- `iphone-gestures.js`: compared in full; original touch ownership, block drops,
  interruptions, navigation bounds and preference saving are retained. Only
  continuous scale rendering and deferred text relayout change.
- `iphone.css`: compared in full; additions expose the palette grip and full
  names. Existing native safe areas, toolbar and touch controls are retained.

The main versions therefore preserve the distinct native behavior plus the
newer browser support. Both native and browser packaging/tests must verify this
resolution. An initial automatic approval rejected selecting these files before
the complete comparison; that refusal did not change the working tree.

## Paused integration and JavaScript direction

This section records the checkpoint before the user's explicit authorization
to reconcile the four files individually. Integration has since resumed; the
pause receipt is retained as historical evidence.

Following interruption, the merge is preserved with four unresolved mobile
files. No conflict-side selection, browser termination, push or publication was
performed by the denied operations. Local main is `acf9f08`; remote main and the
published site remain `a651529`. The iPhone merge parent is `e10a5ee`; SFC has
not been merged. The complete comparisons above are review evidence, not a
claim that the integration was completed or tested.

The user's latest direction is JavaScript v3 as the main editor, with legacy GP
separate. Verified the JS migration branch against main: both source manifests
pin the same official JavaScript engine `5564b1e42d6790360450ebf11c9eb33a1c6877f2`.
The actual commit subject and bundled `versions` report **IDE 2.5.12 / VM 421**;
the manifest calls this experimental migration staging on upstream `dev`.
This is evidence of a real pure-JavaScript editor, not certification of a
released official v3. The VM 421 version advertisement also does not upgrade
this project's pinned v417 runtime. The official announcement URL could not be
retrieved through the web tool during this check; no release claim relies on it.
The migration package adds Linux/MicroDuck compiler/transport compatibility and
legacy matrix-slot adapters around that engine. Its portal still opens
`editor/<board>/microblocks.html`, the old GP package path. The published main
instead has a separate `js-preview/` tree plus a pure-JS mobile editor. Merely
merging that branch therefore does not make desktop JavaScript the default.

The coherent next integration must make the JavaScript desktop entry explicit,
share the source pin and phone UI, retain real transport capability checks, and
keep frozen GP assets as legacy. GP-only SFC/custom P4 hooks cannot be represented
as JavaScript support until actually ported and tested. Keep their source and
evidence, document that boundary, and avoid replacing working JS/browser paths
with the older portal's assumptions. Do not promote a moving upstream preview
or silently change the VM pin.
