# Waveshare ESP32-P4-WIFI6 - native Zephyr camera

Required architecture: native Zephyr, SmallVM v417, portable image primitives,
and a P4 video driver. Future ArduinoCore-Zephyr compatibility is a goal;
arbitrary Arduino library support is not assumed. Real IMX219 capture,
resize/grayscale/RGB888 preprocessing and export passed on native Zephyr.
See [START_HERE](START_HERE.md) for reproduction and current limitations.

The working ESP-IDF camera proof is preserved on the separate **local-only**
branch `codex/p4-idf-reference` at `86c116b`. It is not the requested final port.
See [architecture review](docs/ARCHITECTURE_REVIEW.md) and [spec](docs/SPEC.md).
