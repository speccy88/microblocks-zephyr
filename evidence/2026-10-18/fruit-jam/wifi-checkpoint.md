# Fruit Jam Wi-Fi checkpoint

The native image from source `95c4b70ee8c8a9fb4ecd7e178b4a4386d9522752`
compiled and was installed with verified SWD programming. Physical acceptance
then covered identification/canonical MAC, one explicit user-triggered
association and assigned IPv4 configuration, USB arithmetic, code CRCs and
reconnect. It does not cover TCP/HTTP/WebSocket or an embedded IDE.

Build source hashes exclude documentation and test-only checkpoint updates.
`wifi-build-verification.json` records exact dependency/source/artifact hashes,
load addresses and partition bounds. `build-fruit-jam-wifi.sh` is the exact
native command script. The target README explains preparation of its isolated
Arduino module and pinned SmallVM source. No Waveshare build/source was modified.

Final validation:

- Real C parser: PASS, 193 checks (`wifi-parser-harness.json`).
- Real VM: PASS, ten arithmetic runs, 50 ordered outputs, 83 I/O checks including
  32 bulk-I2C checks, plus control-envelope credential isolation/wiping assertions
  (`wifi-vm-harness.json`). These are simulations, not peripheral measurements.
- Native build: PASS, 34.312 seconds, four jobs, peak owned RSS 183,284 KiB,
  minimum system available memory 5,343,924 KiB; no GPU access.
- Physical installation: PASS (`physical-wifi-installation.json`).
- Physical identification: PASS (`physical-wifi-identification.json`).
- Physical association/IP and USB regression: PASS
  (`physical-wifi-association.json`), confirmed by the user.
- Three isolated physical button presses/releases: PASS
  (`physical-buttons-synchronized.json`), confirmed by the user.

VM harness attempts 1 and 2 failed because the new fixture did not fully drain
forced seven-byte output writes, then left a queued ACK ahead of a later ping.
The fixture was corrected to drain the complete response and clear its own
queued output. Attempt 3 passed; the failed resource/time records are retained.
These attempts did not access hardware or use real credentials.

No compilation, firmware programming, esptool or SWD recovery operation remains
running at this checkpoint. The bounded build window has finished and its heavy
resources are released. The reusable Windows credential and private firmware
backups remain outside Git; the published association record is sanitized.
