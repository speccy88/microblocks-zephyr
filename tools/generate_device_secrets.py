#!/usr/bin/env python3
"""Create protected fallback Wi-Fi values outside the source tree; never print them."""
# SPDX-License-Identifier: MIT
import json
from pathlib import Path
import secrets
import sys

root = Path(sys.argv[1]).resolve()
root.mkdir(parents=True, exist_ok=True)
path = root / "device-private.json"
if not path.exists():
    values = {"ssid": "MicroBlocks-" + secrets.token_hex(2).upper(),
              "psk": secrets.token_hex(8)}
    path.write_text(json.dumps(values))
    path.chmod(0o600)
values = json.loads(path.read_text())
# Migrate legacy build files without changing the existing Wi-Fi values.
values = {key: values[key] for key in ("ssid", "psk")}
path.write_text(json.dumps(values))
header = "#pragma once\n" + "\n".join(
    f"#define MB_DEVICE_{key.upper()} {json.dumps(value)}" for key, value in values.items()) + "\n"
(root / "device_secrets.h").write_text(header)
(root / "device_secrets.h").chmod(0o600)
