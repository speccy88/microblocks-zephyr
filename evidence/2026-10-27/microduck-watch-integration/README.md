# Watch integration and commissioning preparation

Local branch: codex/pi5-watch-integration-20261027. Shared main and the active
P4 checkout are unchanged. No branch, release or Pages deployment was pushed.
The final read-only upstream recheck still reports published main
9db5c3ff9cf5287a7edcd6c1b0fb0cde3aa33226; unpublished P4 work was not read.

## Integrated watch

Merge 5272ce8c67d490c2040e920cf8b7d8df10a9b321 has parents
e5fd3d0a1d77f7024cade03136e9d6e859947cc5 and
62fb982268a9db7f749057842696ad3b74c6b85b. Its tested tree is
7c6ec8aad8ebdb500237b3ede5052d04d5660464. Product code at that merge exactly
matches preparation 62fb982. One integration-plan append conflict was resolved
by keeping the historical receipt and the follow-up scope; there were no
product-code conflicts and no unresolved index entries.

- [169 selected Node tests](node-169.txt): PASS, zero skips.
- [181 required Linux tests](linux-181.txt): PASS, zero skips, 249.159 seconds.
- [Seven-profile packaging](packaging.json): original GP JS/data hashes and
  connection flags match the earlier canonical-LF integration package. Current
  watch JS/HTML assets match the merged source bytes.
- [Machine-readable merge assessment](assessment.json) records the exact scope.

The original e5fd3d0 candidate and preparation 62fb982 branches remain unchanged.
The historical Pi bytecode/installer evidence is retained. No native C, UBL or
gateway implementation changed in this follow-up, so no fresh Pi bytecode run
is claimed. The ordinary/sanitizer native Pi evidence remains separately scoped.

## Next safe improvement

The following additive commit implements the
[filesystem-only preflight](../../../linux/microduck/PREFLIGHT.md) and the
[remaining-objectives ledger](../../../docs/MICRODUCK_REMAINING_OBJECTIVES.md).
The preflight reuses existing private-config and socket metadata rules, makes
no daemon connection/request/listener, changes no permissions/services and
does not generate configuration. API versions, connected peer UIDs, robot-ready
and mutation authorization remain unknown or ungranted.

- 22 focused Linux fixture tests: PASS, zero skips.
- 203 full repository tests after the addition: PASS, zero skips, 262.179 seconds.
- The actual Pi 5 stand-in ran the same hash-verified source with no config or
  runtime argument. It observed Linux/aarch64, 64-bit pointers, Python 3.13.5,
  glibc 2.41 and UID 1000, then correctly returned INCOMPLETE. No daemon/API,
  shipping-image or physical MicroDuck acceptance is inferred.
- The deployment wrapper created only fresh private project source/evidence
  files. The inspection created no cache/output files or system changes.
- [Preflight validation](../../../linux/microduck/tests/preflight-validation.json)
  binds current source, captures, fixtures and the real host-only observation.

The browser code and seven GP profiles are unchanged by the Python preflight;
the 169-node-test merge acceptance remains applicable. Its CI change only adds
the two checked preflight test classes. Hosted CI itself remains unexecuted.

## Remaining gates

Continuous motion/camera transports and broader command coverage remain missing
software. Verified confidential real commissioning, actual daemon/peer/caller
policy and physical sensor/action behavior remain separate gates. Graphical
Edge validation is still stopped by platform URL-policy checking; no retry or
alternate UI route is attempted. Publication/final release bindings, trusted WSS,
hosted CI, startup/reboot and coordination with the P4 owner's intended commit
are still required. The ledger distinguishes these categories explicitly.

No previous safety-denied action was retried. No new credential, security,
startup or reboot change was made. No approval is pending. All robot behavior
used by automated tests is simulated; the Pi host-only observation is real and
does not turn those mocks into MicroDuck evidence.
