# Whistle voice control for OLED eyes

## Contract before implementation (2026-10-29)

Use the existing native Zephyr Whistle C99 d4 engine and P4 ES8311 microphone,
not a computer transcription service. Enable the separately verified model
profile alongside current eyes, camera and fast serial features. Preserve the
existing pinned engine/model hashes, bounded arena/stack/cancellation and flash
limits. No raw audio, weights, private transcripts or flash dumps enter Git.

Expose a real MicroBlocks if/else chain for exactly `up`, `down`, `left`,
`right`, `angry`, `happy`, `tired`, `normal`. ASCII case and punctuation are
ignored; match whole words so `cup`, `bright` and `abnormal` do not trigger.
If several command words occur, use the first in spoken/text order. Direction
changes gaze only, mood changes mood only; normal means default mood. No match,
empty/silent text, cancelled capture/transcription or error changes either
state. Turn off face following, face idle policy and idle wandering in this
example so they cannot overwrite the voice-controlled state. Autoblink can
continue without changing the saved gaze/mood.

Start initializes eyes but leaves recording OFF. Default is an explicit
**Listen once** action: short preparation cue, record 3000ms (500ms settling
before LISTENING, followed by a 2500ms speech window), stop microphone,
transcribe English (language 0), apply the first recognised command, then wait.
Publish `Ready`, `Get ready`, `LISTENING`, `TRANSCRIBING`, and result/status
variables so the user knows when speech is accepted. Native scalar Whistle
previously took 20–35s, so do not imply continuous recognition during inference.
Optional repeat mode starts another window only after inference plus a gap;
never queue recordings or old transcripts. Pause stops repetition and cancels
the active job while retaining eyes. Stop All uses native cleanup and retains
the last OLED frame. A busy latch prevents overlapping button/script invocations.
Release the original audio handle immediately after successful sttRequest,
because the Whistle worker owns a copy, and release it on request failure too.

Keep the keyword parser and if/else mapper as editable project custom blocks.
Acceptance: actual GP compilation/execution for all eight words, case and
punctuation, substring negatives, multiword ordering, and unknown-last-state
retention; native model build/flash/hash checks; physical mic/Whistle lifecycle,
cancel/reuse and empty/error retention; preserve camera/fast-link/eyes behavior.
Acoustic recognition accuracy is reported separately from injected-text tests.

An advanced read-only `eye settings` reporter exposes desired gaze/mood and
running/ready/idle flags to verify unchanged state, without touching I2C or
changing the animation. It does not prove display appearance by itself.

## Using the project

Open the local editor at `http://127.0.0.1:8874/?bridge=1`, then **Projects &
board → Board examples → Whistle voice eyes (Listen once / repeat)**. Connect
USB and press Start. Start prepares the OLED, disables camera/face control and
leaves the microphone off. Click the **Listen once (2.5 seconds)** script;
wait for **LISTENING**, then say one command during that window. The status
bubble changes to **TRANSCRIBING** while the microphone is off. Wait for
**Applied command: …** or **No command recognised. Eye state kept.** before
trying again. There is no wake word or voice-activity endpoint in this project.

| Word | Change | Retained |
|---|---|---|
| up / down / left / right | Gaze | Expression |
| angry / happy / tired / normal | Expression (`normal` = default) | Gaze |
| No recognised command | None | Gaze and expression |

**Start repeated listening** opts into repeated windows, each followed by
transcription and a one-second gap. Say commands only while LISTENING is
shown. **Pause listening (keep eyes)** stops that loop and cancels active work;
it does not reset gaze or mood. A second Listen once invocation while busy is
ignored. Start is initialization and resets eyes; it is not the listening
button. Stop All freezes the last OLED frame via native cleanup.

The editable project is `integration/voice-eyes.ubp`. Its custom
**apply eye command from text** block contains the explicit if/else chain.
Use its Define action (or show My Blocks definitions) to inspect it. The
**first eye command in** block tokenizes whole English words and ignores case
and punctuation; `look left, happy` applies only `left`. The loose text test
script can exercise commands without waiting for speech recognition. Change
the `3000` argument of `audioRequest` and `500` settling delay in
**record voice command** to adjust the recording/window lengths. Keep the
full recording within Whistle's four-second bound. This changes the project,
without another firmware flash.

Native scalar inference takes tens of seconds, so manual Listen once is the
recommended starting point. A physical ES8311 component test of the local
speaker word `happy` took **20.436s** after a 2.5s recording. The final complete
GP block took **26.527s** from TRANSCRIBING to Applied command after its 3s
recording (500ms settling plus the 2.5s speech window). These are controlled
acoustic samples, not an accuracy score for all eight words or the user's
voice. A small command classifier would be a different model/integration.

The initial complete-block trials missed the test word; a synchronized trial
recognised it when the speaker waited 450ms after the original cue. The final
project starts recording 500ms before displaying LISTENING so speech can
begin at the cue. This is a practical settling allowance, not a measured
characterisation of every microphone startup or an acoustic accuracy claim.

## Native build and installed image

Source base: `622c0c09fd0ad942f34048806629c0dd7a62c045` plus the local changes.
Zephyr target `esp32p4_wifi6/esp32p4/hpcore`, Zephyr
`a915b2f12675b48b16d56653ea145dcd8f20cbbf`, HAL
`b16851b3c20e6fad3d2da42ec24a3e82d0b8b444`. WSL Ubuntu 26.04,
Zephyr SDK 1.0.1 / GCC 14.3.0. Exact build command:

```sh
source /home/fred/microblocks-zephyr-work/.venv/bin/activate
cd /home/fred/microblocks-zephyr-work
export ZEPHYR_BASE=/home/fred/microblocks-zephyr-work/zephyr-robot-eyes
export ZEPHYR_SDK_INSTALL_DIR=/home/fred/microblocks-zephyr-work/tools/zephyr-sdk-1.0.1
west build -b esp32p4_wifi6/esp32p4/hpcore \
  -s /mnt/c/Users/fred_/Documents/Codex/microblocks-zephyr/boards/waveshare_esp32p4_wifi6/zephyr \
  -d build-p4-voice-eyes -- \
  -DSMALLVM_SOURCE_DIR=/mnt/c/Users/fred_/Documents/Codex/2026-10-25/task-2/microblocks-zephyr/build-artifacts/p4-sources/smallvm \
  -DP4_WHISTLE_SOURCES=/mnt/c/Users/fred_/Documents/Codex/2026-10-25/task-2/microblocks-zephyr/build-artifacts/whistle-sources \
  -DP4_WHISTLE_MODEL=/mnt/c/Users/fred_/Documents/Codex/whistle_esp32_s3_rlcd_v0.1.0/whistle-esp32/release/whistle_d4.cact \
  -DEXTRA_CONF_FILE=profiles/whistle.conf
```

The pinned engine is `9e9e996e55b0f945438da1082eac4a087ed3ca39` and model
SHA256 is `e2ccbe2d342a8438ec9a7610809ad095acdbcc359b959202fe18dc4fef66dbb1`
(14,515,887 bytes, flash mapped, no fixture audio embedded). The 15,015,184-byte
pre-v3 guarded image SHA256 is
`1b73d3920950f3110830b6c212b5e3ec6bf4fac102593401d805debeb233db03`.
Only the native application at `0x2000` was written and hash verified; it ends
below the reserved `0xfe0000` boundary. Existing assets/NVS/recovery are retained.
No ESP-IDF/FreeRTOS substitute, C6 flash, eFuse action or firmware dump.

Build log: `evidence/2026-10-29/p4-voice-eyes-build.txt`; flash record:
`evidence/2026-10-29/voice-eyes-flash.json`. Firmware/model binaries and audio
stay under ignored build-artifacts, outside Git. The optional model profile
must be enabled for STT; an eyes-only build reports unavailable clearly.

## Acceptance evidence

| Check | Result / evidence |
|---|---|
| Actual GP 2.5.8 compiler and P4 execution, all eight commands, case/punctuation, substring negatives, first-word ordering, empty/unknown state retention | **21/21 PASS**, `evidence/2026-10-29/voice-eyes-gp-tests.json`. Exact production function source is reused by `tools/make_voice_eyes_fixture.py`; `tools/read_voice_eyes_fixture.py` independently reads native globals/settings over COM5. Fixture scripts are split into small broadcasts to respect VM script-size limits. |
| Native ES8311 capture → Whistle, responsive VM, immediate audio-handle release, job memory reclamation, cancellation and old-text clearing | **PASS**, `evidence/2026-10-29/voice-eyes-microphone.json`; controlled speaker `happy` recognised, no raw audio exported. |
| Complete original Listen once → native Whistle → if/else → happy mood while preserving left gaze; concurrent second invocation ignored; Pause during a second capture retains settings and frees audio | **2/2 PASS**, `evidence/2026-10-29/voice-eyes-gp-microphone-initial.json`; synchronized speaker with 450ms delay after the original cue. New settling-cue version is separately tested below. |
| Final settled-microphone Listen once, speaker starts immediately at LISTENING, then concurrent invocation/Pause during second capture | **2/2 PASS**, `evidence/2026-10-29/voice-eyes-gp-microphone.json`; first command `happy`, gaze remains left (0,500), mood becomes happy (3), Pause keeps those settings, zero audio handles, no active inference. Browser-observed speech window 2544ms and transcription-to-apply 26527ms. |
| OLED appearance | Original user-confirmed complete border/centered cross and working eyes; new voice tests read desired native gaze/mood. Appearance of every expression and the user's eight spoken words still needs user observation. |

Generate reproducible fixtures with `python tools/make_voice_eyes_fixture.py
--output <path>.ubp` (mapping, microphone off), or add `--suite microphone`
(controlled spoken `happy` at the first LISTENING cue, then automatic busy/Pause
checks). Load the generated project in the genuine editor and press Start.
After it reports VOICE_TESTS_PASSED, disconnect the editor and independently
read native results with `python tools/read_voice_eyes_fixture.py --execute
--evidence <path>.json`, adding `--suite microphone` for that fixture. No raw
transcript or audio is saved in the evidence. The final production workspace
must then be reloaded; fixtures are not normal listening examples.
