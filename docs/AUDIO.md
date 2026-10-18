# Waveshare speaker output

## Behavior and acceptance

Implement output only: ES8311 DAC at I2C0 address 0x18, I2S0 controller,
24 kHz, signed 16-bit stereo frames containing the same mono sample. MCLK is
6.144 MHz (256 x sample rate). The official schematic and pinned vendor
`07_Audio_Test/src/ExternLib/codec_board/board_cfg.h` agree on GPIO16 MCLK,
9 BCLK, 45 LRCK, 10 DAC data and GPIO46 active-high NS4150B amplifier enable.
GPIO8/ES7210 microphone input remains unused.

Provide tone (50..4000 Hz, 1..5000 ms, volume 0..100), busy, stop and diagnostic
text blocks. A tone starts asynchronously; use `wait until not audio busy`
between notes. Reject malformed arguments before touching hardware. Only one
tone can run; overlapping requests report an explicit VM error. No sound at
boot. Amplifier is disabled and DAC muted on completion, stop or error. The IDE
global Stop uses the existing `stopTone` hook. A dedicated worker feeds a fixed
DMA slab so HTTP and the VM remain responsive. PCM is capped at one quarter
full scale, with 5 ms attack/release ramps; validation uses volume 10 and at most
200 ms. No microphone, files, streaming music or external-pin functionality.

Preserve the HTTP/RTC checkpoint and program/settings partitions. Build against
the pinned Zephyr tree, record image/hash and app-only COM4 flash. Check codec
identity and configuration readback, I2S buffer reclamation, submitted/completed
frames, explicit/global stop, rejected arguments, sensor/RTC readback and one
50-result VM run. These observations do not establish audible output or exact
clock/waveform quality; hearing confirmation and electrical capture are separate.

The vendor documentation identifies an external speaker connector (MX1.25
2-pin). A speaker must be physically connected for audible output. Do not
assume one is present or connect amplifier outputs to ground.

## Sources

- [Official board resources and schematic](https://docs.waveshare.com/ESP32-S3-RLCD-4.2/Resources-And-Documents)
- [Official board overview and speaker connector](https://docs.waveshare.com/ESP32-S3-RLCD-4.2)
- [Pinned vendor audio configuration](https://github.com/waveshareteam/ESP32-S3-RLCD-4.2/blob/a861929d91f25e7fbe2e0e014691f0fbedcaa64e/examples/arduino/examples/07_Audio_Test/src/ExternLib/codec_board/board_cfg.h)
- [Espressif ES8311 implementation in that snapshot](https://github.com/waveshareteam/ESP32-S3-RLCD-4.2/blob/a861929d91f25e7fbe2e0e014691f0fbedcaa64e/examples/arduino/examples/07_Audio_Test/src/ExternLib/esp_codec_dev/device/es8311/es8311.c)

The Zephyr adaptation retains Espressif's Apache-2.0 attribution. It uses the
vendor DAC initialization and the 6.144 MHz/24 kHz clock coefficient; no vendor
FreeRTOS tasks, music sample or ESP-IDF codec framework is linked.

The default 16 DMA descriptors consumed excessive internal RAM. Initial silent
tests reclaimed 200 ms PCM in 106..107 ms with two descriptors and also with
one. GPIO interrupt edge counting confirms WS near 24 kHz; register readback
confirms two 16-bit slots. These failures disprove the initial assumption that
descriptor count alone selects a safe queued path. Polling measurements were
replaced by interrupt edge counting to avoid aliasing.

One descriptor keeps a bounded queued/restart path only when append attempts
are rejected before `dma_reload`. The pinned I2S driver currently attempts that
reload even with one descriptor, allowing an idle descriptor FSM to replace an
in-flight buffer. `tools/prepare_i2s.py` verifies the exact upstream source hash
and generates a copy with a small guard; CMake builds that copy. The upstream
Zephyr checkout remains unchanged. Silent timing acceptance must pass before
this repair is accepted. Gapless music and oscilloscope waveform quality are
outside this tone feature. Failed evidence is retained.

## Current physical evidence

`evidence/2026-10-18/audio-silent-guarded.json` passes on image SHA-256
`3df0e7a541258ccb6720866c59ecb030ce222060b0bfef3d60903b7cff5f18cb`.
Each 200 ms silent note submitted/reclaimed 4800 stereo frames in 19 blocks;
worker elapsed time was 202 and 204 ms. Interrupt edge counting observed
23985 and 23965 Hz WS, with register readback confirming two 16-bit slots.
All four DMA buffers returned. Invalid arguments, overlapping requests,
explicit/global stop, concurrent RTC reads and original program preservation
passed, with zero settled allocator loss. The exact upstream Zephyr tree is
unchanged; the guarded generated driver is selected only for this target.

These are digital timing and driver observations. DMA reclamation does not
measure the DAC/analog tail, loudspeaker waveform, volume or audible quality.
The external speaker is connected according to the owner. Audible confirmation
is pending. A coordinated listening check is reproducible with:

```sh
python3 tools/test_audio.py --host <board-ip> \
  --evidence evidence/audio-listening.json --firmware-sha256 <flashed-image-hash>
```

It plays only two 200 ms notes, 440 then 660 Hz, at volume 10; stop tests use
volume zero. Disconnect the graphical controller first. Add `--silent` for
zero-volume driver validation. The script restores its initially vacant test
chunk and verifies all original CRCs; hearing confirmation must be recorded
separately from its PASS result.
