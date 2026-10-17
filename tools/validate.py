#!/usr/bin/env python3
"""Validate the hardware inventory before adding a new board or adapter."""
import subprocess
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
raise SystemExit(subprocess.call([sys.executable, "-m", "unittest", "discover",
                                  "-s", str(root / "tests"), "-v"]))
