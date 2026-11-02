"""Main-owned SFC overlay shared by every JavaScript editor package."""
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ('sfc-core.js', 'sfc-editor.js')


def assets():
    result = {name: (ROOT / 'web/js-editor' / name).read_bytes() for name in SCRIPTS}
    for path in sorted((ROOT / 'tests/fixtures/sfc_native').glob('*.ubp')):
        if not path.name.startswith('invalid-'):
            result['Examples/SFC/' + path.name] = path.read_bytes()
    return result


def scripts():
    return '\n'.join('<script src="' + name + '"></script>' for name in SCRIPTS) + '\n'
