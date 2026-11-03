"""Canonical editor behavior shared by desktop, mobile and native packages."""
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import hashlib
import json
import re
from sfc_js_assets import assets as sfc_assets, SCRIPTS as SFC_SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (*SFC_SCRIPTS, 'board-project-readback.js')


def assets():
    result = sfc_assets()
    result['board-project-readback.js'] = (ROOT / 'web/js-editor/board-project-readback.js').read_bytes()
    return result


def scripts():
    return '\n'.join('<script src="' + name + '"></script>' for name in SCRIPTS) + '\n'


def target_assets(profile):
    """Refresh owned target libraries after verifying the frozen engine archive."""
    if profile != 'propeller2':
        return {}
    source = 'boards/propeller2/integration/P2_Hardware.ubl'
    bundle = 'Libraries/Targets/Propeller 2 Project.ubl'
    raw = (ROOT / source).read_bytes()
    receipt = {'schema': 1, 'source_path': source, 'bundle': bundle,
               'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
               'required_extension_revision': 7,
               'function_names': re.findall(r'^to\s+(\w+)', raw.decode('utf-8'), re.M),
               'physical_hardware_scope': 'See boards/propeller2/hardware.json; blocks alone do not establish hardware acceptance.'}
    return {bundle: raw, 'target-library-source.json': (json.dumps(receipt, indent=2)+'\n').encode()}
