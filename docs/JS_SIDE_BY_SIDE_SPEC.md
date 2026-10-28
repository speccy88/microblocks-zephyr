# Target-specific JavaScript preview packaging

Keep the GP artifact byte-identical and add a separate `js-preview/` hub with
Raspberry Pi 5 and MicroDuck Rockchip RK3566 entries. Build both from the same
pinned upstream manifest, retaining every upstream engine byte, licenses and
existing sync tooling. Do not deploy, update pins, replace GP, import SFC or
rewrite the VM in this slice.

Pi 5 packages core editing without the custom MicroDuck library bundle. It may
connect only through the existing explicit high-port HTTP 127.0.0.1 bridge flow.
Hosted HTTPS permits editing but has no commissioned WSS path in this slice.
MicroDuck includes the six typed gateway libraries for explicit offline import;
all transport entry points must reject connections before opening any provider.
Its placeholder status is independent of whether the page is locally hosted.
The existing development package retains its current behavior for VM tests.

Use external local profile/bootstrap adapters, not edits to upstream files. A
repeat profile installation is harmless; changing an already installed profile
must fail. No automatic connections, service workers, firmware or network
credential storage are added. No ordinary static preview implies VM readiness.

The compositor accepts an existing GP build, rejects overlapping/symlink inputs
and output collisions, and records input/output hashes and source pins. The new
hub offers links to the JS profiles and existing GP editor; it does not alter GP
navigation, projects or iframe behavior. Future publication needs an explicit
pipeline integration and live acceptance after approval.

Verify profile guards with fake providers, package/source hash preservation,
library inclusion/exclusion and immutable GP assets. Exercise the actual pinned
compiler and MicroDuck importer, then inspect both profiles and the typed library
picker in a local browser. Run the full repository validator. Do not disturb
existing Pi processes; hardware and hosted-WSS acceptance remain separate.
