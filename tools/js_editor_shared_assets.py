"""Canonical editor behavior shared by desktop, mobile and native packages."""
# SPDX-License-Identifier: MPL-2.0
from pathlib import Path
import hashlib
import json
import re
from sfc_js_assets import assets as sfc_assets, SCRIPTS as SFC_SCRIPTS
from p2_library_groups import split_library, GROUPS

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = (*SFC_SCRIPTS, 'board-project-readback.js', 'target-blocks.js', 'p2-install-link.js')


def assets():
    result = sfc_assets()
    result['board-project-readback.js'] = (ROOT / 'web/js-editor/board-project-readback.js').read_bytes()
    result['target-blocks.js'] = (ROOT / 'web/js-editor/target-blocks.js').read_bytes()
    result['p2-install-link.js'] = (ROOT / 'web/js-editor/p2-install-link.js').read_bytes()
    return result


def scripts():
    return '\n'.join('<script src="' + name + '"></script>' for name in SCRIPTS) + '\n'


def target_assets(profile):
    """Refresh owned target libraries after verifying the frozen engine archive."""
    if profile != 'propeller2':
        return {}
    source = 'boards/propeller2/integration/P2_Hardware.ubl'
    bundle = 'Libraries/Targets/Propeller 2 Project.ubl'
    canonical = (ROOT / source).read_bytes()
    groups, owners = split_library(canonical)
    raw = b'\n'.join(groups.values())
    receipt = {'schema': 1, 'source_path': source, 'bundle': bundle,
               'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
               'required_extension_revision': 8,
               'function_names': re.findall(r'^to\s+(\w+)', raw.decode('utf-8'), re.M),
               'modules': [name for name, _ in GROUPS], 'selector_libraries': owners,
               'canonical_source_sha256': hashlib.sha256(canonical).hexdigest(),
               'legacy_module': 'P2 Hardware', 'library_version': '0.11',
               'physical_hardware_scope': 'See boards/propeller2/hardware.json; blocks alone do not establish hardware acceptance.'}
    optional = {'Libraries/P2/' + path.name: path.read_bytes()
                for path in sorted((ROOT/'boards/propeller2/integration/libraries').glob('*.ubl'))}
    examples = {'Examples/P2/' + path.name: path.read_bytes()
                for path in sorted((ROOT/'boards/propeller2/integration/examples').glob('*.ubp'))}
    optional_receipt={'schema':1,'status':'candidate firmware; not in the reviewed revision-8 installer',
                      'automatic':False,'physical_tested':False,'libraries':list(optional),
                      'examples':list(examples),'implementation':'docs/PROPELLER2_PERIPHERALS.md'}
    return {**groups, **optional, **examples,
            'optional-peripherals.json':(json.dumps(optional_receipt,indent=2)+'\n').encode(),bundle: raw,
            'target-library-source.json': (json.dumps(receipt, indent=2)+'\n').encode()}
