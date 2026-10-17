#!/usr/bin/env python3
"""Validate the hardware inventory before adding a new board or adapter."""
import subprocess
from pathlib import Path

root = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call(["python3", "-m", "unittest", "discover",
                                  "-s", str(root / "tests"), "-v"]))
