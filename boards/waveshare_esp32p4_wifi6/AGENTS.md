# Native Zephyr P4 port

Fred requires native Zephyr for cross-platform MicroBlocks and future
ArduinoCore-Zephyr integration. Do not substitute an ESP-IDF/FreeRTOS image.
The tested IDF work is preserved only on local branch codex/p4-idf-reference.
It is a hardware reference, not the requested finished integration.

COM5 only, revision 1.3/pre-v3, 32 MiB flash and PSRAM. No COM12, firmware
backup, eFuse/security, firewall or unapproved network configuration actions.
Current authorization permits replacing P4 firmware for native Zephyr tests.
Never flash the C6 or infer credentials without a separate approved plan.

Use Zephyr video, I2C, DMA, clocks and synchronization interfaces. Keep a
portable image/handle API, with explicit unsupported errors and capability
status for missing hardware. Preserve both sensor drivers and licenses.
No image/raw frame, credential, unique identifier or raw live log in Git.
Physical success needs real frames and VM tests. Build success is separate.
