# Consolidated human hardware validation

The user is often away from the boards, including while using chat at work.
Do not infer physical availability from an open chat or lack of response.
Prepare all supported visual/audible checks together, then wait for an explicit
ready-at-the-boards message before starting. The parent conversation coordinates
the session. Do not issue scattered observation prompts or surprise patterns.

## Already accepted

Five NeoPixels, positions 1..5 in red at 8/255, then pixel 1 green/blue and all
off, were repeated at 700 ms per step at the user's request. The user confirmed
that everything worked perfectly. This remains valid; no repeat is pending.

## One future checklist, gated by implemented drivers

1. Three buttons: one prompted press/release per button, with USB timestamps.
   The input primitives exist; only released-state reads are currently measured.
2. DVI: one clear test pattern and readable text, when an HSTX driver exists.
   No Fruit Jam display driver or visual PASS is claimed yet.
3. USB host: keyboard and mouse recognition plus deliberate input, when the
   PIO host driver exists. No host-enumeration PASS is claimed yet.
4. Audio: brief low-volume tone, immediate stop and headphones/speaker selection
   only when I2S and codec configuration are implemented. No sound now.
5. Any new user-requested LED/IR or attached-output checks: list them before
   the same session, with exclusive pin ownership and safe levels.

Skip unavailable drivers explicitly. Keep all outputs off/quiet afterwards.
Record direct observations with the actual firmware hash. Automated protocol,
build, storage and silent diagnostics may continue without a human session.
The cancelled SHT40/41 work is excluded.
