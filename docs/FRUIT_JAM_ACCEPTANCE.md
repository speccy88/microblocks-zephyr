# Fruit Jam hardware acceptance plan

The user authorized replacing the Fruit Jam firmware and developing/testing
its onboard hardware on 2026-10-18. Other boards and their serial ports remain
outside this task. The attached STEMMA QT sensor is a user-described SHT40/41
at address 0x44; that address alone cannot distinguish the exact variant.
Later instruction: the user asked to leave this sensor alone. SHT4x testing
and its disconnect request are withdrawn; retained source stays unvalidated
and inactive, with no automatic probe/read or exposed library blocks. Do not
resume its diagnosis unless the user asks. Shared-bus restrictions on an
onboard peripheral remain documented dependencies.

## Baseline behavior and evidence

1. Preserve a private full-flash recovery copy, then program the previously
   cross-built ELF through the SWD-identified Pico probe. Verify programmed
   contents. Never commit full flash dumps or credentials.
2. Identify the new native USB CDC port from its USB identity; never select
   COM4/COM5 or the Pico's UART bridge by port number alone.
3. Test the actual binary VM protocol: ping/version, ten arithmetic results,
   one live edit, exactly 50 ordered outputs, fragmented upload, partial-frame
   recovery, stop/variable inspection and disconnect/reconnect.
4. Save a known startup program, allow snapshot debounce, reboot only this
   target through SWD, and verify CRCs, arithmetic and startup variable.
5. Connect the actual MicroBlocks graphical IDE to the verified transport and
   test a representative program. A Python protocol test alone is not a
   graphical IDE PASS.

## Peripheral development contract

Every capability in boards/adafruit_fruit_jam/hardware.json retains a separate
implementation status and physical evidence. Source, build and physical
results are distinct. No display appearance, audible sound, button presses,
external waveforms or unattached device operation is inferred from a driver
return value.

- SHT4x: send high-precision no-heater command 0xFD to 0x44, wait at least
  10 ms, read six bytes, verify CRC-8 polynomial 0x31/init 0xFF separately
  for each 16-bit word, convert T=-45+175*raw/65535 degrees C and
  RH=-6+125*raw/65535 percent (clamp RH to 0..100). Read serial with 0x89
  and CRC when supported. No heater command or address scan is required.
  Provide temperature/humidity/raw-status blocks and record measured bytes.
- Buttons: poll released state and record each actual press/release from the
  user. Never drive the BOOT/ESP boot pin.
- GPIO/ADC/PWM: retain extension allowlist and logical mapping. Actual output
  voltage, loopback and ADC accuracy need suitable wiring/measurement.
- NeoPixels: low brightness, short patterns, explicit off after each test.
  Reserve PIO1 with GPIO base 16 for physical GPIO32; refuse to change that
  base if another state machine is claimed. Use five fixed RGB entries,
  no DMA/interrupt masking, a 20 ms transfer deadline and no initialization
  until a pixel command is explicitly requested. Check each pixel/color on
  real hardware; a successful transfer return does not prove light output.
- SD: detect and read only initially; no formatting or test file writes.
- AirLift: audit and use the factory SPI protocol before changing firmware.
  Do not store credentials in Git. Shared GPIO22 reset also affects audio;
  initialize networking before codec configuration.
- Codec/I2S: validate control-register access and streaming separately; any
  sound is short and moderate volume. Listening requires user observation.
- DVI/HSTX: implement a Zephyr-compatible bounded DMA/PIO allocation and
  confirm a real attached display; do not substitute another firmware stack.
- USB host/hub: add a PIO host controller path compatible with the Zephyr
  scheduler and verify actual attached HID devices. Device USB remains VM.
- PSRAM: qualify timing/size with bounded pattern checks before allocating
  VM objects or framebuffers there. Preserve XIP/program-store boundaries.
- LED/IR: mutually exclusive modes for shared GPIO29. IR decoding requires
  actual received frames, not just idle-level sampling.

## Build and resource coordination

Already-built firmware can be flashed and lightweight hardware tests can run
while the separate GPU benchmark continues. New compilation waits for a
parent-coordinated benchmark window. Use four build jobs at most, retain the
existing resource monitor and record exact source/build/artifact hashes.
No GPU/Ollama process is controlled by this hardware task.

## Completion criteria

Run offline validation, targeted VM and physical checks, preserve the working
Waveshare source/artifacts, update the canonical Fruit Jam manifest and board
documentation truthfully, commit/push development/fruit-jam and verify CI.
Any missing physical attachment, observation, driver or build window remains
an explicit blocker rather than a PASS.
