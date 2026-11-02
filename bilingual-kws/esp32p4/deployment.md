# Native Zephyr command model deployment

The build script does **not** flash, reset or open a serial port. Current task
authorization excludes those actions, including COM12. Preserve the installed
image, programs, C6 firmware and network settings. A physical acceptance session
requires separate explicit authorization.

## Build

Use the existing pinned west workspace and its reviewed local native patches.
Zephyr base commit is `a915b2f12675b48b16d56653ea145dcd8f20cbbf`;
TFLM is `43b2a106a391dd8a099ac47f2ae858630a397264`;
SDK is 1.0.1 / GCC 14.3.0. The local `zephyr-robot-eyes` checkout preserves the
existing eye/camera work. Inspect its source diff when reproducing elsewhere.

The existing KWS worker still embeds its separately hash-pinned Okay Nabu
model. Download that public Apache-2.0 asset if absent:

```bash
mkdir -p build-artifacts/p4-kws
curl --fail --location \
  https://raw.githubusercontent.com/esphome/micro-wake-word-models/40ff33f57f8fc6ad71a75ef085abbf742495b225/models/v2/okay_nabu.tflite \
  -o build-artifacts/p4-kws/okay_nabu.tflite
bash bilingual-kws/esp32p4/build.sh 2>&1 | tee build-artifacts/bilingual-kws-native-build.txt
```

The script contains the complete `west build` command and model paths. CMake
checks the trained model manifest/hash, fixed dimensions, integer tensors,
size ceiling and TFLM revision before generating mapped read-only assets.
Firmware verifies the hash and FlatBuffer again, then AllocateTensors and
the actual INT8 tensor contract. An incompatible model reports an error.

To retain the existing native Whistle STT in the same built image, supply the
already verified local model and source checkout explicitly. The script adds
the original Whistle application/reserved-storage overlay and checks its image
boundary. This still only builds:

```bash
P4_WHISTLE_MODEL=/absolute/path/to/whistle_d4.cact \
P4_WHISTLE_SOURCES=/absolute/path/to/pinned/whistle-sources \
bash bilingual-kws/esp32p4/build.sh
```

To produce the linked-model inspection and exact build report used by this
project, run with the west workspace Python (which supplies `pyelftools`):

```bash
/home/fred/microblocks-zephyr-work/.venv/bin/python \
  bilingual-kws/scripts/capture_native_build.py \
  --whistle-model /absolute/path/to/whistle_d4.cact \
  --whistle-sources /absolute/path/to/pinned/whistle-sources
```

The report records target/base commits, toolchain, native source hashes, actual
ELF model mapping, selected-model and image hashes, flash boundary, and the
offline revision guard. The guarded binary stays under ignored
`build-artifacts/bilingual-kws/`; creating it does not contact a board.

The ordinary NN importer, camera, RoboEyes, Okay Nabu and Whistle implementations
remain separate. Audio hardware remains exclusive, and heavy concurrent CPU/RAM
work may stop the listener on an explicit overflow or memory-pressure error.
Compilation does not establish concurrent physical performance.

There is one serialized KWS worker, one permanent bounded PCM message ring and
one frontend owner. Okay Nabu and command inference cannot run concurrently.
An ordinary saved PCM clip is copied into worker-owned storage before dispatch.
The microphone stream is exclusively acquired only after explicit listening.
Stop/Stop All stops the DMA path, invalidates pending commands and clears audio.
Failure to stop quarantines the stream; buffers are not silently reused.

Command inference keeps 118 streaming feature frames and invokes every 10 new
frames (100 ms). Each session resets the frontend; initial output needs a full
1.2-second feature window. Thereafter confidence smoothing, two stable windows,
an 800 ms default cooldown and three rejection windows before rearming prevent
repeated triggers from one sustained prediction. Unknown/silence never emit an
action. These are tested rules, not a measured false-positive guarantee.

## MicroBlocks use

Recreate the genuine pinned GP 2.5.8 editor package from the repository root:

```bash
python tools/fetch_p4_sources.py --output build-artifacts/p4-sources
python tools/package_p4_ide.py \
  --ide-source build-artifacts/p4-sources/ide \
  --output build-artifacts/p4-editor-bilingual-kws
```

The supplied package at `build-artifacts/p4-editor-bilingual-kws` contains the
new library and compiler/runtime event-hat patch. The self-contained example
is `bilingual-kws/esp32p4/microblocks/voice-commands-eyes.ubp`. Packaging and
the schematic preview are host checks, not a claim of running the new blocks
on a physical P4.

The packaged editor includes `P4_Voice_Commands.ubl`. Start/Stop and Stop All are
explicit. Importing the library, opening the editor, and inspecting scores do
not start the microphone. Do not pass the model to the restricted dense importer.

1. Use `voice commands available?` and inspect `voice command status`.
2. Run `start voice commands` in a user-started script.
3. Under `when voice command detected`, read `recognized command` and
   `command confidence`. `score for command` accepts all ten lowercase names.
4. Run `stop voice commands` or Stop All when finished.
5. A saved 16 kHz mono PCM handle can use the advanced clip block without
   activating the microphone. The clip must include at least 1.2 seconds.

Events compile to SmallVM's existing broadcast receiver mechanism using the
reserved `_p4.voice.command` name. Receive-any-message scripts may observe that
name; do not reuse it for application messages. A running handler is not
re-entered. Four events are queued; diagnostics count overflow. Keep event
handlers short and copy command/confidence to project variables when needed.

## Eye controller

Import `bilingual-kws/esp32p4/microblocks/Voice_Eyes.ubl` and initialize its state.
The eight actions change gaze or expression without requiring any display:
UP `(500,0)`, DOWN `(500,1000)`, LEFT `(0,500)`, RIGHT `(1000,500)`;
ANGRY/HAPPY/TIRED/NORMAL change mood to angry/happy/tired/default. Rejected
commands retain state. The host schematic is `reports/eyes_preview.png`.

In the detection hat call `apply voice eye command (recognized command)`.
For an independently initialized, explicitly selected Robot Eyes OLED, optionally
call `render voice eye state on initialized OLED`. This library never probes or
initializes a display. Display attachment and physical rendering remain separate
from host preview and command inference acceptance.

## Physical acceptance still required

Use the exact built image and model hash, with a revision guard and preserved
recovery/program path, during an explicitly authorized future device session.
Measure the real arena/frontend/stack and total RAM, median/p95 invoke and
post-word latency, queue behavior and CPU use while MicroBlocks runs. Compare
scores to pinned host TFLM fixtures, repeat start/stop/cancel/pressure tests, and
test multiple real English/French speakers including French-Canadian voices.
Use long representative continuous negatives to measure false positives/hour.
A native build and host TFLM cannot satisfy these physical gates.
