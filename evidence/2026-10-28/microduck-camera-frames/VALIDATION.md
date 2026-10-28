# Final validation

The unchanged repository validator passed **593 tests**, zero failures and
zero skips, in 324.205 seconds. All 2553 frozen inputs matched
both the original working tree and the Linux replica after validation.

The sanitizer VM SHA-256 is `ee7ea42108ca7c15f1dff5fd33dfcce42ad34288adec2e732915d340219bf503`. The build manifest
checks every port source against this checkpoint and retains the pinned runtime.
The primitive registry test verifies all 22 names. No timeout or exclusion was
relaxed. See `validation.json`, `validation.txt` and the reproduction scripts.

All camera data are fictional. There was no camera hardware, new Pi execution,
graphical camera test, reboot, movement, network change or publication. The prior
Pi installer checkpoint and its denied, unexecuted reboot remain separate.
