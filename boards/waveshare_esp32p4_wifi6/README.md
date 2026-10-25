# Waveshare ESP32-P4-WIFI6 - native Zephyr camera and audio

Required architecture: native Zephyr, SmallVM v417, portable image primitives,
and a P4 video driver. Future ArduinoCore-Zephyr compatibility is a goal;
arbitrary Arduino library support is not assumed. Real IMX219 capture,
resize/grayscale/RGB888 preprocessing and export passed on native Zephyr.
Bounded ES8311 PCM capture and experimental local Whistle speech-to-text are
implemented. A private controlled microphone clip matched the host/P4 text;
the actual graphical speech block also executes, with variable recognition
accuracy and scalar latency of tens of seconds. Wake word, acceleration and
true board hosting remain separate unfinished stages. The approved C6 AP has
not yet been enabled. Current dark camera frames need a lit-scene retest;
the strict content check remains failed in the latest evidence.
See [START_HERE](START_HERE.md) for reproduction and current limitations.

The working ESP-IDF camera proof is preserved on the separate **local-only**
branch `codex/p4-idf-reference` at `86c116b`. It is not the requested final port.
See [architecture review](docs/ARCHITECTURE_REVIEW.md) and [spec](docs/SPEC.md).
