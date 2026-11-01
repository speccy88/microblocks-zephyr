# Final validation result

The final unchanged validator passed **474 tests, zero failures and zero skips**
in 216.361 seconds. `full-validation.json`, `full-validation.log` and
`validation-summary.json` bind that result to the 2053 hash-verified input files
in `validation-inputs.json`. Only evidence receipts/this result note were added
afterward; the tested source files stayed unchanged.

The focused Windows suite also passed all nine tests in 29.547 seconds using
temporary directories within this owned workspace. An earlier default-temp
attempt encountered sandbox-folder permission errors before packaging. No
security setting was changed or denied folder reused.

The initial full run completed 474 tests with four failures, all Windows Node
UNC parent-package lookup errors. Those results are retained in
`initial-unc-failure.log` and `.json`. A temporary-replica inspection found that
the prior Linux directory was already absent and stopped before any write or
test. The final run used the explicit, dependency-free CommonJS repository
metadata; all four previously failing cases and the entire suite passed. No
assertion, timeout or test exclusion was weakened.

The fixture `ProjectRoundtrip.ubp` intentionally retains the browser serializer's
final blank line. Its byte-for-byte identity is more useful than normalizing
that evidence artifact. Source/documentation whitespace checks pass; the raw
file's blank-line-at-EOF warning is the sole declared data-format exception.
See its exact SHA-256 in `file-and-gui-receipt.json`.

Native test executables were built/exercised in Linux. The production Pi VM and
Zephyr firmware were not rebuilt or connected. Browser Save was completed by
Fred, then the existing file was verified and reopened graphically without
another download. Automatic native-dialog/clipboard control remains unverified.
