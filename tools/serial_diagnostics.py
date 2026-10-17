#!/usr/bin/env python3
"""Exercise the diagnostic shell only; this tool cannot erase or flash."""
# SPDX-License-Identifier: MIT
import argparse
from pathlib import Path
import re
import time
import serial
from serial.tools import list_ports


def collect(port, seconds):
    result = bytearray()
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        result.extend(port.read(min(4096, port.in_waiting or 1)))
        if len(result) > 65536:
            raise RuntimeError("Unexpected unbounded shell output")
    return bytes(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", default="COM4")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--display", action="store_true")
    args = parser.parse_args()
    info = next((p for p in list_ports.comports() if p.device == args.port), None)
    if info is None or info.vid != 0x303A or info.pid != 0x1001:
        raise SystemExit("Expected Espressif USB Serial/JTAG interface is absent")
    if args.port.upper() == "COM5":
        raise SystemExit("COM5 is excluded from this project")
    port = serial.Serial(port=None, baudrate=115200, timeout=0.1)
    port.port = args.port
    port.dtr = False
    port.rts = False
    try:
        port.open()
        log = bytearray(collect(port, 5))
        if b"Waveshare ESP32-S3-RLCD-4.2 Zephyr hardware bring-up" not in log:
            port.write(b"\r")
            log.extend(collect(port, 1))
            if b"uart:~$" not in log and b"uart:~" not in log:
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(log.decode("utf-8", errors="replace"), encoding="utf-8")
                raise RuntimeError("No diagnostic banner or Zephyr shell prompt observed: " + repr(bytes(log[-1200:])))
        commands = ["hw status", "hw sensor", "hw sensor", "hw sensor",
                    "hw rtc", "hw rtc", "hw battery", "hw buttons"]
        if args.display:
            commands.append("hw display checker")
        for command in commands:
            log.extend(("\nCOMMAND: " + command + "\n").encode())
            port.write((command + "\r").encode())
            log.extend(collect(port, 1.2))
    finally:
        port.close()
    text = log.decode("utf-8", errors="replace")
    text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
