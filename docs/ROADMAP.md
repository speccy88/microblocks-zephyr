# Roadmap / acceptance criteria

This is a living spec with objectively verifiable milestones, not a claim that
all hardware already works.

| Stage | Deliverable | Acceptance evidence | Current status |
|---|---|---|---|
| 0. Repository | MIT/MPL notice, manifest, board layout, CI | `python3 tools/validate.py` passes | Private repository and offline validation pass |
| 1. Zephyr hardware bring-up | Display, SHTC3, RTC, buttons, battery diagnostics | Compiler logs + readings + photo + raw observations | Pinned build and physical sensor/ADC/LCD-transfer evidence; appearance/presses pending |
| 2. MicroBlocks runtime | SmallVM with USB transport | Connect and reconnect; `5+7=12`; 500 ordered outputs; zero CRC errors | Linked v417; wireless and graphical execution/reconnect/CRC/reboot pass |
| 3. Graphical peripherals | Sensor / display / buttons blocks | Run `.ubl` on physical board; exact observed outputs | Graphical temperature read passes; other visual/physical checks pending |
| 4. Arduino API | A compatible Zephyr Arduino module and known-working libraries | `pinMode`, Wire, SPI and one library physical test | Real API compiled with Wire adapter; third-party library physical tests pending |
| 5. Full Waveshare coverage | microSD, Wi-Fi, BLE, I²S microphones, speaker, safe power APIs | One test per device + concurrent VM runs | Planned |
| 6. Portability | Same MicroBlocks project on UNO Q and Waveshare | Real tests against both boards | Planned |

## Stage 1 in detail

Build the pinned upstream `hello_world` target before running diagnostics.
Back up full flash to private storage, verify checksum and document recovery.
Use [board acceptance matrix](../boards/waveshare_esp32s3_rlcd_4_2/docs/ACCEPTANCE_MATRIX.md).
Don't mark any device PASS based on an on-paper DTS entry or a mere successful
build; record physical observations, firmware revision, date and any failures.

## Scope controls

- First get serial diagnostics and verified display/sensor/button operation.
- Then bring up SmallVM's official protocol without a graphical library.
- Only then integrate convenience blocks, Arduino libraries, and audio.
- Do not silently copy/replace a user’s existing UNO Q firmware or refactor
  their working `uno-q-microblocks` repository.
