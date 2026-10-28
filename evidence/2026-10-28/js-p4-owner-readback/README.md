# P4 owner reconciliation and actual JavaScript readback

The isolated migration branch reconciles101 sealed owner source paths against
base9db5c3f, with zero merge conflicts, preserving2,259 unrelated tracked paths.
`dependencies/p4-native-owner.json` records raw and canonical-LF hashes, the
sealed archive SHA256, seven required SDK changes and the distinct installed
and uninstalled combined-image identities. The protected owner checkout and
COM5/COM12 were not accessed. SFC remains paused. GP and live assets are unchanged.

The owner reports fe01c3fb as installed. That is owner evidence, not a new
physical test here. The reconciled Zephyr firmware is **not compiled** here;
no SDK patch, flash, board connection, network/security change or publication
was performed. The independent combined candidate139ef2e0 is not installed.

The actual pinned JS compiler, connection and decompiler now restore the full
11-module P4 library:64 functions and189 block definitions, including native
palette specs and defaults. All64 functions recompile byte-identically after
wire padding. Verified local library sources are bounded and hash checked;
unknown modules retain the upstream fallback. Native namespaces remain target
specific. Legacy while compiles with correct condition/body/exit semantics;
the actual local Linux VM returned0,3,3,4 for four programs.

During project readback, only ping/version/variables/code queries are admitted.
Sync, extension requests, run and concurrent reads are blocked; cancellation
does not clear/reset/upload code. Ordinary connection setup retains upstream
control behavior and must not be described as non-disruptive.

Full unchanged validator: **532 tests passed**, zero skips/failures,289.818s.
The wrapper completed in297.874s and verified all2,371 source inputs against
both working tree and Linux replica after testing. New screenshots/evidence
were added afterward. The test environment used the existing verified local
x86-64 VM695fc61a, fictional robot services, and synthetic USB. No new Pi or
physical MicroDuck/P4 acceptance is claimed.

Graphical IAB fixture: full readback, cancellation and source reopen passed.
`graphical-readback.png` shows64 functions/189 definitions/3 scripts;
`graphical-cancel.png` records no clear/reset/upload/run during cancelled read;
`graphical-reopen.png` shows189 definitions and3 scripts after reopening.
The fixture-only handshake emits control frames, labelled separately from
the query-only read phase. No actual camera/audio data was acquired.

Remaining: coordinated physical P4 JS readback/SD/media acceptance, new Zephyr
build against the exact SDK patch set, trusted WSS commissioning and eventual
publication. The separate poll-budget SDK test was not run in this checkpoint.

Eleven additional native host suites passed with synthetic OS/filesystem/radio:
SD worker/I/O/readonly, saved boot, transport loss/latency, Wi-Fi latency policy,
HTTP diagnostics, SD wire, native storage bridge and hosted assets. The first
bridge attempt could not start because its pinned sender-source provenance was
absent; after verified source preparation, that test alone passed. See native
receipts and logs. Host sanitizer results do not constitute a Zephyr image build.
