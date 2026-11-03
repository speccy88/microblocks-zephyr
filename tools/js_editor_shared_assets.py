"""Canonical editor behavior shared by desktop, mobile and native packages."""
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
from sfc_js_assets import assets as sfc_assets, SCRIPTS as SFC_SCRIPTS

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (*SFC_SCRIPTS, 'board-project-readback.js')


def assets():
    result = sfc_assets()
    result['board-project-readback.js'] = (ROOT / 'web/js-editor/board-project-readback.js').read_bytes()
    return result


def scripts():
    return '\n'.join('<script src="' + name + '"></script>' for name in SCRIPTS) + '\n'
