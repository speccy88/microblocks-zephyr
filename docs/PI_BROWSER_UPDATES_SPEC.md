# Browser SmallVM updates

The two supplied phone captures concern the native VM, not editor assets: the
editor compares Pi v417 to upstream v421, then routes installation to desktop
USB. The validated Linux ARM64 port remains v417. Do not offer an unvalidated
v421 ARM64 upgrade or send a board flash image to the Pi process.

Provide a Pi-only update panel and compatible-version policy. A browser uploads
an existing native ARM64 release archive and its independently supplied SHA-256
over the same-origin WebSocket. Show bounded upload progress, validate archive,
ELF, manifest and pinned VM/source, then present version/digest for review.

Installation requires an explicit confirmed version and digest and a managed
runtime with installation enabled. Default is review-only until a native update
is authorized. Reuse the guarded native installer without its service option.
Stop only the supervisor's own VM, snapshot its persisted program, atomically
select the candidate, and restart that same managed service. Preserve the old
binary and config. Failed candidate startup restores the old selection/program
on the next service start. All apply/rollback tests use temporary directories
and simulated native installation/restart; do not replace the real Pi runtime.

Test corrupt/oversized/traversal/link/duplicate packages, wrong architecture,
wrong VM/source/digest, review-only refusal, explicit confirmation, install
failure preservation, successful selection, and failed-start rollback. Test the
phone-size panel and file flow without relying on crypto.subtle (HTTP origin).
Keep the generic USB guard for other boards and all existing SFC source unchanged.

Discovery is reserved for the native iPhone application (Bonjour/local network
permissions). Do not add a Safari LAN scanner. Known-address web access remains.

## GitHub release selection

Check only public releases of `speccy88/microblocks-zephyr`, explicitly separate
from upstream MicroBlocks board releases. The Pi fetches through verified HTTPS
without credentials or browser-supplied URLs. Bound catalog size, redirects,
bytes and duration. Previews are opt-in. Never publish a release as part of
checking it.

Find the latest compatible native asset named
`smallvm-linux-arm64-<release-tag>.tar.gz`. Obtain its GitHub SHA-256 (or exact
SHA256SUMS entry), check size, archive, ELF, manifest VM/source and required host
capabilities. A future package must carry the port commit provenance; compare
it with the known installed native revision and require a descendant. Identical
binary means up to date; older, diverging or unorderable binaries are refused.
Bounded search must report uncertainty rather than silently selecting older.

Show source repository, release version, date, preview status, native VM,
capabilities and SHA-256. Let the user explicitly choose that verified release,
then use the existing confirmation/apply/backup/recovery flow. A check and
selection never execute the package. Preserve the manual upload alternative.

Tests cover no suitable release, exclusion of whole editor/old Pi bundles,
checksums, wrong capability/architecture/VM/source, outdated/divergent commit,
same binary, expired selection, changed installed baseline, download failure,
redirect restrictions and progress. Simulate the positive compatible release
and phone UI. Check the real published catalog without installing a new VM.
