# Public Linux target deployment, 2026-10-28

Fred explicitly requested deploying the website to explore Pi 5, MicroDuck and
the robot libraries. Main advanced non-destructively from `9db5c3f` to
`6e2b4f9c0687006ac04a5d9a1bb14c265193cb3d`. The five-file publication contains
only the Pages workflow, composition/build tools, focused tests and target docs.
The local graphical evidence/readback commit `4fa9262` was not published.

All hosted workflows at the new main commit succeeded, including Browser portal
run **40619957388** with successful build and deploy jobs. The separate approved
Linux migration commit `2c060b7` also has successful x86_64/aarch64 native CI,
offline validation and XRP checks. Local source-only deployment validation
passed all68 tests. The separate readback checkpoint passed492 tests.

Live URLs verified in the browser:

- https://speccy88.github.io/microblocks-zephyr/#editor — both new selector entries.
- https://speccy88.github.io/microblocks-zephyr/preview/editor/raspberry-pi5/microblocks.html — Linux Core, independent of robot services.
- https://speccy88.github.io/microblocks-zephyr/preview/editor/microduck/microblocks.html — typed robot, coherent depth, gamepad and IMU libraries; separate simulation libraries.

Screenshots show actual live robotd telemetry, coherent depth, padd gamepad and
mediad simulation palettes. Blocks were inspected, not run against hardware.
MicroDuck is explicitly a disconnected experimental placeholder. Normal read-only
paths were previously exercised on the real Pi with fictional robot services.
Live physical motion, camera pixel blocks, mediad audio and shipping MicroDuck
commissioning remain incomplete/unverified. Public HTTPS-to-VM WSS commissioning
is separate from the tested Pi loopback SSH editor path.

The live manifest identifies main `6e2b4f9`, Linux source `2c060b7`, an explicit
one-line placeholder-status overlay and1070 output hashes. The composition
preserves763 files from the hosted stable five-board build. Fifteen critical live
files, including both Linux HTML/adapter/GP script/data sets, were downloaded and
SHA-verified. The entire output hash map matches the canonical UTF-8 preview.

The first strict comparison found three local/hosted differences in existing P4
adapter typography, its dependent HTML cache hash and build manifest. The existing
P4 generator reads text with the OS default encoding: Windows inspection produced
CP1252 mojibake; the hosted Linux UTF-8 text is correct. Reversing exactly that
encoding conversion reproduces the live bytes and dependent hashes. No P4 source,
VM behavior, hardware, COM port or owner checkout was changed.

The local deployment validation launcher initially missed a `sys` import and
failed before starting tests. Its corrected run passed68; no public mutation
occurred during that failure. The deployment itself completed on its first run.

The public site retains the current GP editor; the JS migration remains separate.
Future integration must account for the new main workflow: this composition
expects a five-board stable input, whereas the migration branch's GP packager
already generates seven profiles. Do not blindly merge the workflow and publish.
The P4 checkout and paused SFC work remain untouched. No reboot, persistent user
service, network/security change, physical robot command or new credential was
performed. No approval is pending.
