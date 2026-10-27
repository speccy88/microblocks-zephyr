# GP preservation and JavaScript editor staging checkpoint

Local `gp` and `codex/js-editor-migration-20261027` refs were created and
verified at `3905dc1808f65dad65d5a37b05990f74cc4fca83` before this slice.
The former retains the complete known clone history; the latter holds the
new staging work. Local main and remote main remain unchanged. Independent
P4/SFC seals are inventoried, preserved and unmerged; SFC work was paused by
the user. The protected P4 checkout, boards and serial ports were not accessed.

## Final verified behavior

- Official JS source pinned independently to Codeberg
  `5564b1e42d6790360450ebf11c9eb33a1c6877f2`; 550 verified blobs. Engine files
  stay unchanged. Existing GP and SmallVM pins and binaries stay unchanged.
- Five focused Python checks cover path/ref refusal, pin separation, source
  manifest tampering, deterministic packaging and the actual upstream JS
  compiler/connection contract. Ten JavaScript checks cover the real compiler,
  isolated primitive maps, unknown-set refusal, transport readiness, bounds,
  ordering, backpressure and shutdown. No mock interpreter is used.
- Final `tools/validate.py`: **470 tests, zero failures or skips**. Executed
  in a byte-identical Linux-filesystem copy with the existing verified local
  sanitizer VM and pinned runtime source. WSL has no Node installation; the
  new JS check uses the existing Windows Node 24.19.0 through path translation.
  No test assertion, deadline or exclusion was changed. Earlier full pass is
  separate from the final readiness/CRC revision.
- Real Raspberry Pi 5 / AArch64 / Node 22.22.2: actual pinned compiler and code
  manager upload through the adapter and unchanged verified loopback bridge
  to the real SmallVM v417. Stock CRC acknowledgement passes. Arithmetic
  returns **12** and `[microduck:configured]` returns **false** with no gateway.
  No robot command, simulated robot reading or physical movement was sent.
- All **558 served package files** and four probe source inputs match the
  final local files byte-for-byte by SHA-256. The private test VM and bridge
  stopped. Existing older editor sessions and Pi services remain untouched.

## Evidence and reproduction

`pi-probe.json` contains the final actual Pi results, bytecode CRCs/digests,
native binary identity and stopped-child receipt. `pi-input-hashes.json`
records every served file and the four probe inputs. `static-package.json`
identifies the local deterministic static candidate archive; it is not a VM
package, published release or deployable MicroDuck service.

`full-validation.json` and `full-validation.txt` describe the final 470-test
run. The exact source pin and all upstream blob hashes are committed in
`dependencies/editor-js.json`. The build's per-file output manifest is inside
the candidate package. `source-checksums.json` binds changed implementation
and specification files to this tested checkpoint.

See [migration instructions](../../../docs/JS_EDITOR_MIGRATION.md) for the
offline package command, candidate-based upstream sync and integration gates.
Use `tests/js_editor_pi_probe.py` with a verified existing binary, bridge
Python environment and private root for bounded foreground reproduction.
It creates no services, credentials, remote listener or networking settings.

## Failures retained and limitations

`earlier-attempts.json` preserves four completed failed Pi attempts: wrong
virtual-environment interpreter resolution, missing fixed bridge entry file,
the newly handled readiness control marker, and missing probe upload padding.
The final probe uses the actual upstream code-manager CRC path. Every failed
attempt stopped its own children before a corrected attempt was started.

No browser graphical acceptance, physical MicroDuck validation, custom GP
slot/API migration, P4 media acceptance, typed-library JS import, SFC merge,
security/network change or release is claimed. No pending approval or stuck
process blocks this checkpoint. The remaining consolidation gate is the
independent P4 owner's latest checkpoint, followed by an isolated merge and
graphical/custom-feature acceptance before changing shared main.
