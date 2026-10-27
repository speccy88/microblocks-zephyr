# Candidate release contract

This is a local preparation contract. Nothing here publishes, tags, pushes,
installs, changes services or marks the portal's release as available.

The candidate must bind the executable to the tested native AArch64 report,
the exact prepared source manifest, an immutable port commit, the pinned
upstream commit, dependency notices, and a self-contained corresponding-source
archive. Preparing a source archive from current files is insufficient unless
those native inputs match that port commit byte for byte and regenerate the
tested sources. A PASS report must describe a real AArch64 execution; mocks and
ELF-header fixtures cannot be substituted for it.

`tools/prepare_linux_arm64_release.py` must fail closed on a changed binary,
changed source, sanitized build, failed/non-AArch64 report, dirty native inputs,
unsafe source path or pre-existing output. Output contains binary/source
archives, installer scripts, evidence, a candidate manifest and SHA256SUMS.
All archives have fixed timestamps, ownership and ordering. Identical inputs
must reproduce identical artifacts. Output remains `available: false` and must
not contain a proposed public URL presented as a verified resource.

Acceptance tests tamper with each binding and verify deterministic artifacts.
An actual candidate uses the retained ordinary Pi binary and native source
manifest; it does not rerun the denied Pi numeric-specific suite. Building the
extracted source and repeating the safe ordinary core acceptance are separate
release checks. OS reboot, service startup, physical MicroDuck and publication
remain separate gates. See [integration plan](../../docs/LINUX_MICRODUCK_INTEGRATION_PLAN.md).
