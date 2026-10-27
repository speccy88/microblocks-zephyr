# Published upstream integration rehearsal, 2026-10-27

The separate integration branch passes against the published upstream checked
on this date. It has not been pushed, and shared main has not been merged.
The active P4 checkout, its board, COM5 and COM12 were not accessed. This result
does not include the P4 owner's unpublished work.

## Exact Git state

- Remote: https://github.com/speccy88/microblocks-zephyr.git
- Fetched origin/main: 9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226, unchanged at the
  second fetch before the local merge.
- Preparation branch: codex/pi5-microduck-preparation at
  961b4401a4cd81add9d56d929ebcc4a2afb1d446, left clean and unchanged.
- Separate worktree: microblocks-zephyr-integration-20261027.
- Integration branch: codex/pi5-upstream-integration-20261027.
- Local merge: acd315cd711b80e317d0651c4d43f836fba3dbdc. Its first parent is the
  fetched main above; its second parent is the preparation tip above.
- Tested tree: 5cb67edc7c0dcb5a5c0caf1da9309561668d9976, exactly identical to the
  preparation tip's tree. The following evidence commit changes documentation
  and receipts only.

The remote is an ancestor of preparation: zero upstream-only commits and twelve
preparation-only commits. A no-fast-forward merge in the new worktree produced
zero conflicts and zero unmerged index entries. There are 149 new paths, seven
modified preexisting paths and no deletions. The seven shared paths are README.md,
tools/package_pages.py and web/portal/{index.html,portal-adapter.js,portal-core.js,
portal.css,portal.js}. These remain the main coordination points for future P4
work; a conflict-free merge against today's remote cannot predict its changes.

## Fresh validation

| Check | Result | Evidence |
|---|---|---|
| Required Linux repository validator | 181 tests, zero skips, PASS | [Full output](linux-validator.txt) |
| Selected Linux/MicroDuck/portal Node suites | 139 tests, zero skips, PASS | [Full output](node-selected.txt) |
| Additional Pages/P4 mock regressions | 26 other tests plus four P4 transport tests, PASS | [Initial output](pages-initial-attempt.txt), [runtime recovery](p4-transport-recovery.txt) |
| Actual Pi ordinary SmallVM | 50 bytecode executions and core/persistence suite, PASS | [Native report](pi-ordinary.json) |
| Actual Pi ASan/UBSan SmallVM | 20 bytecode executions and core/persistence suite, PASS | [Native report](pi-sanitizers.json) |
| Actual Pi MicroDuck adapter, ordinary | Ten original adapter tests and eight typed-reading tests, zero skips, PASS | [Report](pi-microduck-ordinary.json), [output](pi-microduck-ordinary.txt) |
| Actual Pi MicroDuck adapter, ASan/UBSan | Same eighteen tests, zero skips, PASS | [Report](pi-microduck-sanitizers.json), [output](pi-microduck-sanitizers.txt) |
| Fresh published-base and integration portal packages | Original five profiles retain exact GP JS/data hashes and connection flags; seven-profile integration package builds | [Comparison](packaging.json), [base manifest](published-base-package.json), [integration manifest](integration-package.json) |

The first Pages regression command could not load its P4 fixture because the
default Windows Python launcher returned spawnSync python EACCES. Its other 26
tests passed. Setting the test's existing PYTHON environment override to the
bundled Python executable made all four P4 transport tests pass. No source,
execution policy or security setting was changed. The initial failure is retained.
Captured Windows text logs use LF in Git; [capture conversions](capture-conversions.json)
record the original and retained hashes. Only CRLF was converted to LF, with other
console glyphs retained as captured. Raw logs remain under local build-artifacts.

The Linux validator ran under Ubuntu-26.04 WSL with the existing bridge virtual
environment. Node ran using the bundled Node runtime. The command sets are:

~~~sh
python tools/validate.py
node --test tests/portal-core.test.cjs tests/linux-install-command.test.cjs tests/linux-adapter.test.cjs tests/linux-transport.test.cjs tests/test_microduck_protocol.cjs tests/test_microduck_panel.cjs tests/test_microduck_simulation.cjs tests/test_microduck_simulation_panel.cjs tests/test_microduck_console_core.cjs tests/test_microduck_console_fixture.cjs tests/test_microduck_console_panel.cjs
node --test tests/portal-adapter-guard.test.cjs tests/p4-transport.test.cjs tests/p4_media_core.test.js tests/p4_nn_core.test.js tests/device_files.test.js
python tools/package_pages.py --ide-source build-artifacts/ide-source --output build-artifacts/pages-integration
python tools/run_pi5_smallvm.py --upstream ../smallvm-linux-upstream --target rpi5 --output build-artifacts/pi5-integration --repeat 50
python tools/run_pi5_smallvm.py --upstream ../smallvm-linux-upstream --target rpi5 --output build-artifacts/pi5-integration-sanitizers --sanitize --repeat 20
python tools/run_pi5_microduck.py --native-evidence PATH_TO_EACH_FRESH_REPORT --target rpi5
~~~

The base package was generated from a Git archive of exactly 9db5c3f using the
same verified public GP asset cache. No P4 working files were read. The Node
regressions use fake transports/DOM; they do not use serial ports or a real MCU.
The Pi tests execute real AArch64 bytecode and the native C adapter/gateway, with
private simulated robot daemons. No actual MicroDuck command or secret was sent.
Both MicroDuck reports explicitly record numeric_acceptance_suite_executed=false.

## Source bytes and historical artifacts

This fresh worktree uses core.autocrlf=false and canonical Git LF bytes. The older
Windows preparation worktree has 1,087 checkout byte differences, all verified
as exact LF-to-CRLF conversions; its committed tree is the same tested tree.
Among prepared native inputs, only common/json/json_config.h changes raw hash.
The fresh [ordinary manifest](prepared-source-ordinary.json) and
[sanitizer manifest](prepared-source-sanitizers.json) bind the actual LF input.
The assessment records both hashes and the exact conversion check.

The newly built ordinary binary is byte-identical to historical typed evidence:
0b5c2b269fb4e12b7ef8422c2961e2b1e09094de287796a297a93620ea43136f.
The sanitizer binary is also byte-identical:
49360b487b7d36267848622845b12f1835173b7aeaaee170ee137a5af6eb811e.
Both were nevertheless rebuilt and executed from the fresh source manifest.

Waveshare, P2 and P4 package hashes differ from older CRLF-built artifacts because
their unchanged embedded source payloads used CRLF. The canonical-LF packages of
all five original boards match the canonical-LF published base exactly. Pi and
MicroDuck code hashes also match the earlier tested package. Console JS assets
match source bytes and all its local references resolve. Release availability
remains false; its VM connection flag does not imply physical robot acceptance.

## Integration hold and remaining boundaries

1. Obtain the P4 owner's intended committed integration point, fetch it into a
   separate checkout and repeat the merge and affected regressions if it advances.
   Preserve the shared packager/portal behavior rather than replacing whole files.
2. Regenerate final candidate provenance, corresponding source, checksums and
   installer bindings from that final coordinated commit. Existing older release
   candidates remain historical and must not be paired with the new library.
3. Hosted CI, production Pages, graphical protected-console acceptance, actual
   reboot/startup and physical MicroDuck tests remain unverified. This rehearsal
   neither publishes nor claims them. No existing Pi services were changed.

No approval request is currently pending. The previously denied extra Pi numeric
acceptance action targeting rpi5 was not retried; its safety denial remains
isolated. The optional native-design/library-contract subagent review was flagged
for possible cybersecurity risk and remains incomplete, without retry. The prior
Edge window18679338 control request timed out awaiting app approval and was not
retried or bypassed. These do not turn the completed independent tests into
hardware, graphical or review acceptance.

[Machine-readable assessment](assessment.json) records the exact scope.
[Evidence hashes](evidence-sha256.json) bind this directory's retained receipts.
