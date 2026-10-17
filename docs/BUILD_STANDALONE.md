# Reproduce the standalone build

This is an experimental port. Read DEVELOPMENT_SESSION.md for physical evidence
and remaining failures before deploying it. Keep credentials, SDK workspaces,
prepared sources and generated firmware outside Git.

The verified environment uses Linux/WSL, Python 3.12.15, west 1.5.0,
CMake 4.4.4, Ninja 1.13.2, Zephyr SDK 1.0.1 (Xtensa ESP32-S3 GCC 14.3.0),
gperf 3.3 and esptool 5.6.0. Python tooling can be installed with uv in a local
virtual environment. Zephyr requirements-base.txt provides PyYAML and its other
build dependencies. Limit compilation to four jobs on the tested host.

Pin Zephyr to `a915b2f12675b48b16d56653ea145dcd8f20cbbf`. Required west
projects are `hal_espressif`, `hal_xtensa`, `mbedtls`, `tf-psa-crypto`, and
`zcbor`, at their manifest revisions. Run `west blobs fetch hal_espressif`;
the current driver CMake verifies every listed Espressif blob, including those
for other chips. Keep their licenses.

Stage source snapshots from the existing reference, without executing its scripts:

```sh
git clone https://github.com/speccy88/uno-q-microblocks ../uno-q-reference
git -C ../uno-q-reference checkout 70690291ac44a5c3a50dce572ee0c29ba99dc57f
python tools/stage_reference.py ../uno-q-reference ../verified-sources

git clone https://github.com/zephyrproject-rtos/ArduinoCore-zephyr ../arduino-api
git -C ../arduino-api checkout af5b8610f9be6d7b962e2ba6dd8e6859697c44ff
python tools/prepare_arduino.py ../arduino-api --fetch-api
```

The staging tool checks every VM and IDE file against committed SHA-256
manifests. SmallVM is v417, canonical revision
`2071df569623ba9cdcd6f8106b61796e047df38b`; the snapshot is taken from its
pinned UNO Q mirror. The Arduino module's own pinned manifest verifies all API
1.5.2 source blobs. Wire fixes are applied only to the reviewed revision and
refuse unrelated local modifications.

From the repository, inside the prepared west workspace/environment:

```sh
export ZEPHYR_BASE=/absolute/path/to/zephyr
export ZEPHYR_SDK_INSTALL_DIR=/absolute/path/to/zephyr-sdk-1.0.1
export CMAKE_BUILD_PARALLEL_LEVEL=4
west build -b esp32s3_rlcd_4_2/esp32s3/procpu \
  -d /absolute/path/to/build/standalone \
  boards/waveshare_esp32s3_rlcd_4_2/standalone -- \
  -DZEPHYR_EXTRA_MODULES=/absolute/path/to/arduino-api \
  -DSMALLVM_SOURCE_DIR=/absolute/path/to/verified-sources/smallvm \
  -DIDE_SOURCE_DIR=/absolute/path/to/verified-sources/ide
```

The build generates private AP/pairing values in the build directory. Preserve
that private directory across builds so access values remain stable; never
commit it. The production image serves about 3.51 MB of compressed editor assets
from flash. Program snapshots use the dedicated 256 KiB `vmstore` partition;
Wi-Fi settings use the separate 64 KiB settings partition. MicroSD is not needed.

Production disables console/log output so a serial reader is not required.
For focused recovery diagnostics, add `-DEXTRA_CONF_FILE=debug.conf` using a
separate build directory. Diagnostic results do not establish unattended
production stability; run the physical tests with the production image too.

The tested simple-boot image is written at offset zero. Only flash the exact
board the user authorized; never erase or change eFuses implicitly. Normal
app-only updates preserve the program/settings partitions above 13 MiB. The
user explicitly authorized erase without backup for this COM4 development
session; that instruction does not apply to another board or session.

Offline checks: `python tools/validate.py`. Physical transport checks require
`websocket-client==1.9.0` and the locally generated private JSON:

```sh
python tools/test_wireless_vm.py --host BOARD_IP --private PRIVATE_JSON \
  --evidence evidence/wireless-vm.json
```

This replaces VM test chunks and deliberately persists them. The optional
`--reboot-port COM4` performs a recovery reset and checks CRCs after reboot;
it does not flash firmware. Display transfer success still requires physical
visual confirmation, and released button reads do not validate button presses.
