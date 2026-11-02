# P4 local work integrated into main

This integration starts from main `962b5c4fd8422b2dbbdb761666bdd56d4a5d28f3`
and carries forward the useful Windows working changes based on
`622c0c09fd0ad942f34048806629c0dd7a62c045`. The original working directory,
branches, recordings, build files and private evidence are preserved separately.

## Behavior and scope

Preserve the current shared VM, JavaScript/mobile/Linux editors and SFC sources.
Add the existing P4 native OLED eyes, face/pose leases, bounded camera controls,
preview/serial negotiation and explicit Whistle command example. The bilingual
INT8 listener remains an optional trusted firmware model with explicit start,
stop, confidence, cooldown and release rules. Import and boot do not start the
microphone. Generic neural import remains restricted to its existing operators.

SFC was already integrated on main; this change retains its canonical source
and checks the existing JavaScript semantics against real sanitized C fixtures.
The P4 GP packaging additions do not establish JavaScript palette support for
every new P4 block. Device capability and profile limitations remain explicit.

No flashing, hardware access, Pi service change or deployment is part of this
integration. Historical physical observations from October 29 are distinct from
host checks and the compilation of this source tree. New acoustic command
accuracy, live vision, every OLED expression and concurrent hardware performance
remain unverified. The hardware manifest is canonical; the reviewed matrix is
regenerated from its updated hash without transferring validation to other boards.

## Dependencies and acceptance

The external pinned RoboEyes header and full GPL-3.0-or-later notice must be
fetched with `python3 tools/fetch_roboeyes.py`; no upstream source is silently
vendored. Zephyr is `a915b2f12675b48b16d56653ea145dcd8f20cbbf`, HAL is
`b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`, TFLM is
`43b2a106a391dd8a099ac47f2ae858630a397264`. Existing native patches must
already be applied. Use SDK 1.0.1 / GCC 14.3.0 and verified SmallVM v417 inputs.

The trained model's original frontend digest includes Windows CRLF. The public
manifests retain that training-checkout digest and add `adapter_lf_sha256` after
byte comparison proved that LF normalization is the sole difference. Firmware
preparation accepts either pinned representation and rejects semantic changes;
the model bytes, frontend arithmetic and trained weights are unchanged.

Required checks:

```sh
python3 tools/validate.py
python3 tools/capability_matrix.py --check
python3 tools/test_eyes_pose.py
python3 tools/test_p4_images.py
python3 tools/build_sfc_native_fixture.py
python3 tools/test_sfc_execution.py
MB_SFC_HOST="$PWD/build-artifacts/sfc-native/host" \
MB_SFC_EXECUTION_HOST="$PWD/build-artifacts/sfc-execution/host" \
node --test tests/sfc-*.test.js tests/p4_media_core.test.js \
  tests/p4_nn_core.test.js tests/p4-transport.test.cjs
```

The voice decision C fixture is compiled with ASan/UBSan by the P4 host-contract
workflow. That workflow also checks trusted model generation and corruption
rejection without training dependencies. The mandatory offline validation and
the existing SFC CI remain enabled.

For the complete native image, provide local verified inputs and an isolated
build directory:

```sh
P4_WORKSPACE=/path/to/west-workspace \
P4_BUILD_DIR=/tmp/p4-main-integration \
P4_WHISTLE_MODEL=/path/to/whistle_d4.cact \
P4_WHISTLE_SOURCES=/path/to/pinned/whistle-sources \
bash bilingual-kws/esp32p4/build.sh
```

The script contains the exact `west build -b esp32p4_wifi6/esp32p4/hpcore`
arguments. Neither the script nor acceptance commands flash a device.

## Publication boundary

Version the implementation, generic projects, tests, source pins, public-corpus
aggregate reports and small INT8 models needed for reproduction. The three
report images are generated plots/schematics without private camera content.
Historical JSON evidence contains technical measurements, not a new hardware
acceptance claim. The historical native-build report has local paths redacted.

Keep Keras checkpoints, raw corpus/recordings, speaker-identifying manifests,
camera/editor screenshots, raw build/test logs, firmware, archives, credentials
and private HTTPS/WSS receipts outside publication. They are preserved locally;
references to historical raw logs do not mean those private files are shipped.
