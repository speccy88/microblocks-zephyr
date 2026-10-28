# JavaScript editor preview

Open https://speccy88.github.io/microblocks-zephyr/js-preview/ after the Pages
deployment completes. The existing GP editor stays at the site root. This is an
experimental preview, with explicit target selection and no automatic connection.

Raspberry Pi5 is a standalone Linux target, independent of robot services. Its
existing local session/SSH tunnel is the tested connection path; direct hosted
WSS is not commissioned. MicroDuck Rockchip RK3566 remains a disconnected
placeholder. Load its normal service libraries, Starter Lab or Camera Lab to
explore170/213/235 functions. Simple and advanced categories coexist in a project.
Practice actions are explicitly simulated; depth/IMU/gamepad/camera fixtures are
not physical sensor acceptance. No live robot motion, mediad audio or camera
stream is enabled by this preview. The H264 lab uses generated local canvas video.

Other target profiles retain explicit identity/version checks and existing
runtime protections. Physical JavaScript board acceptance remains unverified.
This website deployment does not install firmware or update a Pi service.

The source/assets are in the hash-pinned prerelease archive named by
dependencies/js-preview-site.json. It includes plaintext JS and MicroBlocks
libraries, component source pins and licenses. The editor engine remains pinned
to5564b1e42d6790360450ebf11c9eb33a1c6877f2. No VM upgrade is required by this
static deployment. Local implementation/evidence history is not published by it.

Pages builds the frozen GP baseline6e2b4f9 plus its pinned2c060b7 Linux overlay.
tools/add_js_preview.py verifies the complete archive, every asset and every GP
input hash before adding only js-preview/. Existing GP bytes remain unchanged.
The same Pages permissions/deployment job is retained. Hosted tests compile and
round-trip all three MicroDuck bundles with the actual pinned engine and a fake
DOM; this does not establish graphical or hardware acceptance. Live HTTPS checks
and graphical results are reported separately after deployment.
